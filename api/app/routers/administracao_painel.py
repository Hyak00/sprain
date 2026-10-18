"""Administração da empresa sem substituir os contratos do painel."""
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, ConfigDict, Field

from app.database import get_connection
from app.schemas import CustosCaminhao, ParametrosFinanceiros
from app.seguranca import get_current_user_claims, require_role
from app.routers.gestao_usuarios import exigir_admin_individual
from app.services.gestao_usuarios import _travar_empresa_e_validar_admin
from app.services import administracao_painel as servico

router = APIRouter(prefix='/api/v1/administracao', tags=['Administração do painel'])


class CustosEmpresa(CustosCaminhao):
    model_config = ConfigDict(extra='forbid')


class Financeiro(BaseModel):
    model_config = ConfigDict(extra='forbid')
    versao: int = Field(ge=0)
    custos: CustosEmpresa


class Email(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=3, max_length=254)


class Recuperar(Email):
    codigo: str = Field(min_length=20, max_length=100)
    senha: str = Field(min_length=15, max_length=256)


class Liberacao(BaseModel):
    model_config = ConfigDict(extra='forbid')
    identidade_conferida: bool


@router.get('/financeiro', dependencies=[Depends(require_role(['ADMIN','OPERATOR','VIEWER']))])
async def financeiro(response: Response, claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    response.headers['Cache-Control'] = 'no-store'
    r = await conn.fetchrow('SELECT * FROM painel_financeiro WHERE tenant_id=$1', claims['tenant_id'])
    custos=json.loads(r['dados']) if r and isinstance(r['dados'],str) else (r['dados'] if r else {})
    return {'custos':custos,
            'referencias_sistema':ParametrosFinanceiros().model_dump(),
            'versao':r['versao'] if r else 0, 'atualizado_em':r['atualizado_em'] if r else None,
            'atualizado_por':str(r['atualizado_por']) if r else None}


@router.put('/financeiro')
async def salvar_financeiro(dados: Financeiro, response: Response, claims=Depends(exigir_admin_individual), conn=Depends(get_connection)):
    response.headers['Cache-Control'] = 'no-store'
    custos = dados.custos.model_dump(mode='json', exclude_none=True)
    async with conn.transaction():
        await _travar_empresa_e_validar_admin(conn, claims)
        atual = await conn.fetchval('SELECT versao FROM painel_financeiro WHERE tenant_id=$1 FOR UPDATE', claims['tenant_id'])
        if (atual or 0) != dados.versao:
            raise HTTPException(409, 'Configuração mudou. Recarregue antes de salvar.')
        await conn.execute('''INSERT INTO painel_financeiro(tenant_id,dados,atualizado_por)
            VALUES($1,$2::jsonb,$3) ON CONFLICT(tenant_id) DO UPDATE SET dados=EXCLUDED.dados,
            versao=painel_financeiro.versao+1,atualizado_por=EXCLUDED.atualizado_por,atualizado_em=now()''',
            claims['tenant_id'], json.dumps(custos), UUID(claims['usuario_id']))
        await servico.auditar(conn, claims, 'PREMISSAS_FINANCEIRAS', dados=custos)
    return await financeiro(response,claims,conn)


@router.post('/recuperacao/solicitar')
async def solicitar(dados: Email, request: Request, response: Response, conn=Depends(get_connection)):
    response.headers['Cache-Control'] = 'no-store'
    return await servico.solicitar(conn,dados.email,request.client.host if request.client else 'sem-ip')


@router.post('/recuperacao/concluir')
async def concluir(dados: Recuperar, request: Request, response: Response, conn=Depends(get_connection)):
    response.headers['Cache-Control'] = 'no-store'
    return await servico.concluir(conn,dados.email,dados.codigo,dados.senha,request.client.host if request.client else 'sem-ip')


@router.get('/recuperacao')
async def pedidos(response: Response, offset: int=Query(0,ge=0), claims=Depends(exigir_admin_individual), conn=Depends(get_connection)):
    response.headers['Cache-Control'] = 'no-store'
    rows = await conn.fetch('''SELECT r.id,u.email,u.id AS usuario_id,r.criado_em,r.expira_em,r.liberado_em
        FROM painel_recuperacoes r JOIN painel_usuarios u ON u.id=r.usuario_id
        WHERE u.tenant_id=$1 AND u.ativo AND r.consumido_em IS NULL AND r.cancelado_em IS NULL
        AND r.expira_em>now() ORDER BY r.criado_em,r.id OFFSET $2 LIMIT 51''',claims['tenant_id'],offset)
    return {'items':[dict(r) for r in rows[:50]],'proximo_offset':offset+50 if len(rows)>50 else None}


@router.post('/recuperacao/{pedido}/liberar')
async def liberar(pedido: UUID, dados: Liberacao, response: Response, claims=Depends(exigir_admin_individual), conn=Depends(get_connection)):
    response.headers['Cache-Control'] = 'no-store'
    if not dados.identidade_conferida:
        raise HTTPException(422, 'Confira a identidade antes de liberar.')
    return await servico.liberar(conn,claims,pedido)


@router.post('/recuperacao/{pedido}/cancelar')
async def cancelar(pedido: UUID, response: Response, claims=Depends(exigir_admin_individual), conn=Depends(get_connection)):
    response.headers['Cache-Control'] = 'no-store'
    async with conn.transaction():
        await _travar_empresa_e_validar_admin(conn,claims)
        u = await conn.fetchval('''UPDATE painel_recuperacoes r SET cancelado_em=now()
            FROM painel_usuarios u WHERE r.id=$1 AND r.usuario_id=u.id AND u.tenant_id=$2
            AND r.consumido_em IS NULL AND r.cancelado_em IS NULL RETURNING r.usuario_id''',pedido,claims['tenant_id'])
        if not u:
            raise HTTPException(404, 'Solicitação não encontrada ou encerrada.')
        await servico.auditar(conn,claims,'RECUPERACAO_CANCELADA',u)
    return {'cancelada':True}


# Lista fechada: nunca interpolar nomes fornecidos pelo cliente nem exportar segredos.
EXPORTACOES = {
    nome:f'SELECT to_jsonb(t) AS dados FROM {nome} t WHERE t.tenant_id=$1'
    for nome in ('veiculos','operacoes','recomendacoes_operacao','cenarios_clima',
        'decisoes_gestor_operacao','painel_corredores','painel_recorrencias','painel_despachos',
        'painel_consultas','painel_relatos','painel_financeiro','painel_onboarding','painel_usuarios_auditoria',
        'painel_admin_auditoria','feedback_alertas_operacionais','infraestrutura_viaria',
        'infraestrutura_revisoes','malha_importacoes','malha_limites_revisoes','auditoria_previsao_realidade')
}
EXPORTACOES['malha_privada'] = '''SELECT to_jsonb(t)-'geom' || jsonb_build_object('geometria',
    ST_AsGeoJSON(ST_Transform(t.geom,4326))::jsonb) AS dados FROM trechos_osm t WHERE tenant_malha=$1'''
EXPORTACOES['infraestrutura_viaria'] = '''SELECT to_jsonb(t)-'geom' || jsonb_build_object('geometria',
    ST_AsGeoJSON(t.geom)::jsonb) AS dados FROM infraestrutura_viaria t WHERE tenant_id=$1'''
EXPORTACOES['webhooks_configuracao'] = '''SELECT jsonb_build_object('eventos',eventos,
    'atualizado_em',atualizado_em) AS dados FROM webhooks_tenant WHERE tenant_id=$1'''
EXPORTACOES['usuarios'] = '''SELECT jsonb_build_object('id',id,'email',email,'empresa',empresa,
    'papel',papel,'ativo',ativo,'atualizado_em',atualizado_em) AS dados
    FROM painel_usuarios WHERE tenant_id=$1'''
EXPORTACOES['rotas_trechos'] = '''SELECT to_jsonb(t) AS dados FROM operacao_rotas_trechos t
    JOIN operacoes o ON o.id_operacao=t.id_operacao WHERE o.tenant_id=$1'''


@router.get('/exportacao')
async def exportar(claims=Depends(exigir_admin_individual), conn=Depends(get_connection)):
    arquivo = tempfile.SpooledTemporaryFile(max_size=2*1024*1024, mode='w+b')
    total = 0
    contagens = {}
    try:
        async with conn.transaction(isolation='repeatable_read',readonly=True):
            # Revalidar até mesmo em testes/integrações que injetem claims.
            valido = await conn.fetchval('''SELECT 1 FROM painel_usuarios
                WHERE id=$1 AND tenant_id=$2 AND ativo AND papel='ADMIN' ''',UUID(claims['usuario_id']),claims['tenant_id'])
            if not valido:
                raise HTTPException(403,'Acesso administrativo inválido.')
            with zipfile.ZipFile(arquivo,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for nome,sql in EXPORTACOES.items():
                    contagens[nome] = 0
                    with z.open(nome+'.jsonl','w') as destino:
                        async for row in conn.cursor(sql,claims['tenant_id'],prefetch=100):
                            dado = row['dados']
                            linha = ((dado if isinstance(dado,str) else json.dumps(jsonable_encoder(dado),ensure_ascii=False))+'\n').encode()
                            total += len(linha)
                            if total>100*1024*1024:
                                raise HTTPException(413,'Exportação excede 100 MB. Solicite uma extração administrativa assistida.')
                            destino.write(linha)
                            contagens[nome] += 1
                # Este módulo legado cria a tabela apenas quando é utilizado.
                if await conn.fetchval("SELECT to_regclass('public.operacoes_cliente_frota') IS NOT NULL"):
                    contagens['operacoes_cliente_frota']=0
                    with z.open('operacoes_cliente_frota.jsonl','w') as destino:
                        async for row in conn.cursor('SELECT to_jsonb(t) AS dados FROM operacoes_cliente_frota t WHERE tenant_id=$1',claims['tenant_id'],prefetch=100):
                            linha=(row['dados']+'\n').encode()
                            total+=len(linha)
                            if total>100*1024*1024:
                                raise HTTPException(413,'Exportação excede 100 MB.')
                            destino.write(linha)
                            contagens['operacoes_cliente_frota']+=1
                z.writestr('manifesto.json',json.dumps({'tenant_id':claims['tenant_id'],
                    'exportado_em':datetime.now(timezone.utc).isoformat(),'formato':'JSON Lines UTF-8',
                    'contagens':contagens,'escopo':'Dados privados da empresa, em fotografia consistente. Fontes públicas compartilhadas não são propriedade do cliente.',
                    'modulos_nao_utilizados':[] if 'operacoes_cliente_frota' in contagens else ['operacoes_cliente_frota'],
                    'excluidos':['senhas e hashes','sessões e chaves','URLs e segredos de webhook','códigos e solicitações de recuperação','dados de outras empresas']},ensure_ascii=False))
        if arquivo.tell()>19*1024*1024:
            raise HTTPException(413,'Arquivo compactado excede 19 MB. Solicite extração administrativa assistida.')
        arquivo.seek(0)
    except BaseException:
        arquivo.close()
        raise

    def partes():
        try:
            while bloco:=arquivo.read(65536):
                yield bloco
        finally:
            arquivo.close()
    return StreamingResponse(partes(),media_type='application/zip',background=BackgroundTask(arquivo.close),
        headers={'Cache-Control':'no-store','Content-Disposition':'attachment; filename="sprain-dados-cliente.zip"'})
