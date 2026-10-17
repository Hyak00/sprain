"""Fluxos 3.2 em banco isolado: permissões, recuperação e exportação real."""
import io
import json
import zipfile
from uuid import uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.config import settings
from app.database import get_connection
from app.routers.administracao_painel import router
from app.seguranca import get_current_user_claims
from app.services import administracao_painel as s
from app.services.acesso_painel import SCHEMA as ACESSO, conferir, resumo


@pytest_asyncio.fixture
async def a():
    conn=await asyncpg.connect(settings.database_url)
    await conn.execute(ACESSO+s.SCHEMA)
    tenant='admin32_'+uuid4().hex[:12]
    ids=[uuid4(),uuid4(),uuid4()]
    emails=[f'{i}-{tenant}@example.test' for i in range(3)]
    for i in range(3):
        await conn.execute('''INSERT INTO painel_usuarios(id,email,empresa,tenant_id,papel,senha_hash)
            VALUES($1,$2,'Teste',$3,$4,'hash-nao-exportar')''',ids[i],emails[i],tenant if i<2 else tenant+'_outra','ADMIN' if i!=1 else 'OPERATOR')
    claims={'usuario_id':str(ids[0]),'tenant_id':tenant,'role':'ADMIN'}
    app=FastAPI();app.include_router(router)
    async def identidade():return claims
    async def conexao():yield conn
    app.dependency_overrides[get_current_user_claims]=identidade
    app.dependency_overrides[get_connection]=conexao
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://teste') as cli:
        try:yield conn,cli,claims,ids,emails,tenant
        finally:
            await conn.execute('DELETE FROM painel_recuperacao_tentativas WHERE conta_hash=ANY($1::text[])',[resumo(e) for e in emails])
            await conn.execute('DELETE FROM painel_recuperacoes WHERE usuario_id=ANY($1::uuid[])',ids)
            await conn.execute('DELETE FROM painel_sessoes WHERE usuario_id=ANY($1::uuid[])',ids)
            for table in ('painel_financeiro','painel_admin_auditoria'):
                await conn.execute(f'DELETE FROM {table} WHERE tenant_id=ANY($1::text[])',[tenant,tenant+'_outra'])
            await conn.execute('DELETE FROM painel_usuarios WHERE id=ANY($1::uuid[])',ids)
            await conn.close()


@pytest.mark.asyncio
async def test_financeiro_versionado_isolado_e_sem_substituir_frota(a):
    conn,cli,claims,ids,emails,tenant=a
    r=await cli.get('/api/v1/administracao/financeiro');assert r.json()['versao']==0
    r=await cli.put('/api/v1/administracao/financeiro',json={'versao':0,'custos':{'custo_hora_motorista':80,'custo_por_km':0}})
    assert r.status_code==200,r.text
    assert r.json()['custos']['custo_por_km']==0
    assert r.json()['versao']==1
    assert (await cli.put('/api/v1/administracao/financeiro',json={'versao':0,'custos':{}})).status_code==409
    assert (await cli.put('/api/v1/administracao/financeiro',json={'versao':1,'custos':{'consumo_km_l':0}})).status_code==422
    claims.update(tenant_id=tenant+'_outra',usuario_id=str(ids[2]))
    assert (await cli.get('/api/v1/administracao/financeiro')).json()['custos']=={}
    claims.update(tenant_id=tenant,usuario_id=str(ids[0]),role='VIEWER')
    assert (await cli.put('/api/v1/administracao/financeiro',json={'versao':1,'custos':{}})).status_code==403
    claims.update(role='ADMIN');claims.pop('usuario_id')
    assert (await cli.put('/api/v1/administracao/financeiro',json={'versao':1,'custos':{}})).status_code==403


@pytest.mark.asyncio
async def test_recuperacao_solicita_libera_consume_revoga_e_nao_reutiliza(a):
    conn,cli,claims,ids,emails,tenant=a
    r=await cli.post('/api/v1/administracao/recuperacao/solicitar',json={'email':emails[1]})
    desconhecido=await cli.post('/api/v1/administracao/recuperacao/solicitar',json={'email':'inexistente-'+tenant+'@example.test'})
    assert r.json()==desconhecido.json()
    pedidos=(await cli.get('/api/v1/administracao/recuperacao')).json()['items'];assert len(pedidos)==1
    pedido=pedidos[0]['id']
    assert (await cli.post(f'/api/v1/administracao/recuperacao/{pedido}/liberar',json={'identidade_conferida':False})).status_code==422
    liberado=await cli.post(f'/api/v1/administracao/recuperacao/{pedido}/liberar',json={'identidade_conferida':True})
    assert liberado.status_code==200,liberado.text
    token=liberado.json()['codigo'];assert token not in (await cli.get('/api/v1/administracao/recuperacao')).text
    assert await conn.fetchval('SELECT token_hash FROM painel_recuperacoes WHERE id=$1',__import__('uuid').UUID(pedido))==resumo(token)
    assert (await cli.post(f'/api/v1/administracao/recuperacao/{pedido}/liberar',json={'identidade_conferida':True})).status_code==409
    await conn.execute('INSERT INTO painel_sessoes(token_hash,usuario_id,expira_em) VALUES($1,$2,now()+interval \'1 hour\')',resumo(tenant),ids[1])
    senha='  Nova senha somente para testes 123  '
    body={'email':emails[1],'codigo':token,'senha':senha}
    r=await cli.post('/api/v1/administracao/recuperacao/concluir',json=body);assert r.status_code==200,r.text
    assert conferir(senha,await conn.fetchval('SELECT senha_hash FROM painel_usuarios WHERE id=$1',ids[1]))
    assert await conn.fetchval('SELECT revogado_em IS NOT NULL FROM painel_sessoes WHERE token_hash=$1',resumo(tenant))
    assert (await cli.post('/api/v1/administracao/recuperacao/concluir',json=body)).status_code==400
    assert (await cli.get('/api/v1/administracao/recuperacao')).json()['items']==[]


@pytest.mark.asyncio
async def test_recuperacao_cancelada_expirada_ou_outra_empresa_nao_funciona(a):
    conn,cli,claims,ids,emails,tenant=a
    await cli.post('/api/v1/administracao/recuperacao/solicitar',json={'email':emails[1]})
    pedido=(await cli.get('/api/v1/administracao/recuperacao')).json()['items'][0]['id']
    claims.update(tenant_id=tenant+'_outra',usuario_id=str(ids[2]))
    assert (await cli.get('/api/v1/administracao/recuperacao')).json()['items']==[]
    assert (await cli.post(f'/api/v1/administracao/recuperacao/{pedido}/liberar',json={'identidade_conferida':True})).status_code==404
    claims.update(tenant_id=tenant,usuario_id=str(ids[0]))
    token=(await cli.post(f'/api/v1/administracao/recuperacao/{pedido}/liberar',json={'identidade_conferida':True})).json()['codigo']
    await cli.post(f'/api/v1/administracao/recuperacao/{pedido}/cancelar')
    assert (await cli.post('/api/v1/administracao/recuperacao/concluir',json={'email':emails[1],'codigo':token,'senha':'Senha longa para testar cancelado'})).status_code==400
    await cli.post('/api/v1/administracao/recuperacao/solicitar',json={'email':emails[1]})
    novo=(await cli.get('/api/v1/administracao/recuperacao')).json()['items'][0]['id']
    await conn.execute("UPDATE painel_recuperacoes SET expira_em=now()-interval '1 minute' WHERE id=$1",__import__('uuid').UUID(novo))
    assert (await cli.post(f'/api/v1/administracao/recuperacao/{novo}/liberar',json={'identidade_conferida':True})).status_code==409


@pytest.mark.asyncio
async def test_exportacao_zip_real_sem_segredos_ou_outra_empresa(a):
    conn,cli,claims,ids,emails,tenant=a
    r=await cli.get('/api/v1/administracao/exportacao');assert r.status_code==200,r.text
    assert r.headers['cache-control']=='no-store'
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        manifesto=json.loads(z.read('manifesto.json'))
        assert manifesto['tenant_id']==tenant
        assert manifesto['contagens']['usuarios']==2
        usuarios=z.read('usuarios.jsonl').decode()
        assert emails[0] in usuarios and emails[1] in usuarios
        assert emails[2] not in usuarios and 'senha_hash' not in usuarios
        assert b'hash-nao-exportar' not in b''.join(z.read(n) for n in z.namelist())
        assert 'painel_sessoes.jsonl' not in z.namelist()
        for nome,n in manifesto['contagens'].items():assert len(z.read(nome+'.jsonl').splitlines())==n
    claims['role']='OPERATOR'
    assert (await cli.get('/api/v1/administracao/exportacao')).status_code==403


@pytest.mark.asyncio
async def test_solicitacao_nao_invalida_codigo_e_limita_abuso(a):
    conn,cli,claims,ids,emails,tenant=a
    for _ in range(5):assert (await cli.post('/api/v1/administracao/recuperacao/solicitar',json={'email':emails[1]})).status_code==200
    assert (await cli.post('/api/v1/administracao/recuperacao/solicitar',json={'email':emails[1]})).status_code==429
    assert len((await cli.get('/api/v1/administracao/recuperacao')).json()['items'])==1


@pytest.mark.asyncio
async def test_codigo_expirado_de_outra_conta_ou_usuario_desativado_nao_troca_senha(a):
    conn,cli,claims,ids,emails,tenant=a
    await cli.post('/api/v1/administracao/recuperacao/solicitar',json={'email':emails[1]})
    pedido=(await cli.get('/api/v1/administracao/recuperacao')).json()['items'][0]['id']
    token=(await cli.post(f'/api/v1/administracao/recuperacao/{pedido}/liberar',json={'identidade_conferida':True})).json()['codigo']
    body={'email':emails[0],'codigo':token,'senha':'senha longa que nunca deve ser gravada'}
    assert (await cli.post('/api/v1/administracao/recuperacao/concluir',json=body)).status_code==400
    body['email']=emails[1]
    await conn.execute('UPDATE painel_usuarios SET ativo=false WHERE id=$1',ids[1])
    assert (await cli.post('/api/v1/administracao/recuperacao/concluir',json=body)).status_code==400
    await conn.execute('UPDATE painel_usuarios SET ativo=true WHERE id=$1',ids[1])
    await conn.execute("UPDATE painel_recuperacoes SET expira_em=now()-interval '1 second' WHERE id=$1",__import__('uuid').UUID(pedido))
    assert (await cli.post('/api/v1/administracao/recuperacao/concluir',json=body)).status_code==400
    assert await conn.fetchval('SELECT senha_hash FROM painel_usuarios WHERE id=$1',ids[1])=='hash-nao-exportar'
