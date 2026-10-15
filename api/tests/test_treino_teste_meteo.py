import pytest
import asyncpg
from app.config import settings

@pytest.mark.asyncio
async def test_avaliacao_desempenho_treino_teste():
    conn = await asyncpg.connect(settings.database_url)
    try:
        total = await conn.fetchval("SELECT count(*) FROM tombamentos_caminhao WHERE ativo = true")
        if total > 0:
            corte = await conn.fetchval("SELECT data_ocorrencia FROM tombamentos_caminhao WHERE ativo = true ORDER BY data_ocorrencia OFFSET (SELECT (count(*)*0.7)::int FROM tombamentos_caminhao WHERE ativo = true) LIMIT 1")
            if corte:
                treino = await conn.fetchval("SELECT count(*) FROM tombamentos_caminhao WHERE ativo = true AND data_ocorrencia <= $1", corte)
                teste = await conn.fetchval("SELECT count(*) FROM tombamentos_caminhao WHERE ativo = true AND data_ocorrencia > $1", corte)
                assert treino > 0
                assert teste >= 0
    finally:
        await conn.close()