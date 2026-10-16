"""Identidade, papeis e revogacao reais, em banco isolado de testes."""
from datetime import datetime,timezone,timedelta
from uuid import uuid4
import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import Request,Response,HTTPException
from app.config import settings
from app.services.acesso_painel import cadastrar,conferir,resumo,SCHEMA
from app.routers import acesso_painel


@pytest_asyncio.fixture
async def acesso():
    conn=await asyncpg.connect(settings.database_url)
    await conn.execute(SCHEMA)
    email='teste-'+uuid4().hex+'@example.test';senha='Senha somente de teste '+uuid4().hex
    uid=await cadastrar(conn,email,senha,'Empresa de teste','demo_corp','VIEWER')
    cli=httpx.AsyncClient(base_url='http://127.0.0.1:8000',timeout=90)
    yield conn,cli,email,senha,uid
    await conn.execute('DELETE FROM painel_sessoes WHERE usuario_id=$1',uid)
    await conn.execute('DELETE FROM painel_usuarios WHERE id=$1',uid)
    await conn.execute('DELETE FROM painel_login_tentativas WHERE conta_hash=$1',resumo(email))
    await cli.aclose();await conn.close()


@pytest.mark.asyncio
async def test_login_individual_revogacao_papeis_e_sem_senha_na_resposta(acesso):
    conn,cli,email,senha,uid=acesso
    protegido=await conn.fetchval('SELECT senha_hash FROM painel_usuarios WHERE id=$1',uid)
    assert protegido!=senha and conferir(senha,protegido) and not conferir('incorreta',protegido)
    r=await cli.post('/api/v1/acesso/login',json={'email':email.upper(),'senha':senha})
    assert r.status_code==200,r.text
    assert r.headers['cache-control']=='no-store'
    d=r.json();assert senha not in r.text and protegido not in r.text
    assert d['usuario_id']==str(uid) and d['tipo_acesso']=='INDIVIDUAL'
    token=d['api_key'];cab={'X-API-Key':token}
    assert not await conn.fetchval('SELECT 1 FROM painel_sessoes WHERE token_hash=$1',token)
    assert (await cli.get('/api/v1/painel/corredores',headers=cab)).status_code==200
    assert (await cli.post('/api/v1/painel/corredores',headers=cab,json={})).status_code==403
    assert (await cli.post('/api/v1/acesso/logout',headers=cab)).status_code==200
    assert (await cli.get('/api/v1/painel/corredores',headers=cab)).status_code==401
    assert (await cli.get('/api/v1/painel/corredores',headers={'X-API-Key':'key_viewer_demo'})).status_code==200


@pytest.mark.asyncio
async def test_sessao_expirada_usuario_inativo_e_papel_atual(acesso):
    conn,cli,email,senha,uid=acesso
    async def entrar():
        d=(await cli.post('/api/v1/acesso/login',json={'email':email,'senha':senha})).json()
        return d['api_key'],{'X-API-Key':d['api_key']}
    token,cab=await entrar()
    await conn.execute("UPDATE painel_sessoes SET expira_em=now()-interval '1 second' WHERE token_hash=$1",resumo(token))
    assert (await cli.get('/api/v1/painel/consultas',headers=cab)).status_code==401
    _,cab=await entrar()
    await conn.execute("UPDATE painel_usuarios SET papel='OPERATOR' WHERE id=$1",uid)
    assert (await cli.post('/api/v1/painel/corredores',headers=cab,json={})).status_code==422
    await conn.execute('UPDATE painel_usuarios SET ativo=false WHERE id=$1',uid)
    assert (await cli.get('/api/v1/painel/consultas',headers=cab)).status_code==401
    assert (await cli.post('/api/v1/acesso/login',json={'email':email,'senha':senha})).status_code==401


@pytest.mark.asyncio
async def test_login_individual_em_producao_nao_usa_conta_demo(acesso,monkeypatch):
    conn,_,email,senha,_=acesso
    monkeypatch.setattr(acesso_painel,'is_production',lambda:True)
    assert (await acesso_painel.configuracao(Response()))['demonstracao_disponivel'] is False
    req=Request({'type':'http','client':('127.0.0.2',1234),'headers':[]})
    r=await acesso_painel.login(acesso_painel.Login(email=email,senha=senha),req,Response(),conn)
    assert r['tipo_acesso']=='INDIVIDUAL'
    with pytest.raises(HTTPException) as erro:
        await acesso_painel.login(acesso_painel.Login(email='operacoes@democorp.com.br',senha='sprain2026'),req,Response(),conn)
    assert erro.value.status_code==401
    await conn.execute('DELETE FROM painel_login_tentativas WHERE conta_hash=$1',resumo('operacoes@democorp.com.br'))


@pytest.mark.asyncio
async def test_limite_de_tentativas_persistido_e_generico(acesso):
    conn,cli,email,_,_=acesso
    await conn.execute('''INSERT INTO painel_login_tentativas(conta_hash,ip_hash)
        SELECT $1,'ip-teste' FROM generate_series(1,10)''',resumo(email))
    r=await cli.post('/api/v1/acesso/login',json={'email':email,'senha':'errada'})
    assert r.status_code==429 and email not in r.text


@pytest.mark.asyncio
async def test_autoria_individual_na_consulta_e_isolamento_de_empresa(acesso):
    conn,cli,email,senha,uid=acesso
    d=(await cli.post('/api/v1/acesso/login',json={'email':email,'senha':senha})).json();cab={'X-API-Key':d['api_key']}
    op=await conn.fetchval("SELECT id_operacao FROM operacoes WHERE tenant_id='demo_corp' LIMIT 1")
    r=await cli.post('/api/v1/painel/consultas',headers=cab,json={'id_operacao':op})
    assert r.status_code==200,r.text
    cid=r.json()['consulta']['id']
    try:
        assert r.json()['explicacao']['contexto_consulta']['autoria_individual']==str(uid)
        await conn.execute("UPDATE painel_usuarios SET tenant_id='log_express' WHERE id=$1",uid)
        assert (await cli.get('/api/v1/painel/consultas/'+cid,headers=cab)).status_code==404
    finally:await conn.execute('DELETE FROM painel_consultas WHERE id=$1',__import__('uuid').UUID(cid))
