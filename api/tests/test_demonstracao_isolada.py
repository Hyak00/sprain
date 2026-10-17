import json
from unittest.mock import AsyncMock

import asyncpg
import pytest
from fastapi import HTTPException
from app.config import settings
from app.services import demonstracao as demo
from app.services.routing_engine import RoutingEngine


@pytest.mark.asyncio
async def test_guardas_demo_rejeitam_producao_flag_ausente_banco_comum_e_conexao_divergente(monkeypatch):
    conn=AsyncMock();conn.fetchval.return_value='sprain_demo'
    monkeypatch.setenv('ENVIRONMENT','production');monkeypatch.setenv('SPRAIN_DEMO_ENABLED','1')
    with pytest.raises(HTTPException):await demo.exigir_ambiente(conn)
    with pytest.raises(RuntimeError):demo.validar_configuracao()
    conn.fetchval.assert_not_awaited()
    monkeypatch.setenv('ENVIRONMENT','testing');monkeypatch.delenv('SPRAIN_DEMO_ENABLED')
    with pytest.raises(HTTPException):await demo.exigir_ambiente(conn)
    monkeypatch.setenv('SPRAIN_DEMO_ENABLED','1');monkeypatch.setattr(settings,'DB_NAME','banco_cliente')
    with pytest.raises(HTTPException):await demo.exigir_ambiente(conn)
    with pytest.raises(RuntimeError):demo.validar_configuracao()
    monkeypatch.setattr(settings,'DB_NAME','sprain_demo')
    conn.fetchval.return_value='banco_cliente'
    with pytest.raises(HTTPException):await demo.exigir_ambiente(conn)
    conn.fetchval.return_value='sprain_demo'
    await demo.exigir_ambiente(conn)


@pytest.mark.asyncio
async def test_exercicio_real_no_motor_e_idempotente_sem_alterar_alertas(monkeypatch):
    # Único teste que passa pela guarda: transação no banco exclusivo da suíte.
    # As próprias guardas contra conexão incorreta são testadas acima sem esse mock.
    monkeypatch.setattr(demo,'exigir_ambiente',AsyncMock())
    conn=await asyncpg.connect(settings.database_url);tx=conn.transaction();await tx.start()
    RoutingEngine._cache.clear()
    try:
        alertas=await conn.fetchval("SELECT coalesce(jsonb_agg(to_jsonb(a) ORDER BY id_evento),'[]'::jsonb)::text FROM alertas_operacionais a")
        a=await demo.preparar(conn,'demo_corp');b=await demo.preparar(conn,'demo_corp')
        assert a['id_operacao']==b['id_operacao'] and a['importacao_id']==b['importacao_id']
        assert await conn.fetchval('SELECT count(*) FROM operacoes WHERE id_operacao=$1',demo.OPERACAO)==1
        assert await conn.fetchval('SELECT count(*) FROM veiculos WHERE id_veiculo=$1',demo.VEICULO)==1
        livre=await demo.reproduzir(conn,'demo_corp','SEM_BLOQUEIO')
        bloqueio=await demo.reproduzir(conn,'demo_corp','BLOQUEIO')
        liberacao=await demo.reproduzir(conn,'demo_corp','LIBERACAO')
        assert livre['rota_original'] and bloqueio['rota_alternativa']
        assert bloqueio['comparativo_rotas']['rota_alternativa_km']>livre['comparativo_rotas']['rota_original_km']
        assert liberacao['comparativo_rotas']['rota_alternativa_km']==livre['comparativo_rotas']['rota_original_km']
        assert set(bloqueio['bloqueios_somente_nesta_consulta']).isdisjoint(bloqueio['rota_alternativa']['ids_trechos'])
        assert alertas==await conn.fetchval("SELECT coalesce(jsonb_agg(to_jsonb(a) ORDER BY id_evento),'[]'::jsonb)::text FROM alertas_operacionais a")
        with pytest.raises(HTTPException) as erro:await demo.preparar(conn,'log_express')
        assert erro.value.status_code==403
        await conn.execute('UPDATE malha_importacoes SET ativo=false WHERE id=$1',a['importacao_id'])
        with pytest.raises(HTTPException):await demo.preparar(conn,'demo_corp')
        assert not await conn.fetchval('SELECT ativo FROM malha_importacoes WHERE id=$1',a['importacao_id'])
    finally:
        await tx.rollback();await conn.close();RoutingEngine._cache.clear()


@pytest.mark.asyncio
async def test_sem_rota_nao_cria_distancia_ou_financeiro_substituto(monkeypatch):
    monkeypatch.setattr(demo,'exigir_ambiente',AsyncMock())
    conn=AsyncMock()
    conn.fetchrow.return_value={'dimensoes':'{}','custos_operacionais':'{}','origem_lon':-47.84,'origem_lat':-22.25,'destino_lon':-47.82,'destino_lat':-22.25}
    conn.fetch.return_value=[{'id_trecho':n,'name':'DEMONSTRAÇÃO - ligação sintética '+nome} for n,nome in enumerate(['A-B','B-C','A-D','D-C'])]
    monkeypatch.setattr(RoutingEngine,'compute_route',AsyncMock(return_value=None))
    r=await demo.reproduzir(conn,'demo_corp','BLOQUEIO')
    assert all(v is None for v in r['comparativo_rotas'].values()) and r['financeiro'] is None


def test_manifesto_separa_fonte_historica_de_parametros_sinteticos():
    r=demo.referencia();assert r['id']=='ARTESP_OC17928'
    assert r['fonte_url'].startswith('https://ccm.artesp.sp.gov.br/')
    assert 'PESQUISADA' in r['origem_referencia']
    assert r['marcos'] and r['incognitas']
    assert all(s['nome'].startswith('DEMONSTRAÇÃO') for s in demo.malha()['segmentos'])
