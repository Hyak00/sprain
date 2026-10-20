import pytest
import asyncpg
from app.config import settings
from app.services.weather import WeatherService


@pytest.mark.asyncio
async def test_meteorologia_fonte_fora_do_ar_e_desatualizada():
    conn = await asyncpg.connect(settings.database_url)
    transacao = conn.transaction()
    await transacao.start()
    try:
        await conn.execute("DELETE FROM leituras_meteorologicas")
        await conn.execute("DELETE FROM estacoes_meteorologicas")
        await conn.execute("DELETE FROM fontes_meteorologicas")

        await conn.execute("""
            INSERT INTO fontes_meteorologicas (id_fonte, nome, tipo, frequencia_minutos)
            VALUES ('CGE_OFF', 'CGE Fora do Ar', 'OBSERVACAO', 30);
            INSERT INTO estacoes_meteorologicas (id_estacao, id_fonte, nome, geom)
            VALUES ('EST_OFF', 'CGE_OFF', 'Estacao Off', ST_SetSRID(ST_MakePoint(-48.17, -21.79), 4326));
        """)

        id_trecho = await conn.fetchval("SELECT id_trecho FROM trechos_osm LIMIT 1")
        ws = WeatherService(conn)

        res = await ws.obter_clima_trecho(id_trecho)
        assert res["status"] in ("INDISPONIVEL", "FORA_DE_COBERTURA")
        assert res["precipitacao_mm"] is None
    finally:
        await transacao.rollback()
        await conn.close()
