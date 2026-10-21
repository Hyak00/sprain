"""Contas sintéticas exclusivamente para compose.e2e.yml; nunca para clientes."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'api'))
from app.config import settings
from app.database import init_db_pool,close_db_pool,get_connection
from app.services.acesso_painel import cadastrar,resumo
from app.services.demonstracao import preparar

SENHA_TESTE='Apenas-Teste-Isolado-2026!'


async def main():
    if settings.ambiente_atual!='testing' or settings.DB_NAME!='sprain_demo':
        raise SystemExit('Seed permitido somente em testing no banco reservado sprain_demo.')
    await init_db_pool()
    try:
        async for conn in get_connection():
            if await conn.fetchval('SELECT current_database()')!='sprain_demo':
                raise SystemExit('Banco conectado incorreto; nenhuma conta criada.')
            async with conn.transaction():
                for nome,papel,tenant in [('admin','ADMIN','demo_corp'),('operador','OPERATOR','demo_corp'),('leitor','VIEWER','demo_corp'),('outra','ADMIN','log_express')]:
                    email=nome+'@e2e.invalid'
                    existente=await conn.fetchrow('SELECT tenant_id,papel FROM painel_usuarios WHERE email=$1',email)
                    if existente:
                        if existente['tenant_id']!=tenant or existente['papel']!=papel:
                            raise RuntimeError('Conta de teste existente incompatível; nenhum acesso sobrescrito.')
                    else:await cadastrar(conn,email,SENHA_TESTE,'TRANSPORTADORA SINTÉTICA E2E DE CARGAS E DISTRIBUIÇÃO REGIONAL',tenant,papel)
                await preparar(conn,'demo_corp')
                # Reinicia apenas a medição sintética reservada para o teste de onboarding.
                await conn.execute("DELETE FROM painel_onboarding WHERE tenant_id='demo_corp'")
                # Fixture reservada: permite repetir a suíte local sem esgotar o
                # limite de login das quatro contas sintéticas. Regra da API intacta.
                await conn.execute('DELETE FROM painel_login_tentativas WHERE conta_hash=ANY($1::text[])',
                    [resumo(nome+'@e2e.invalid') for nome in ('admin','operador','leitor','outra')])
            print('Fixtures sintéticas preparadas no banco exclusivo de E2E.')
    finally:await close_db_pool()


if __name__=='__main__':asyncio.run(main())
