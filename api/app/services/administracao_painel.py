"""Configuração e recuperação assistida, isoladas por empresa."""
import asyncio
import json
import secrets
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException
from app.database import get_connection
from app.services.acesso_painel import proteger, resumo, hash_slots
from app.services.gestao_usuarios import _travar_empresa_e_validar_admin

SCHEMA = (Path(__file__).resolve().parents[3] / 'db/ci/13_administracao_painel.sql').read_text(encoding='utf-8')


async def garantir_schema():
    async for conn in get_connection():
        await conn.execute(SCHEMA)


async def custos_empresa(conn, tenant):
    dados = await conn.fetchval('SELECT dados FROM painel_financeiro WHERE tenant_id=$1', tenant)
    return json.loads(dados) if isinstance(dados, str) else (dados or {})


async def auditar(conn, claims, acao, alvo=None, dados=None):
    await conn.execute('''INSERT INTO painel_admin_auditoria(tenant_id,ator_id,acao,alvo_id,dados)
        VALUES($1,$2,$3,$4,$5::jsonb)''', claims['tenant_id'], UUID(claims['usuario_id']),
        acao, alvo, json.dumps(dados or {}))


async def limitar(conn, conta, ip):
    conta, ip = resumo(conta), resumo(ip)
    async with conn.transaction():
        await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))', 'recuperar:'+ip)
        await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))', 'recuperar-conta:'+conta)
        n = await conn.fetchrow('''SELECT count(*) FILTER(WHERE conta_hash=$1) AS conta,
            count(*) FILTER(WHERE ip_hash=$2) AS ip FROM painel_recuperacao_tentativas
            WHERE criado_em>now()-interval '15 minutes' AND (conta_hash=$1 OR ip_hash=$2)''', conta, ip)
        if n['conta'] >= 5 or n['ip'] >= 50:
            raise HTTPException(429, 'Aguarde antes de tentar novamente.')
        await conn.execute('INSERT INTO painel_recuperacao_tentativas(conta_hash,ip_hash) VALUES($1,$2)', conta, ip)


async def solicitar(conn, email, ip):
    email = email.strip().lower()
    await limitar(conn, email, ip)
    async with conn.transaction():
        usuario = await conn.fetchrow('SELECT id FROM painel_usuarios WHERE email=$1 AND ativo FOR UPDATE', email)
        if usuario:
            # Solicitar novamente não invalida um código já entregue nem cria uma fila duplicada.
            await conn.execute('''INSERT INTO painel_recuperacoes(id,usuario_id,expira_em)
                SELECT $1,$2,now()+interval '24 hours' WHERE NOT EXISTS (
                SELECT 1 FROM painel_recuperacoes WHERE usuario_id=$2 AND consumido_em IS NULL
                AND cancelado_em IS NULL AND expira_em>now())''', uuid4(), usuario['id'])
    return {'mensagem': 'Se houver uma conta ativa, a solicitação ficará disponível ao administrador da empresa. Contate-o para conferir sua identidade e receber um código. Nenhum e-mail automático é enviado.'}


async def liberar(conn, claims, pedido):
    async with conn.transaction():
        await _travar_empresa_e_validar_admin(conn, claims)
        alvo = await conn.fetchval('''SELECT r.usuario_id FROM painel_recuperacoes r
            JOIN painel_usuarios u ON u.id=r.usuario_id WHERE r.id=$1 AND u.tenant_id=$2''',pedido,claims['tenant_id'])
        if alvo:
            await conn.fetchrow('SELECT id FROM painel_usuarios WHERE id=$1 FOR UPDATE',alvo)
        r = await conn.fetchrow('''SELECT r.*,u.ativo FROM painel_recuperacoes r
            JOIN painel_usuarios u ON u.id=r.usuario_id
            WHERE r.id=$1 AND u.tenant_id=$2 FOR UPDATE OF r''', pedido, claims['tenant_id'])
        if not r:
            raise HTTPException(404, 'Solicitação não encontrada.')
        if not r['ativo'] or r['consumido_em'] or r['cancelado_em'] or r['liberado_em']:
            raise HTTPException(409, 'Solicitação encerrada ou já liberada.')
        valido = await conn.fetchval('SELECT $1::timestamptz>now()', r['expira_em'])
        if not valido:
            raise HTTPException(409, 'Solicitação expirada.')
        token = secrets.token_urlsafe(32)
        expira = await conn.fetchval('''UPDATE painel_recuperacoes SET token_hash=$2,
            liberado_por=$3,liberado_em=now(),expira_em=now()+interval '30 minutes'
            WHERE id=$1 RETURNING expira_em''', pedido, resumo(token), UUID(claims['usuario_id']))
        await auditar(conn, claims, 'RECUPERACAO_LIBERADA', r['usuario_id'])
    return {'codigo': token, 'expira_em': expira, 'mensagem': 'Código exibido uma única vez. Entregue somente após confirmar a identidade por um canal já conhecido.'}


async def concluir(conn, email, token, senha, ip):
    await limitar(conn, email.strip().lower(), ip)
    # Derivação limitada também para tentativas inválidas; nenhum novo acesso é concedido.
    async with hash_slots:
        senha_hash = await asyncio.to_thread(proteger, senha)
    async with conn.transaction():
        # Mesma ordem de travas do login: usuário antes de pedido.
        u = await conn.fetchrow('SELECT * FROM painel_usuarios WHERE email=$1 AND ativo FOR UPDATE', email.strip().lower())
        r = await conn.fetchrow('''SELECT * FROM painel_recuperacoes WHERE token_hash=$1
            AND usuario_id=$2 AND expira_em>now() AND consumido_em IS NULL AND cancelado_em IS NULL
            FOR UPDATE''', resumo(token), u['id']) if u else None
        if not r:
            raise HTTPException(400, 'Código inválido, expirado ou já utilizado.')
        await conn.execute('UPDATE painel_usuarios SET senha_hash=$2,atualizado_em=now() WHERE id=$1', u['id'], senha_hash)
        await conn.execute('UPDATE painel_sessoes SET revogado_em=now() WHERE usuario_id=$1 AND revogado_em IS NULL', u['id'])
        await conn.execute('UPDATE painel_recuperacoes SET consumido_em=now() WHERE id=$1', r['id'])
        await conn.execute('''UPDATE painel_recuperacoes SET cancelado_em=now() WHERE usuario_id=$1
            AND id<>$2 AND consumido_em IS NULL AND cancelado_em IS NULL''', u['id'], r['id'])
        await auditar(conn, {'tenant_id':u['tenant_id'],'usuario_id':str(u['id'])}, 'ACESSO_RECUPERADO', u['id'])
    return {'mensagem': 'Senha atualizada. As sessões anteriores foram encerradas. Entre com a nova senha.'}
