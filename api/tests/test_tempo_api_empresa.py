"""Tempo de resposta agregado por empresa e pelo mes local."""

from datetime import datetime, timezone
from uuid import uuid4

import asyncpg
import pytest

from app.config import settings
from app.services.medicao_processamento import registrar_atendimento
from app.services.planos_empresa import SCHEMA, SCHEMA_CHAMADAS, SCHEMA_TEMPO, resumo


@pytest.mark.asyncio
async def test_agregado_mensal_nao_mistura_empresas_nem_fuso():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    tenant = "TEST_TIMING_" + uuid4().hex[:12]
    outro = "TEST_OTHER_" + uuid4().hex[:12]
    setembro = datetime(2026, 10, 1, 2, 59, tzinfo=timezone.utc)
    outubro = datetime(2026, 10, 1, 3, 1, tzinfo=timezone.utc)
    try:
        await conn.execute(SCHEMA)
        await conn.execute(SCHEMA_CHAMADAS)
        await conn.execute(SCHEMA_TEMPO)
        await registrar_atendimento(conn, tenant, 200, 12.5, setembro)
        await registrar_atendimento(conn, tenant, 500, 7.5, outubro)
        await registrar_atendimento(conn, outro, 200, 99.0, outubro)
        setembro_uso = (await resumo(conn, tenant, setembro))["uso"]
        outubro_uso = (await resumo(conn, tenant, outubro))["uso"]
        outro_uso = (await resumo(conn, outro, outubro))["uso"]
        assert (setembro_uso["requisicoes_mes"], setembro_uso["erros_mes"], setembro_uso["tempo_resposta_total_ms"]) == (1, 0, 12.5)
        assert (outubro_uso["requisicoes_mes"], outubro_uso["erros_mes"], outubro_uso["tempo_resposta_total_ms"]) == (1, 1, 7.5)
        assert (outro_uso["requisicoes_mes"], outro_uso["tempo_resposta_total_ms"]) == (1, 99.0)
    finally:
        await tx.rollback()
        await conn.close()
