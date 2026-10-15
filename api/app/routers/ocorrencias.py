import re
import unicodedata
import uuid
from datetime import datetime, timezone, timedelta
import asyncpg
from fastapi import APIRouter, HTTPException, Depends
from app.schemas import AlertaRapidoCreate, OcorrenciaTextoCreate
from app.nlp import extrair_dados_ocorrencia
from app.database import get_connection
from app.seguranca import exigir_api_key, require_role

router = APIRouter(prefix="/api/v1/ocorrencias", tags=["Ocorrencias"])

def normalizar_texto(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return re.sub(r"[^a-zA-Z0-9\s]", " ", sem_acento).lower().strip()

@router.post("/alerta-rapido", dependencies=[Depends(exigir_api_key)])
async def registrar_alerta_rapido(dados: AlertaRapidoCreate, conn: asyncpg.Connection = Depends(get_connection)):
    status_map = {
        "VERDE": "TRANSITAVEL",
        "AMARELO": "TRANSITAVEL_ALERTA",
        "LARANJA": "INTRANSITAVEL_LEVES",
        "VERMELHO": "INTRANSITAVEL"
    }
    novo_status = status_map[dados.nivel]
    relato = f"[{dados.corporacao}] Alerta tatico: {dados.nivel}. {dados.observacao or ''}".strip()
    id_evento = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)
    expiracao = agora + timedelta(hours=4)

    row = await conn.fetchrow("""
        SELECT t.id_trecho, t.name
        FROM trechos_osm t
        WHERE ST_DWithin(t.geom, ST_Transform(ST_SetSRID(ST_MakePoint($1, $2), 4326), ST_SRID(t.geom)), 150)
        ORDER BY t.geom <-> ST_Transform(ST_SetSRID(ST_MakePoint($1, $2), 4326), ST_SRID(t.geom))
        LIMIT 1
    """, dados.longitude, dados.latitude)

    if not row:
        raise HTTPException(404, "Nenhuma via identificada num raio de 150 metros.")

    await conn.execute("""
        INSERT INTO estado_operacional_trechos (id_trecho, status, severidade, relato_origem, registrado_em)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (id_trecho) DO UPDATE
        SET status = EXCLUDED.status, severidade = EXCLUDED.severidade, relato_origem = EXCLUDED.relato_origem, registrado_em = $5
    """, row["id_trecho"], novo_status, dados.nivel, relato, agora)

    await conn.execute("""
        INSERT INTO alertas_operacionais 
        (id_evento, categoria, fonte, primeira_deteccao, ultima_atualizacao, expiracao_em, confianca, status_evento, o_que_nao_sabemos, trechos_afetados)
        VALUES ($1, 'OCORRENCIA_CONFIRMADA', $2, $3, $3, $4, 0.90, 'CONFIRMADO', $5, ARRAY[$6::integer])
    """, id_evento, dados.corporacao, agora, expiracao, "Extensao exata do impacto na via", row["id_trecho"])

    return {
        "sucesso": True,
        "id_evento": id_evento,
        "id_trecho": row["id_trecho"],
        "via": row["name"] or "Sem denominacao",
        "novo_status": novo_status,
        "severidade": dados.nivel,
        "confianca": 0.90,
        "expiracao_em": expiracao.isoformat()
    }

@router.get("/ativas")
async def listar_ocorrencias_ativas(conn: asyncpg.Connection = Depends(get_connection)):
    rows = await conn.fetch("""
        SELECT 
            a.id_evento, a.categoria, a.fonte, a.confianca, a.status_evento, a.o_que_nao_sabemos,
            a.primeira_deteccao, a.ultima_atualizacao, a.expiracao_em, a.trechos_afetados,
            EXTRACT(EPOCH FROM (now() - a.ultima_atualizacao))/60 AS idade_minutos
        FROM alertas_operacionais a
        WHERE a.expiracao_em > now() AND a.status_evento != 'DESCARTADO'
        ORDER BY a.ultima_atualizacao DESC
        LIMIT 50
    """)
    return [{
        "id_evento": r["id_evento"], "categoria": r["categoria"], "fonte": r["fonte"],
        "idade_minutos": int(r["idade_minutos"]), "confianca": float(r["confianca"]),
        "status_evento": r["status_evento"], "o_que_nao_sabemos": r["o_que_nao_sabemos"],
        "primeira_deteccao": r["primeira_deteccao"].isoformat(),
        "ultima_atualizacao": r["ultima_atualizacao"].isoformat(),
        "expiracao_em": r["expiracao_em"].isoformat(), "trechos_afetados": r["trechos_afetados"]
    } for r in rows]

@router.post("/resetar-todas", dependencies=[Depends(require_role(["ADMIN"]))])
async def resetar_todas_ocorrencias(conn: asyncpg.Connection = Depends(get_connection)):
    await conn.execute("UPDATE estado_operacional_trechos SET status = 'TRANSITAVEL', severidade = 'BAIXA', relato_origem = 'Reset', registrado_em = NOW() WHERE status != 'TRANSITAVEL'")
    await conn.execute("UPDATE alertas_operacionais SET status_evento = 'DESCARTADO', ultima_atualizacao = now() WHERE expiracao_em > now()")
    return {"sucesso": True}

@router.post("/processar-texto", dependencies=[Depends(exigir_api_key)])
async def processar_texto(dados: OcorrenciaTextoCreate, conn: asyncpg.Connection = Depends(get_connection)):
    extraido = extrair_dados_ocorrencia(dados.texto)
    if not extraido["via"]:
        raise HTTPException(422, "Nao identificou via.")
    if not extraido["status"]:
        raise HTTPException(422, "Nao identificou situacao.")

    termo_limpo = normalizar_texto(extraido["via"])
    ignorar = ("avenida", "rua", "alameda", "estrada", "rodovia", "av", "r")
    palavras = [w for w in termo_limpo.split() if w not in ignorar]
    termo_busca = " ".join(palavras) if palavras else termo_limpo
    if len(termo_busca) < 3:
        raise HTTPException(422, "Nome da via curto demais.")

    rows = await conn.fetch("""
        SELECT id_trecho, name
        FROM trechos_osm
        WHERE name IS NOT NULL
          AND (
              translate(lower(name), 'áàâãéêíóôõúç', 'aaaaeeiooouc') % $1
              OR word_similarity($1, translate(lower(name), 'áàâãéêíóôõúç', 'aaaaeeiooouc')) >= 0.35
          )
        ORDER BY GREATEST(
            similarity(translate(lower(name), 'áàâãéêíóôõúç', 'aaaaeeiooouc'), $1),
            word_similarity($1, translate(lower(name), 'áàâãéêíóôõúç', 'aaaaeeiooouc'))
        ) DESC
        LIMIT 50
    """, termo_busca)

    if not rows:
        raise HTTPException(404, "Nenhuma via encontrada.")

    id_evento = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)
    expiracao = agora + timedelta(hours=2)
    trechos = [r["id_trecho"] for r in rows]
    nomes_afetados = list({r["name"] for r in rows if r["name"]})

    for r in rows:
        await conn.execute("""
            INSERT INTO estado_operacional_trechos (id_trecho, status, severidade, relato_origem, registrado_em)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id_trecho) DO UPDATE SET status = EXCLUDED.status, severidade = EXCLUDED.severidade, relato_origem = EXCLUDED.relato_origem, registrado_em = $5
        """, r["id_trecho"], extraido["status"], extraido["severidade"], dados.texto, agora)

    await conn.execute("""
        INSERT INTO alertas_operacionais 
        (id_evento, categoria, fonte, primeira_deteccao, ultima_atualizacao, expiracao_em, confianca, status_evento, o_que_nao_sabemos, trechos_afetados)
        VALUES ($1, 'TRANSITO_OBSERVADO', $2, $3, $3, $4, 0.65, 'INCERTO', $5, $6::integer[])
    """, id_evento, dados.fonte, agora, expiracao, "Nivel exato de severidade fisica e validacao local", trechos)

    return {
        "sucesso": True,
        "id_evento": id_evento,
        "confianca": 0.65,
        "status_evento": "INCERTO",
        "vias_identificadas": nomes_afetados,
        "status_definido": extraido["status"],
        "severidade": extraido["severidade"]
    }