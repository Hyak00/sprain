import pytest


@pytest.mark.parametrize(
    ("confianca", "multiplicador_esperado"),
    [
        (0.00, 1.0),
        (0.50, 6.0),
        (0.99, 10.9),
        (1.00, 11.0),
    ],
)
def test_multiplicador_penalidade_alerta_incerto(
    confianca, multiplicador_esperado
):
    multiplicador = 1.0 + confianca * 10.0

    assert multiplicador == pytest.approx(multiplicador_esperado)


def test_sql_do_motor_aplica_penalidade_e_isola_tenant():
    from pathlib import Path

    caminho = Path("api/app/services/routing_engine.py") if Path("api/app/services/routing_engine.py").exists() else Path("app/services/routing_engine.py")
    codigo = caminho.read_text(
        encoding="utf-8"
    )

    assert "status_evento = 'INCERTO'" in codigo
    assert "MAX(a.confianca) * 10.0" in codigo
    assert "t.id_trecho = ANY(a.trechos_afetados)" in codigo
    assert "a.tenant_id = {empresa_sql}" in codigo
    assert "a.escopo = 'GLOBAL'" in codigo
    assert "a.tenant_id = 'GLOBAL'" in codigo
    assert "cost_sql += penalidade_alerta" in codigo

from pathlib import Path


def test_penalidade_incerta_tem_multiplicador_e_filtros_corretos():
    codigo = Path(
        ("api/app/services/routing_engine.py" if Path("api/app/services/routing_engine.py").exists() else "app/services/routing_engine.py")
    ).read_text(encoding="utf-8")

    inicio = codigo.index("if any(a[\"status_evento\"] == \"INCERTO\"")
    fim = codigo.index("\n        restricao =", inicio)
    bloco = codigo[inicio:fim]

    assert "MAX(a.confianca) * 10.0" in bloco
    assert "1.0 + COALESCE(" in bloco
    assert "a.expiracao_em > now()" in bloco
    assert "a.status_evento = 'INCERTO'" in bloco
    assert "t.id_trecho = ANY(a.trechos_afetados)" in bloco
    assert "a.tenant_id = {empresa_sql}" in bloco
    assert "a.escopo = 'GLOBAL'" in bloco
    assert "a.tenant_id = 'GLOBAL'" in bloco
    assert "cost_sql += penalidade_alerta" in bloco

@pytest.mark.asyncio
async def test_penalidade_incerta_chega_ao_sql_do_pgr_dijkstra():
    from app.services.routing_engine import RoutingEngine

    class ConexaoTeste:
        def __init__(self):
            self.sql_arestas = None
            self.chamadas_vertice = 0

        async def fetch(self, query, *args):
            if "alertas_operacionais" in query:
                return [{
                    "trechos_afetados": [100],
                    "confianca": 0.50,
                    "status_evento": "INCERTO",
                }]
            if "pgr_dijkstra" in query:
                self.sql_arestas = args[2]
                return [{
                    "seq": 1,
                    "node": 2,
                    "edge": 100,
                    "cost": 1.0,
                    "id_trecho": 100,
                    "name": "Trecho de teste",
                    "length": 100.0,
                    "highway": "primary",
                    "classe_declividade": 1.0,
                    "ivi_score": 10.0,
                    "sentido": "AMBOS",
                    "limites_malha": None,
                    "fonte_malha": None,
                    "limites_verificado_em": None,
                    "limites_valido_ate": None,
                    "geojson": None,
                }]
            return []

        async def fetchrow(self, query, *args):
            if "trechos_osm_vertices_pgr" in query:
                self.chamadas_vertice += 1
                return {
                    "id": self.chamadas_vertice,
                    "coberto": True,
                }
            return None

    RoutingEngine.clear_cache()
    conexao = ConexaoTeste()

    try:
        resultado = await RoutingEngine.compute_route(
            conexao,
            -46.468, -23.542,
            -46.452, -23.535,
            "FASTEST", 0.0, "VUC", "tenant_teste_penalidade"
        )

        assert resultado is not None
        assert conexao.sql_arestas is not None
        assert "MAX(a.confianca) * 10.0" in conexao.sql_arestas
        assert "t.id_trecho = ANY(a.trechos_afetados)" in conexao.sql_arestas
        assert "a.tenant_id = 'tenant_teste_penalidade'" in conexao.sql_arestas
        assert "1.0 + COALESCE(" in conexao.sql_arestas
        assert "AS cost" in conexao.sql_arestas
        assert "AS reverse_cost" in conexao.sql_arestas
    finally:
        RoutingEngine.clear_cache()
from app.services.routing_engine import RoutingEngine


def test_assinatura_alertas_incerto_muda_com_confianca_ou_trechos():
    def assinatura(alertas):
        return sorted(
            (
                tuple(sorted(int(edge) for edge in (a["trechos_afetados"] or []))),
                round(float(a["confianca"] or 0.0), 6),
            )
            for a in alertas
            if a["status_evento"] == "INCERTO"
        )

    base = [{"trechos_afetados": [100], "confianca": 0.5, "status_evento": "INCERTO"}]
    confianca_alterada = [{"trechos_afetados": [100], "confianca": 0.8, "status_evento": "INCERTO"}]
    trechos_alterados = [{"trechos_afetados": [200], "confianca": 0.5, "status_evento": "INCERTO"}]

    assert assinatura(base) != assinatura(confianca_alterada)
    assert assinatura(base) != assinatura(trechos_alterados)


def test_assinatura_alertas_incerto_ignora_alertas_nao_incerto():
    incerto = [{"trechos_afetados": [100], "confianca": 0.5, "status_evento": "INCERTO"}]
    com_confirmado = incerto + [{"trechos_afetados": [200], "confianca": 0.9, "status_evento": "CONFIRMADO"}]

    def assinatura(alertas):
        return sorted(
            (
                tuple(sorted(int(edge) for edge in (a["trechos_afetados"] or []))),
                round(float(a["confianca"] or 0.0), 6),
            )
            for a in alertas
            if a["status_evento"] == "INCERTO"
        )

    assert assinatura(incerto) == assinatura(com_confirmado)


@pytest.mark.asyncio
async def test_cache_compute_route_invalida_quando_alerta_incerto_muda():
    from app.services.routing_engine import RoutingEngine

    class ConexaoTeste:
        def __init__(self):
            self.alertas = [{
                "trechos_afetados": [100],
                "confianca": 0.50,
                "status_evento": "INCERTO",
            }]
            self.chamadas_pgr = 0
            self.chamadas_vertice = 0

        async def fetch(self, query, *args):
            if "alertas_operacionais" in query:
                return self.alertas

            if "pgr_dijkstra" in query:
                self.chamadas_pgr += 1
                return [{
                    "seq": 1,
                    "node": 2,
                    "edge": 100,
                    "cost": 1.0,
                    "id_trecho": 100,
                    "name": "Trecho de teste",
                    "length": 100.0,
                    "highway": "primary",
                    "classe_declividade": 1.0,
                    "ivi_score": 10.0,
                    "sentido": "AMBOS",
                    "limites_malha": None,
                    "fonte_malha": None,
                    "limites_verificado_em": None,
                    "limites_valido_ate": None,
                    "geojson": None,
                }]

            return []

        async def fetchrow(self, query, *args):
            if "trechos_osm_vertices_pgr" in query:
                self.chamadas_vertice += 1
                return {
                    "id": 1 if self.chamadas_vertice % 2 else 2,
                    "coberto": True,
                }
            return None

    conexao = ConexaoTeste()
    RoutingEngine.clear_cache()
    argumentos = (
        conexao,
        -46.468, -23.542,
        -46.452, -23.535,
        "FASTEST", 0.0, "VUC",
        "teste_cache_alerta_incerto",
    )

    try:
        primeira = await RoutingEngine.compute_route(*argumentos)
        assert primeira is not None
        assert conexao.chamadas_pgr == 1

        # Mesmos alertas: deve reutilizar o cache.
        segunda = await RoutingEngine.compute_route(*argumentos)
        assert segunda is not None
        assert conexao.chamadas_pgr == 1

        # MudanÃ§a na confianÃ§a: deve recalcular.
        conexao.alertas[0]["confianca"] = 0.80
        terceira = await RoutingEngine.compute_route(*argumentos)
        assert terceira is not None
        assert conexao.chamadas_pgr == 2

        # MudanÃ§a nos trechos afetados: deve recalcular novamente.
        conexao.alertas[0]["trechos_afetados"] = [200]
        quarta = await RoutingEngine.compute_route(*argumentos)
        assert quarta is not None
        assert conexao.chamadas_pgr == 3

    finally:
        RoutingEngine.clear_cache()
