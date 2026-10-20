import pytest
import asyncpg
import httpx
from fastapi import FastAPI
from app.config import settings
from app.database import get_connection
from app.routers.rotas import router


@pytest.mark.asyncio
async def test_corredor_com_chuva_critica_recomenda_desvio_e_roi_positivo():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute("""
            INSERT INTO condicoes_corredor (id_trecho, status_pista, precipitacao_mm_h, fator_atraso, atualizado_em)
            VALUES (1, 'LIBERADA', 2.0, 1.0, now()),
                   (2, 'LIBERADA', 10.0, 1.15, now()),
                   (3, 'RISCO_CRITICO_ALAGAMENTO', 65.0, 2.5, now()),
                   (4, 'LIBERADA', 0.0, 1.0, now()),
                   (5, 'LIBERADA', 0.0, 1.0, now()),
                   (6, 'LIBERADA', 0.0, 1.0, now())
            ON CONFLICT (id_trecho) DO UPDATE
            SET status_pista = EXCLUDED.status_pista,
                precipitacao_mm_h = EXCLUDED.precipitacao_mm_h,
                fator_atraso = EXCLUDED.fator_atraso,
                atualizado_em = EXCLUDED.atualizado_em;
        """)

        app = FastAPI()
        app.include_router(router)

        async def conexao():
            yield conn

        app.dependency_overrides[get_connection] = conexao

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "key_admin_demo"}) as cliente:
            resp = await cliente.get("/api/v1/rotas/intermunicipal", params={"origem": "Araraquara", "destino": "Sao Paulo", "tipo_veiculo": "TRUCK_3_EIXOS"})
            assert resp.status_code == 200
            corpo = resp.json()
            decisao = corpo["decisao_logistica"]
            assert decisao["recomendacao"] == "DESVIAR"
            assert decisao["desvio"] == "CONTORNO_RODOVIAS_PARALELAS"
            assert len(decisao["trechos_criticos"]) > 0
            financeiro = decisao["analise_financeira"]
            assert financeiro["beneficio_liquido_reais"] > 0
            assert financeiro["roi_positivo"] is True
            assert financeiro["custo_diesel_adicional_reais"] > 0
            assert financeiro["economia_tempo_reais"] > 0

        registros = await conn.fetchval("SELECT count(*) FROM historico_avaliacoes_risco WHERE regra_versao = 'v1.1'")
        assert registros >= 6
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_corredor_com_tempo_limpo_mantem_rota_sem_desvio():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute("""
            INSERT INTO condicoes_corredor (id_trecho, status_pista, precipitacao_mm_h, fator_atraso, atualizado_em)
            VALUES (1, 'LIBERADA', 0.0, 1.0, now()),
                   (2, 'LIBERADA', 1.0, 1.0, now()),
                   (3, 'LIBERADA', 2.0, 1.0, now()),
                   (4, 'LIBERADA', 0.0, 1.0, now()),
                   (5, 'LIBERADA', 0.0, 1.0, now()),
                   (6, 'LIBERADA', 0.0, 1.0, now())
            ON CONFLICT (id_trecho) DO UPDATE
            SET status_pista = EXCLUDED.status_pista,
                precipitacao_mm_h = EXCLUDED.precipitacao_mm_h,
                fator_atraso = EXCLUDED.fator_atraso,
                atualizado_em = EXCLUDED.atualizado_em;
        """)

        app = FastAPI()
        app.include_router(router)

        async def conexao():
            yield conn

        app.dependency_overrides[get_connection] = conexao

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "key_admin_demo"}) as cliente:
            resp = await cliente.get("/api/v1/rotas/intermunicipal", params={"origem": "Araraquara", "destino": "Sao Paulo", "tipo_veiculo": "VUC"})
            assert resp.status_code == 200
            corpo = resp.json()
            decisao = corpo["decisao_logistica"]
            assert decisao["recomendacao"] == "INDISPONIVEL"
            assert decisao["desvio"] is None
            assert decisao["motivo_indisponivel"] == "Sem risco de alagamento calculado para o corredor, nao ha base para sugerir desvio."
            assert decisao["analise_financeira"]["beneficio_liquido_reais"] is None
            assert decisao["analise_financeira"]["roi_positivo"] is None
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_corredor_sem_dados_recentes_permanece_indisponivel():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute("DELETE FROM condicoes_corredor;")

        app = FastAPI()
        app.include_router(router)

        async def conexao():
            yield conn

        app.dependency_overrides[get_connection] = conexao

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "key_admin_demo"}) as cliente:
            resp = await cliente.get("/api/v1/rotas/intermunicipal", params={"origem": "Araraquara", "destino": "Sao Paulo", "tipo_veiculo": "CARRETA_5_EIXOS"})
            assert resp.status_code == 200
            corpo = resp.json()
            decisao = corpo["decisao_logistica"]
            assert decisao["recomendacao"] == "INDISPONIVEL"
            assert decisao["desvio"] is None
            assert decisao["analise_financeira"]["beneficio_liquido_reais"] is None
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_corredor_com_calibracao_de_tempo_retorna_eta_e_atraso():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute("""
            INSERT INTO condicoes_corredor (id_trecho, status_pista, precipitacao_mm_h, fator_atraso, atualizado_em)
            VALUES (1, 'LIBERADA', 0.0, 1.0, now()),
                   (2, 'LIBERADA', 10.0, 1.15, now()),
                   (3, 'LIBERADA', 0.0, 1.0, now()),
                   (4, 'LIBERADA', 0.0, 1.0, now()),
                   (5, 'LIBERADA', 0.0, 1.0, now()),
                   (6, 'LIBERADA', 0.0, 1.0, now())
            ON CONFLICT (id_trecho) DO UPDATE
            SET status_pista = EXCLUDED.status_pista,
                precipitacao_mm_h = EXCLUDED.precipitacao_mm_h,
                fator_atraso = EXCLUDED.fator_atraso,
                atualizado_em = EXCLUDED.atualizado_em;
        """)

        app = FastAPI()
        app.include_router(router)

        async def conexao():
            yield conn

        app.dependency_overrides[get_connection] = conexao

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "key_admin_demo"}) as cliente:
            resp = await cliente.get("/api/v1/rotas/intermunicipal", params={"origem": "Araraquara", "destino": "Sao Paulo", "tipo_veiculo": "TRUCK_3_EIXOS", "calibrar_tempo": "true"})
            assert resp.status_code == 200
            corpo = resp.json()
            resumo = corpo["resumo"]
            assert resumo["tempo_nominal_min"] is not None
            assert resumo["tempo_nominal_min"] > 180.0
            assert resumo["tempo_real_estimado_min"] is not None
            assert resumo["tempo_real_estimado_min"] >= resumo["tempo_nominal_min"]
            assert resumo["atraso_climatico_min"] is not None
            assert resumo["atraso_climatico_min"] >= 0.0
            for seg in corpo["segmentos"]:
                assert seg["tempo_nominal_min"] is not None
                assert seg["tempo_nominal_min"] > 0
                assert seg["tempo_real_min"] is not None
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_corredor_com_tarifas_artesp_calcula_pedagios_por_eixo():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    try:
        app = FastAPI()
        app.include_router(router)

        async def conexao():
            yield conn

        app.dependency_overrides[get_connection] = conexao

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "key_admin_demo"}) as cliente:
            resp_truck = await cliente.get("/api/v1/rotas/intermunicipal", params={"origem": "Araraquara", "destino": "Sao Paulo", "tipo_veiculo": "TRUCK_3_EIXOS", "incluir_tarifas_artesp": "true"})
            assert resp_truck.status_code == 200
            corpo_truck = resp_truck.json()
            pedagios_truck = corpo_truck["pedagios"]
            assert pedagios_truck["quantidade_pracas"] == 5
            assert pedagios_truck["custo_total_pedagio_reais"] == 141.30
            assert pedagios_truck["cobertura_completa"] is False

            resp_vuc = await cliente.get("/api/v1/rotas/intermunicipal", params={"origem": "Araraquara", "destino": "Sao Paulo", "tipo_veiculo": "VUC", "incluir_tarifas_artesp": "true"})
            assert resp_vuc.status_code == 200
            corpo_vuc = resp_vuc.json()
            assert corpo_vuc["pedagios"]["custo_total_pedagio_reais"] == 47.10

            resp_carreta = await cliente.get("/api/v1/rotas/intermunicipal", params={"origem": "Araraquara", "destino": "Sao Paulo", "tipo_veiculo": "CARRETA_5_EIXOS", "incluir_tarifas_artesp": "true"})
            assert resp_carreta.status_code == 200
            corpo_carreta = resp_carreta.json()
            assert corpo_carreta["pedagios"]["custo_total_pedagio_reais"] == 235.50
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_corredor_sentido_interior_sao_paulo_para_araraquara():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    try:
        app = FastAPI()
        app.include_router(router)

        async def conexao():
            yield conn

        app.dependency_overrides[get_connection] = conexao

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "key_admin_demo"}) as cliente:
            resp = await cliente.get("/api/v1/rotas/intermunicipal", params={"origem": "Sao Paulo", "destino": "Araraquara", "tipo_veiculo": "TRUCK_3_EIXOS", "incluir_tarifas_artesp": "true"})
            assert resp.status_code == 200
            corpo = resp.json()
            assert corpo["sentido"] == "INTERIOR"
            assert corpo["trechos_percorridos"] == 6
            assert corpo["resumo"]["distancia_total_km"] in (244.9, 245.0)
            assert corpo["pedagios"]["quantidade_pracas"] == 5
            assert corpo["pedagios"]["custo_total_pedagio_reais"] == 141.30
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_corredor_subtrecho_campinas_para_sao_paulo():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    try:
        app = FastAPI()
        app.include_router(router)

        async def conexao():
            yield conn

        app.dependency_overrides[get_connection] = conexao

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "key_admin_demo"}) as cliente:
            resp = await cliente.get("/api/v1/rotas/intermunicipal", params={"origem": "Campinas", "destino": "Sao Paulo", "tipo_veiculo": "TRUCK_3_EIXOS", "incluir_tarifas_artesp": "true"})
            assert resp.status_code == 200
            corpo = resp.json()
            assert corpo["sentido"] == "CAPITAL"
            assert corpo["trechos_percorridos"] == 2
            assert corpo["resumo"]["distancia_total_km"] == 76.1
            assert corpo["pedagios"]["quantidade_pracas"] == 2
            assert corpo["pedagios"]["custo_total_pedagio_reais"] == 70.80
    finally:
        await tx.rollback()
        await conn.close()


def test_sincronizacao_clima_com_redundancia_e_fallbacks():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import sincronizar_clima_corredor as s

    v_prim, f_prim = s.consultar_precipitacao_resiliente(-21.90, -48.03)
    assert v_prim is not None
    assert f_prim in ("OPEN_METEO_PRIMARIO", "OPEN_METEO_GFS_REDUNDANCIA", "WTTR_IN_REDUNDANCIA")

    orig_prim = s._consultar_open_meteo_primario
    orig_gfs = s._consultar_open_meteo_gfs
    orig_wttr = s._consultar_wttr_in
    try:
        def falha_prim(lat, lon):
            raise RuntimeError("Falha primario")
        s._consultar_open_meteo_primario = falha_prim

        v_fb1, f_fb1 = s.consultar_precipitacao_resiliente(-21.90, -48.03)
        assert v_fb1 is not None
        assert f_fb1 in ("OPEN_METEO_GFS_REDUNDANCIA", "WTTR_IN_REDUNDANCIA")

        def falha_gfs(lat, lon):
            raise RuntimeError("Falha GFS")
        s._consultar_open_meteo_gfs = falha_gfs

        v_fb2, f_fb2 = s.consultar_precipitacao_resiliente(-21.90, -48.03)
        assert v_fb2 is not None
        assert f_fb2 == "WTTR_IN_REDUNDANCIA"

        def falha_wttr(lat, lon):
            raise RuntimeError("Falha WTTR")
        s._consultar_wttr_in = falha_wttr

        v_none, f_none = s.consultar_precipitacao_resiliente(-21.90, -48.03)
        assert v_none is None
        assert f_none == "INDISPONIVEL"
    finally:
        s._consultar_open_meteo_primario = orig_prim
        s._consultar_open_meteo_gfs = orig_gfs
        s._consultar_wttr_in = orig_wttr
