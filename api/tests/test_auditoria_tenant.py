"""Acuracia deve contar somente eventos da empresa autenticada."""

import httpx
import pytest

from app.database import get_connection
from app.main import app


class AuditoriaEmMemoria:
    def __init__(self):
        self.registros = [
            ("empresa_a", "VERDADEIRO_POSITIVO"),
            ("empresa_a", "FALSO_NEGATIVO"),
            ("empresa_b", "FALSO_POSITIVO"),
            ("empresa_b", "FALSO_POSITIVO"),
            (None, "VERDADEIRO_NEGATIVO"),
        ]
        self.consultas = []

    async def fetchrow(self, query, *args):
        self.consultas.append((query, args))
        assert "WHERE tenant_id = $1" in query
        assert len(args) == 1
        classificacoes = [resultado for tenant, resultado in self.registros if tenant == args[0]]
        return {
            "total_avaliado": len(classificacoes),
            "vp": classificacoes.count("VERDADEIRO_POSITIVO"),
            "fp": classificacoes.count("FALSO_POSITIVO"),
            "vn": classificacoes.count("VERDADEIRO_NEGATIVO"),
            "fn": classificacoes.count("FALSO_NEGATIVO"),
        }


@pytest.mark.asyncio
async def test_acuracia_isolada_por_empresa_autenticada(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv(
        "TENANT_API_KEYS",
        "chave_a:VIEWER:empresa_a;chave_b:VIEWER:empresa_b",
    )
    conn = AuditoriaEmMemoria()

    async def conexao_teste():
        yield conn

    app.dependency_overrides[get_connection] = conexao_teste
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://teste") as client:
            a = await client.get("/api/v1/logistica/auditoria/acuracia", headers={"X-API-Key": "chave_a"})
            b = await client.get("/api/v1/logistica/auditoria/acuracia", headers={"X-API-Key": "chave_b"})
            rejeitada = await client.get(
                "/api/v1/logistica/auditoria/acuracia?tenant_id=empresa_b",
                headers={"X-API-Key": "chave_a"},
            )
        assert a.status_code == 200
        assert a.json()["amostra_historica_total"] == 2
        assert a.json()["matriz_confusao"]["verdadeiros_positivos"] == 1
        assert a.json()["matriz_confusao"]["falsos_negativos"] == 1
        assert b.status_code == 200
        assert b.json()["amostra_historica_total"] == 2
        assert b.json()["matriz_confusao"]["falsos_positivos"] == 2
        assert rejeitada.status_code == 403
        assert [args for _, args in conn.consultas] == [("empresa_a",), ("empresa_b",)]
    finally:
        app.dependency_overrides.pop(get_connection, None)
