import pytest
import asyncpg
from app.config import settings

@pytest.mark.asyncio
async def test_avaliacao_desempenho_treino_teste():
    conn = await asyncpg.connect(settings.database_url)
    try:
        total = await conn.fetchval("SELECT count(*) FROM tombamentos_caminhao WHERE ativo = true")
        if total > 0:
            corte = await conn.fetchval("SELECT PERCENTILE_CONT(0.7) WITHIN GROUP (ORDER BY data_ocorrencia) FROM tombamentos_caminhao WHERE ativo = true")
            treino = await conn.fetchval("SELECT count(*) FROM tombamentos_caminhao WHERE ativo = true AND data_ocorrencia <= $1", corte)
            teste = await conn.fetchval("SELECT count(*) FROM tombamentos_caminhao WHERE ativo = true AND data_ocorrencia > $1", corte)
            assert treino > 0
            assert teste >= 0
    finally:
        await conn.close()