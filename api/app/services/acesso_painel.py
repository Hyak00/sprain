"""Acesso individual opcional; chaves das integracoes continuam independentes."""
import asyncio
import hashlib
import secrets
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from app.database import get_connection

PREFIXO = 'sprain_session_'
SCHEMA = (Path(__file__).resolve().parents[3]/'db/ci/11_acesso_painel.sql').read_text(encoding='utf-8')
hash_slots = asyncio.Semaphore(2)


def resumo(valor):
    return hashlib.sha256(valor.encode()).hexdigest()


def proteger(senha, sal=None):
    sal = sal or secrets.token_hex(16)
    resultado = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal), n=2**17, r=8, p=1,
                              maxmem=256*1024*1024, dklen=32)
    return 'scrypt$'+sal+'$'+resultado.hex()


def conferir(senha, registro):
    try:
        algoritmo, sal, _ = registro.split('$')
        return algoritmo == 'scrypt' and secrets.compare_digest(proteger(senha,sal),registro)
    except (ValueError, TypeError):
        return False


async def garantir_schema():
    async for conn in get_connection():
        await conn.execute(SCHEMA)


async def autenticar(conn, email, senha, ip):
    conta, endereco = resumo(email), resumo(ip)
    # Serializa a contabilizacao por IP; nao confia em X-Forwarded-For enviado pelo cliente.
    async with conn.transaction():
        await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))', 'login-conta:'+conta)
        await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))', 'login:'+endereco)
        n = await conn.fetchrow('''SELECT count(*) FILTER(WHERE conta_hash=$1) AS conta,
            count(*) FILTER(WHERE ip_hash=$2) AS ip FROM painel_login_tentativas
            WHERE criado_em>now()-interval '15 minutes' AND (conta_hash=$1 OR ip_hash=$2)''',conta,endereco)
        if n['conta']>=10 or n['ip']>=100:
            raise HTTPException(429,'Muitas tentativas. Aguarde antes de entrar novamente.')
        await conn.execute('INSERT INTO painel_login_tentativas(conta_hash,ip_hash) VALUES($1,$2)',conta,endereco)
    usuario = await conn.fetchrow('SELECT * FROM painel_usuarios WHERE email=$1',email)
    # Mesmo trabalho criptografico para conta inexistente; nao revelar cadastro.
    registro = usuario['senha_hash'] if usuario else 'scrypt$'+'00'*16+'$'+'00'*32
    async with hash_slots:
        valido = await asyncio.to_thread(conferir,senha,registro)
    if not usuario or not usuario['ativo'] or not valido:
        raise HTTPException(401,'E-mail ou senha invalidos.')
    token = PREFIXO+secrets.token_urlsafe(32)
    async with conn.transaction():
        atual=await conn.fetchrow('SELECT * FROM painel_usuarios WHERE id=$1 FOR UPDATE',usuario['id'])
        if not atual['ativo'] or atual['senha_hash']!=registro:
            raise HTTPException(401,'E-mail ou senha invalidos.')
        validade=await conn.fetchval('''INSERT INTO painel_sessoes(token_hash,usuario_id,expira_em)
            VALUES($1,$2,now()+interval '8 hours') RETURNING expira_em''',resumo(token),atual['id'])
    return {'autenticado':True,'api_key':token,'email':atual['email'],'empresa':atual['empresa'],
            'tenant_id':atual['tenant_id'],'role':atual['papel'],'usuario_id':str(atual['id']),
            'expira_em':validade.isoformat(),'tipo_acesso':'INDIVIDUAL'}


async def claims_sessao(token):
    async for conn in get_connection():
        row=await conn.fetchrow('''SELECT u.id,u.email,u.tenant_id,u.papel FROM painel_sessoes s
            JOIN painel_usuarios u ON u.id=s.usuario_id WHERE s.token_hash=$1 AND u.ativo
            AND s.revogado_em IS NULL AND s.expira_em>now()''',resumo(token))
    if not row:
        raise HTTPException(401,'Sessao expirada ou revogada.')
    return {'usuario_id':str(row['id']),'email':row['email'],'tenant_id':row['tenant_id'],'role':row['papel']}


async def cadastrar(conn,email,senha,empresa,tenant,papel):
    if papel not in ('ADMIN','OPERATOR','VIEWER') or not tenant.strip() or not empresa.strip():
        raise ValueError('Empresa, tenant e papel validos sao obrigatorios.')
    if '@' not in email or len(email)>254 or not 15<=len(senha)<=256:
        raise ValueError('Informe e-mail valido e senha de 15 a 256 caracteres.')
    protegido=await asyncio.to_thread(proteger,senha)
    # Criacao administrativa explicita. Conta existente nao e sobrescrita silenciosamente.
    return await conn.fetchval('''INSERT INTO painel_usuarios(id,email,empresa,tenant_id,papel,senha_hash)
        VALUES($1,$2,$3,$4,$5,$6) RETURNING id''',uuid4(),email.strip().lower(),empresa.strip(),tenant.strip(),papel,protegido)
