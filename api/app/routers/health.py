import time
import logging
import asyncpg
from fastapi import APIRouter, HTTPException, status
from app.config import settings
import app.database as db

router = APIRouter(prefix="/api/v1/health", tags=["health"])
logger = logging.getLogger(__name__)

TABELAS_OBRIGATORIAS = (
    "trechos_osm", "trechos_osm_vertices_pgr", "infraestrutura_viaria",
    "tombamentos_caminhao", "postos_combustivel", "precos_combustivel",
    "fontes_dados_externos", "fontes_meteorologicas",
    "estacoes_meteorologicas", "leituras_meteorologicas",
    "historico_avaliacoes_risco", "alertas_operacionais",
    "auditoria_qualidade_espacial", "feedback_alertas_operacionais",
    "bacias_hidrograficas",
    "painel_financeiro", "painel_admin_auditoria", "painel_recuperacoes",
    "painel_recuperacao_tentativas",
    "monitor_importacoes",
    "painel_onboarding",
)


async def verificar_dependencias(conn):
    faltantes = await conn.fetchval("""
        SELECT array_agg(nome ORDER BY nome)
        FROM unnest($1::text[]) AS nome
        WHERE to_regclass('public.' || nome) IS NULL
    """, list(TABELAS_OBRIGATORIAS))
    if faltantes:
        logger.warning("Readiness: tabelas ausentes: %s", ", ".join(faltantes))
        raise RuntimeError("Esquema operacional incompleto")
    await conn.fetchval("SELECT PostGIS_Version()")
    total_trechos = await conn.fetchval("SELECT COUNT(*) FROM trechos_osm")
    if not total_trechos:
        raise RuntimeError("Malha viaria vazia")
    return total_trechos

@router.get("/liveness", status_code=status.HTTP_200_OK)
async def check_liveness():
    return {
        "status": "UP",
        "timestamp": time.time(),
        "servico": "sprain_api"
    }

@router.get("/readiness", status_code=status.HTTP_200_OK)
async def check_readiness():
    inicio = time.perf_counter()
    try:
        if getattr(db, "db_pool", None) is not None:
            async with db.db_pool.acquire() as conn:
                total_trechos = await verificar_dependencias(conn)
        else:
            conn = await asyncpg.connect(settings.database_url, timeout=5.0)
            try:
                total_trechos = await verificar_dependencias(conn)
            finally:
                await conn.close()

        latencia_db_ms = round((time.perf_counter() - inicio) * 1000.0, 2)
        return {
            "status": "READY",
            "banco": "sprain_db",
            "postgis": "OPERACIONAL",
            "total_trechos_osm": total_trechos,
            "latencia_db_ms": latencia_db_ms
        }
    except Exception as exc:
        logger.warning("Readiness indisponivel: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dependencias da API indisponiveis."
        ) from None
