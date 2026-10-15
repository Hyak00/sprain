"""Regressoes de autorizacao e isolamento do mapa publico."""

import json

import asyncpg
import httpx
import pytest
from fastapi import HTTPException

from app.config import Settings, settings
from app.database import get_connection
from app.main import app
from app.routers import monitoramento
from app.routers.demonstracao import gerar_cenario_historico_sp310
from app.routers.trechos import get_trechos_geojson
from app.seguranca import exigir_api_key, is_production


@pytest.fixture
def chaves_teste(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv(
        "TENANT_API_KEYS",
        "monitor_admin:ADMIN:empresa_a;monitor_operator:OPERATOR:empresa_a;"
        "monitor_viewer:VIEWER:empresa_a",
    )


class ConexaoFalsa:
    def __init__(self):
        self.gravacoes = 0

    async def execute(self, *_args):
        self.gravacoes += 1
        return "UPDATE 1"

    async def fetch(self, *_args):
        self.gravacoes += 1
        return []


@pytest.mark.asyncio
@pytest.mark.parametrize("rota", [
    "/api/v1/monitoramento/simular-chuva?acumulado_mm=40",
    "/api/v1/monitoramento/sincronizar-cge",
])
async def test_monitoramento_so_operador_ou_admin(rota, chaves_teste, monkeypatch):
    conn = ConexaoFalsa()

    async def conexao_teste():
        yield conn

    monkeypatch.setattr(monitoramento, "coletar_chuva_cge", lambda: {
        "posto": "teste", "nome": "Teste", "chuva_acumulada_recente_mm": 40,
    })
    app.dependency_overrides[get_connection] = conexao_teste
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://teste") as client:
            sem_chave = await client.post(rota)
            visualizador = await client.post(rota, headers={"X-API-Key": "monitor_viewer"})
            operador = await client.post(rota, headers={"X-API-Key": "monitor_operator"})
        assert sem_chave.status_code == 401
        assert visualizador.status_code == 403
        assert operador.status_code == 200
        assert conn.gravacoes == 1
    finally:
        app.dependency_overrides.pop(get_connection, None)


@pytest.mark.asyncio
async def test_reset_global_exige_admin(chaves_teste):
    conn = ConexaoFalsa()

    async def conexao_teste():
        yield conn

    app.dependency_overrides[get_connection] = conexao_teste
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://teste") as client:
            sem_chave = await client.post("/api/v1/ocorrencias/resetar-todas")
            operador = await client.post("/api/v1/ocorrencias/resetar-todas",
                                          headers={"X-API-Key": "monitor_operator"})
            admin = await client.post("/api/v1/ocorrencias/resetar-todas",
                                       headers={"X-API-Key": "monitor_admin"})
        assert sem_chave.status_code == 401
        assert operador.status_code == 403
        assert admin.status_code == 200
        assert conn.gravacoes == 2
    finally:
        app.dependency_overrides.pop(get_connection, None)


@pytest.mark.asyncio
async def test_api_keys_ausentes_nao_aceitam_chave_arbitraria(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setattr(settings, "API_KEYS", "")
    with pytest.raises(HTTPException) as erro:
        await exigir_api_key("chave_qualquer")
    assert erro.value.status_code == 503


def test_modo_producao_lido_do_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ENVIRONMENT=production\n", encoding="utf-8")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    configuracao = Settings(_env_file=env_file)
    monkeypatch.setattr(settings, "ENVIRONMENT", configuracao.ENVIRONMENT)
    assert is_production()


@pytest.mark.asyncio
async def test_login_demo_recusado_em_producao(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://teste") as client:
        resposta = await client.post("/api/v1/logistica/auth/login", json={
            "email": "operacoes@democorp.com.br", "senha": "sprain2026",
        })
    assert resposta.status_code == 503


@pytest.mark.asyncio
async def test_cenario_demo_exige_admin_e_nao_roda_em_producao(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://teste") as client:
        sem_chave = await client.post("/api/v1/demonstracao/cenario-historico-sp310")
        visualizador = await client.post("/api/v1/demonstracao/cenario-historico-sp310",
                                         headers={"X-API-Key": "key_viewer_demo"})
    assert sem_chave.status_code == 401
    assert visualizador.status_code == 403

    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(HTTPException) as erro:
        await gerar_cenario_historico_sp310()
    assert erro.value.status_code == 503


@pytest.mark.asyncio
async def test_geojson_publico_nao_expoe_malha_privada():
    conn = await asyncpg.connect(settings.database_url)
    transacao = conn.transaction()
    await transacao.start()
    try:
        id_privado = await conn.fetchval("SELECT MIN(id_trecho) - 1 FROM trechos_osm")
        await conn.execute("""INSERT INTO trechos_osm(id_trecho,name,highway,geom,tenant_malha)
            VALUES($1,'TRECHO PRIVADO','primary',
                ST_Transform(ST_SetSRID(ST_MakeLine(ST_Point(-46.5,-23.5),
                    ST_Point(-46.49,-23.5)),4326),31983),'empresa_b')""", id_privado)
        resposta = await get_trechos_geojson(classe=None, limit=1, conn=conn)
        features = json.loads(resposta.body)["features"]
        assert len(features) == 1
        assert features[0]["properties"]["id_trecho"] != id_privado
    finally:
        await transacao.rollback()
        await conn.close()
