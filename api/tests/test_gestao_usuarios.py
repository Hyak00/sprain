"""Gestao de usuarios: permissoes, isolamento e revogacao transacional."""

from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from fastapi import FastAPI, HTTPException

from app.config import settings
from app.database import get_connection
from app.routers.gestao_usuarios import exigir_admin_individual, router
from app.seguranca import get_current_user_claims
from app.services.acesso_painel import SCHEMA, resumo


def test_chave_compartilhada_e_visualizador_nao_gerem_usuarios():
    for claims in (
        {'tenant_id': 'empresa_a', 'role': 'ADMIN'},
        {'tenant_id': 'empresa_a', 'role': 'VIEWER', 'usuario_id': str(uuid4())},
    ):
        with pytest.raises(HTTPException) as erro:
            exigir_admin_individual(claims)
        assert erro.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_so_gerencia_sua_empresa_e_revoga_sessoes():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    sufixo = uuid4().hex
    tenant_a, tenant_b = 'gestao_a_' + sufixo, 'gestao_b_' + sufixo
    admin_a, admin_b, usuario_b = uuid4(), uuid4(), uuid4()
    claims = {'tenant_id': tenant_a, 'role': 'ADMIN', 'usuario_id': str(admin_a)}
    app = FastAPI()
    app.include_router(router)

    async def identidade():
        return claims

    async def conexao():
        yield conn

    app.dependency_overrides[get_current_user_claims] = identidade
    app.dependency_overrides[get_connection] = conexao
    try:
        await conn.execute(SCHEMA)
        for uid, email, empresa, tenant, papel in (
            (admin_a, f'admin-a-{sufixo}@example.test', 'Empresa A', tenant_a, 'ADMIN'),
            (admin_b, f'admin-b-{sufixo}@example.test', 'Empresa B', tenant_b, 'ADMIN'),
            (usuario_b, f'usuario-b-{sufixo}@example.test', 'Empresa B', tenant_b, 'VIEWER'),
        ):
            await conn.execute(
                '''INSERT INTO painel_usuarios
                   (id, email, empresa, tenant_id, papel, senha_hash)
                   VALUES ($1, $2, $3, $4, $5, 'hash-de-teste')''',
                uid, email, empresa, tenant, papel,
            )
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://teste') as cli:
            lista = await cli.get('/api/v1/acesso/usuarios')
            assert lista.status_code == 200
            assert lista.headers['cache-control'] == 'no-store'
            assert lista.json()['total'] == 1
            assert [u['id'] for u in lista.json()['usuarios']] == [str(admin_a)]
            assert 'senha_hash' not in lista.text

            senha = 'Senha longa somente para teste ' + sufixo
            criado = await cli.post('/api/v1/acesso/usuarios', json={
                'email': f'NOVO-{sufixo}@EXAMPLE.TEST', 'senha': senha, 'papel': 'OPERATOR',
            })
            assert criado.status_code == 201, criado.text
            assert senha not in criado.text
            novo_id = criado.json()['id']
            novo_uuid = UUID(novo_id)
            assert await conn.fetchval(
                'SELECT empresa FROM painel_usuarios WHERE id=$1 AND tenant_id=$2',
                novo_uuid, tenant_a,
            ) == 'Empresa A'

            for caminho, metodo, dados in (
                (f'/api/v1/acesso/usuarios/{usuario_b}/papel', 'patch', {'papel': 'ADMIN'}),
                (f'/api/v1/acesso/usuarios/{usuario_b}/desativar', 'post', None),
            ):
                r = await getattr(cli, metodo)(caminho, json=dados) if dados else await getattr(cli, metodo)(caminho)
                assert r.status_code == 404
            assert await conn.fetchval('SELECT ativo FROM painel_usuarios WHERE id=$1', usuario_b)

            assert (await cli.patch(f'/api/v1/acesso/usuarios/{admin_a}/papel',
                                    json={'papel': 'VIEWER'})).status_code == 409
            assert (await cli.post(f'/api/v1/acesso/usuarios/{admin_a}/desativar')).status_code == 409

            token = 'sessao-de-teste-' + sufixo
            await conn.execute(
                '''INSERT INTO painel_sessoes(token_hash, usuario_id, expira_em)
                   VALUES($1, $2, now()+interval '1 hour')''', resumo(token), novo_uuid,
            )
            alterado = await cli.patch(f'/api/v1/acesso/usuarios/{novo_id}/papel',
                                       json={'papel': 'VIEWER'})
            assert alterado.status_code == 200
            assert await conn.fetchval(
                'SELECT revogado_em IS NOT NULL FROM painel_sessoes WHERE token_hash=$1', resumo(token)
            )
            desativado = await cli.post(f'/api/v1/acesso/usuarios/{novo_id}/desativar')
            assert desativado.status_code == 200
            assert not await conn.fetchval('SELECT ativo FROM painel_usuarios WHERE id=$1', novo_uuid)
            trilha = await cli.get('/api/v1/acesso/usuarios/auditoria')
            assert trilha.status_code == 200
            assert [item['acao'] for item in trilha.json()] == [
                'DESATIVADO', 'PAPEL_ALTERADO', 'CRIADO'
            ]

            claims.clear()
            claims.update({'tenant_id': tenant_b, 'role': 'ADMIN', 'usuario_id': str(admin_b)})
            outra_lista = await cli.get('/api/v1/acesso/usuarios')
            assert outra_lista.status_code == 200
            assert outra_lista.json()['total'] == 2
            assert all(u['empresa'] == 'Empresa B' for u in outra_lista.json()['usuarios'])
            assert (await cli.get('/api/v1/acesso/usuarios/auditoria')).json() == []

            claims.clear()
            claims.update({'tenant_id': tenant_a, 'role': 'ADMIN'})
            assert (await cli.get('/api/v1/acesso/usuarios')).status_code == 403

            claims['usuario_id'] = str(admin_b)
            forjado = await cli.post('/api/v1/acesso/usuarios', json={
                'email': f'forjado-{sufixo}@example.test',
                'senha': 'Senha longa somente para teste ' + sufixo,
                'papel': 'ADMIN',
            })
            assert forjado.status_code == 403
            assert not await conn.fetchval(
                'SELECT 1 FROM painel_usuarios WHERE email=$1', f'forjado-{sufixo}@example.test'
            )
    finally:
        await tx.rollback()
        await conn.close()
