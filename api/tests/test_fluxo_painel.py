"""Fluxos persistentes da secao 3.1; executar somente no banco/API de testes."""
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from app.config import settings
from app.services.painel import SCHEMA

BASE='http://127.0.0.1:8000/api/v1'
OP={'X-API-Key':'key_operator_demo'}
VIEW={'X-API-Key':'key_viewer_demo'}
OUTRA={'X-API-Key':'key_admin_express'}


@pytest_asyncio.fixture
async def ambiente():
    conn=await asyncpg.connect(settings.database_url)
    cliente=httpx.AsyncClient(base_url=BASE,headers=OP,timeout=90)
    origem=await conn.fetchrow("""SELECT origem_nome,origem_lat,origem_lon,destino_nome,destino_lat,destino_lon
        FROM operacoes WHERE tenant_id='demo_corp' ORDER BY id_operacao LIMIT 1""")
    assert origem
    ids={'operacoes':[],'corredores':[],'relatos':[],'eventos':[]}
    yield conn,cliente,dict(origem),ids
    for op in ids['operacoes']:
        cenarios=await conn.fetch('SELECT id_cenario FROM recomendacoes_operacao WHERE id_operacao=$1',op)
        await conn.execute('DELETE FROM painel_despachos WHERE id_operacao=$1',op)
        await conn.execute('DELETE FROM decisoes_gestor_operacao WHERE id_operacao=$1',op)
        await conn.execute('DELETE FROM painel_consultas WHERE id_operacao=$1',op)
        await conn.execute('DELETE FROM recomendacoes_operacao WHERE id_operacao=$1',op)
        await conn.execute('DELETE FROM operacao_rotas_trechos WHERE id_operacao=$1',op)
        await conn.execute('DELETE FROM operacoes WHERE id_operacao=$1',op)
        for c in cenarios:
            if c['id_cenario'] and c['id_cenario'].startswith('SIM_PAINEL_'):
                await conn.execute('DELETE FROM cenarios_clima WHERE id_cenario=$1',c['id_cenario'])
    for c in ids['corredores']:
        await conn.execute('DELETE FROM painel_recorrencias WHERE corredor_id=$1',c)
        await conn.execute('DELETE FROM painel_corredores WHERE id=$1',c)
    for r in ids['relatos']:
        await conn.execute('DELETE FROM painel_relatos WHERE id=$1',r)
    for e in ids['eventos']:
        await conn.execute('DELETE FROM alertas_operacionais WHERE id_evento=$1',e)
    await cliente.aclose();await conn.close()


async def nova_operacao(a):
    _,cli,origem,ids=a
    id_op='TEST_MVP_'+uuid4().hex[:12];ids['operacoes'].append(id_op)
    agora=datetime.now(timezone.utc)
    r=await cli.post('/logistica/operacoes',json={**origem,'id_operacao':id_op,'janela_inicio':agora.isoformat(),'janela_fim':(agora+timedelta(hours=4)).isoformat()})
    assert r.status_code==200,r.text
    return id_op


@pytest.mark.asyncio
async def test_migracao_aditiva_repetivel(ambiente):
    conn,*_=ambiente
    await conn.execute(SCHEMA);await conn.execute(SCHEMA)
    assert await conn.fetchval("SELECT count(*) FROM information_schema.columns WHERE table_name='decisoes_gestor_operacao' AND column_name='consulta_id'")==1


@pytest.mark.asyncio
@pytest.mark.parametrize('cabecalho',[OP,VIEW,OUTRA])
async def test_leituras_painel_por_perfil(ambiente,cabecalho):
    _,cli,_,_=ambiente
    for path in ['/painel/corredores','/painel/consultas','/painel/eventos']:
        r=await cli.get(path,headers=cabecalho);assert r.status_code==200,r.text
    assert (await cli.get('/painel/consultas?limite=101')).status_code==422


@pytest.mark.asyncio
async def test_consulta_persistida_viewer_isolada_e_sem_credencial(ambiente):
    conn,cli,_,_=ambiente;op=await nova_operacao(ambiente)
    r=await cli.post('/painel/consultas',headers=VIEW,json={'id_operacao':op});assert r.status_code==200,r.text
    d=r.json();ident=d['consulta']['id'];assert d['explicacao']['contexto_consulta']['perfil']=='VIEWER'
    assert (await cli.get('/painel/consultas/'+ident,headers=OUTRA)).status_code==404
    historico=(await cli.get('/painel/consultas?id_operacao='+op,headers=VIEW)).json()
    assert historico['items'][0]['id']==ident
    foto=await conn.fetchval('SELECT snapshot::text FROM painel_consultas WHERE id=$1',__import__('uuid').UUID(ident))
    assert 'key_viewer_demo' not in foto and 'api_key' not in foto
    assert (await cli.post('/painel/corredores',headers=VIEW,json={})).status_code==403
    assert (await cli.post('/painel/relatos',headers=VIEW,json={})).status_code==403
    assert (await cli.put('/painel/operacoes/'+op+'/premissas',headers=VIEW,json={})).status_code==403


@pytest.mark.asyncio
async def test_corredor_recorrencia_edicao_despacho_idempotente(ambiente):
    from uuid import UUID
    conn,cli,origem,ids=ambiente
    payload={**origem,'nome':'Corredor de teste'}
    r=await cli.post('/painel/corredores',json=payload);assert r.status_code==200,r.text
    c=r.json();ids['corredores'].append(UUID(c['id']))
    assert (await cli.put('/painel/corredores/'+c['id'],headers=OUTRA,json={**payload,'versao':1})).status_code==404
    r=await cli.put('/painel/corredores/'+c['id'],json={**payload,'nome':'Corredor editado','versao':1});assert r.status_code==200,r.text
    assert (await cli.put('/painel/corredores/'+c['id'],json={**payload,'versao':1})).status_code==409
    rec={'nome':'Agenda de teste','dias_semana':list(range(7)),'horario_local':'23:00','janela_minutos':240}
    invalido=await cli.post('/painel/corredores/'+c['id']+'/recorrencias',json={**rec,'dias_semana':[1,1]});assert invalido.status_code==422
    r=await cli.post('/painel/corredores/'+c['id']+'/recorrencias',json=rec);assert r.status_code==200,r.text
    agenda=r.json()
    novo=await cli.put('/painel/recorrencias/'+agenda['id'],json={**rec,'nome':'Agenda editada','versao':1});assert novo.status_code==200
    assert (await cli.put('/painel/recorrencias/'+agenda['id'],json={**rec,'versao':1})).status_code==409
    data=(datetime.now(timezone.utc)+timedelta(days=2)).date().isoformat();chave=str(uuid4());path='/painel/recorrencias/'+agenda['id']+'/despachar'
    r=await cli.post(path,json={'data_local':data,'chave_idempotencia':chave});assert r.status_code==200,r.text
    op=r.json()['id_operacao'];ids['operacoes'].append(op)
    for k in [chave,str(uuid4())]:
        rep=await cli.post(path,json={'data_local':data,'chave_idempotencia':k});assert rep.status_code==200,rep.text
        assert rep.json()=={'id_operacao':op,'reutilizado':True}
    assert await conn.fetchval('SELECT count(*) FROM painel_despachos WHERE id_operacao=$1',op)==1
    assert (await cli.post(path,headers=OUTRA,json={'data_local':data,'chave_idempotencia':str(uuid4())})).status_code==404


@pytest.mark.asyncio
async def test_premissas_recalculo_conflito_snapshot_e_decisao(ambiente):
    conn,cli,_,_=ambiente;op=await nova_operacao(ambiente)
    c=(await cli.post('/painel/consultas',json={'id_operacao':op})).json();selo=c['explicacao']['contexto_consulta']['selo_premissas']
    body={'selo_esperado':selo,'precipitacao_mm':0,'custos_operacionais':{'custo_por_km':9.5}}
    r=await cli.put('/painel/operacoes/'+op+'/premissas',json=body);assert r.status_code==200,r.text
    assert (await cli.put('/painel/operacoes/'+op+'/premissas',json=body)).status_code==409
    assert (await cli.post('/logistica/operacoes/'+op+'/decisao',json={'decisao':'AGUARDAR_MELHORA','consulta_id':c['consulta']['id']})).status_code==409
    nova=(await cli.post('/painel/consultas',json={'id_operacao':op})).json()
    assert nova['explicacao']['contexto_consulta']['premissas_editaveis']['custo_por_km']==9.5
    assert nova['explicacao']['contexto_consulta']['precipitacao_mm']==0
    assert nova['explicacao']['infraestrutura']['financeiro']['premissas']['custo_por_km']==9.5
    r=await cli.post('/logistica/operacoes/'+op+'/decisao',json={'decisao':'AGUARDAR_MELHORA','motivo_gestor':'Teste de fotografia','consulta_id':nova['consulta']['id']});assert r.status_code==200,r.text
    hist=(await cli.get('/logistica/operacoes/'+op+'/decisoes')).json();assert hist[0]['consulta_id']==nova['consulta']['id']
    await conn.execute("UPDATE operacoes SET custos_operacionais='{}'::jsonb WHERE id_operacao=$1",op)
    foto=(await cli.get('/painel/consultas/'+nova['consulta']['id'])).json()
    assert foto['snapshot']['contexto_consulta']['premissas_editaveis']['custo_por_km']==9.5


@pytest.mark.asyncio
async def test_relato_privado_mapa_sem_confirmacao_ou_bloqueio(ambiente):
    from uuid import UUID
    conn,cli,origem,ids=ambiente
    antes=await conn.fetchval('SELECT count(*) FROM alertas_operacionais')
    r=await cli.post('/painel/relatos',json={'categoria':'ALAGAMENTO','descricao':'Teste: agua relatada, nao confirmada','ocorrido_em':datetime.now(timezone.utc).isoformat(),'latitude':origem['origem_lat'],'longitude':origem['origem_lon']});assert r.status_code==200,r.text
    id_relato=r.json()['id'];ids['relatos'].append(UUID(id_relato));assert r.json()['status']=='PENDENTE_VALIDACAO'
    eventos=(await cli.get('/painel/eventos')).json();e=next(x for x in eventos['items'] if x['id_evento']==id_relato)
    assert e['confianca'] is None and e['natureza']=='RELATO_NAO_VALIDADO'
    assert any(x['properties']['id_evento']==id_relato for x in eventos['mapa']['features'])
    assert not any(x['id_evento']==id_relato for x in (await cli.get('/painel/eventos',headers=OUTRA)).json()['items'])
    assert await conn.fetchval('SELECT count(*) FROM alertas_operacionais')==antes


@pytest.mark.asyncio
async def test_evento_publico_geometria_fonte_natureza(ambiente):
    conn,cli,_,ids=ambiente;trecho=await conn.fetchval('SELECT id_trecho FROM trechos_osm WHERE tenant_malha IS NULL LIMIT 1');assert trecho is not None
    identificador='TEST_PREVISAO_'+uuid4().hex;ids['eventos'].append(identificador)
    await conn.execute("""INSERT INTO alertas_operacionais(id_evento,categoria,fonte,primeira_deteccao,ultima_atualizacao,expiracao_em,confianca,status_evento,trechos_afetados)
        VALUES($1,'PREVISAO','Fonte de teste',now(),now(),now()+interval '1 hour',0.6,'INCERTO',ARRAY[$2::integer])""",identificador,trecho)
    d=(await cli.get('/painel/eventos')).json();e=next(x for x in d['items'] if x['id_evento']==identificador)
    assert e['natureza']=='PREVISAO' and e['fonte']=='Fonte de teste'
    assert e['consequencia_possivel'] and any(f['properties']['id_evento']==identificador for f in d['mapa']['features'])
    geometria=next(f for f in d['mapa']['features'] if f['properties']['id_evento']==identificador)
    assert geometria['properties']['expiracao']==e['expiracao_em']


@pytest.mark.asyncio
async def test_relato_idempotente_nao_duplica_e_recusa_conflito(ambiente):
    conn,cli,origem,ids=ambiente
    chave=uuid4()
    payload={'categoria':'OUTRO','descricao':'Relato de teste idempotente',
        'ocorrido_em':datetime.now(timezone.utc).isoformat(),'latitude':origem['origem_lat'],
        'longitude':origem['origem_lon'],'chave_idempotencia':str(chave)}
    primeiro=await cli.post('/painel/relatos',json=payload);assert primeiro.status_code==200,primeiro.text
    identificador=__import__('uuid').UUID(primeiro.json()['id']);ids['relatos'].append(identificador)
    repetido=await cli.post('/painel/relatos',json=payload);assert repetido.status_code==200,repetido.text
    assert repetido.json()['id']==primeiro.json()['id'] and repetido.json()['reutilizado'] is True
    assert await conn.fetchval('SELECT count(*) FROM painel_relatos WHERE id=$1',identificador)==1
    assert (await cli.post('/painel/relatos',json={**payload,'descricao':'Alteracao conflitante'})).status_code==409
    outro=await cli.post('/painel/relatos',headers=OUTRA,json=payload);assert outro.status_code==200,outro.text
    ids['relatos'].append(__import__('uuid').UUID(outro.json()['id']))
    assert outro.json()['id']!=primeiro.json()['id']


@pytest.mark.asyncio
async def test_sem_recomendacao_nao_inventa_alternativa_confianca_ou_custos(ambiente):
    _, cli, _, _ = ambiente
    op = await nova_operacao(ambiente)
    r = await cli.post('/painel/consultas', json={'id_operacao':op})
    assert r.status_code == 200, r.text
    d = r.json()['explicacao']
    assert d['contexto_consulta']['id_recomendacao'] is None
    assert d['confianca'] is None and d['acao_recomendada'] == 'SEM_RECOMENDACAO'
    assert d['metricas']['distancia_alternativa_km'] is None
    assert d['metricas']['custo_desvio_brl'] is None


@pytest.mark.asyncio
async def test_rejeita_texto_vazio_apos_remover_espacos(ambiente):
    _, cli, origem, _ = ambiente
    r = await cli.post('/painel/corredores', json={**origem,'nome':'   '})
    assert r.status_code == 422
    r = await cli.post('/painel/relatos', json={'categoria':'OUTRO','descricao':'     ',
        'ocorrido_em':datetime.now(timezone.utc).isoformat(),'latitude':-23,'longitude':-46})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_alertas_ativos_nao_reexibem_recomendacao_antiga(ambiente):
    conn, cli, _, _ = ambiente
    op = await nova_operacao(ambiente)
    for nivel in ('CRITICO', 'NORMAL'):
        await conn.execute('''INSERT INTO recomendacoes_operacao(id_operacao,tenant_id,nivel_risco,tipo_acao,motivo)
            VALUES($1,'demo_corp',$2,'MANTER_ROTA_ORIGINAL','Teste de atualidade')''', op,nivel)
    d = (await cli.get('/logistica/alertas/ativos',headers=VIEW)).json()
    assert not any(r['id_operacao']==op for r in d)


@pytest.mark.asyncio
async def test_contratos_http_usados_no_painel_existem_no_openapi(ambiente):
    _, cli, _, _ = ambiente
    spec = (await cli.get('http://127.0.0.1:8000/openapi.json')).json()['paths']
    contratos = {
        '/api/v1/acesso/login':['post'],'/api/v1/acesso/logout':['post'],'/api/v1/acesso/configuracao':['get'],
        '/api/v1/logistica/auth/login':['post'], '/api/v1/logistica/veiculos':['get','post'],
        '/api/v1/logistica/operacoes':['get','post'], '/api/v1/logistica/operacoes/importar-lote':['post'],
        '/api/v1/logistica/vias/buscar':['get'], '/api/v1/logistica/simular-impacto':['post'],
        '/api/v1/logistica/alertas/ativos':['get'], '/api/v1/logistica/exportar-contingencia/csv':['get'],
        '/api/v1/logistica/operacoes/{id_operacao}/decisao':['post'],
        '/api/v1/logistica/operacoes/{id_operacao}/decisoes':['get'],
        '/api/v1/logistica/relatorios/sumario-executivo':['get'],
        '/api/v1/logistica/observabilidade/metricas':['get'], '/api/v1/rotas/intermunicipal':['get'],
        '/api/v1/infraestrutura/rota-caminhao':['post'], '/api/v1/infraestrutura/pendencias':['get'],
        '/api/v1/infraestrutura/pontos':['get','post'],
        '/api/v1/infraestrutura/pontos/{ponto_id}':['put','delete'],
        '/api/v1/infraestrutura/pontos/{ponto_id}/historico':['get'],
        '/api/v1/infraestrutura/malha/trechos-proximos':['get'], '/api/v1/dados-publicos/consultar-rota':['post'],
        '/api/v1/dados-publicos/roubo-carga/por-regiao':['get'], '/api/v1/dados-publicos/fontes':['get'],
        '/api/v1/indicadores/qualidade':['get'], '/api/v1/health/liveness':['get'],
        '/api/v1/health/readiness':['get'], '/api/v1/alertas/precisao':['get'], '/api/v1/alertas/feedback':['post'],
        '/api/v1/painel/corredores':['get','post'], '/api/v1/painel/corredores/{identificador}':['put'],
        '/api/v1/painel/corredores/{identificador}/recorrencias':['post'],
        '/api/v1/painel/recorrencias/{identificador}':['put'],
        '/api/v1/painel/recorrencias/{identificador}/despachar':['post'],
        '/api/v1/painel/consultas':['get','post'], '/api/v1/painel/consultas/{identificador}':['get'],
        '/api/v1/painel/operacoes/{identificador}/premissas':['put'],
        '/api/v1/painel/relatos':['post'], '/api/v1/painel/eventos':['get']}
    import re
    normalizar = lambda s: re.sub(r'\{[^}]+\}', '{}', s)
    disponiveis = {normalizar(k):v for k,v in spec.items()}
    for rota, metodos in contratos.items():
        assert normalizar(rota) in disponiveis, rota
        for metodo in metodos:
            assert metodo in disponiveis[normalizar(rota)], (metodo,rota)


@pytest.mark.asyncio
async def test_leituras_reais_de_todos_modulos_painel(ambiente):
    _,cli,origem,_=ambiente
    caminhos=['/logistica/veiculos','/logistica/operacoes','/logistica/alertas/ativos',
        '/logistica/vias/buscar?q=Rua','/logistica/relatorios/sumario-executivo',
        '/logistica/observabilidade/metricas','/infraestrutura/pontos?limite=1','/infraestrutura/pendencias',
        '/infraestrutura/malha/trechos-proximos?somente_regional=false&longitude='+str(origem['origem_lon'])+'&latitude='+str(origem['origem_lat']),
        '/dados-publicos/roubo-carga/por-regiao','/dados-publicos/fontes','/indicadores/qualidade',
        '/health/liveness','/health/readiness','/alertas/precisao',
        '/rotas/intermunicipal?origem=Araraquara&destino=Sao%20Paulo&tipo_veiculo=VUC',
        '/painel/corredores','/painel/consultas','/painel/eventos','/acesso/configuracao']
    for path in caminhos:
        r=await cli.get(path,headers={'X-API-Key':'key_admin_demo'} if '/malha/' in path else OP)
        assert r.status_code==200,(path,r.status_code,r.text[:200])
        assert isinstance(r.json(),(dict,list)),path
    csv=await cli.get('/logistica/exportar-contingencia/csv')
    assert csv.status_code==200 and 'text/csv' in csv.headers['content-type']


@pytest.mark.asyncio
async def test_confianca_zero_preservada_e_data_real_da_frota(ambiente):
    conn,cli,_,_=ambiente;op=await nova_operacao(ambiente)
    await conn.execute('''INSERT INTO recomendacoes_operacao(id_operacao,tenant_id,nivel_risco,tipo_acao,motivo,confianca)
        VALUES($1,'demo_corp','NORMAL','MANTER_ROTA_ORIGINAL','Teste de incerteza',0)''',op)
    d=(await cli.post('/painel/consultas',json={'id_operacao':op})).json()
    assert d['explicacao']['confianca']==0
    ident='QA_FROTA_'+uuid4().hex[:12]
    try:
        r=await cli.post('/logistica/veiculos',json={'id_veiculo':ident,'placa':'QA00000','modelo':'Exemplo de teste','tipo_veiculo':'VUC','lat_atual':-23.5,'lon_atual':-46.4})
        assert r.status_code==200,r.text
        frota=(await cli.get('/logistica/veiculos')).json()
        row=next(v for v in frota if v['id_veiculo']==ident)
        assert datetime.fromisoformat(row['atualizado_em']).tzinfo is not None
    finally:await conn.execute('DELETE FROM veiculos WHERE id_veiculo=$1',ident)
