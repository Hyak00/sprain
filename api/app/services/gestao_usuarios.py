"""Gestao de identidades dentro da empresa autenticada."""

import asyncio
from uuid import UUID, uuid4

import asyncpg
from fastapi import HTTPException

from app.services.acesso_painel import proteger
from app.services.cotas_plano import verificar_cota


async def _travar_empresa_e_validar_admin(conn, claims):
    tenant_id = claims['tenant_id']
    ator_id = UUID(claims['usuario_id'])
    await conn.execute(
        'SELECT pg_advisory_xact_lock(hashtextextended($1, 0))',
        'gestao-usuarios:' + tenant_id,
    )
    ator = await conn.fetchrow(
        'SELECT id, empresa, tenant_id, papel, ativo FROM painel_usuarios WHERE id=$1 FOR UPDATE',
        ator_id,
    )
    if not ator or not ator['ativo'] or ator['papel'] != 'ADMIN' or ator['tenant_id'] != tenant_id:
        raise HTTPException(403, 'Sessão ADMIN inválida para esta empresa.')
    return ator


async def listar(conn, claims, limit, offset):
    tenant_id = claims['tenant_id']
    total = await conn.fetchval(
        'SELECT count(*) FROM painel_usuarios WHERE tenant_id=$1', tenant_id
    )
    rows = await conn.fetch(
        '''SELECT id, email, empresa, papel, ativo, atualizado_em
           FROM painel_usuarios WHERE tenant_id=$1
           ORDER BY email, id LIMIT $2 OFFSET $3''',
        tenant_id, limit, offset,
    )
    return {
        'total': total,
        'limit': limit,
        'offset': offset,
        'usuarios': [
            {**dict(row), 'id': str(row['id'])} for row in rows
        ],
    }


async def criar(conn, claims, email, senha, papel):
    email = email.strip().lower()
    if '@' not in email or email.startswith('@') or email.endswith('@'):
        raise HTTPException(422, 'E-mail inválido.')
    senha_hash = await asyncio.to_thread(proteger, senha)
    usuario_id = uuid4()
    try:
        async with conn.transaction():
            ator = await _travar_empresa_e_validar_admin(conn, claims)
            await verificar_cota(conn, claims['tenant_id'], 'usuarios')
            await conn.execute(
                '''INSERT INTO painel_usuarios
                   (id, email, empresa, tenant_id, papel, senha_hash)
                   VALUES ($1, $2, $3, $4, $5, $6)''',
                usuario_id, email, ator['empresa'], claims['tenant_id'], papel, senha_hash,
            )
            await conn.execute(
                '''INSERT INTO painel_usuarios_auditoria
                   (tenant_id, ator_id, usuario_id, acao, papel_novo)
                   VALUES ($1, $2, $3, 'CRIADO', $4)''',
                claims['tenant_id'], ator['id'], usuario_id, papel,
            )
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(409, 'Não foi possível cadastrar este usuário.') from exc
    return {'id': str(usuario_id), 'email': email, 'empresa': ator['empresa'],
            'papel': papel, 'ativo': True}


async def alterar_papel(conn, claims, usuario_id, papel):
    async with conn.transaction():
        ator = await _travar_empresa_e_validar_admin(conn, claims)
        alvo = await conn.fetchrow(
            '''SELECT id, email, papel, ativo FROM painel_usuarios
               WHERE id=$1 AND tenant_id=$2 FOR UPDATE''',
            usuario_id, claims['tenant_id'],
        )
        if not alvo:
            raise HTTPException(404, 'Usuário não encontrado.')
        if alvo['id'] == ator['id']:
            raise HTTPException(409, 'Use outro administrador para alterar seu próprio acesso.')
        if not alvo['ativo']:
            raise HTTPException(409, 'Usuário desativado não pode mudar de papel.')
        if alvo['papel'] == papel:
            return {'id': str(usuario_id), 'papel': papel, 'alterado': False}
        if alvo['papel'] == 'ADMIN':
            restantes = await conn.fetchval(
                '''SELECT count(*) FROM painel_usuarios
                   WHERE tenant_id=$1 AND papel='ADMIN' AND ativo AND id<>$2''',
                claims['tenant_id'], usuario_id,
            )
            if not restantes:
                raise HTTPException(409, 'A empresa precisa manter um administrador ativo.')
        await conn.execute(
            '''UPDATE painel_usuarios SET papel=$1, atualizado_em=now()
               WHERE id=$2 AND tenant_id=$3''',
            papel, usuario_id, claims['tenant_id'],
        )
        await conn.execute(
            '''UPDATE painel_sessoes SET revogado_em=now()
               WHERE usuario_id=$1 AND revogado_em IS NULL''', usuario_id,
        )
        await conn.execute(
            '''INSERT INTO painel_usuarios_auditoria
               (tenant_id, ator_id, usuario_id, acao, papel_anterior, papel_novo)
               VALUES ($1, $2, $3, 'PAPEL_ALTERADO', $4, $5)''',
            claims['tenant_id'], ator['id'], usuario_id, alvo['papel'], papel,
        )
    return {'id': str(usuario_id), 'papel': papel, 'alterado': True}


async def desativar(conn, claims, usuario_id):
    async with conn.transaction():
        ator = await _travar_empresa_e_validar_admin(conn, claims)
        alvo = await conn.fetchrow(
            '''SELECT id, papel, ativo FROM painel_usuarios
               WHERE id=$1 AND tenant_id=$2 FOR UPDATE''',
            usuario_id, claims['tenant_id'],
        )
        if not alvo:
            raise HTTPException(404, 'Usuário não encontrado.')
        if alvo['id'] == ator['id']:
            raise HTTPException(409, 'Não é possível desativar a própria conta.')
        if not alvo['ativo']:
            return {'id': str(usuario_id), 'ativo': False, 'alterado': False}
        if alvo['papel'] == 'ADMIN':
            restantes = await conn.fetchval(
                '''SELECT count(*) FROM painel_usuarios
                   WHERE tenant_id=$1 AND papel='ADMIN' AND ativo AND id<>$2''',
                claims['tenant_id'], usuario_id,
            )
            if not restantes:
                raise HTTPException(409, 'A empresa precisa manter um administrador ativo.')
        await conn.execute(
            '''UPDATE painel_usuarios SET ativo=false, atualizado_em=now()
               WHERE id=$1 AND tenant_id=$2''', usuario_id, claims['tenant_id'],
        )
        await conn.execute(
            '''UPDATE painel_sessoes SET revogado_em=now()
               WHERE usuario_id=$1 AND revogado_em IS NULL''', usuario_id,
        )
        await conn.execute(
            '''INSERT INTO painel_usuarios_auditoria
               (tenant_id, ator_id, usuario_id, acao, papel_anterior)
               VALUES ($1, $2, $3, 'DESATIVADO', $4)''',
            claims['tenant_id'], ator['id'], usuario_id, alvo['papel'],
        )
    return {'id': str(usuario_id), 'ativo': False, 'alterado': True}


async def listar_auditoria(conn, claims, limit, offset):
    rows = await conn.fetch(
        '''SELECT id, ator_id, usuario_id, acao, papel_anterior, papel_novo, criado_em
           FROM painel_usuarios_auditoria WHERE tenant_id=$1
           ORDER BY criado_em DESC, id DESC LIMIT $2 OFFSET $3''',
        claims['tenant_id'], limit, offset,
    )
    return [{**dict(row), 'ator_id': str(row['ator_id']),
             'usuario_id': str(row['usuario_id'])} for row in rows]
