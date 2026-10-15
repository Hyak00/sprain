import pytest
import asyncpg
from app.config import settings
from app.services.routing_engine import RoutingEngine

@pytest.mark.asyncio
async def test_motor_rotas_com_alertas_e_bloqueios():
    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute("UPDATE alertas_operacionais SET expiracao_em = now() - interval '1 day'")
        RoutingEngine.clear_cache()
        
        orig_lon, orig_lat = -46.468, -23.542
        dest_lon, dest_lat = -46.452, -23.535
        
        rota_limpa = await RoutingEngine.compute_route(conn, orig_lon, orig_lat, dest_lon, dest_lat, "FASTEST", 0.0, "VUC", "demo_corp")
        assert rota_limpa is not None
        trechos_originais = rota_limpa["ids_trechos"]
        
        await conn.execute("INSERT INTO alertas_operacionais (id_evento, categoria, fonte, primeira_deteccao, ultima_atualizacao, expiracao_em, confianca, status_evento, trechos_afetados) VALUES ('TESTE_BLOQUEIO', 'TRANSITO', 'TESTE', now(), now(), now() + interval '1 day', 0.99, 'CONFIRMADO', ARRAY[$1::integer])", trechos_originais[0])
        RoutingEngine.clear_cache()
        
        rota_desviada = await RoutingEngine.compute_route(conn, orig_lon, orig_lat, dest_lon, dest_lat, "FASTEST", 0.0, "VUC", "demo_corp")
        assert rota_desviada is not None
        assert trechos_originais[0] not in rota_desviada["ids_trechos"]
        
        await conn.execute("UPDATE alertas_operacionais SET status_evento = 'INCERTO', confianca = 0.50 WHERE id_evento = 'TESTE_BLOQUEIO'")
        RoutingEngine.clear_cache()
        
        rota_penalizada = await RoutingEngine.compute_route(conn, orig_lon, orig_lat, dest_lon, dest_lat, "FASTEST", 0.0, "VUC", "demo_corp")
        assert rota_penalizada is not None
        
    finally:
        await conn.execute("DELETE FROM alertas_operacionais WHERE id_evento = 'TESTE_BLOQUEIO'")
        await conn.close()