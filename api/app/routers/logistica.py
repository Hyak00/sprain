from fastapi import Request, APIRouter, Depends, HTTPException, Header, Query
from fastapi.responses import StreamingResponse
import asyncio
import io
import csv
import json
import uuid
import asyncpg
from typing import List, Dict, Any, Optional, Literal

from app.services.rate_limiter import TenantRateLimiter
from app.seguranca import require_role, get_current_user_claims, is_production
from app.database import get_connection
from app.schemas import (
    VeiculoCreate,
    OperacaoCreate,
    SimulacaoB2BRequest,
    WebhookAlertaRequest,
    PlanejamentoD1Request,
    ParametrosFinanceiros
)
from app.services.routing_engine import RoutingEngine
from app.services.custo_combustivel import custo_quilometrico, resolver_custos
from app.services.viagem_caminhao import ContextoViagens, dados_viagem, objeto, gravar_recomendacao
from app.services.infraestrutura_viaria import dimensoes_veiculo
from app.schemas_infraestrutura import VeiculoDimensoes
from app.url_segura import is_safe_url, post_seguro

router = APIRouter(prefix="/api/v1/logistica", tags=["Logistica B2B"])

async def aplicar_rate_limit(request: Request, claims: dict = Depends(get_current_user_claims)):
    limite, restantes = TenantRateLimiter.check_rate_limit(claims["tenant_id"])
    request.state.ratelimit_limit = limite
    request.state.ratelimit_remaining = restantes

def resolve_tenant(x_tenant_id: Optional[str] = Header(None), tenant_id: Optional[str] = Query(None), claims: dict = Depends(get_current_user_claims)) -> str:
    tenant_autenticado = claims["tenant_id"]
    tenant_solicitado = x_tenant_id or tenant_id
    if tenant_solicitado and tenant_solicitado != tenant_autenticado:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    return tenant_autenticado

@router.post("/veiculos", dependencies=[Depends(require_role(["ADMIN", "OPERATOR"])), Depends(aplicar_rate_limit)])
async def cadastrar_veiculo(dados: VeiculoCreate, conn: asyncpg.Connection = Depends(get_connection), tenant_id: str = Depends(resolve_tenant)):
    dados.tenant_id = tenant_id
    query_check = "SELECT tenant_id FROM veiculos WHERE id_veiculo = $1;"
    dono_atual = await conn.fetchval(query_check, dados.id_veiculo)
    if dono_atual and dono_atual != dados.tenant_id:
        raise HTTPException(status_code=403, detail="Veiculo pertence a outro tenant.")

    query = """
    INSERT INTO veiculos (id_veiculo, placa, modelo, tipo_veiculo, lat_atual, lon_atual, tenant_id, dimensoes, custos_operacionais,atualizado_em)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb,now())
    ON CONFLICT (id_veiculo) DO UPDATE
    SET placa = EXCLUDED.placa, modelo = EXCLUDED.modelo, tipo_veiculo = EXCLUDED.tipo_veiculo, lat_atual = EXCLUDED.lat_atual, lon_atual = EXCLUDED.lon_atual,
        atualizado_em=now(),dimensoes=COALESCE(EXCLUDED.dimensoes,veiculos.dimensoes),
        custos_operacionais=CASE WHEN EXCLUDED.custos_operacionais IS NULL THEN veiculos.custos_operacionais
            ELSE COALESCE(veiculos.custos_operacionais,'{}'::jsonb) || EXCLUDED.custos_operacionais END
    WHERE veiculos.tenant_id = EXCLUDED.tenant_id
    RETURNING id_veiculo;
    """
    res = await conn.fetchval(query, dados.id_veiculo, dados.placa, dados.modelo, dados.tipo_veiculo, dados.lat_atual, dados.lon_atual, dados.tenant_id, dados.dimensoes.model_dump_json() if dados.dimensoes else None,
        dados.custos_operacionais.model_dump_json(exclude_none=True) if dados.custos_operacionais else None)
    if not res:
        raise HTTPException(status_code=403, detail="Nao foi possivel atualizar o veiculo.")
    return {"sucesso": True, "id_veiculo": res, "tenant_id": dados.tenant_id}

@router.get("/veiculos", dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"])), Depends(aplicar_rate_limit)])
async def listar_veiculos(tenant_id: str = Depends(resolve_tenant), conn: asyncpg.Connection = Depends(get_connection)):
    rows = await conn.fetch("SELECT * FROM veiculos WHERE tenant_id = $1 ORDER BY id_veiculo;", tenant_id)
    return [{**dict(r), "dimensoes":objeto(r["dimensoes"]) or None,
             "custos_operacionais":objeto(r["custos_operacionais"]) or None} for r in rows]

async def _geocodificar_via_se_necessario(conn: asyncpg.Connection, nome: str, lat: float, lon: float, padrao_offset: int = 0, tenant: str = "global"):
    if nome and nome.strip():
        termo = f"%{nome.strip()}%"
        row = await conn.fetchrow("""
            SELECT
                ST_Y(ST_Centroid(ST_Transform(geom, 4326)))::float AS lat,
                ST_X(ST_Centroid(ST_Transform(geom, 4326)))::float AS lon
            FROM trechos_osm
            WHERE name IS NOT NULL AND source IS NOT NULL AND target IS NOT NULL
              AND (tenant_malha IS NULL OR tenant_malha=$3)
              AND (importacao_malha_id IS NULL OR EXISTS(SELECT 1 FROM malha_importacoes m WHERE m.id=importacao_malha_id AND m.ativo))
              AND translate(lower(name), 'áàâãéêíóôõúç', 'aaaaeeiooouc') LIKE translate(lower($1), 'áàâãéêíóôõúç', 'aaaaeeiooouc')
            ORDER BY id_trecho ASC
            OFFSET $2 LIMIT 1;
        """, termo, padrao_offset, tenant)
        if row:
            return row["lat"], row["lon"]
    if lat and lon and abs(lat) > 1.0 and abs(lon) > 1.0:
        return lat, lon
    fallback = await conn.fetchrow("""
        SELECT
            ST_Y(ST_Centroid(ST_Transform(geom, 4326)))::float AS lat,
            ST_X(ST_Centroid(ST_Transform(geom, 4326)))::float AS lon
        FROM trechos_osm
        WHERE source IS NOT NULL AND target IS NOT NULL
        AND (tenant_malha IS NULL OR tenant_malha=$2)
        AND (importacao_malha_id IS NULL OR EXISTS(SELECT 1 FROM malha_importacoes m WHERE m.id=importacao_malha_id AND m.ativo))
        ORDER BY id_trecho ASC
        OFFSET $1 LIMIT 1;
    """, padrao_offset * 25, tenant)
    if not fallback:
        raise HTTPException(422,"Endereco sem cobertura na malha da empresa.")
    return fallback["lat"], fallback["lon"]

@router.post("/operacoes", dependencies=[Depends(require_role(["ADMIN", "OPERATOR"])), Depends(aplicar_rate_limit)])
async def criar_operacao(dados: OperacaoCreate, conn: asyncpg.Connection = Depends(get_connection), tenant_id: str = Depends(resolve_tenant)):
    dados.tenant_id = tenant_id
    if not dados.origem_lat or not dados.origem_lon or abs(dados.origem_lat) < 1.0:
        dados.origem_lat, dados.origem_lon = await _geocodificar_via_se_necessario(conn, dados.origem_nome, dados.origem_lat, dados.origem_lon, 0, tenant_id)
    if not dados.destino_lat or not dados.destino_lon or abs(dados.destino_lat) < 1.0:
        dados.destino_lat, dados.destino_lon = await _geocodificar_via_se_necessario(conn, dados.destino_nome, dados.destino_lat, dados.destino_lon, 5, tenant_id)
    cadastradas=await dimensoes_veiculo(conn,tenant_id,dados.id_veiculo)
    dims=dados.dimensoes.model_dump() if dados.dimensoes else cadastradas
    frota=await conn.fetchrow("SELECT tipo_veiculo,custos_operacionais FROM veiculos WHERE id_veiculo=$1 AND tenant_id=$2",dados.id_veiculo,tenant_id)
    from app.services.administracao_painel import custos_empresa
    custos=await custos_empresa(conn,tenant_id) | (objeto(frota['custos_operacionais']) if frota else {}) | (
        dados.custos_operacionais.model_dump(mode="json", exclude_none=True) if dados.custos_operacionais else {})
    custos=await resolver_custos(conn,custos,dims)
    dono=await conn.fetchval("SELECT tenant_id FROM operacoes WHERE id_operacao=$1",dados.id_operacao)
    if dono and dono!=tenant_id:
        raise HTTPException(403,"Operacao pertence a outra empresa.")
    rota_inicial = await RoutingEngine.compute_route(
        conn, dados.origem_lon, dados.origem_lat, dados.destino_lon, dados.destino_lat, profile="FASTEST", rain_mm=0.0, tenant_id=dados.tenant_id,
        tipo_veiculo=frota["tipo_veiculo"] if frota else "VUC", vehicle_dimensions=dims
    )
    if not rota_inicial:
        raise HTTPException(status_code=400, detail="Nao foi possivel trancar rota para as coordenadas fornecidas.")

    dist_km = rota_inicial["distancia_km"]
    tempo_min = rota_inicial["tempo_min"]
    premissas=ParametrosFinanceiros().model_dump() | custos
    custo_estimado=(dist_km*custo_quilometrico(premissas)['custo_por_km_aplicado']+(tempo_min/60)*(premissas['custo_hora_motorista']+premissas['custo_operacional_veiculo_hora'])
                    +rota_inicial['infraestrutura']['pedagios']['subtotal_conhecido_reais'])

    query = """
    INSERT INTO operacoes (
        id_operacao, id_veiculo, origem_nome, origem_lat, origem_lon,
        destino_nome, destino_lat, destino_lon, janela_inicio, janela_fim,
        status, distancia_planejada_km, tempo_planejado_min, custo_estimado, tenant_id, dimensoes, custos_operacionais
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NULLIF($9::text, '')::timestamp, NULLIF($10::text, '')::timestamp, 'PLANNED', $11, $12, $13, $14, $15::jsonb, $16::jsonb)
    ON CONFLICT (id_operacao) DO UPDATE SET
        id_veiculo = EXCLUDED.id_veiculo,
        origem_nome = EXCLUDED.origem_nome,
        origem_lat = EXCLUDED.origem_lat,
        origem_lon = EXCLUDED.origem_lon,
        destino_nome = EXCLUDED.destino_nome,
        destino_lat = EXCLUDED.destino_lat,
        destino_lon = EXCLUDED.destino_lon,
        distancia_planejada_km = EXCLUDED.distancia_planejada_km,
        tempo_planejado_min = EXCLUDED.tempo_planejado_min,
        custo_estimado = EXCLUDED.custo_estimado,
        dimensoes=EXCLUDED.dimensoes,custos_operacionais=EXCLUDED.custos_operacionais
    WHERE operacoes.tenant_id = EXCLUDED.tenant_id
    RETURNING id_operacao;
    """
    async with conn.transaction():
        # Serializa o identificador inclusive quando ainda nao existe uma linha.
        # O DELETE legado nao pode ocorrer antes de conferir a empresa proprietaria.
        await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", dados.id_operacao)
        titular = await conn.fetchval("SELECT tenant_id FROM operacoes WHERE id_operacao=$1 FOR UPDATE", dados.id_operacao)
        if titular is not None and titular != tenant_id:
            raise HTTPException(409, "Identificador de operacao indisponivel.")
        await conn.execute("DELETE FROM operacao_rotas_trechos WHERE id_operacao = $1;", dados.id_operacao)
        await conn.execute(
            query, dados.id_operacao, dados.id_veiculo, dados.origem_nome, dados.origem_lat, dados.origem_lon,
            dados.destino_nome, dados.destino_lat, dados.destino_lon, dados.janela_inicio, dados.janela_fim,
            dist_km, tempo_min, custo_estimado, dados.tenant_id, json.dumps(dims) if dims else None,json.dumps(custos)
        )

        trechos_params = [(dados.id_operacao, idx, t_id) for idx, t_id in enumerate(rota_inicial["ids_trechos"])]
        await conn.executemany(
            "INSERT INTO operacao_rotas_trechos (id_operacao, seq, id_trecho) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING;",
            trechos_params
        )

    return {
        "sucesso": True,
        "id_operacao": dados.id_operacao,
        "tenant_id": dados.tenant_id,
        "distancia_km": dist_km,
        "tempo_min": tempo_min,
        "custo_estimado_brl": round(custo_estimado, 2),
        "infraestrutura":rota_inicial["infraestrutura"]
    }

@router.get("/operacoes")
async def listar_operacoes(tenant_id: str = Depends(resolve_tenant), conn: asyncpg.Connection = Depends(get_connection)):
    rows = await conn.fetch("SELECT * FROM operacoes WHERE tenant_id = $1 ORDER BY criado_em DESC;", tenant_id)
    return [{**dict(r), "dimensoes":objeto(r["dimensoes"]) or None,
             "custos_operacionais":objeto(r["custos_operacionais"]) or None} for r in rows]

@router.post("/simular-impacto", dependencies=[Depends(require_role(["ADMIN", "OPERATOR"])), Depends(aplicar_rate_limit)])
async def simular_impacto(dados: SimulacaoB2BRequest, conn: asyncpg.Connection = Depends(get_connection), tenant_id: str = Depends(resolve_tenant)):
    dados.tenant_id = tenant_id
    id_cenario = f"SIM_{int(dados.precipitacao_mm)}MM_{uuid.uuid4().hex[:6]}"
    await conn.execute(
        "INSERT INTO cenarios_clima (id_cenario, nome, precipitacao_mm, tipo, tenant_id) VALUES ($1, $2, $3, 'SIMULACAO', $4);",
        id_cenario, f"Simulacao {dados.precipitacao_mm} mm", dados.precipitacao_mm, dados.tenant_id
    )

    contexto=await ContextoViagens.carregar(conn,tenant_id)
    contagens={'NORMAL':0,'RISCO':0,'CRITICO':0}
    recomendacoes=[]
    for op in contexto.ops:
        analise=await contexto.analisar(op,dados.precipitacao_mm,dados.parametros_custo.model_dump())
        contagens[analise['nivel_risco']]+=1
        if analise['necessita_desvio']:
            recomendacoes.append(await gravar_recomendacao(conn,op,tenant_id,id_cenario,analise))
    return {'id_cenario':id_cenario,'tenant_id':tenant_id,'clima_simulado_mm':dados.precipitacao_mm,
        'resumo_operacional':{'total_operacoes':len(contexto.ops),'normais':contagens['NORMAL'],
            'atencao':0,'em_risco':contagens['RISCO'],'criticas':contagens['CRITICO']},
        'recomendacoes':recomendacoes}

@router.get("/operacoes/{id_operacao}/explicacao")
async def obter_explicacao_decisao(id_operacao: str, tenant_id: str = Depends(resolve_tenant), conn: asyncpg.Connection = Depends(get_connection)):
    op = await conn.fetchrow("SELECT * FROM operacoes WHERE id_operacao = $1 AND tenant_id = $2;", id_operacao, tenant_id)
    if not op:
        raise HTTPException(status_code=404, detail="Operacao nao encontrada.")

    veiculo = await conn.fetchrow("SELECT placa, modelo, tipo_veiculo FROM veiculos WHERE id_veiculo = $1 AND tenant_id = $2;", op["id_veiculo"], tenant_id)
    rec = await conn.fetchrow("""
        SELECT tipo_acao, nivel_risco, motivo, confianca, km_adicionais, minutos_adicionais, custo_desvio, prejuizo_potencial_evitado, rota_alternativa_geojson, analise_infraestrutura
        FROM recomendacoes_operacao
        WHERE id_operacao = $1 AND tenant_id = $2
        ORDER BY id_recomendacao DESC LIMIT 1;
    """, id_operacao, tenant_id)

    trechos_criticos = await conn.fetch("""
        SELECT t.id_trecho, t.name, t.length, t.classe_risco, t.ivi_score,
               ST_AsGeoJSON(ST_Transform(t.geom, 4326)) AS geojson
        FROM operacao_rotas_trechos ort
        JOIN trechos_osm t ON t.id_trecho = ort.id_trecho
        WHERE ort.id_operacao = $1 AND t.classe_risco IN ('Alto', 'Critico', 'Muito Alto')
        ORDER BY t.ivi_score DESC;
    """, id_operacao)

    trechos_originais = await conn.fetch("""
        SELECT t.id_trecho, t.name, t.length, t.classe_risco, t.ivi_score,
               ST_AsGeoJSON(ST_Transform(t.geom, 4326)) AS geojson
        FROM operacao_rotas_trechos ort
        JOIN trechos_osm t ON t.id_trecho = ort.id_trecho
        WHERE ort.id_operacao = $1
        ORDER BY ort.seq;
    """, id_operacao)

    dist_orig = round(float(op["distancia_planejada_km"] or 0.0), 2)
    delta_km = round(float(rec["km_adicionais"]), 2) if rec and rec["km_adicionais"] is not None else 0.0
    dist_alt = round(dist_orig + delta_km, 2)

    tempo_orig = round(float(op["tempo_planejado_min"] or 0.0), 1)
    delta_tempo = round(float(rec["minutos_adicionais"]), 1) if rec and rec["minutos_adicionais"] is not None else 0.0
    tempo_alt = round(tempo_orig + delta_tempo, 1)

    custo_desvio = float(rec["custo_desvio"]) if rec and rec["custo_desvio"] is not None else round((delta_km * 4.50) + ((delta_tempo / 60.0) * 85.0), 2)
    prejuizo_evitado = float(rec["prejuizo_potencial_evitado"]) if rec and rec["prejuizo_potencial_evitado"] is not None else 0.0

    def _limpar_nome_via(nome, id_t):
        if not nome:
            return f"Via Urbana #{id_t}"
        limpo = "".join(c for c in str(nome) if c.isprintable() and ord(c) < 65533)
        limpo = limpo.replace("[", "").replace("÷", "u").replace("û", "a").strip()
        return limpo or f"Via Urbana #{id_t}"

    pontos_bloqueio = [
        {
            "id_trecho": r["id_trecho"],
            "nome_via": _limpar_nome_via(r["name"], r["id_trecho"]),
            "status": r["classe_risco"],
            "extensao_metros": round(float(r["length"] or 0), 1),
            "score_risco": round(float(r["ivi_score"] or 0), 1),
            "motivo": f"Vulnerabilidade fisica/hidrologica IVI {round(float(r['ivi_score'] or 0), 1)}"
        }
        for r in trechos_criticos
    ]

    rota_original_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": json.loads(r["geojson"]),
                "properties": {"id_trecho": r["id_trecho"], "classe_risco": r["classe_risco"]}
            }
            for r in trechos_originais if r["geojson"]
        ]
    }

    trechos_criticos_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": json.loads(r["geojson"]),
                "properties": {"id_trecho": r["id_trecho"], "nome_via": _limpar_nome_via(r["name"], r["id_trecho"]), "ivi_score": float(r["ivi_score"] or 0)}
            }
            for r in trechos_criticos if r["geojson"]
        ]
    }

    justificativa = rec["motivo"] if rec and rec["motivo"] else (
        f"A rota planejada intercepta {len(pontos_bloqueio)} trecho(s) classificados com severidade de alagamento. Recomendado desvio preventivo para resguardar o veiculo e a carga."
        if pontos_bloqueio else "Operacao em trechos normais sem restricoes severas de alagamento."
    )

    contexto=await ContextoViagens.carregar(conn,tenant_id,id_operacao)
    original=contexto.original(contexto.ops[0])
    snapshot=objeto(rec['analise_infraestrutura']) if rec else {}
    infraestrutura={'original':original['infraestrutura'],
        'alternativa':snapshot.get('alternativa',{}).get('infraestrutura') if snapshot.get('alternativa') else None,
        'financeiro':snapshot.get('financeiro'),'dimensoes':dados_viagem(contexto.ops[0])[0],
        'aviso':'Custos da recomendacao sao uma fotografia do recalculo; cadastros atuais da rota original podem ter mudado.'}
    infraestrutura['custo_planejado_conhecido_brl']=float(op['custo_estimado'] or 0)
    if snapshot.get('alternativa'):
        dist_alt=snapshot['alternativa']['distancia_km']
        tempo_alt=snapshot['alternativa']['tempo_min']
    return {
        "id_operacao": op["id_operacao"],
        "tenant_id": op["tenant_id"],
        "id_veiculo": op["id_veiculo"],
        "placa": veiculo["placa"] if veiculo else "N/A",
        "modelo": veiculo["modelo"] if veiculo else "N/A",
        "tipo_veiculo": veiculo["tipo_veiculo"] if veiculo else "N/A",
        "status_operacao": op["status"],
        "infraestrutura":infraestrutura,
        "acao_recomendada": rec["tipo_acao"] if rec else ("ALTERAR_ROTA" if pontos_bloqueio else "MANTER_ROTA"),
        "nivel_risco": rec["nivel_risco"] if rec else ("CRITICO" if pontos_bloqueio else "NORMAL"),
        "confianca": float(rec["confianca"]) if rec and rec["confianca"] else 0.95,
        "justificativa": justificativa,
        "metricas": {
            "distancia_original_km": dist_orig,
            "distancia_alternativa_km": dist_alt,
            "delta_km": delta_km,
            "tempo_original_min": tempo_orig,
            "tempo_alternativo_min": tempo_alt,
            "delta_tempo_min": delta_tempo,
            "custo_desvio_brl": custo_desvio,
            "prejuizo_evitado_brl": prejuizo_evitado
        },
        "pontos_bloqueio": pontos_bloqueio,
        "validacao_rota": {
            "rota_alternativa_disponivel": bool(rec and rec["rota_alternativa_geojson"]),
            "avisos_limitacao": "Malha OSM urbana validada para conectividade; restricoes fisicas locais de balanca e altura devem ser conferidas pelo motorista."
        },
        "coordenadas": {
            "origem_nome": op["origem_nome"],
            "origem_lat": float(op["origem_lat"]),
            "origem_lon": float(op["origem_lon"]),
            "destino_nome": op["destino_nome"],
            "destino_lat": float(op["destino_lat"]),
            "destino_lon": float(op["destino_lon"])
        },
        "geometrias": {
            "rota_original_geojson": rota_original_fc,
            "rota_alternativa_geojson": json.loads(rec["rota_alternativa_geojson"]) if rec and rec["rota_alternativa_geojson"] else None,
            "trechos_criticos_geojson": trechos_criticos_fc
        }
    }

@router.get("/exportar-contingencia/csv")
async def exportar_plano_contingencia_csv(tenant_id: str = Depends(resolve_tenant), conn: asyncpg.Connection = Depends(get_connection)):
    query = """
        SELECT
            o.id_operacao,
            o.tenant_id,
            o.id_veiculo,
            v.placa,
            v.modelo,
            v.tipo_veiculo,
            o.status AS status_operacao,
            COALESCE(r.tipo_acao, 'MANTER_ROTA') AS acao_recomendada,
            COALESCE(r.nivel_risco, 'NORMAL') AS nivel_risco,
            COALESCE(r.confianca, 0.95) AS confianca,
            o.distancia_planejada_km,
            COALESCE(r.km_adicionais, 0.0) AS km_adicionais,
            ROUND((o.distancia_planejada_km + COALESCE(r.km_adicionais, 0.0))::numeric, 2) AS distancia_total_km,
            o.tempo_planejado_min,
            COALESCE(r.minutos_adicionais, 0.0) AS minutos_adicionais,
            ROUND((o.tempo_planejado_min + COALESCE(r.minutos_adicionais, 0.0))::numeric, 2) AS tempo_total_min,
            COALESCE(r.custo_desvio, 0.0) AS custo_desvio_brl,
            COALESCE(r.prejuizo_potencial_evitado, 0.0) AS prejuizo_evitado_brl,
            COALESCE(r.motivo, 'Operacao sem impedimentos detectados.') AS justificativa
        FROM operacoes o
        LEFT JOIN veiculos v ON v.id_veiculo = o.id_veiculo AND v.tenant_id = o.tenant_id
        LEFT JOIN LATERAL (
            SELECT tipo_acao, nivel_risco, confianca, km_adicionais, minutos_adicionais, custo_desvio, prejuizo_potencial_evitado, motivo
            FROM recomendacoes_operacao
            WHERE id_operacao = o.id_operacao AND tenant_id = o.tenant_id
            ORDER BY id_recomendacao DESC
            LIMIT 1
        ) r ON true
        WHERE o.tenant_id = $1
        ORDER BY o.id_operacao;
    """
    rows = await conn.fetch(query, tenant_id)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        "TENANT_ID", "ID_OPERACAO", "ID_VEICULO", "PLACA", "MODELO", "TIPO_VEICULO",
        "STATUS", "ACAO_RECOMENDADA", "NIVEL_RISCO", "CONFIANCA",
        "KM_PLANEJADO", "KM_ADICIONAIS", "KM_TOTAL",
        "TEMPO_PLANEJADO_MIN", "MINUTOS_ADICIONAIS", "TEMPO_TOTAL_MIN",
        "CUSTO_DESVIO_BRL", "PREJUIZO_EVITADO_BRL", "JUSTIFICATIVA"
    ])

    for row in rows:
        writer.writerow([
            row["tenant_id"],
            row["id_operacao"],
            row["id_veiculo"],
            row["placa"] or "N/A",
            row["modelo"] or "N/A",
            row["tipo_veiculo"] or "N/A",
            row["status_operacao"],
            row["acao_recomendada"],
            row["nivel_risco"],
            row["confianca"],
            row["distancia_planejada_km"],
            row["km_adicionais"],
            row["distancia_total_km"],
            row["tempo_planejado_min"],
            row["minutos_adicionais"],
            row["tempo_total_min"],
            row["custo_desvio_brl"],
            row["prejuizo_evitado_brl"],
            row["justificativa"]
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=plano_contingencia_{tenant_id}.csv"}
    )

@router.post("/operacoes/importar-lote", dependencies=[Depends(require_role(["ADMIN", "OPERATOR"])), Depends(aplicar_rate_limit)],
             summary="Importar operacoes com resultado por item",
             description="Importacao nao atomica: algumas operacoes podem ser gravadas mesmo quando outras falham. "
                         "Confira sucessos/falhas antes de reenviar. O identificador ja existente na mesma empresa "
                         "atualiza a operacao; use a previa da central para evitar substituicoes acidentais.")
async def importar_operacoes_lote(lote: List[Dict[str, Any]], tenant_id: str = Depends(resolve_tenant), conn: asyncpg.Connection = Depends(get_connection)):
    from datetime import datetime, timedelta, timezone
    from pydantic import ValidationError
    sucessos=0
    erros=[]
    for item in lote:
        try:
            agora=datetime.now(timezone.utc)
            payload=OperacaoCreate(**{
                'origem_nome':'Ponto de Coleta','destino_nome':'Destinatario',
                'janela_inicio':agora.isoformat(),'janela_fim':(agora+timedelta(hours=4)).isoformat(),
                **item,'tenant_id':tenant_id})
            await criar_operacao(payload,conn,tenant_id)
            sucessos+=1
        except (HTTPException,ValidationError,ValueError,TypeError,asyncpg.PostgresError) as exc:
            erros.append({'id_operacao':item.get('id_operacao'),
                'erro':exc.detail if isinstance(exc,HTTPException) else 'Cadastro invalido ou rota indisponivel.'})
    return {'total_recebido':len(lote),'tenant_id':tenant_id,'sucessos':sucessos,
            'falhas':len(erros),'detalhe_falhas':erros}

@router.post("/alertas/disparar-webhook", dependencies=[Depends(require_role(["ADMIN", "OPERATOR"]))])
async def disparar_alerta_webhook(dados: WebhookAlertaRequest, conn: asyncpg.Connection = Depends(get_connection), tenant_autenticado: str = Depends(resolve_tenant)):
    if dados.tenant_id != tenant_autenticado:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    if not is_safe_url(dados.webhook_url):
        raise HTTPException(status_code=400, detail="SSRF bloqueado")
    op = await conn.fetchrow("SELECT * FROM operacoes WHERE id_operacao = $1 AND tenant_id = $2;", dados.id_operacao, dados.tenant_id)
    if not op:
        raise HTTPException(status_code=404, detail="Operacao nao encontrada.")

    veiculo = await conn.fetchrow("SELECT placa, modelo, tipo_veiculo FROM veiculos WHERE id_veiculo = $1 AND tenant_id = $2;", op["id_veiculo"], dados.tenant_id)
    rec = await conn.fetchrow("""
        SELECT tipo_acao, nivel_risco, motivo, confianca, km_adicionais, minutos_adicionais, custo_desvio, prejuizo_potencial_evitado
        FROM recomendacoes_operacao
        WHERE id_operacao = $1 AND tenant_id = $2
        ORDER BY id_recomendacao DESC LIMIT 1;
    """, dados.id_operacao, dados.tenant_id)

    payload_alerta = {
        "evento": "ALERTA_OPERACAO_CRITICA",
        "tenant_id": dados.tenant_id,
        "timestamp": str(op["criado_em"]),
        "operacao": {
            "id_operacao": op["id_operacao"],
            "status": op["status"],
            "veiculo": {
                "id_veiculo": op["id_veiculo"],
                "placa": veiculo["placa"] if veiculo else "N/A",
                "modelo": veiculo["modelo"] if veiculo else "N/A"
            },
            "recomendacao": {
                "acao": rec["tipo_acao"] if rec else "ALTERAR_ROTA",
                "nivel_risco": rec["nivel_risco"] if rec else "CRITICO",
                "motivo": rec["motivo"] if rec else "Risco de inundacao severa no trajeto.",
                "confianca": float(rec["confianca"]) if rec and rec["confianca"] else 0.88
            },
            "impacto_financeiro": {
                "custo_desvio_brl": float(rec["custo_desvio"]) if rec and rec["custo_desvio"] is not None else 0.0,
                "prejuizo_evitado_brl": float(rec["prejuizo_potencial_evitado"]) if rec and rec["prejuizo_potencial_evitado"] is not None else 0.0
            }
        }
    }

    status_envio = "SIMULADO"
    status_code = 200
    try:
        req_data = json.dumps(payload_alerta).encode("utf-8")
        status_code = await asyncio.to_thread(
            post_seguro, dados.webhook_url,
            {"Content-Type": "application/json", "User-Agent": "SPRain-Resilience-Engine/1.0"},
            req_data, 4.0
        )
        status_envio = "ENVIADO"
    except Exception:
        status_envio = "FALHA_ENVIO"
        status_code = 502

    return {
        "sucesso": status_code in [200, 201, 202],
        "status_envio": status_envio,
        "codigo_http": status_code,
        "payload_gerado": payload_alerta
    }

@router.get("/alertas/ativos")
async def listar_alertas_ativos(tenant_id: str = Depends(resolve_tenant), conn: asyncpg.Connection = Depends(get_connection)):
    query = """
        SELECT
            o.id_operacao,
            o.tenant_id,
            o.id_veiculo,
            v.placa,
            v.modelo,
            r.tipo_acao,
            r.nivel_risco,
            r.motivo,
            r.custo_desvio,
            r.km_adicionais, r.minutos_adicionais,
            r.prejuizo_potencial_evitado,
            r.gerado_em
        FROM recomendacoes_operacao r
        JOIN operacoes o ON o.id_operacao = r.id_operacao AND o.tenant_id = r.tenant_id
        LEFT JOIN veiculos v ON v.id_veiculo = o.id_veiculo AND v.tenant_id = o.tenant_id
        WHERE r.tenant_id = $1 AND r.nivel_risco IN ('CRITICO', 'RISCO')
          AND r.id_recomendacao = (SELECT max(atual.id_recomendacao) FROM recomendacoes_operacao atual
              WHERE atual.id_operacao=r.id_operacao AND atual.tenant_id=r.tenant_id)
        ORDER BY r.id_recomendacao DESC
        LIMIT 50;
    """
    rows = await conn.fetch(query, tenant_id)
    return [dict(r) for r in rows]

@router.post("/planejamento-d1", dependencies=[Depends(require_role(["ADMIN", "OPERATOR"]))])
async def planejar_operacoes_d1(dados: PlanejamentoD1Request, conn: asyncpg.Connection = Depends(get_connection), tenant_id: str = Depends(resolve_tenant)):
    dados.tenant_id = tenant_id
    from app.services.weather import OpenMeteoProvider

    if dados.previsao_chuva_mm <= 0:
        provider = OpenMeteoProvider()
        dados.previsao_chuva_mm = (provider.get_forecast_rainfall(-21.79, -48.17, days=1) or 0.0)

    query_ops = """
        SELECT o.id_operacao, o.id_veiculo, o.distancia_planejada_km, o.tempo_planejado_min, o.custo_estimado,
               v.placa, v.modelo, v.tipo_veiculo
        FROM operacoes o
        LEFT JOIN veiculos v ON v.id_veiculo = o.id_veiculo AND v.tenant_id = o.tenant_id
        WHERE o.tenant_id = $1
        ORDER BY o.id_operacao;
    """
    ops = await conn.fetch(query_ops, dados.tenant_id)

    operacoes_em_risco = []
    total_desvio_estimado = 0.0
    prejuizo_total_resguardado = 0.0

    contexto=await ContextoViagens.carregar(conn,tenant_id)
    por_id={o['id_operacao']:o for o in contexto.ops}
    for r in ops:
        dist=float(r['distancia_planejada_km'] or 5.0)
        exposicao_score=(dados.previsao_chuva_mm*0.65)*(dist/10.0)*dados.fator_severidade
        op=por_id[r['id_operacao']]
        fisico=bool(contexto.original(op)['infraestrutura']['trechos_incompativeis'])
        if exposicao_score<25.0 and not fisico:
            continue
        analise=await contexto.analisar(op,dados.previsao_chuva_mm,forcar=True)
        financeiro=analise['financeiro'] or {}
        custo=financeiro.get('custo_desvio_brl',0)
        total_desvio_estimado+=custo
        prejuizo_total_resguardado+=financeiro.get('prejuizo_potencial_evitado_brl',0)
        operacoes_em_risco.append({'id_operacao':r['id_operacao'],'id_veiculo':r['id_veiculo'],
            'placa':r['placa'] or 'N/A','modelo':r['modelo'] or 'N/A',
            'exposicao_score':round(exposicao_score,1),
            'acao_sugerida':('AGUARDAR_MELHORA' if not analise['alternativa'] else
                'ALTERAR_ROTA_PREVENTIVA' if fisico or exposicao_score>=40 else 'MONITORAR_JANELA'),
            'delta_km_projetado':analise.get('delta_km',0),
            'delta_tempo_projetado_min':analise.get('delta_tempo_min',0),
            'custo_desvio_projetado_brl':custo,'infraestrutura':analise})

    return {
        "data_planejamento": dados.data_alvo,
        "tenant_id": dados.tenant_id,
        "previsao_aplicada_mm": dados.previsao_chuva_mm,
        "total_operacoes_analisadas": len(ops),
        "total_operacoes_em_risco": len(operacoes_em_risco),
        "custo_total_desvio_projetado_brl": round(total_desvio_estimado, 2),
        "prejuizo_potencial_preservado_brl": round(prejuizo_total_resguardado, 2),
        "detalhamento_risco": operacoes_em_risco
    }

@router.get("/auditoria/acuracia", dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])
async def obter_auditoria_acuracia(conn: asyncpg.Connection = Depends(get_connection), tenant_id: str = Depends(resolve_tenant)):
    query = """
        SELECT
            COUNT(*) AS total_avaliado,
            COUNT(*) FILTER (WHERE resultado_classificacao = 'VERDADEIRO_POSITIVO') AS vp,
            COUNT(*) FILTER (WHERE resultado_classificacao = 'FALSO_POSITIVO') AS fp,
            COUNT(*) FILTER (WHERE resultado_classificacao = 'VERDADEIRO_NEGATIVO') AS vn,
            COUNT(*) FILTER (WHERE resultado_classificacao = 'FALSO_NEGATIVO') AS fn
        FROM auditoria_previsao_realidade
        WHERE tenant_id = $1;
    """
    row = await conn.fetchrow(query, tenant_id)

    if row is None:
        raise HTTPException(status_code=500, detail="Falha ao consultar os dados.")
    total = int(row["total_avaliado"] or 0)
    vp = int(row["vp"] or 0)
    fp = int(row["fp"] or 0)
    vn = int(row["vn"] or 0)
    fn = int(row["fn"] or 0)

    base_calc = vp + fp + vn + fn
    if base_calc == 0:
        return {
            "amostra_historica_total": 0,
            "matriz_confusao": {"verdadeiros_positivos": 0, "falsos_positivos": 0, "verdadeiros_negativos": 0, "falsos_negativos": 0},
            "metricas_resiliencia": {"acuracia_global_pct": 0.0, "precisao_alertas_pct": 0.0, "sensibilidade_deteccao_pct": 0.0},
            "status_motor": "SEM_DADOS_SUFICIENTES",
            "aviso": "Auditoria sem registros operacionais reais no banco."
        }

    acuracia = round(((vp + vn) / base_calc) * 100.0, 1)
    precisao = round((vp / max(1, vp + fp)) * 100.0, 1)
    sensibilidade = round((vp / max(1, vp + fn)) * 100.0, 1)

    return {
        "amostra_historica_total": base_calc,
        "matriz_confusao": {
            "verdadeiros_positivos": vp,
            "falsos_positivos": fp,
            "verdadeiros_negativos": vn,
            "falsos_negativos": fn
        },
        "metricas_resiliencia": {
            "acuracia_global_pct": acuracia,
            "precisao_alertas_pct": precisao,
            "sensibilidade_deteccao_pct": sensibilidade
        },
        "status_motor": "CALIBRADO_ALTA_CONFIANCA" if acuracia >= 85.0 else "EM_CALIBRACAO"
    }

@router.get("/performance/cache", dependencies=[Depends(require_role(["ADMIN", "OPERATOR"]))])
async def obter_status_cache(tenant_id: str = Depends(resolve_tenant)):
    return RoutingEngine.cache_stats(tenant_id)

@router.post("/performance/cache/limpar", dependencies=[Depends(require_role(["ADMIN"]))])
async def limpar_cache(tenant_id: str = Depends(resolve_tenant)):
    RoutingEngine.clear_cache(tenant_id)
    return {"sucesso": True, "mensagem": "Cache de rotas da empresa esvaziado"}

from app.services.observabilidade import MetricsCollector

@router.get("/observabilidade/metricas", dependencies=[Depends(require_role(["ADMIN", "OPERATOR"]))])
async def obter_metricas_sistema(tenant_id: str = Depends(resolve_tenant)):
    return MetricsCollector.obter_metricas(tenant_id)

@router.post("/observabilidade/reset", dependencies=[Depends(require_role(["ADMIN"]))])
async def resetar_metricas_sistema(tenant_id: str = Depends(resolve_tenant)):
    MetricsCollector.resetar(tenant_id)
    return {"sucesso": True, "mensagem": "Metricas de observabilidade da empresa zeradas"}

@router.get("/relatorios/auditoria.csv", dependencies=[Depends(require_role(["ADMIN", "OPERATOR"]))])
async def exportar_auditoria_csv(tenant_id: str = Depends(resolve_tenant), conn: asyncpg.Connection = Depends(get_connection)):
    query = """
        SELECT
            COALESCE(o.id_veiculo, 'N/A') AS id_veiculo,
            COALESCE(o.origem_nome, 'Origem') AS origem,
            COALESCE(o.destino_nome, 'Destino') AS destino,
            COALESCE(c.precipitacao_mm, 0.0) AS precipitacao_mm,
            COALESCE(r.nivel_risco, 'NORMAL') AS impacto_detectado,
            COALESCE(r.prejuizo_potencial_evitado, 0.0) AS custo_evitado_reais,
            TO_CHAR(COALESCE(r.gerado_em, o.criado_em), 'YYYY-MM-DD HH24:MI') AS data_registro
        FROM operacoes o
        LEFT JOIN recomendacoes_operacao r ON r.id_operacao = o.id_operacao AND r.tenant_id = o.tenant_id
        LEFT JOIN cenarios_clima c ON c.id_cenario = r.id_cenario
        WHERE o.tenant_id = $1
        ORDER BY o.criado_em DESC
        LIMIT 500;
    """
    rows = await conn.fetch(query, tenant_id)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["id_veiculo", "origem", "destino", "precipitacao_mm", "impacto_detectado", "custo_evitado_reais", "data_registro"])

    if not rows:
        writer.writerow(["SEM_DADOS", "Nenhum registro para o tenant informado", "", 0.0, "N/A", 0.0, ""])
    else:
        for r in rows:
            writer.writerow([
                r["id_veiculo"],
                r["origem"],
                r["destino"],
                r["precipitacao_mm"],
                r["impacto_detectado"],
                r["custo_evitado_reais"],
                r["data_registro"]
            ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=auditoria_logistica_{tenant_id}.csv"}
    )

@router.get("/relatorios/sumario-executivo", dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])
async def obter_sumario_executivo(tenant_id: str = Depends(resolve_tenant), conn: asyncpg.Connection = Depends(get_connection)):
    query = """
        SELECT
            COUNT(o.id_operacao)::int AS total_operacoes,
            COUNT(r.id_operacao) FILTER (WHERE r.nivel_risco IN ('CRITICO', 'RISCO'))::int AS rotas_em_risco,
            COUNT(r.id_operacao) FILTER (WHERE r.tipo_acao = 'ALTERAR_ROTA')::int AS rotas_recalculadas,
            COALESCE(SUM(r.prejuizo_potencial_evitado), 0.0)::float AS prejuizo_evitado,
            COALESCE(SUM(r.minutos_adicionais), 0.0)::float AS tempo_desvios
        FROM operacoes o
        LEFT JOIN LATERAL (
            SELECT id_operacao, nivel_risco, tipo_acao, prejuizo_potencial_evitado, minutos_adicionais
            FROM recomendacoes_operacao
            WHERE id_operacao = o.id_operacao AND tenant_id = o.tenant_id
            ORDER BY id_recomendacao DESC
            LIMIT 1
        ) r ON true
        WHERE o.tenant_id = $1;
    """
    row = await conn.fetchrow(query, tenant_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Falha ao consultar os dados.")
    total_ops = int(row["total_operacoes"] or 0)
    rotas_risco = int(row["rotas_em_risco"] or 0)
    recalculadas = int(row["rotas_recalculadas"] or 0)
    indice_resiliencia = 100.0 if rotas_risco == 0 else round((recalculadas / max(1, rotas_risco)) * 100.0, 1)

    return {
        "tenant_id": tenant_id,
        "periodo": "D-0 / D+1",
        "kpis": {
            "total_operacoes": total_ops,
            "rotas_em_risco_alagamento": rotas_risco,
            "rotas_recalculadas_com_sucesso": recalculadas,
            "indice_resiliencia_pct": indice_resiliencia,
            "prejuizo_estimado_evitado_brl": round(float(row["prejuizo_evitado"] or 0.0), 2),
            "tempo_total_desvios_min": round(float(row["tempo_desvios"] or 0.0), 1),
            "status_sla": "OPERACAO_PROTEGIDA" if (rotas_risco == 0 or recalculadas == rotas_risco) else "ATENCAO_OPERACIONAL"
        }
    }

from app.services.webhook_dispatcher import WebhookDispatcher
from pydantic import BaseModel
from uuid import UUID

class WebhookConfigRequest(BaseModel):
    url: str
    secret: str
    eventos: list[str]

class WebhookTestRequest(BaseModel):
    evento: str = "ALERTA_ALAGAMENTO"
    dados: dict
    enviar: bool = False

@router.post("/webhooks/configurar", dependencies=[Depends(require_role(["ADMIN"]))])
async def configurar_webhook_tenant(payload: WebhookConfigRequest, tenant_id: str = Depends(resolve_tenant), conn: asyncpg.Connection = Depends(get_connection)):
    if not is_safe_url(payload.url):
        raise HTTPException(status_code=400, detail="SSRF bloqueado")
    return await WebhookDispatcher.configurar_webhook(conn, tenant_id, payload.url, payload.secret, payload.eventos)

@router.post("/webhooks/testar", dependencies=[Depends(require_role(["ADMIN", "OPERATOR"]))])
async def testar_webhook_tenant(payload: WebhookTestRequest, tenant_id: str = Depends(resolve_tenant), conn: asyncpg.Connection = Depends(get_connection)):
    resultado = await WebhookDispatcher.disparar_evento_sincrono(conn, tenant_id, payload.evento, payload.dados)
    if not resultado["sucesso"]:
        raise HTTPException(status_code=400, detail=resultado["motivo"])
    if payload.enviar:
        resultado["envio"] = await WebhookDispatcher.enviar_resultado(resultado)
    return resultado

from app.schemas_economic import DecisaoEconomicaRequest
from app.services.economic_engine import EconomicDecisionEngine

@router.post("/decisao-economica", dependencies=[Depends(aplicar_rate_limit)])
async def tomar_decisao_economica(dados: DecisaoEconomicaRequest, conn: asyncpg.Connection = Depends(get_connection), tenant_id: str = Depends(resolve_tenant)):
    dados.tenant_id = tenant_id
    cadastradas=await dimensoes_veiculo(conn,tenant_id,dados.id_veiculo)
    dims=dados.dimensoes.model_dump() if dados.dimensoes else cadastradas
    custos=objeto(await conn.fetchval('SELECT custos_operacionais FROM veiculos WHERE id_veiculo=$1 AND tenant_id=$2',dados.id_veiculo,tenant_id))
    custos=await resolver_custos(conn,custos,dims)
    parametros=dados.parametros.model_dump()
    mapeamento={'custo_por_km':'custo_por_km','custo_hora_motorista':'custo_hora_motorista',
                'custo_operacional_veiculo_hora':'custo_hora_veiculo'}
    for origem,destino in mapeamento.items():
        if origem in custos and destino not in dados.parametros.model_fields_set:
            parametros[destino]=custos[origem]
    if all(custos.get(k) is not None for k in ('consumo_km_l', 'preco_combustivel_litro', 'custo_por_km_sem_combustivel')) and not {'custo_por_km','consumo_km_l','preco_diesel_litro'} & dados.parametros.model_fields_set:
        parametros['custo_por_km'] = custo_quilometrico(custos)['custo_por_km_aplicado']
    rota_direta = await RoutingEngine.compute_route(
        conn, dados.origem_lon, dados.origem_lat, dados.destino_lon, dados.destino_lat, profile="FASTEST", rain_mm=0.0, tenant_id=dados.tenant_id, vehicle_dimensions=dims
    )
    rota_segura = await RoutingEngine.compute_route(
        conn, dados.origem_lon, dados.origem_lat, dados.destino_lon, dados.destino_lat, profile="SAFEST", rain_mm=dados.precipitacao_mm, tenant_id=dados.tenant_id, vehicle_dimensions=dims
    )

    if not rota_direta or not rota_segura:
        raise HTTPException(status_code=400, detail="Nao foi possivel rotear os pontos informados sobre a malha viaria.")

    rota_direta_info = {
        "distancia_km": rota_direta["distancia_km"],
        "tempo_min": rota_direta["tempo_min"],
        "probabilidade_atraso": None,
        "probabilidade_bloqueio": None,
        "motivo_indisponivel": "Probabilidades de atraso e bloqueio dependem de modelo calibrado contra ocorrencias reais.",
        "custo_pedagio_conhecido":rota_direta["infraestrutura"]["pedagios"]["subtotal_conhecido_reais"]
    }

    rota_segura_info = {
        "distancia_km": rota_segura["distancia_km"],
        "tempo_min": rota_segura["tempo_min"],
        "probabilidade_atraso": None,
        "probabilidade_bloqueio": None,
        "motivo_indisponivel": "Probabilidades de atraso e bloqueio dependem de modelo calibrado contra ocorrencias reais.",
        "custo_pedagio_conhecido":rota_segura["infraestrutura"]["pedagios"]["subtotal_conhecido_reais"]
    }

    resultado = EconomicDecisionEngine.compare_and_recommend(
        rota_direta=rota_direta_info,
        rota_segura=rota_segura_info,
        parametros=parametros
    )

    return {
        "tenant_id": dados.tenant_id,
        "chuva_simulada_mm": dados.precipitacao_mm,
        "decisao": resultado,
        "infraestrutura":{"original":rota_direta["infraestrutura"],"alternativa":rota_segura["infraestrutura"]},
        "modo_risco":"HEURISTICA_EXISTENTE_NAO_CALIBRADA",
        "rotas_geometria": {
            "rota_direta": rota_direta["geojson"],
            "rota_alternativa": rota_segura["geojson"]
        }
    }

@router.get("/central-frota", dependencies=[Depends(aplicar_rate_limit)])
async def obter_painel_central_frota(tenant_id: str = Depends(resolve_tenant), precipitacao_referencia_mm: float = 60.0, prejuizo_referencia_brl: Optional[float] = Query(None, description="Prejuizo potencial configuravel informado pelo gestor"), conn: asyncpg.Connection = Depends(get_connection)):
    query = """
        SELECT
            v.id_veiculo,
            v.placa,
            v.modelo,
            v.tipo_veiculo,
            COALESCE(v.lat_atual, -23.542) AS lat_atual,
            COALESCE(v.lon_atual, -46.468) AS lon_atual,
            o.id_operacao,
            o.origem_nome,
            o.destino_nome,
            o.distancia_planejada_km,
            o.tempo_planejado_min,
            o.status AS status_operacao,
            o.janela_fim,
            COUNT(ort.id_trecho) AS total_trechos_rota,
            COUNT(ort.id_trecho) FILTER (WHERE t.classe_risco IN ('Alto', 'Critico')) AS trechos_risco
        FROM veiculos v
        LEFT JOIN operacoes o ON o.id_veiculo = v.id_veiculo AND o.tenant_id = v.tenant_id AND o.status IN ('PLANNED', 'IN_TRANSIT')
        LEFT JOIN operacao_rotas_trechos ort ON ort.id_operacao = o.id_operacao
        LEFT JOIN trechos_osm t ON t.id_trecho = ort.id_trecho
        WHERE v.tenant_id = $1
        GROUP BY v.id_veiculo, v.placa, v.modelo, v.tipo_veiculo, v.lat_atual, v.lon_atual, o.id_operacao, o.origem_nome, o.destino_nome, o.distancia_planejada_km, o.tempo_planejado_min, o.status, o.janela_fim
        ORDER BY v.id_veiculo;
    """
    rows = await conn.fetch(query, tenant_id)

    frota = []
    total_veiculos = len(rows)
    veiculos_em_risco = 0
    impacto_financeiro_evitavel_total = 0.0

    recs = await conn.fetch("""
        SELECT DISTINCT ON (id_operacao)
            id_operacao, tipo_acao, nivel_risco, custo_desvio,
            prejuizo_potencial_evitado, analise_infraestrutura
        FROM recomendacoes_operacao
        WHERE tenant_id = $1
        ORDER BY id_operacao, id_recomendacao DESC;
    """, tenant_id)
    recs_map = {rec["id_operacao"]: rec for rec in recs}

    for r in rows:
        tem_operacao = r["id_operacao"] is not None
        trechos_risco = int(r["trechos_risco"] or 0)

        if not tem_operacao:
            status_frota = "DISPONIVEL"
            nivel_risco = "BAIXO"
            prob_atraso = None
            eta_min = None
            acao = "AGUARDANDO_DESPACHO"
            custo_desvio = None
            economia_estimada = 0.0
            analise = None
        else:
            status_frota = "EM_TRANSITO"
            dist_km = float(r["distancia_planejada_km"] or 8.0)
            tempo_base_min = float(r["tempo_planejado_min"] or 20.0)

            fator_chuva = min(1.0, precipitacao_referencia_mm / 100.0)
            score_exposicao = (trechos_risco * 25.0) + (fator_chuva * 40.0)

            if score_exposicao >= 60.0 or trechos_risco >= 2:
                nivel_risco = "ALTO"
                prob_atraso = None
                eta_min = None
                acao = "ALTERAR_ROTA_IMEDIATO"
                custo_desvio = None
                economia_estimada = prejuizo_referencia_brl
                veiculos_em_risco += 1
                if economia_estimada is not None:
                    impacto_financeiro_evitavel_total += economia_estimada
            elif score_exposicao >= 35.0 or trechos_risco == 1:
                nivel_risco = "MEDIO"
                prob_atraso = None
                eta_min = None
                acao = "MONITORAR_ALERTA"
                custo_desvio = None
                economia_estimada = 0.0
            else:
                nivel_risco = "BAIXO"
                prob_atraso = None
                eta_min = None
                acao = "MANTER_CURSO"
                custo_desvio = None
                economia_estimada = 0.0

            rec = recs_map.get(r["id_operacao"])
            analise = objeto(rec["analise_infraestrutura"]) if rec and rec["analise_infraestrutura"] else None
            if analise:
                financeiro = analise.get("financeiro") or {}
                if rec["custo_desvio"] is not None:
                    custo_desvio = rec["custo_desvio"]
                elif financeiro.get("custo_desvio_brl") is not None:
                    custo_desvio = financeiro.get("custo_desvio_brl")
                if prejuizo_referencia_brl is not None:
                    economia_estimada = prejuizo_referencia_brl
                elif rec["prejuizo_potencial_evitado"] is not None:
                    economia_estimada = rec["prejuizo_potencial_evitado"]
                acao = rec["tipo_acao"]
                if analise.get("restricao_fisica"):
                    nivel_risco = "ALTO"
            # Totals recalculated from the completed rows below.
        frota.append({
            "id_veiculo": r["id_veiculo"],
            "placa": r["placa"],
            "modelo": r["modelo"],
            "tipo_veiculo": r["tipo_veiculo"],
            "status_monitoramento": status_frota,
            "infraestrutura":analise,
            "operacao_atual": {
                "id_operacao": r["id_operacao"],
                "rota": f"{r['origem_nome']} -> {r['destino_nome']}" if tem_operacao else None,
                "distancia_km": float(r["distancia_planejada_km"]) if tem_operacao and r["distancia_planejada_km"] is not None else None,
                "eta_estimado_min": eta_min
            } if tem_operacao else None,
            "analise_risco": {
                "nivel": nivel_risco,
                "probabilidade_atraso_pct": round(prob_atraso * 100, 1) if prob_atraso is not None else None,
                "trechos_vulneraveis_rota": trechos_risco,
                "recomendacao_acao": acao
            },
            "impacto_financeiro_projetado": {
                "custo_desvio_brl": custo_desvio,
                "economia_potencial_brl": economia_estimada
            }
        })

    veiculos_em_risco=sum(v['analise_risco']['nivel']=='ALTO' for v in frota)
    impacto_financeiro_evitavel_total=sum(v['impacto_financeiro_projetado']['economia_potencial_brl'] or 0.0 for v in frota if v['impacto_financeiro_projetado']['economia_potencial_brl'] is not None)
    return {
        "tenant_id": tenant_id,
        "clima_referencia_mm": precipitacao_referencia_mm,
        "sumario_central": {
            "total_frota": total_veiculos,
            "em_operacao": sum(1 for v in frota if v["status_monitoramento"] == "EM_TRANSITO"),
            "veiculos_alto_risco": veiculos_em_risco,
            "taxa_comprometimento_pct": round((veiculos_em_risco / max(1, total_veiculos)) * 100, 1),
            "economia_potencial_total_brl": round(impacto_financeiro_evitavel_total, 2) if prejuizo_referencia_brl is not None else None
        },
        "veiculos": frota
    }

from app.services.weather_alert_engine import SevereWeatherEngine

@router.get("/alertas-meteorologicos", dependencies=[Depends(aplicar_rate_limit)])
async def obter_alertas_meteorologicos_regiao(precipitacao_mm: float = 65.0, rajada_vento_kmh: float = 40.0):
    alerta = SevereWeatherEngine.parse_alert_severity(precipitacao_mm, rajada_vento_kmh)
    return {
        "fonte": "Motor de Classificacao Parametrizada SPRain",
        "modo_dados": "AVALIACAO_PARAMETRIZADA_SIMULADA",
        "aviso_operacional": "Classificacao calculada a partir dos parametros informados na requisicao. Nao representa leitura automatica de estacao em tempo real.",
        "jurisdicao": "Regiao Metropolitana de Sao Paulo - Polo Zona Leste",
        "alerta": alerta
    }

@router.post("/rate-limit/reset", dependencies=[Depends(require_role(["ADMIN"]))])
async def resetar_rate_limit_servidor(tenant_id: str = Depends(resolve_tenant)):
    TenantRateLimiter.reset(tenant_id)
    return {"sucesso": True, "status": "RATE_LIMIT_RESETADO"}



class DecisaoGestorRequest(BaseModel):
    decisao: str
    motivo_gestor: str = "Validado pela mesa operacional"
    consulta_id: UUID | None = None

@router.post("/operacoes/{id_operacao}/decisao", dependencies=[Depends(require_role(["ADMIN", "OPERATOR"])), Depends(aplicar_rate_limit)])
async def registrar_decisao_gestor(id_operacao: str, payload: DecisaoGestorRequest, tenant_id: str = Depends(resolve_tenant), conn: asyncpg.Connection = Depends(get_connection), claims=Depends(get_current_user_claims)):
    if payload.decisao not in ("APROVAR_DESVIO", "MANTER_ROTA_ORIGINAL", "AGUARDAR_MELHORA"):
        raise HTTPException(status_code=400, detail="Decisao invalida.")
    op = await conn.fetchrow("SELECT id_operacao FROM operacoes WHERE id_operacao = $1 AND tenant_id = $2;", id_operacao, tenant_id)
    if not op:
        raise HTTPException(status_code=404, detail="Operacao nao encontrada.")
    fotografia = None
    perfil_consulta = None
    if payload.consulta_id:
        from app.services.painel import selo
        consulta = await conn.fetchrow('''SELECT snapshot,perfil FROM painel_consultas
            WHERE id=$1 AND tenant_id=$2 AND id_operacao=$3''', payload.consulta_id, tenant_id, id_operacao)
        if not consulta:
            raise HTTPException(404, 'Consulta nao encontrada para esta operacao.')
        fotografia = objeto(consulta['snapshot'])
        perfil_consulta = claims['role']
        if fotografia.get('contexto_consulta',{}).get('selo_premissas') != await selo(conn, tenant_id, id_operacao):
            raise HTTPException(409, 'A consulta ficou desatualizada. Atualize a operacao antes de decidir.')
    if payload.decisao in ('MANTER_ROTA_ORIGINAL','APROVAR_DESVIO'):
        contexto=await ContextoViagens.carregar(conn,tenant_id,id_operacao)
        viagem=contexto.ops[0]
        if payload.decisao=='MANTER_ROTA_ORIGINAL' and contexto.original(viagem)['infraestrutura']['trechos_incompativeis']:
            raise HTTPException(409,'A rota original tem restricoes incompativeis ou medidas ausentes. Corrija os dados e recalcule.')
        if payload.decisao=='APROVAR_DESVIO':
            rec=await conn.fetchrow('''SELECT r.rota_alternativa_geojson,c.precipitacao_mm FROM recomendacoes_operacao r
                LEFT JOIN cenarios_clima c ON c.id_cenario=r.id_cenario AND c.tenant_id=r.tenant_id
                WHERE r.id_operacao=$1 AND r.tenant_id=$2 ORDER BY r.id_recomendacao DESC LIMIT 1''',id_operacao,tenant_id)
            if not rec or not rec['rota_alternativa_geojson']:
                raise HTTPException(409,'Nenhuma alternativa disponivel para aprovar. Recalcule a operacao.')
            avaliacao=await contexto.analisar(viagem,float(rec['precipitacao_mm'] or 0),forcar=True)
            ids={f['properties']['id_trecho'] for f in objeto(rec['rota_alternativa_geojson']).get('features',[])}
            if not avaliacao['alternativa'] or ids!=set(avaliacao['alternativa']['ids_trechos']):
                raise HTTPException(409,'A alternativa mudou ou ficou indisponivel para este caminhao. Recalcule antes de aprovar.')
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS decisoes_gestor_operacao (
            id_decisao SERIAL PRIMARY KEY,
            id_operacao TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            decisao TEXT NOT NULL,
            motivo_gestor TEXT NOT NULL,
            registrado_em TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    row = await conn.fetchrow("""
        INSERT INTO decisoes_gestor_operacao (id_operacao, tenant_id, decisao, motivo_gestor, consulta_id, perfil_registro, snapshot,usuario_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb,$8)
        RETURNING id_decisao, registrado_em;
    """, id_operacao, tenant_id, payload.decisao, payload.motivo_gestor, payload.consulta_id, perfil_consulta,
        json.dumps(fotografia,default=str) if fotografia else None,UUID(claims['usuario_id']) if claims.get('usuario_id') else None)
    return {
        "sucesso": True,
        "id_decisao": row["id_decisao"],
        "id_operacao": id_operacao,
        "tenant_id": tenant_id,
        "decisao_registrada": payload.decisao,
        "motivo_gestor": payload.motivo_gestor,
        "registrado_em": row["registrado_em"].isoformat()
    }

@router.get("/operacoes/{id_operacao}/decisoes", dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"])), Depends(aplicar_rate_limit)])
async def listar_decisoes_gestor(id_operacao: str, tenant_id: str = Depends(resolve_tenant), conn: asyncpg.Connection = Depends(get_connection)):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS decisoes_gestor_operacao (
            id_decisao SERIAL PRIMARY KEY,
            id_operacao TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            decisao TEXT NOT NULL,
            motivo_gestor TEXT NOT NULL,
            registrado_em TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    rows = await conn.fetch("""
        SELECT id_decisao, id_operacao, tenant_id, decisao, motivo_gestor, registrado_em, consulta_id, perfil_registro,usuario_id
        FROM decisoes_gestor_operacao
        WHERE id_operacao = $1 AND tenant_id = $2
        ORDER BY id_decisao DESC;
    """, id_operacao, tenant_id)
    return [
        {
            "id_decisao": r["id_decisao"],
            "id_operacao": r["id_operacao"],
            "tenant_id": r["tenant_id"],
            "decisao": r["decisao"],
            "motivo_gestor": r["motivo_gestor"],
            "consulta_id": str(r['consulta_id']) if r['consulta_id'] else None,
            "perfil_consulta": r['perfil_registro'],
            "usuario_id": str(r['usuario_id']) if r['usuario_id'] else None,
            "registrado_em": r["registrado_em"].isoformat()
        }
        for r in rows
    ]


class LoginCorporativoRequest(BaseModel):
    email: str
    senha: str

USUARIOS_CORPORATIVOS = {
    "operacoes@democorp.com.br": {
        "senha": "sprain2026",
        "empresa": "TransPaulista Logistica S.A.",
        "tenant_id": "demo_corp",
        "role": "OPERATOR",
        "api_key": "key_operator_demo"
    },
    "diretoria@democorp.com.br": {
        "senha": "sprain2026",
        "empresa": "TransPaulista Logistica S.A.",
        "tenant_id": "demo_corp",
        "role": "ADMIN",
        "api_key": "key_admin_demo"
    },
    "auditoria@democorp.com.br": {
        "senha": "sprain2026",
        "empresa": "TransPaulista Logistica S.A.",
        "tenant_id": "demo_corp",
        "role": "VIEWER",
        "api_key": "key_viewer_demo"
    },
    "frota@logexpress.com.br": {
        "senha": "express2026",
        "empresa": "LogExpress Transportes Regionais Ltda.",
        "tenant_id": "log_express",
        "role": "ADMIN",
        "api_key": "key_admin_express"
    }
}

@router.post("/auth/login")
async def login_corporativo(dados: LoginCorporativoRequest):
    if is_production():
        raise HTTPException(status_code=503, detail="Login de demonstracao indisponivel em producao.")
    email_limpo = dados.email.strip().lower()
    user = USUARIOS_CORPORATIVOS.get(email_limpo)
    if not user or user["senha"] != dados.senha:
        raise HTTPException(status_code=401, detail="Credenciais corporativas invalidas.")
    return {
        "autenticado": True,
        "email": email_limpo,
        "empresa": user["empresa"],
        "tenant_id": user["tenant_id"],
        "role": user["role"],
        "api_key": user["api_key"]
    }

@router.get("/vias/buscar", dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])
async def buscar_vias_malha(q: str = Query("", min_length=0), conn: asyncpg.Connection = Depends(get_connection), tenant_id: str=Depends(resolve_tenant)):
    termo = f"%{q.strip()}%" if q.strip() else "%"
    rows = await conn.fetch("""
        SELECT DISTINCT ON (t.name)
            t.id_trecho,
            t.name AS nome_via,
            COALESCE(t.classe_risco, 'Baixo') AS classe_risco,
            ROUND(COALESCE(t.ivi_score, 0)::numeric, 1)::float AS ivi_medio,
            ROUND(ST_Y(ST_StartPoint(ST_Transform(t.geom, 4326)))::numeric, 6)::float AS lat,
            ROUND(ST_X(ST_StartPoint(ST_Transform(t.geom, 4326)))::numeric, 6)::float AS lon
        FROM trechos_osm t
        WHERE (t.tenant_malha IS NULL OR t.tenant_malha=$2)
          AND (t.importacao_malha_id IS NULL OR EXISTS(SELECT 1 FROM malha_importacoes m WHERE m.id=t.importacao_malha_id AND m.ativo))
          AND t.name IS NOT NULL
          AND t.source IS NOT NULL
          AND t.target IS NOT NULL
          AND EXISTS (SELECT 1 FROM operacao_rotas_trechos ort WHERE ort.id_trecho = t.id_trecho)
          AND translate(lower(t.name), 'áàâãéêíóôõúç', 'aaaaeeiooouc') LIKE translate(lower($1), 'áàâãéêíóôõúç', 'aaaaeeiooouc')
        ORDER BY t.name, t.ivi_score DESC NULLS LAST
        LIMIT 15;
    """, termo,tenant_id)
    return [
        {
            "id_trecho": r["id_trecho"],
            "nome_via": r["nome_via"],
            "classe_risco": r["classe_risco"],
            "ivi_medio": r["ivi_medio"],
            "lat": r["lat"],
            "lon": r["lon"]
        }
        for r in rows
    ]

@router.get("/operacoes/{id_operacao}/rota-caminhao", dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])
async def rota_operacao(id_operacao: str, tenant_id: str = Depends(resolve_tenant), conn=Depends(get_connection)):
    op = await conn.fetchrow("SELECT * FROM operacoes WHERE id_operacao=$1 AND tenant_id=$2",id_operacao,tenant_id)
    if op is None:
        raise HTTPException(404,"Operacao nao encontrada.")
    dimensoes = json.loads(op["dimensoes"]) if op["dimensoes"] else None
    rota = await RoutingEngine.compute_route(conn,op["origem_lon"],op["origem_lat"],op["destino_lon"],op["destino_lat"],
                                            tenant_id=tenant_id,vehicle_dimensions=dimensoes,profile=op["perfil_rota"])
    if rota is None:
        raise HTTPException(404,"Nenhuma rota disponivel com os limites cadastrados.")
    return {"id_operacao":id_operacao,"rota_atual_avaliada":rota,
            "aviso":"Reavaliacao do trajeto com o cadastro atual; nao altera a rota planejada nem aprova a viagem."}


class PlanejamentoCaminhaoUpdate(BaseModel):
    dimensoes: VeiculoDimensoes
    perfil: Literal['FASTEST','SHORTEST','SAFEST','BALANCED'] = 'FASTEST'


@router.put("/operacoes/{id_operacao}/planejamento-caminhao",dependencies=[Depends(require_role(["ADMIN","OPERATOR"]))])
async def atualizar_planejamento_caminhao(id_operacao: str,dados: PlanejamentoCaminhaoUpdate,
                                          tenant_id: str=Depends(resolve_tenant),conn=Depends(get_connection)):
    async with conn.transaction():
        op=await conn.fetchrow("SELECT * FROM operacoes WHERE id_operacao=$1 AND tenant_id=$2 FOR UPDATE",id_operacao,tenant_id)
        if not op:
            raise HTTPException(404,"Operacao nao encontrada.")
        if op["status"]!='PLANNED':
            raise HTTPException(409,"Somente viagens planejadas podem ter o planejamento alterado.")
        rota=await RoutingEngine.compute_route(conn,op["origem_lon"],op["origem_lat"],op["destino_lon"],op["destino_lat"],
            tenant_id=tenant_id,vehicle_dimensions=dados.dimensoes.model_dump(),profile=dados.perfil)
        if rota is None:
            raise HTTPException(422,"Nao existe rota disponivel para essas medidas na malha cadastrada.")
        premissas=ParametrosFinanceiros().model_dump() | await resolver_custos(conn,objeto(op['custos_operacionais']),dados.dimensoes.model_dump())
        custo=(rota['distancia_km']*custo_quilometrico(premissas)['custo_por_km_aplicado']+(rota['tempo_min']/60)*(premissas['custo_hora_motorista']+premissas['custo_operacional_veiculo_hora'])
               +rota['infraestrutura']['pedagios']['subtotal_conhecido_reais'])
        await conn.execute("""UPDATE operacoes SET dimensoes=$3::jsonb,distancia_planejada_km=$4,
            tempo_planejado_min=$5,custo_estimado=$6,perfil_rota=$7 WHERE id_operacao=$1 AND tenant_id=$2""",
            id_operacao,tenant_id,dados.dimensoes.model_dump_json(),rota["distancia_km"],rota["tempo_min"],custo,dados.perfil)
        await conn.execute("DELETE FROM operacao_rotas_trechos WHERE id_operacao=$1",id_operacao)
        await conn.executemany("INSERT INTO operacao_rotas_trechos(id_operacao,seq,id_trecho) VALUES($1,$2,$3)",
            [(id_operacao,i,t) for i,t in enumerate(rota["ids_trechos"])])
    return {"sucesso":True,"id_operacao":id_operacao,"rota":rota,"aviso":"Planejamento atualizado; a viagem ainda exige conferencia operacional."}
