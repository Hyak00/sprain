"""Recuperação assistida quando nenhum ADMIN consegue entrar.

Executar em terminal confiável no servidor, após conferir a identidade.
Não recebe nem imprime senha; exibe somente um código temporário de uso único.
"""
import argparse
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'api'))
from app.database import init_db_pool, close_db_pool, get_connection
from app.services.administracao_painel import garantir_schema, liberar


async def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--email',required=True)
    p.add_argument('--tenant',required=True)
    p.add_argument('--identidade-conferida',action='store_true',required=True)
    a=p.parse_args()
    await init_db_pool()
    try:
        await garantir_schema()
        async for conn in get_connection():
            async with conn.transaction():
                await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))','gestao-usuarios:'+a.tenant)
                u=await conn.fetchrow('''SELECT id FROM painel_usuarios
                    WHERE email=$1 AND tenant_id=$2 AND ativo AND papel='ADMIN' FOR UPDATE''',a.email.strip().lower(),a.tenant)
                if not u:
                    raise SystemExit('ADMIN ativo não encontrado nesta empresa. Nenhum acesso foi alterado.')
                await conn.execute('''UPDATE painel_recuperacoes SET cancelado_em=now()
                    WHERE usuario_id=$1 AND consumido_em IS NULL AND cancelado_em IS NULL''',u['id'])
                pedido=uuid4()
                await conn.execute('''INSERT INTO painel_recuperacoes(id,usuario_id,expira_em)
                    VALUES($1,$2,now()+interval '24 hours')''',pedido,u['id'])
                r=await liberar(conn,{'usuario_id':str(u['id']),'tenant_id':a.tenant,'role':'ADMIN'},pedido)
        print('Entregue em particular; válido até '+r['expira_em'].isoformat())
        print(r['codigo'])
        print('Use Recuperar acesso na tela de entrada. Não registre este código em logs ou chamados.')
    finally:
        await close_db_pool()


if __name__=='__main__':
    asyncio.run(main())
