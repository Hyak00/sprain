"""Contratos da central e regressao de colisao de identificador entre empresas.

Executar somente em API/banco de testes, como o restante da suite.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import httpx
import pytest

from app.config import settings

BASE = 'http://127.0.0.1:8000/api/v1'


@pytest.mark.asyncio
@pytest.mark.parametrize('chave', ['key_admin_demo', 'key_operator_demo', 'key_viewer_demo'])
async def test_contratos_de_leitura_da_central(chave):
    async with httpx.AsyncClient(base_url=BASE, timeout=60, headers={'X-API-Key': chave}) as cliente:
        for endpoint, tipo in [('/logistica/operacoes', list), ('/logistica/relatorios/sumario-executivo', dict),
                               ('/dados-publicos/fontes', dict), ('/indicadores/qualidade', dict),
                               ('/health/liveness', dict), ('/health/readiness', dict), ('/alertas/precisao', dict)]:
            resposta = await cliente.get(endpoint)
            assert resposta.status_code == 200, endpoint
            assert isinstance(resposta.json(), tipo), endpoint


async def payload(conn, identificador):
    origem = await conn.fetchrow("""SELECT origem_nome,origem_lat,origem_lon,destino_nome,destino_lat,destino_lon
        FROM operacoes WHERE tenant_id='demo_corp' AND origem_lat IS NOT NULL AND destino_lat IS NOT NULL
        ORDER BY CASE WHEN id_operacao = 'OP-001' THEN 0 ELSE 1 END, id_operacao LIMIT 1""")
    assert origem is not None, 'Fixture de operacoes do CI ausente'
    agora = datetime.now(timezone.utc)
    return {**dict(origem), 'id_operacao': identificador, 'janela_inicio': agora.isoformat(),
            'janela_fim': (agora + timedelta(hours=4)).isoformat()}


async def limpar(conn, identificador):
    await conn.execute('DELETE FROM operacao_rotas_trechos WHERE id_operacao=$1', identificador)
    await conn.execute('DELETE FROM operacoes WHERE id_operacao=$1', identificador)


@pytest.mark.asyncio
async def test_colisao_nao_apaga_rota_da_outra_empresa():
    conn = await asyncpg.connect(settings.database_url)
    identificador = 'TEST_PORTAL_' + uuid.uuid4().hex[:12]
    try:
        dados = await payload(conn, identificador)
        async with httpx.AsyncClient(base_url=BASE, timeout=90) as cliente:
            criado = await cliente.post('/logistica/operacoes', json=dados, headers={'X-API-Key': 'key_admin_demo'})
            assert criado.status_code == 200, criado.text
            antes = await conn.fetch('SELECT seq,id_trecho FROM operacao_rotas_trechos WHERE id_operacao=$1 ORDER BY seq', identificador)
            assert antes
            colisao = await cliente.post('/logistica/operacoes', json=dados, headers={'X-API-Key': 'key_admin_express'})
            assert colisao.status_code == 403
            depois = await conn.fetch('SELECT seq,id_trecho FROM operacao_rotas_trechos WHERE id_operacao=$1 ORDER BY seq', identificador)
            assert antes == depois
            assert await conn.fetchval('SELECT tenant_id FROM operacoes WHERE id_operacao=$1', identificador) == 'demo_corp'
    finally:
        await limpar(conn, identificador)
        await conn.close()


@pytest.mark.asyncio
async def test_criacao_concorrente_nao_compartilha_identificador():
    conn = await asyncpg.connect(settings.database_url)
    identificador = 'TEST_PORTAL_RACE_' + uuid.uuid4().hex[:12]
    try:
        dados = await payload(conn, identificador)
        async with httpx.AsyncClient(base_url=BASE, timeout=90) as cliente:
            await conn.execute('SELECT pg_advisory_lock(hashtextextended($1, 0))', identificador)
            tarefas = [asyncio.create_task(cliente.post('/logistica/operacoes', json=dados, headers={'X-API-Key': chave}))
                       for chave in ['key_admin_demo', 'key_admin_express']]
            esperando = 0
            try:
                for _ in range(100):
                    esperando = await conn.fetchval("""SELECT count(*) FROM pg_locks WHERE locktype='advisory'
                        AND NOT granted AND database=(SELECT oid FROM pg_database WHERE datname=current_database())""")
                    if esperando >= 2:
                        break
                    await asyncio.sleep(0.05)
            finally:
                await conn.execute('SELECT pg_advisory_unlock(hashtextextended($1, 0))', identificador)
            respostas = await asyncio.gather(*tarefas)
            assert esperando >= 2, 'As duas criacoes devem passar pela verificacao inicial antes da insercao'
            assert sorted(r.status_code for r in respostas) == [200, 409]
            titular = await conn.fetchval('SELECT tenant_id FROM operacoes WHERE id_operacao=$1', identificador)
            vencedor = 'demo_corp' if respostas[0].status_code == 200 else 'log_express'
            assert titular == vencedor
            assert await conn.fetchval('SELECT count(*) FROM operacao_rotas_trechos WHERE id_operacao=$1', identificador) > 0
    finally:
        await limpar(conn, identificador)
        await conn.close()
