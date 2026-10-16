"""Provisiona um acesso individual no banco configurado, sem senha em argumentos/logs.

Dentro do container: python /app/scripts/cadastrar_acesso_painel.py --email ... --empresa ... --tenant ... --papel VIEWER
"""
import argparse
import asyncio
import getpass
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'api'))
from app.database import init_db_pool,close_db_pool,get_connection
from app.services.acesso_painel import garantir_schema,cadastrar


async def main():
    p=argparse.ArgumentParser(description=__doc__)
    for campo in ('email','empresa','tenant'):p.add_argument('--'+campo,required=True)
    p.add_argument('--papel',choices=['ADMIN','OPERATOR','VIEWER'],required=True)
    a=p.parse_args()
    senha=getpass.getpass('Senha (minimo 15 caracteres): ')
    if senha!=getpass.getpass('Confirme a senha: '):raise SystemExit('As senhas nao coincidem.')
    await init_db_pool()
    try:
        await garantir_schema()
        async for conn in get_connection():
            await cadastrar(conn,a.email,senha,a.empresa,a.tenant,a.papel)
        print('Acesso individual criado. Nenhuma senha ou sessao foi exibida.')
    finally:await close_db_pool()


if __name__=='__main__':asyncio.run(main())
