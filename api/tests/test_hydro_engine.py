import pytest
import asyncpg
from app.config import settings
from app.services.hydro_engine import HydroEngine

@pytest.mark.asyncio
async def test_proporcao_intersecao_trecho_bacia():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute("DELETE FROM bacias_hidrograficas WHERE codigo_otto = 'OTTO_TESTE';")
        await conn.execute("DELETE FROM trechos_osm WHERE id_trecho = 999999;")
        
        await conn.execute("""
            INSERT INTO bacias_hidrograficas (codigo_otto, nome, area_km2, tempo_concentracao_min, geom)
            VALUES ('OTTO_TESTE', 'Bacia Teste', 1.0, 60.0, ST_Transform(ST_SetSRID(ST_GeomFromText('POLYGON((0 0, 1000 0, 1000 1000, 0 1000, 0 0))'), 31983), 4326));
        """)
        
        await conn.execute("""
            INSERT INTO trechos_osm (id_trecho, name, highway, length, source, target, geom)
            VALUES (999999, 'Via Teste Bacia', 'primary', 2000.0, 999991, 999992, ST_SetSRID(ST_GeomFromText('LINESTRING(0 500, 2000 500)'), 31983));
        """)
        
        engine = HydroEngine(conn)
        proporcoes = await engine.get_bacia_trecho_proportions(999999)
        
        assert len(proporcoes) == 1
        assert proporcoes[0]["codigo_otto"] == "OTTO_TESTE"
        assert float(proporcoes[0]["proportion"]) == 0.5000
        
    finally:
        await tx.rollback()
        await conn.close()

def test_marshall_palmer_conversion():
    engine = HydroEngine()
    assert engine.convert_dbz_to_mmh(14.0) == 0.0
    assert engine.convert_dbz_to_mmh(35.0) == 5.62
    assert engine.convert_dbz_to_mmh(45.0) == 23.68

def test_calculate_effective_rainfall():
    engine = HydroEngine()
    proporcoes = [
        {"codigo_otto": "B1", "proportion": 0.40},
        {"codigo_otto": "B2", "proportion": 0.60}
    ]
    radar_data = {
        "B1": 45.0,
        "B2": 35.0
    }
    resultado = engine.calculate_effective_rainfall(proporcoes, radar_data)
    esperado = round((23.68 * 0.40) + (5.62 * 0.60), 2)
    assert resultado == esperado