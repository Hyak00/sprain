from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock
import sys
import asyncpg
import httpx
import pytest
from fastapi import Response
from app.config import settings
from app.routers.operacional_interno import idade,importacoes,fontes
from app.routers.indicadores import obter_indicadores_qualidade

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.auditoria_importacoes import executar_auditado


def test_idade_nunca_converte_ausencia_futuro_ou_fuso_desconhecido_em_zero():
    agora=datetime.now(timezone.utc)
    assert idade(None,agora) is None and idade(agora+timedelta(minutes=1),agora) is None
    assert idade(agora.replace(tzinfo=None),agora) is None
    assert idade(agora,agora)==0


@pytest.mark.asyncio
async def test_painel_interno_exige_admin_e_valida_filtros():
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8000',timeout=30) as c:
        for url in ['/api/v1/operacional/fontes','/api/v1/operacional/importacoes']:
            for key in ['key_viewer_demo','key_operator_demo']:
                assert (await c.get(url,headers={'X-API-Key':key})).status_code==403
            assert (await c.get(url)).status_code==401
            r=await c.get(url,headers={'X-API-Key':'key_admin_demo'})
            assert r.status_code==200 and r.headers['cache-control']=='no-store'
        assert (await c.get('/api/v1/operacional/importacoes?status=INVALIDO',headers={'X-API-Key':'key_admin_demo'})).status_code==422


@pytest.mark.asyncio
async def test_importacoes_paginadas_isolam_empresas_e_preservam_logs_publicos():
    conn=await asyncpg.connect(settings.database_url);tx=conn.transaction();await tx.start()
    empresa='TEST_MON_'+uuid4().hex
    try:
        for tenant in [empresa,empresa,'outra_empresa',None]:
            await conn.execute("INSERT INTO monitor_importacoes(id,fonte,tenant_id,status) VALUES($1,'TEST_FONTE',$2,'FALHA')",uuid4(),tenant)
        d=await importacoes(Response(),status='FALHA',offset=0,limite=1,tenant_id=empresa,conn=conn)
        assert len(d['items'])==1 and d['proximo_offset']==1
        todos=await importacoes(Response(),status='FALHA',offset=0,limite=100,tenant_id=empresa,conn=conn)
        filtrados=[i for i in todos['items'] if i['fonte']=='TEST_FONTE']
        assert len(filtrados)==3
        assert all('tenant_id' not in i for i in filtrados)
    finally:await tx.rollback();await conn.close()


@pytest.mark.asyncio
async def test_fontes_separam_cobertura_coleta_e_referencia_sem_fingir_atualidade():
    agora=datetime.now(timezone.utc);conn=AsyncMock()
    conn.fetch.side_effect=[[
        {'nome':'Sem sucesso','ultimo_sucesso_em':None,'registros_importados':0},
        {'nome':'Antiga','ultimo_sucesso_em':agora-timedelta(days=4),'registros_importados':2}],
        [{'id_fonte':'MET','nome':'Estação','tipo':'OBSERVACAO','frequencia_minutos':30,'estacoes':2,'com_leitura':1,
          'referencia_mais_antiga':agora-timedelta(hours=2),'ultima_coleta':agora,'validade_mais_curta':agora-timedelta(hours=1)}],
        [{'fonte':'DADOS_PUBLICOS/anp','status':'FALHA','iniciado_em':agora,
          'encerrado_em':agora,'motivo_codigo':'EXECUCAO_INTERROMPIDA'}]]
    conn.fetchrow.return_value={'total':6,'com_leitura':0,'mais_antiga':None}
    d=await fontes(Response(),conn);status={f['id']:f['status'] for f in d['fontes']}
    assert status=={'Sem sucesso':'SEM_DATA_VALIDA','Antiga':'ATRASADA','MET':'COBERTURA_INCOMPLETA','OPEN_METEO_CORREDOR':'COBERTURA_INCOMPLETA'}
    assert d['fontes'][2]['idade_minutos']>=120 and d['integracoes'][0]['status']=='DESATIVADA'
    assert d['tentativas_dados_publicos'][0]['status']=='FALHA'
    assert 'tenant_id IS NULL' in conn.fetch.call_args_list[2].args[0]


@pytest.mark.asyncio
async def test_falha_inicial_aparece_mesmo_sem_fonte_importada():
    agora=datetime.now(timezone.utc);conn=AsyncMock()
    conn.fetch.side_effect=[[],[],[{'fonte':'DADOS_PUBLICOS/anp','status':'FALHA',
        'iniciado_em':agora,'encerrado_em':agora,'motivo_codigo':'EXECUCAO_INTERROMPIDA'}]]
    conn.fetchrow.return_value={'total':0,'com_leitura':0,'mais_antiga':None}
    d=await fontes(Response(),conn)
    assert not any(f['tipo']=='DADOS_PUBLICOS' for f in d['fontes'])
    assert d['tentativas_dados_publicos'][0]['status']=='FALHA'


@pytest.mark.asyncio
async def test_indicador_legado_recusa_data_nula_e_futura():
    conn=AsyncMock();conn.fetchval.return_value=0
    conn.fetch.return_value=[{'nome':'X','registros_importados':0,'ultimo_sucesso_em':None,'horas_desde_ultima_atualizacao':None},
        {'nome':'Futuro','registros_importados':1,'ultimo_sucesso_em':datetime.now(timezone.utc)+timedelta(days=1),'horas_desde_ultima_atualizacao':-24}]
    d=await obter_indicadores_qualidade(conn)
    assert d['percentual_fontes_atualizadas_prazo']==0
    assert all(f['status_prazo']=='SEM_DATA_VALIDA' and f['horas_desde_ultima_atualizacao'] is None for f in d['detalhamento_fontes'])


def test_auditoria_persiste_sucesso_parcial_falha_e_nao_grava_segredos():
    import psycopg2
    fonte='TEST_AUDITORIA_'+uuid4().hex
    conectar=lambda:psycopg2.connect(settings.database_url)
    try:
        executar_auditado(lambda:{'registros':3,'falhas':0},conectar,fonte)
        executar_auditado(lambda:{'registros':2,'falhas':1},conectar,fonte)
        def falhar():raise ValueError('segredo-senha-nao-publicar')
        with pytest.raises(ValueError):executar_auditado(falhar,conectar,fonte)
        conn=conectar()
        try:
            with conn.cursor() as c:
                c.execute('SELECT status,motivo_codigo,encerrado_em FROM monitor_importacoes WHERE fonte=%s ORDER BY iniciado_em',(fonte,))
                rows=c.fetchall()
                assert [r[0] for r in rows]==['CONCLUIDO','PARCIAL','FALHA']
                assert all(r[2] for r in rows) and 'segredo' not in str(rows)
        finally:conn.close()
    finally:
        conn=conectar()
        try:
            with conn.cursor() as c:c.execute('DELETE FROM monitor_importacoes WHERE fonte=%s',(fonte,))
            conn.commit()
        finally:conn.close()


@pytest.mark.asyncio
async def test_lote_invalido_preserva_contrato_e_registra_falha_da_empresa():
    from app.routers.logistica import importar_operacoes_lote
    conn=await asyncpg.connect(settings.database_url);tx=conn.transaction();await tx.start()
    empresa='TEST_LOTE_'+uuid4().hex
    try:
        r=await importar_operacoes_lote([{}],empresa,conn)
        assert r['falhas']==1 and r['sucessos']==0 and len(r['detalhe_falhas'])==1
        registro=await conn.fetchrow('SELECT status,falhas,registros FROM monitor_importacoes WHERE tenant_id=$1',empresa)
        assert dict(registro)=={'status':'FALHA','falhas':1,'registros':0}
    finally:await tx.rollback();await conn.close()


def test_cli_validacao_nao_conecta_e_aplicacao_passsa_pela_auditoria(monkeypatch):
    from scripts import sincronizar_dados_publicos as script,auditoria_importacoes as audit
    from unittest.mock import Mock
    executar=Mock(return_value={'registros':1,'falhas':0});conectar=Mock(side_effect=AssertionError('Não deveria conectar no modo seco'))
    monkeypatch.setattr(script,'_executar',executar);monkeypatch.setattr(script,'conectar',conectar)
    monkeypatch.setattr(sys,'argv',['sincronizar_dados_publicos.py','anp'])
    assert script.main()['registros']==1;conectar.assert_not_called()
    auditado=Mock(return_value={'registros':2});monkeypatch.setattr(audit,'executar_auditado',auditado)
    monkeypatch.setattr(sys,'argv',['sincronizar_dados_publicos.py','anp','--aplicar'])
    assert script.main()['registros']==2
    assert auditado.call_args.args==(executar,conectar,'DADOS_PUBLICOS/anp')
