"""Regressoes para instalacao parcial e readiness do banco."""

from uuid import uuid4

import asyncpg
import pytest
from fastapi import HTTPException

from app.config import settings
from app.routers import health
from app.services.esquema_operacional import aplicar


@pytest.mark.asyncio
async def test_migracoes_operacionais_criam_tabelas_e_podem_repetir():
    conn = await asyncpg.connect(settings.database_url)
    transacao = conn.transaction()
    await transacao.start()
    schema = "teste_operacional_" + uuid4().hex
    try:
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        await conn.execute("SELECT set_config('search_path', $1, true)", schema + ",public")
        await aplicar(conn)
        await aplicar(conn)
        for tabela in (
            "fontes_meteorologicas", "alertas_operacionais",
            "auditoria_qualidade_espacial", "feedback_alertas_operacionais",
            "bacias_hidrograficas",
        ):
            assert await conn.fetchval("SELECT to_regclass($1)", f"{schema}.{tabela}")
    finally:
        await transacao.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_readiness_recusa_esquema_parcial_sem_expor_detalhes(monkeypatch):
    class ConexaoParcial:
        async def fetchval(self, query, *args):
            assert "to_regclass" in query
            return ["alertas_operacionais"]

    class PoolParcial:
        def acquire(self):
            return self

        async def __aenter__(self):
            return ConexaoParcial()

        async def __aexit__(self, *_):
            return False

    monkeypatch.setattr(health.db, "db_pool", PoolParcial())
    with pytest.raises(HTTPException) as erro:
        await health.check_readiness()
    assert erro.value.status_code == 503
    assert "alertas_operacionais" not in erro.value.detail
