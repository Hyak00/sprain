"""Relatórios não alteram o domínio e não misturam dados atuais/históricos."""
import csv
import io
import json
from datetime import date
from uuid import uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException
from app.config import settings
from app.database import get_connection
from app.routers.relatorios_painel import router, periodo
from app.seguranca import get_current_user_claims


@pytest_asyncio.fixture
async def a():
    conn=await asyncpg.connect(settings.database_url)
    tenant='rel33_'+uuid4().hex[:12];op='OP_'+uuid4().hex[:15]
    claims={'tenant_id':tenant,'role':'VIEWER'}
    await conn.execute('''INSERT INTO operacoes(id_operacao,tenant_id,origem_lat,origem_lon,destino_lat,destino_lon,
        janela_inicio,janela_fim,custo_estimado,criado_em) VALUES($1,$2,-23.5,-46.4,-23.6,-46.5,now(),now(),100,'2026-10-16 04:00:00')''',op,tenant)
    app=FastAPI();app.include_router(router)
    async def identidade():return claims
    async def conexao():yield conn
    app.dependency_overrides[get_connection]=conexao;app.dependency_overrides[get_current_user_claims]=identidade
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://teste') as cli:
        try:yield conn,cli,tenant,op,claims
        finally:
            for tabela in ('decisoes_gestor_operacao','painel_consultas','recomendacoes_operacao','operacoes'):
                await conn.execute(f'DELETE FROM {tabela} WHERE tenant_id=$1',tenant)
            await conn.close()


def foto(op,valor=25):
    return {'id_operacao':op,'acao_recomendada':'ALTERAR_ROTA','confianca':0,
        'contexto_consulta':{'fonte':'Fonte sintética de teste','natureza':'SIMULACAO','autoria_individual':str(uuid4())},
        'validacao_rota':{'rota_alternativa_disponivel':False},'geometrias':{'rota_alternativa_geojson':None},
        'infraestrutura':{'financeiro':{'custo_original_conhecido_brl':valor,'custo_alternativa_conhecido_brl':999}}}


@pytest.mark.asyncio
async def test_piloto_soma_uma_recomendacao_por_operacao_e_nao_inventa_observacao(a):
    conn,cli,tenant,op,_=a
    for potencial in (999,0):
        await conn.execute('''INSERT INTO recomendacoes_operacao(id_operacao,tenant_id,tipo_acao,nivel_risco,motivo,prejuizo_potencial_evitado)
            VALUES($1,$2,'ALTERAR_ROTA','RISCO','Teste',$3)''',op,tenant,potencial)
    r=await cli.get('/api/v1/painel/relatorios/piloto');assert r.status_code==200,r.text
    d=r.json();assert d['amostra']['operacoes']==1 and d['amostra']['recomendacoes']==1
    assert d['indicadores']['custo_estimado']['valor_brl']==100
    assert d['indicadores']['impacto_potencial']['valor_brl']==0
    assert d['indicadores']['economia_comprovada']['valor_brl'] is None
    assert d['indicadores']['custo_observado']['valor_brl'] is None
    assert d['fontes'] and d['limitacoes']
    assert r.headers['cache-control']=='no-store'
    await conn.execute('UPDATE operacoes SET custo_estimado=NULL WHERE id_operacao=$1',op)
    d=(await cli.get('/api/v1/painel/relatorios/piloto')).json()
    assert d['indicadores']['custo_estimado']['valor_brl'] is None
    assert d['indicadores']['custo_estimado']['operacoes_sem_valor']==1


@pytest.mark.asyncio
async def test_periodo_brasilia_fim_inclusivo_e_empresa_sem_dados(a):
    conn,cli,tenant,op,claims=a
    p='/api/v1/painel/relatorios/piloto?inicio=2026-10-16&fim=2026-10-16'
    assert (await cli.get(p)).json()['amostra']['operacoes']==1
    await conn.execute("UPDATE operacoes SET criado_em='2026-10-17 02:59:59' WHERE id_operacao=$1",op)
    assert (await cli.get(p)).json()['amostra']['operacoes']==1
    await conn.execute("UPDATE operacoes SET criado_em='2026-10-17 03:00:00' WHERE id_operacao=$1",op)
    assert (await cli.get(p)).json()['amostra']['operacoes']==0
    claims['tenant_id']='outra_sem_dados'
    d=(await cli.get('/api/v1/painel/relatorios/piloto')).json();assert d['amostra']['operacoes']==0
    assert d['indicadores']['impacto_potencial']['valor_brl'] is None


@pytest.mark.asyncio
async def test_decisao_individual_usa_fotografia_e_fallback_so_da_consulta_vinculada(a):
    conn,cli,tenant,op,claims=a
    consulta=uuid4();f=foto(op)
    await conn.execute('INSERT INTO painel_consultas(id,tenant_id,id_operacao,perfil,snapshot) VALUES($1,$2,$3,\'OPERATOR\',$4)',consulta,tenant,op,json.dumps(f))
    d=await conn.fetchval('''INSERT INTO decisoes_gestor_operacao(tenant_id,id_operacao,decisao,motivo_gestor,consulta_id,snapshot)
        VALUES($1,$2,'AGUARDAR_MELHORA','Teste',$3,$4) RETURNING id_decisao''',tenant,op,consulta,json.dumps(foto(op,42)))
    r=await cli.get(f'/api/v1/painel/relatorios/decisoes/{d}');assert r.json()['snapshot']['infraestrutura']['financeiro']['custo_original_conhecido_brl']==42
    await conn.execute('UPDATE operacoes SET custo_estimado=100000 WHERE id_operacao=$1',op)
    assert (await cli.get(f'/api/v1/painel/relatorios/decisoes/{d}')).json()['snapshot']['infraestrutura']['financeiro']['custo_original_conhecido_brl']==42
    await conn.execute('UPDATE decisoes_gestor_operacao SET snapshot=NULL WHERE id_decisao=$1',d)
    assert (await cli.get(f'/api/v1/painel/relatorios/decisoes/{d}')).json()['fonte_snapshot']=='consulta.snapshot vinculada'
    await conn.execute('UPDATE decisoes_gestor_operacao SET consulta_id=NULL WHERE id_decisao=$1',d)
    assert (await cli.get(f'/api/v1/painel/relatorios/decisoes/{d}')).json()['snapshot'] is None
    await conn.execute("UPDATE painel_consultas SET id_operacao='OUTRA_OPERACAO' WHERE id=$1",consulta)
    await conn.execute('UPDATE decisoes_gestor_operacao SET consulta_id=$2 WHERE id_decisao=$1',d,consulta)
    assert (await cli.get(f'/api/v1/painel/relatorios/decisoes/{d}')).json()['snapshot'] is None
    claims['tenant_id']='outra'
    assert (await cli.get(f'/api/v1/painel/relatorios/decisoes/{d}')).status_code==404


@pytest.mark.asyncio
async def test_csv_consultas_e_decisoes_preservam_autor_zero_e_protegem_formulas(a):
    conn,cli,tenant,op,claims=a
    f=foto(op,0);consulta=uuid4();autor=uuid4()
    await conn.execute('INSERT INTO painel_consultas(id,tenant_id,id_operacao,perfil,snapshot) VALUES($1,$2,$3,\'VIEWER\',$4)',consulta,tenant,op,json.dumps(f))
    await conn.execute('''INSERT INTO decisoes_gestor_operacao(tenant_id,id_operacao,decisao,motivo_gestor,consulta_id,snapshot,usuario_id,perfil_registro)
        VALUES($1,$2,'AGUARDAR_MELHORA',$3,$4,$5,$6,'OPERATOR')''',tenant,op,' =HYPERLINK("x");\nAção',consulta,json.dumps(f),autor)
    for tipo in ('consultas','decisoes'):
        r=await cli.get(f'/api/v1/painel/relatorios/{tipo}.csv');assert r.status_code==200,r.text
        assert r.content.startswith(b'\xef\xbb\xbf')
        rows=list(csv.DictReader(io.StringIO(r.text.lstrip('\ufeff')),delimiter=';'));assert len(rows)==1
        row=rows[0];assert row['custo_original_estimado_brl']=='0' and row['confianca']=='0'
        assert row['custo_alternativo_estimado_brl']==''
        assert row['economia_comprovada_brl']=='' and row['custo_observado_brl']==''
        if tipo=='decisoes':assert row['usuario_id']==str(autor) and row['motivo'].startswith("' =")
        else:assert row['usuario_id']==f['contexto_consulta']['autoria_individual']
    await conn.execute('INSERT INTO painel_consultas(id,tenant_id,id_operacao,perfil,snapshot) VALUES($1,$2,$3,\'VIEWER\',$4)',uuid4(),tenant,op,json.dumps(foto(op,999)))
    r=await cli.get(f'/api/v1/painel/relatorios/consultas.csv?id_consulta={consulta}')
    rows=list(csv.DictReader(io.StringIO(r.text.lstrip('\ufeff')),delimiter=';'))
    assert len(rows)==1 and rows[0]['id_consulta']==str(consulta)
    claims['tenant_id']='outra'
    for tipo in ('consultas','decisoes'):
        r=await cli.get(f'/api/v1/painel/relatorios/{tipo}.csv')
        assert len(list(csv.DictReader(io.StringIO(r.text.lstrip('\ufeff')),delimiter=';')))==0


@pytest.mark.asyncio
async def test_lista_decisoes_pagina_sem_perder_ultima_e_filtra_operacao(a):
    conn,cli,tenant,op,_=a
    for _ in range(21):await conn.execute('''INSERT INTO decisoes_gestor_operacao(tenant_id,id_operacao,decisao,motivo_gestor)
        VALUES($1,$2,'AGUARDAR_MELHORA','Teste')''',tenant,op)
    d=(await cli.get('/api/v1/painel/relatorios/decisoes')).json();assert len(d['items'])==20 and d['proximo_offset']==20
    d=(await cli.get('/api/v1/painel/relatorios/decisoes?offset=20')).json();assert len(d['items'])==1 and d['proximo_offset'] is None
    assert (await cli.get('/api/v1/painel/relatorios/decisoes?id_operacao=inexistente')).json()['items']==[]


def test_periodos_invalidos_nao_sao_aplicados_silenciosamente():
    for inicio,fim in [(date(2026,10,1),None),(None,date(2026,10,1)),(date(2026,10,2),date(2026,10,1)),(date(2020,1,1),date(2026,1,1)),(date.max,date.max)]:
        with pytest.raises(HTTPException):periodo(inicio,fim)


@pytest.mark.asyncio
async def test_csv_acima_do_limite_nao_entrega_arquivo_parcial(a):
    conn,cli,tenant,op,_=a
    await conn.execute('''INSERT INTO decisoes_gestor_operacao(tenant_id,id_operacao,decisao,motivo_gestor)
        VALUES($1,$2,'AGUARDAR_MELHORA',$3)''',tenant,op,'x'*(8*1024*1024+1))
    r=await cli.get('/api/v1/painel/relatorios/decisoes.csv')
    assert r.status_code==413 and r.headers.get('content-disposition') is None
    assert len(r.content)<1000
