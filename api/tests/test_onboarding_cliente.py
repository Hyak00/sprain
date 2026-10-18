"""Aceite persistente de onboarding e leitura de decisões; somente banco de testes."""
import json
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import asyncpg
import httpx
import pytest
import pytest_asyncio
from app.config import settings


@pytest_asyncio.fixture
async def onboarding():
    conn=await asyncpg.connect(settings.database_url)
    cliente=httpx.AsyncClient(base_url='http://127.0.0.1:8000',timeout=60)
    # Preserva o registro da empresa sintética da API isolada e restaura no fim.
    anterior=await conn.fetchrow("SELECT * FROM painel_onboarding WHERE tenant_id='demo_corp'")
    await conn.execute("DELETE FROM painel_onboarding WHERE tenant_id='demo_corp'")
    outra='TEST_ONBOARD_'+uuid4().hex[:12]
    await conn.execute('''INSERT INTO operacoes(id_operacao,tenant_id,origem_lat,origem_lon,destino_lat,destino_lon,janela_inicio,janela_fim)
        SELECT $1,'log_express',origem_lat,origem_lon,destino_lat,destino_lon,now(),now()+interval '4 hours'
        FROM operacoes WHERE tenant_id='demo_corp' LIMIT 1''',outra)
    consultas=[]
    yield conn,cliente,consultas
    await conn.execute("DELETE FROM painel_onboarding WHERE tenant_id='demo_corp'")
    for c in consultas:await conn.execute('DELETE FROM painel_consultas WHERE id=$1',c)
    await conn.execute('DELETE FROM operacoes WHERE id_operacao=$1',outra)
    if anterior:
        await conn.execute('''INSERT INTO painel_onboarding(tenant_id,iniciado_em,primeiro_resultado_em,consulta_id,usuario_id,criterio)
            VALUES($1,$2,$3,$4,$5,$6)''',*[anterior[k] for k in ('tenant_id','iniciado_em','primeiro_resultado_em','consulta_id','usuario_id','criterio')])
    await cliente.aclose();await conn.close()


async def fotografia(a,tenant='demo_corp',antiga=False,valida=True):
    conn,_,ids=a;identificador=uuid4()
    op=await conn.fetchval('SELECT id_operacao FROM operacoes WHERE tenant_id=$1 LIMIT 1',tenant)
    assert op
    snapshot={'metricas':{'distancia_original_km':2 if valida else None},
        'geometrias':{'rota_original_geojson':{'features':[{'geometry':{'type':'LineString','coordinates':[[0,0],[1,1]]}}]}}}
    await conn.execute('''INSERT INTO painel_consultas(id,tenant_id,id_operacao,perfil,snapshot,criado_em)
        VALUES($1,$2,$3,'OPERATOR',$4::jsonb,$5)''',identificador,tenant,op,json.dumps(snapshot),datetime.now(timezone.utc)-timedelta(days=1) if antiga else datetime.now(timezone.utc))
    ids.append(identificador);return str(identificador)


def key(papel='operator'):return {'X-API-Key':'key_'+papel+'_demo'}


@pytest.mark.asyncio
async def test_onboarding_e_idempotente_e_tempo_vem_do_servidor(onboarding):
    conn,c,_=onboarding
    inicio=await c.post('/api/v1/painel/onboarding/iniciar',headers=key(),json={})
    assert inicio.status_code==200,inicio.text
    base=inicio.json()['onboarding']['iniciado_em']
    repetido=await c.post('/api/v1/painel/onboarding/iniciar',headers=key(),json={})
    assert repetido.json()['onboarding']['iniciado_em']==base
    consulta=await fotografia(onboarding)
    r=await c.post('/api/v1/painel/onboarding/primeiro-resultado',headers=key(),json={'consulta_id':consulta})
    assert r.status_code==200,r.text
    estado=r.json()['onboarding']
    assert estado['consulta_id']==consulta and estado['tempo_ate_primeiro_resultado_segundos']>=0
    repetido=await c.post('/api/v1/painel/onboarding/primeiro-resultado',headers=key(),json={'consulta_id':await fotografia(onboarding)})
    assert repetido.json()['onboarding']['primeiro_resultado_em']==estado['primeiro_resultado_em']
    assert (await c.get('/api/v1/painel/onboarding',headers=key('viewer'))).json()['onboarding']['consulta_id']==consulta
    assert await conn.fetchval("SELECT consulta_id::text FROM painel_onboarding WHERE tenant_id='demo_corp'")==consulta


@pytest.mark.asyncio
async def test_onboarding_recusa_sem_inicio_consulta_antiga_e_outra_empresa(onboarding):
    _,c,_=onboarding;consulta=await fotografia(onboarding)
    r=await c.post('/api/v1/painel/onboarding/primeiro-resultado',headers=key(),json={'consulta_id':consulta})
    assert r.status_code==409
    await c.post('/api/v1/painel/onboarding/iniciar',headers=key(),json={})
    for consulta,status in [(consulta,422),(await fotografia(onboarding,valida=False),422),(await fotografia(onboarding,'log_express'),404)]:
        r=await c.post('/api/v1/painel/onboarding/primeiro-resultado',headers=key(),json={'consulta_id':consulta})
        assert r.status_code==status,r.text
    estado=(await c.get('/api/v1/painel/onboarding',headers=key())).json()['onboarding']
    assert estado['primeiro_resultado_em'] is None


@pytest.mark.asyncio
async def test_viewer_nao_inicia_nem_confirma_mas_le_acompanhamento(onboarding):
    conn,c,_=onboarding
    for path,body in [('iniciar',{}),('primeiro-resultado',{'consulta_id':str(uuid4())})]:
        assert (await c.post('/api/v1/painel/onboarding/'+path,headers=key('viewer'),json=body)).status_code==403
    op=await conn.fetchval("SELECT id_operacao FROM operacoes WHERE tenant_id='demo_corp' LIMIT 1")
    outra=await conn.fetchval("SELECT id_operacao FROM operacoes WHERE tenant_id='log_express' LIMIT 1")
    r=await c.post('/api/v1/painel/acompanhamento',headers=key('viewer'),json={'operacoes':[op,outra]})
    assert r.status_code==200,r.text
    assert [i['id_operacao'] for i in r.json()['items']]==[op]
    assert isinstance(r.json()['items'][0]['possui_decisao'],bool)
    assert (await c.get('/api/v1/painel/onboarding')).status_code==401
    assert (await c.post('/api/v1/painel/acompanhamento',headers=key(),json={'operacoes':[]})).status_code==422
