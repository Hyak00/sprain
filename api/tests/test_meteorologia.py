import pytest
import asyncpg
from app.config import settings
from app.services.weather import WeatherService

@pytest.mark.asyncio
async def test_clima_valida_regras():
    conn = await asyncpg.connect(settings.database_url)
    transaction = conn.transaction()
    await transaction.start()
    try:
        await conn.execute("DELETE FROM leituras_meteorologicas")
        await conn.execute("DELETE FROM estacoes_meteorologicas")
        await conn.execute("DELETE FROM fontes_meteorologicas")
        
        await conn.execute("""
            INSERT INTO fontes_meteorologicas (id_fonte, nome, tipo, frequencia_minutos) 
            VALUES ('CGE', 'CGE SP', 'OBSERVACAO', 60);
            INSERT INTO estacoes_meteorologicas (id_estacao, id_fonte, nome, geom)
            VALUES ('CGE_ITAQUERA', 'CGE', 'Itaquera', ST_SetSRID(ST_MakePoint(-46.468, -23.542), 4326));
        """)
        
        id_trecho = await conn.fetchval("SELECT id_trecho FROM trechos_osm LIMIT 1")
        ws = WeatherService(conn)
        
        # Teste 1: Estacao ativa sem leituras
        res1 = await ws.obter_clima_trecho(id_trecho)
        assert res1["status"] == "INDISPONIVEL"
        
        # Teste 2: Fonte desatualizada 
        await conn.execute("""
            INSERT INTO leituras_meteorologicas (id_estacao, data_referencia, precipitacao_mm)
            VALUES ('CGE_ITAQUERA', now() - interval '180 minutes', 50.0)
        """)
        res2 = await ws.obter_clima_trecho(id_trecho)
        assert res2["status"] == "DESATUALIZADO"
        assert res2["precipitacao_mm"] is None
        assert "motivo_indisponivel" in res2
        
        # Teste 3: Observacao valida
        await conn.execute("""
            INSERT INTO leituras_meteorologicas (id_estacao, data_referencia, precipitacao_mm)
            VALUES ('CGE_ITAQUERA', now() - interval '10 minutes', 65.5)
        """)
        res3 = await ws.obter_clima_trecho(id_trecho)
        assert res3["status"] == "VALIDO"
        assert res3["precipitacao_mm"] == 65.5
        
        # Teste 4: Registro historico gravado
        historico_antes = await conn.fetchval("SELECT count(*) FROM historico_avaliacoes_risco")
        await ws.registrar_avaliacao_risco(id_trecho, res3["precipitacao_mm"], "CRITICO", res3["fonte"], res3["idade_minutos"], "v1.0")
        hist = await conn.fetchval("SELECT count(*) FROM historico_avaliacoes_risco")
          assert hist == historico_antes + 1
    finally:
        await transaction.rollback()
        await conn.close()
