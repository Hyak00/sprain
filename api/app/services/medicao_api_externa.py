"""Reserva e registra tentativas de chamadas por empresa, sem estimar preco."""

from uuid import uuid4

from app.services.cotas_plano import verificar_cota


async def reservar_osrm(conn, tenant_id: str):
    identificador = uuid4()
    async with conn.transaction():
        await verificar_cota(conn, tenant_id, "externas")
        await conn.execute("""
            INSERT INTO chamadas_api_externa(id,tenant_id,provedor,operacao)
            VALUES($1,$2,'OSRM_DEMO','ESTIMATIVA_ROTA')
        """, identificador, tenant_id)
    return identificador


async def concluir(conn, tenant_id: str, identificador, sucesso: bool):
    await conn.execute("""
        UPDATE chamadas_api_externa
        SET status=$3,concluido_em=now()
        WHERE id=$1 AND tenant_id=$2 AND status='RESERVADA'
    """, identificador, tenant_id, "SUCESSO" if sucesso else "FALHA")
