import pytest
import asyncpg
import uuid
from app.config import settings
from app.services.routing_engine import RoutingEngine


@pytest.mark.asyncio
async def test_motor_rotas_com_alertas_e_bloqueios():
    conn = await asyncpg.connect(settings.database_url)
    tenant = "demo_corp"
    id_evento = f"TESTE_BLOQUEIO_{uuid.uuid4().hex}"

    try:
        try:
            async with conn.transaction():
                RoutingEngine.clear_cache()

                orig_lon, orig_lat = -46.468, -23.542
                dest_lon, dest_lat = -46.452, -23.535

                rota_limpa = await RoutingEngine.compute_route(
                    conn, orig_lon, orig_lat, dest_lon, dest_lat,
                    "FASTEST", 0.0, "VUC", tenant
                )
                assert rota_limpa is not None
                trechos_originais = rota_limpa["ids_trechos"]
                assert trechos_originais

                await conn.execute(
                    """
                    INSERT INTO alertas_operacionais (
                        id_evento, categoria, fonte, primeira_deteccao,
                        ultima_atualizacao, expiracao_em, confianca,
                        status_evento, trechos_afetados, tenant_id, escopo
                    )
                    VALUES (
                        $1, 'TRANSITO', 'TESTE', now(), now(),
                        now() + interval '1 day', 0.99,
                        'CONFIRMADO', $2::integer[], $3, 'TENANT'
                    )
                    """,
                    id_evento, [trechos_originais[0]], tenant
                )

                RoutingEngine.clear_cache()
                rota_desviada = await RoutingEngine.compute_route(
                    conn, orig_lon, orig_lat, dest_lon, dest_lat,
                    "FASTEST", 0.0, "VUC", tenant
                )
                assert rota_desviada is not None
                assert trechos_originais[0] not in rota_desviada["ids_trechos"]

                await conn.execute(
                    """
                    UPDATE alertas_operacionais
                    SET status_evento = 'INCERTO', confianca = 0.50
                    WHERE id_evento = $1 AND tenant_id = $2
                    """,
                    id_evento, tenant
                )

                RoutingEngine.clear_cache()
                rota_penalizada = await RoutingEngine.compute_route(
                    conn, orig_lon, orig_lat, dest_lon, dest_lat,
                    "FASTEST", 0.0, "VUC", tenant
                )
                assert rota_penalizada is not None

                raise _RollbackTeste()
        except _RollbackTeste:
            pass
    finally:
        RoutingEngine.clear_cache()
        await conn.close()


class _RollbackTeste(Exception):
    """Força o rollback da transação de teste."""

