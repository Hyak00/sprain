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
async def test_reset_global_nao_esta_disponivel_para_nenhuma_empresa(chaves_teste, monkeypatch):
    monkeypatch.setenv(
        "TENANT_API_KEYS",
        "monitor_admin:ADMIN:empresa_a;monitor_operator:OPERATOR:empresa_a;"
        "monitor_admin_b:ADMIN:empresa_b",
    )
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
            outra_empresa = await client.post("/api/v1/ocorrencias/resetar-todas",
                                               headers={"X-API-Key": "monitor_admin_b"})
            contrato = await client.get("/openapi.json")
        assert sem_chave.status_code == 401
        assert operador.status_code == 403
        assert admin.status_code == 403
        assert outra_empresa.status_code == 403
        assert "/api/v1/ocorrencias/resetar-todas" not in contrato.json()["paths"]
        assert conn.gravacoes == 0
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


@pytest.mark.asyncio
@pytest.mark.parametrize("metodo,rota", [
    ("GET", "/api/v1/trechos/geojson"),
    ("POST", "/api/v1/rotas/calcular"),
    ("GET", "/api/v1/ocorrencias/ativas"),
    ("POST", "/api/v1/ocorrencias/alerta-rapido"),
    ("POST", "/api/v1/ocorrencias/processar-texto"),
    ("POST", "/api/v1/simulacao/disparar"),
    ("GET", "/api/v1/relatorios/boletim-defesa-civil/json"),
    ("GET", "/api/v1/relatorios/boletim-defesa-civil/csv"),
    ("GET", "/api/v1/estatisticas/distrito"),
    ("GET", "/api/v1/estatisticas/historico-temporal"),
    ("GET", "/api/v1/logistica/alertas-meteorologicos"),
])
async def test_endpoints_privados_recusam_requisicoes_anonimas(metodo, rota, chaves_teste):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://teste") as client:
        resposta = await client.request(metodo, rota, json={"milimetros_chuva": 50.0} if metodo == "POST" else None)
        assert resposta.status_code == 401, f"Rota {rota} deveria exigir autenticacao mas retornou {resposta.status_code}"


@pytest.mark.asyncio
async def test_viewer_bloqueado_em_operacoes_de_escrita_e_simulacao(chaves_teste):
    headers_viewer = {"X-API-Key": "monitor_viewer"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://teste") as client:
        r1 = await client.post("/api/v1/simulacao/disparar", json={"milimetros_chuva": 60.0}, headers=headers_viewer)
        assert r1.status_code == 403

        r2 = await client.post("/api/v1/ocorrencias/alerta-rapido", json={
            "latitude": -23.54, "longitude": -46.46, "nivel": "VERMELHO", "corporacao": "TESTE"
        }, headers=headers_viewer)
        assert r2.status_code == 403


@pytest.mark.asyncio
async def test_auditoria_acuracia_segregada_por_tenant(chaves_teste):
    conn = ConexaoFalsa()
    chamadas_sql = []

    class ConexaoAuditoria:
        async def fetchrow(self, query, *args):
            chamadas_sql.append((query, args))
            return {
                "total_avaliado": 10 if args and args[0] == "empresa_a" else 0,
                "vp": 8 if args and args[0] == "empresa_a" else 0,
                "fp": 1 if args and args[0] == "empresa_a" else 0,
                "vn": 1 if args and args[0] == "empresa_a" else 0,
                "fn": 0
            }

    app.dependency_overrides[get_connection] = lambda: ConexaoAuditoria()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://teste") as client:
            resp_a = await client.get("/api/v1/logistica/auditoria/acuracia", headers={"X-API-Key": "monitor_admin"})
            assert resp_a.status_code == 200
            dados_a = resp_a.json()
            assert dados_a["amostra_historica_total"] == 10
            assert dados_a["matriz_confusao"]["verdadeiros_positivos"] == 8

        assert len(chamadas_sql) > 0
        assert "WHERE tenant_id = $1" in chamadas_sql[0][0]
        assert chamadas_sql[0][1] == ("empresa_a",)
    finally:
        app.dependency_overrides.pop(get_connection, None)


@pytest.mark.asyncio
async def test_alerta_tenant_a_nao_afeta_rotas_tenant_b():
    conn = ConexaoFalsa()
    orig_lon, orig_lat = -46.468, -23.542
    dest_lon, dest_lat = -46.452, -23.535

    queries_executadas = []

    class ConexaoRouting:
        def __init__(self):
            self.chamadas_vert = 0

        async def fetch(self, query, *args):
            queries_executadas.append((query, args))
            if "alertas_operacionais" in query:
                return [{"trechos_afetados": [555], "confianca": 0.99, "status_evento": "CONFIRMADO"}] if args and args[0] == "empresa_a" else []
            if "SELECT t.id_trecho,t.limites_malha" in query:
                return []
            if "pgr_dijkstra" in query:
                return [{
                    "seq": 1, "node": 1, "edge": 100, "cost": 1.0, "id_trecho": 100,
                    "name": "Via Teste", "length": 500.0, "highway": "primary",
                    "classe_declividade": 1.0, "ivi_score": 10.0, "sentido": "AMBOS",
                    "limites_malha": None, "fonte_malha": None, "limites_verificado_em": None,
                    "limites_valido_ate": None, "geojson": '{"type":"LineString","coordinates":[[-46.468,-23.542],[-46.452,-23.535]]}'
                }]
            return []

        async def fetchrow(self, query, *args):
            if "trechos_osm_vertices_pgr" in query:
                self.chamadas_vert += 1
                return {"id": self.chamadas_vert, "coberto": True}
            return None

    c = ConexaoRouting()
    from app.services.routing_engine import RoutingEngine
    RoutingEngine.clear_cache()
    rota_b = await RoutingEngine.compute_route(c, orig_lon, orig_lat, dest_lon, dest_lat, "FASTEST", 0.0, "VUC", "empresa_b")
    assert rota_b is not None
    assert 555 not in rota_b["trechos_excluidos_por_limites"]

    RoutingEngine.clear_cache()
    rota_a = await RoutingEngine.compute_route(c, orig_lon, orig_lat, dest_lon, dest_lat, "FASTEST", 0.0, "VUC", "empresa_a")
    assert rota_a is not None
    assert 555 in rota_a["trechos_excluidos_por_limites"]

