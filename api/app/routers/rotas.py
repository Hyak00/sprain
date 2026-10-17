from app.seguranca import require_role, resolver_tenant_autenticado
from types import SimpleNamespace
from app.services.infraestrutura_viaria import SELECT_PONTOS, avaliar_ponto
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncpg
from datetime import datetime, timezone

from app.database import get_connection

router = APIRouter(prefix="/api/v1/rotas", tags=["Logistica & Roteamento Resiliente"])

SQL_VERTICE_PROXIMO = """
    SELECT id 
    FROM trechos_osm_vertices_pgr 
    ORDER BY the_geom <-> ST_SetSRID(ST_Point($1, $2), 4326) 
    LIMIT 1;
"""

SQL_ARESTAS_PADRAO = """
    SELECT id, source, target, st_length(the_geom, true) as cost 
    FROM trechos_osm
"""

SQL_ARESTAS_RESILIENTE = """
    SELECT 
        t.id, 
        t.source, 
        t.target, 
        (st_length(t.the_geom, true) * (1.0 + (COALESCE(o.severidade, 0) * 10.0))) as cost 
    FROM trechos_osm t
    LEFT JOIN ocorrencias_alagamento o 
        ON ST_DWithin(t.the_geom::geography, o.geom::geography, 30.0) 
        AND o.status = 'ativa'
"""

def montar_query_rota(sql_arestas: str) -> str:
    return f"""WITH caminho AS (
        SELECT seq, edge, cost 
        FROM pgr_dijkstra('{sql_arestas}', $1::bigint, $2::bigint, directed := false)
    )
    SELECT 
        COALESCE(SUM(c.cost), 0.0) as distancia_metros,
        ST_AsGeoJSON(ST_LineMerge(ST_Collect(t.the_geom))) as rota_geojson
    FROM caminho c
    JOIN trechos_osm t ON c.edge = t.id;"""

class RotaRequest(BaseModel):
    origem_lat: float = Field(..., ge=-90.0, le=90.0)
    origem_lon: float = Field(..., ge=-180.0, le=180.0)
    destino_lat: float = Field(..., ge=-90.0, le=90.0)
    destino_lon: float = Field(..., ge=-180.0, le=180.0)
    id_veiculo: str | None = Field(None, max_length=64)

async def executar_rota(conn: asyncpg.Connection, sql_query: str, v_inicio: int, v_fim: int):
    row = await conn.fetchrow(sql_query, v_inicio, v_fim)
    if not row or not row["rota_geojson"]:
        return None
    return {
        "distancia_km": round(float(row["distancia_metros"]) / 1000.0, 2),
        "geojson": row["rota_geojson"]
    }

from app.services.routing_engine import RoutingEngine

@router.post("/calcular", dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])
async def calcular_rota(dados: RotaRequest, conn: asyncpg.Connection = Depends(get_connection), tenant_id: str = Depends(resolver_tenant_autenticado)):
    from app.services.infraestrutura_viaria import dimensoes_veiculo
    dims = await dimensoes_veiculo(conn, tenant_id, dados.id_veiculo)
    exigidas = ("eixos", "altura_m", "largura_m", "comprimento_m", "peso_total_t")
    faltando = [k for k in exigidas if not dims or dims.get(k) is None]
    if faltando:
        raise HTTPException(status_code=422, detail="Informe o id_veiculo de um veiculo com dimensoes cadastradas (faltando: " + ", ".join(faltando) + ") para avaliar as restricoes de altura e peso do trajeto.")
    rota_padrao = await RoutingEngine.compute_route(
        conn, dados.origem_lon, dados.origem_lat, dados.destino_lon, dados.destino_lat,
        profile="FASTEST", rain_mm=0.0, tenant_id=tenant_id, vehicle_dimensions=dims
    )
    rota_resiliente = await RoutingEngine.compute_route(
        conn, dados.origem_lon, dados.origem_lat, dados.destino_lon, dados.destino_lat,
        profile="SAFEST", rain_mm=60.0, tenant_id=tenant_id, vehicle_dimensions=dims
    )

    if not rota_padrao or not rota_resiliente:
        raise HTTPException(status_code=404, detail="Nao foi possivel tracar uma rota entre os pontos informados.")

    return {
        "rota_padrao": {
            "distancia_km": rota_padrao["distancia_km"],
            "tempo_min": rota_padrao["tempo_min"],
            "geojson": rota_padrao["geojson"]
        },
        "rota_resiliente": {
            "distancia_km": rota_resiliente["distancia_km"],
            "tempo_min": rota_resiliente["tempo_min"],
            "geojson": rota_resiliente["geojson"]
        },
        "desvio_necessario": rota_padrao["ids_trechos"] != rota_resiliente["ids_trechos"],
        "rastreabilidade": {
            "motor": "SPRain RoutingEngine PostGIS/pgRouting",
            "tenant_id": tenant_id,
            "calculado_em": datetime.now(timezone.utc).isoformat()
        }
    }

EIXOS_POR_CATEGORIA = {"VUC": 2, "TRUCK_3_EIXOS": 3, "CARRETA_5_EIXOS": 5}
CORREDORES_DISPONIVEIS = {("araraquara", "sao paulo"), ("araraquara", "s\u00e3o paulo")}
MOTIVO_TEMPO = "Tempo por segmento depende de velocidade calibrada por classe de via; ainda nao implementado."
MOTIVO_METEOROLOGIA = "A associacao entre estacao meteorologica e segmento do corredor nao foi verificada; nenhuma condicao e exibida."
MOTIVO_DESVIO = "Sem risco de alagamento calculado para o corredor, nao ha base para sugerir desvio."
AVISO_PEDAGIOS = "Somente pedagios cadastrados e conferidos pela empresa a ate o raio informado do corredor de referencia; cobertura parcial. custo_total_pedagio_reais e o subtotal das tarifas conhecidas, sem as pendentes."

@router.get("/intermunicipal", dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])
async def calcular_rota_intermunicipal(
    origem: str = Query("Araraquara", description="Cidade de origem do transporte"),
    destino: str = Query("Sao Paulo", description="Cidade de destino final"),
    tipo_veiculo: str = Query("TRUCK_3_EIXOS", description="Categoria: VUC, TRUCK_3_EIXOS ou CARRETA_5_EIXOS"),
    raio_pedagio_m: float = Query(100.0, ge=10.0, le=500.0, description="Distancia maxima entre o pedagio cadastrado e o corredor"),
    tenant_id: str = Depends(resolver_tenant_autenticado),
    conn: asyncpg.Connection = Depends(get_connection)
):
    if (origem.strip().casefold(), destino.strip().casefold()) not in CORREDORES_DISPONIVEIS:
        raise HTTPException(status_code=422, detail="Corredor disponivel apenas entre Araraquara e Sao Paulo.")
    categoria = tipo_veiculo.strip().upper()
    eixos = EIXOS_POR_CATEGORIA.get(categoria)
    if eixos is None:
        raise HTTPException(status_code=422, detail="Categoria invalida. Use VUC, TRUCK_3_EIXOS ou CARRETA_5_EIXOS.")

    segmentos = await conn.fetch("""
        SELECT id_trecho, name, ROUND((length / 1000.0)::numeric, 1) AS distancia_km
        FROM corredor_sp_araraquara
        ORDER BY id_trecho
    """)
    total_km = sum(float(s["distancia_km"]) for s in segmentos)

    pontos = await conn.fetch(
        SELECT_PONTOS + """ AND tipo = 'PEDAGIO' AND EXISTS (
            SELECT 1 FROM corredor_sp_araraquara c
            WHERE ST_DWithin(c.geometry, ST_Transform(infraestrutura_viaria.geom, 31983), $2)
        ) ORDER BY id""",
        tenant_id, raio_pedagio_m
    )
    veiculo = SimpleNamespace(eixos=eixos)
    grupos = {}
    for p in pontos:
        chave = p["grupo_cobranca"] or ("ponto", p["id"])
        grupos.setdefault(chave, []).append((p, avaliar_ponto(p, veiculo)))

    pedagios = []
    subtotal = 0.0
    pendentes = 0
    for itens in grupos.values():
        tarifas = {avaliacao["custo_estimado_reais"] for _, avaliacao in itens}
        tarifa = tarifas.pop() if len(tarifas) == 1 else None
        if tarifa is None:
            pendentes += 1
        else:
            subtotal += tarifa
        principal = itens[0][0]
        pedagios.append({
            "id": principal["id"],
            "nome": principal["nome"],
            "fonte": principal["fonte"],
            "origem_dados": principal["origem_dados"],
            "grupo_cobranca": principal["grupo_cobranca"],
            "cabines_cadastradas": len(itens),
            "valido_ate": principal["valido_ate"].isoformat(),
            "tarifa": tarifa
        })

    return {
        "status": "DADOS_PARCIAIS",
        "modalidade": "CONSULTA_CORREDOR_REFERENCIA",
        "origem": origem,
        "destino": destino,
        "tipo_veiculo": categoria,
        "resumo": {
            "distancia_total_km": round(total_km, 1),
            "tempo_nominal_min": None,
            "tempo_real_estimado_min": None,
            "atraso_climatico_min": None,
            "status_geral": "SEM_DADOS_METEOROLOGICOS",
            "motivo_indisponivel": MOTIVO_TEMPO + " " + MOTIVO_METEOROLOGIA
        },
        "decisao_logistica": {
            "recomendacao": "INDISPONIVEL",
            "desvio": None,
            "motivo_indisponivel": MOTIVO_DESVIO,
            "analise_financeira": {
                "custo_diesel_adicional_reais": None,
                "economia_tempo_reais": None,
                "custo_pedagio_rota_reais": round(subtotal, 2),
                "beneficio_liquido_reais": None,
                "roi_positivo": None,
                "motivo_indisponivel": MOTIVO_DESVIO
            }
        },
        "pedagios": {
            "quantidade_pracas": len(pedagios),
            "custo_total_pedagio_reais": round(subtotal, 2),
            "tarifas_pendentes": pendentes,
            "cobertura_completa": False,
            "aviso": AVISO_PEDAGIOS,
            "pracas_detalhadas": pedagios
        },
        "segmentos": [
            {
                "id": s["id_trecho"],
                "nome": s["name"],
                "distancia_km": float(s["distancia_km"]),
                "tempo_nominal_min": None,
                "tempo_real_min": None,
                "status": "SEM_DADO_METEOROLOGICO",
                "precipitacao_mm_h": None
            }
            for s in segmentos
        ],
        "rastreabilidade": {
            "versao_malha": None,
            "regra_utilizada": "consulta_corredor_referencia",
            "coletado_em": datetime.now(timezone.utc).isoformat()
        }
    }
