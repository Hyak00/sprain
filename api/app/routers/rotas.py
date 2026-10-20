from app.seguranca import require_role, resolver_tenant_autenticado
from types import SimpleNamespace
from app.services.infraestrutura_viaria import SELECT_PONTOS, avaliar_ponto
from app.services.limiares_chuva import LIMIARES, impacto_corredor
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

    chuva_observada = None
    fonte_meteorologica = "SIMULACAO_ESTRESSE"
    try:
        from app.services.weather import WeatherService
        ws = WeatherService(conn)
        vertice = await conn.fetchval(
            "SELECT id FROM trechos_osm_vertices_pgr ORDER BY the_geom <-> ST_Transform(ST_SetSRID(ST_Point($1, $2), 4326), 31983) LIMIT 1",
            dados.origem_lon, dados.origem_lat
        )
        trecho_origem = await conn.fetchval(
            "SELECT id_trecho FROM trechos_osm WHERE source = $1 OR target = $1 LIMIT 1",
            vertice
        )
        if trecho_origem:
            clima = await ws.obter_clima_trecho(trecho_origem)
            if clima.get("status") == "VALIDO" and clima.get("precipitacao_mm") is not None:
                chuva_observada = float(clima["precipitacao_mm"])
                fonte_meteorologica = str(clima.get("fonte") or "OBSERVADA_EM_TEMPO_REAL")
                limite_sev = LIMIARES["severo"]["mm"] if isinstance(LIMIARES["severo"], dict) else LIMIARES["severo"]
                limite_aten = LIMIARES["atencao"]["mm"] if isinstance(LIMIARES["atencao"], dict) else LIMIARES["atencao"]
                await ws.registrar_avaliacao_risco(
                    trecho_origem,
                    chuva_observada,
                    "CRITICO" if chuva_observada >= limite_sev else ("MODERADO" if chuva_observada >= limite_aten else "BAIXO"),
                    fonte_meteorologica,
                    int(clima.get("idade_minutos") or 0),
                    "v1.1"
                )
    except Exception:
        chuva_observada = None

    rain_resiliente = chuva_observada if chuva_observada is not None else 60.0

    rota_padrao = await RoutingEngine.compute_route(
        conn, dados.origem_lon, dados.origem_lat, dados.destino_lon, dados.destino_lat,
        profile="FASTEST", rain_mm=0.0, tenant_id=tenant_id, vehicle_dimensions=dims
    )
    rota_resiliente = await RoutingEngine.compute_route(
        conn, dados.origem_lon, dados.origem_lat, dados.destino_lon, dados.destino_lat,
        profile="SAFEST", rain_mm=rain_resiliente, tenant_id=tenant_id, vehicle_dimensions=dims
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
            "calculado_em": datetime.now(timezone.utc).isoformat(),
            "meteorologia": {
                "tipo": "OBSERVADA_EM_TEMPO_REAL" if chuva_observada is not None else "SIMULACAO_ESTRESSE",
                "precipitacao_aplicada_mm": rain_resiliente,
                "fonte": fonte_meteorologica
            }
        }
    }

EIXOS_POR_CATEGORIA = {"VUC": 2, "TRUCK_3_EIXOS": 3, "CARRETA_5_EIXOS": 5}
CORREDORES_DISPONIVEIS = {("araraquara", "sao paulo"), ("araraquara", "s\u00e3o paulo")}
MOTIVO_TEMPO = "Tempo por segmento depende de velocidade calibrada por classe de via; ainda nao implementado."
MOTIVO_METEOROLOGIA = "Chuva observada em pontos de referencia; isso nao confirma pista livre nem substitui validacao de alagamentos e interdiccoes."
MOTIVO_DESVIO = "Sem risco de alagamento calculado para o corredor, nao ha base para sugerir desvio."
AVISO_PEDAGIOS = "Somente pedagios cadastrados e conferidos pela empresa a ate o raio informado do corredor de referencia; cobertura parcial. custo_total_pedagio_reais e o subtotal das tarifas conhecidas, sem as pendentes."

VELOCIDADES_NOMINAIS_CORREDOR = {
    1: 80.0,
    2: 80.0,
    3: 80.0,
    4: 75.0,
    5: 85.0,
    6: 65.0,
}

@router.get("/intermunicipal", dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])
async def calcular_rota_intermunicipal(
    origem: str = Query("Araraquara", description="Cidade de origem do transporte"),
    destino: str = Query("Sao Paulo", description="Cidade de destino final"),
    tipo_veiculo: str = Query("TRUCK_3_EIXOS", description="Categoria: VUC, TRUCK_3_EIXOS ou CARRETA_5_EIXOS"),
    raio_pedagio_m: float = Query(100.0, ge=10.0, le=500.0, description="Distancia maxima entre o pedagio cadastrado e o corredor"),
    calibrar_tempo: bool = Query(False, description="Ativa calculo de velocidade calibrada por classe de rodovia e ETA em minutos"),
    incluir_tarifas_artesp: bool = Query(False, description="Inclui tarifas oficiais da ARTESP das pracas principais do corredor"),
    tenant_id: str = Depends(resolver_tenant_autenticado),
    conn: asyncpg.Connection = Depends(get_connection)
):
    if (origem.strip().casefold(), destino.strip().casefold()) not in CORREDORES_DISPONIVEIS:
        raise HTTPException(status_code=422, detail="Corredor disponivel apenas entre Araraquara e Sao Paulo.")
    categoria = tipo_veiculo.strip().upper()
    eixos = EIXOS_POR_CATEGORIA.get(categoria)
    if eixos is None:
        raise HTTPException(status_code=422, detail="Categoria invalida. Use VUC, TRUCK_3_EIXOS ou CARRETA_5_EIXOS.")

    limite_severo = LIMIARES["severo"]["mm"] if isinstance(LIMIARES["severo"], dict) else LIMIARES["severo"]
    limite_atencao = LIMIARES["atencao"]["mm"] if isinstance(LIMIARES["atencao"], dict) else LIMIARES["atencao"]

    segmentos = await conn.fetch("""
        SELECT c.id_trecho, c.name,
               ROUND((c.length / 1000.0)::numeric, 1) AS distancia_km,
               cc.precipitacao_mm_h, cc.atualizado_em
        FROM corredor_sp_araraquara c
        LEFT JOIN condicoes_corredor cc ON cc.id_trecho = c.id_trecho
        ORDER BY c.id_trecho
    """)
    agora_utc = datetime.now(timezone.utc)
    segmentos_clima = []
    trechos_criticos = []
    for s in segmentos:
        coletado = s["atualizado_em"]
        if coletado is not None and coletado.tzinfo is None:
            coletado = coletado.replace(tzinfo=timezone.utc)
        idade_min = (
            (agora_utc - coletado).total_seconds() / 60
            if coletado is not None else None
        )
        chuva = s["precipitacao_mm_h"]
        recente = (
            idade_min is not None and 0 <= idade_min <= 60
            and chuva is not None
        )
        precipitacao_valor = float(chuva) if recente else None
        if precipitacao_valor is not None and precipitacao_valor >= limite_severo:
            trechos_criticos.append(s["name"])

        if calibrar_tempo:
            v_nominal = VELOCIDADES_NOMINAIS_CORREDOR.get(int(s["id_trecho"]), 75.0)
            t_nom = round((float(s["distancia_km"]) / v_nominal) * 60.0, 1)
            if precipitacao_valor is not None:
                _, fator_atraso = impacto_corredor(precipitacao_valor)
            else:
                fator_atraso = 1.0
            t_real = round(t_nom * fator_atraso, 1)
        else:
            t_nom = None
            t_real = None

        segmentos_clima.append({
            "id": s["id_trecho"],
            "nome": s["name"],
            "distancia_km": float(s["distancia_km"]),
            "tempo_nominal_min": t_nom,
            "tempo_real_min": t_real,
            "status": (
                "DADO_METEOROLOGICO_RECENTE"
                if recente else "SEM_DADO_METEOROLOGICO"
            ),
            "precipitacao_mm_h": precipitacao_valor,
            "coletado_em": coletado.isoformat() if recente else None,
            "idade_dado_min": round(idade_min, 1) if recente else None,
        })

        risco_rotulo = "CRITICO" if (precipitacao_valor is not None and precipitacao_valor >= limite_severo) else ("MODERADO" if (precipitacao_valor is not None and precipitacao_valor >= limite_atencao) else ("BAIXO" if recente else "DESCONHECIDO"))
        await conn.execute("""
            INSERT INTO historico_avaliacoes_risco
            (id_trecho, regra_versao, precipitacao_aplicada_mm, risco_estimado, id_fonte, idade_dado_minutos)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, int(s["id_trecho"]), "v1.1", precipitacao_valor, risco_rotulo, "CORREDOR_INTERMUNICIPAL", int(idade_min or 0))

    total_km = sum(float(s["distancia_km"]) for s in segmentos)
    todos_recentes = bool(segmentos_clima) and all(
        s["status"] == "DADO_METEOROLOGICO_RECENTE"
        for s in segmentos_clima
    )

    pedagios = []
    subtotal = 0.0
    pendentes = 0
    if incluir_tarifas_artesp:
        coluna_tarifa = "tarifa_truck_3eixos"
        if categoria == "VUC":
            coluna_tarifa = "tarifa_vuc"
        elif categoria == "CARRETA_5_EIXOS":
            coluna_tarifa = "tarifa_carreta_5eixos"

        pracas_artesp = await conn.fetch(f"""
            SELECT id, rodovia, km, municipio, concessionaria, {coluna_tarifa} AS tarifa
            FROM pracas_pedagio
            ORDER BY id
        """)
        for p in pracas_artesp:
            t_valor = float(p["tarifa"])
            subtotal += t_valor
            pedagios.append({
                "id": p["id"],
                "nome": f"Pedagio {p['rodovia']} km {float(p['km']):.1f} - {p['municipio']}",
                "fonte": "ARTESP",
                "origem_dados": "CADASTRO_HOMOLOGADO_ARTESP",
                "grupo_cobranca": p["concessionaria"],
                "cabines_cadastradas": 1,
                "valido_ate": None,
                "tarifa": t_valor
            })
    else:
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

    if trechos_criticos:
        km_desvio = 22.0
        minutos_atraso_evitados = 45.0
        consumo_km_l = 2.2 if categoria == "CARRETA_5_EIXOS" else (3.0 if categoria == "TRUCK_3_EIXOS" else 5.0)
        custo_hora = 95.0 if categoria == "CARRETA_5_EIXOS" else 85.0
        custo_diesel_adicional = round((km_desvio / consumo_km_l) * 6.20, 2)
        economia_tempo = round((minutos_atraso_evitados / 60.0) * custo_hora, 2)
        beneficio_liquido = round(economia_tempo - custo_diesel_adicional, 2)
        decisao = {
            "recomendacao": "DESVIAR",
            "desvio": "CONTORNO_RODOVIAS_PARALELAS",
            "motivo_indisponivel": None,
            "trechos_criticos": trechos_criticos,
            "analise_financeira": {
                "custo_diesel_adicional_reais": custo_diesel_adicional,
                "economia_tempo_reais": economia_tempo,
                "custo_pedagio_rota_reais": round(subtotal, 2),
                "beneficio_liquido_reais": beneficio_liquido,
                "roi_positivo": beneficio_liquido > 0,
                "motivo_indisponivel": None
            }
        }
    else:
        decisao = {
            "recomendacao": "INDISPONIVEL",
            "desvio": None,
            "motivo_indisponivel": MOTIVO_DESVIO,
            "trechos_criticos": [],
            "analise_financeira": {
                "custo_diesel_adicional_reais": None,
                "economia_tempo_reais": None,
                "custo_pedagio_rota_reais": round(subtotal, 2),
                "beneficio_liquido_reais": None,
                "roi_positivo": None,
                "motivo_indisponivel": MOTIVO_DESVIO
            }
        }

    tempo_nom_total = round(sum(s["tempo_nominal_min"] for s in segmentos_clima), 1) if calibrar_tempo else None
    tempo_real_total = round(sum(s["tempo_real_min"] for s in segmentos_clima), 1) if calibrar_tempo else None
    atraso_clima_total = round(tempo_real_total - tempo_nom_total, 1) if (calibrar_tempo and tempo_real_total is not None and tempo_nom_total is not None) else None

    return {
        "status": "DADOS_PARCIAIS",
        "modalidade": "CONSULTA_CORREDOR_REFERENCIA",
        "origem": origem,
        "destino": destino,
        "tipo_veiculo": categoria,
        "resumo": {
            "distancia_total_km": round(total_km, 1),
            "tempo_nominal_min": tempo_nom_total,
            "tempo_real_estimado_min": tempo_real_total,
            "atraso_climatico_min": atraso_clima_total,
            "status_geral": ("DADOS_METEOROLOGICOS_RECENTES" if todos_recentes else "DADOS_METEOROLOGICOS_PARCIAIS_OU_INDISPONIVEIS"),
            "motivo_indisponivel": (MOTIVO_METEOROLOGIA if calibrar_tempo else (MOTIVO_TEMPO + " " + MOTIVO_METEOROLOGIA))
        },
        "decisao_logistica": decisao,
        "pedagios": {
            "quantidade_pracas": len(pedagios),
            "custo_total_pedagio_reais": round(subtotal, 2),
            "tarifas_pendentes": pendentes,
            "cobertura_completa": False,
            "aviso": (
                "Tarifas oficiais ARTESP das pracas principais do corredor fiscalizado; pracas de retorno e acessos secundarios nao inclusos."
                if incluir_tarifas_artesp
                else AVISO_PEDAGIOS
            ),
            "pracas_detalhadas": pedagios
        },
        "segmentos": segmentos_clima,
        "rastreabilidade": {
            "versao_malha": None,
            "regra_utilizada": "consulta_corredor_referencia",
            "coletado_em": datetime.now(timezone.utc).isoformat()
        }
    }
