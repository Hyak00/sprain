"""Aviso de manutenção sem escrita nem dependência do banco."""

from datetime import datetime, timezone

import httpx
import pytest

from app.config import settings
from app.main import app
from app.services.manutencao import carregar_janela, estado_manutencao


def configurar(monkeypatch, inicio="2026-10-20T10:00:00-03:00",
              fim="2026-10-20T12:00:00-03:00", aviso="Atualização planejada"):
    monkeypatch.setattr(settings, "MANUTENCAO_INICIO", inicio)
    monkeypatch.setattr(settings, "MANUTENCAO_FIM", fim)
    monkeypatch.setattr(settings, "MANUTENCAO_AVISO", aviso)


def test_janela_distingue_programacao_execucao_e_fim(monkeypatch):
    configurar(monkeypatch)
    assert estado_manutencao(datetime(2026, 10, 20, 12, tzinfo=timezone.utc))["situacao"] == "PROGRAMADA"
    durante = estado_manutencao(datetime(2026, 10, 20, 14, tzinfo=timezone.utc))
    assert durante["situacao"] == "EM_ANDAMENTO"
    assert durante["inicio_em"] == datetime(2026, 10, 20, 13, tzinfo=timezone.utc)
    assert estado_manutencao(datetime(2026, 10, 20, 15, tzinfo=timezone.utc))["situacao"] == "SEM_JANELA"


@pytest.mark.parametrize("inicio,fim,aviso", [
    ("", "2026-10-20T12:00:00-03:00", "Aviso"),
    ("2026-10-20T10:00:00", "2026-10-20T12:00:00-03:00", "Aviso"),
    ("2026-10-20T12:00:00-03:00", "2026-10-20T10:00:00-03:00", "Aviso"),
    ("2026-10-20T10:00:00-03:00", "2026-10-20T12:00:00-03:00", "A" * 241),
])
def test_configuracao_invalida_e_recusada(monkeypatch, inicio, fim, aviso):
    configurar(monkeypatch, inicio, fim, aviso)
    with pytest.raises(ValueError):
        carregar_janela()


@pytest.mark.asyncio
async def test_endpoint_publico_e_pagina_nao_dependem_de_banco(monkeypatch):
    configurar(monkeypatch, "", "", "")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        resposta = await client.get("/api/v1/health/manutencao")
        pagina = await client.get("/static/status.html")
    assert resposta.status_code == 200
    assert resposta.json()["situacao"] == "SEM_JANELA"
    assert resposta.headers["cache-control"] == "no-store"
    assert pagina.status_code == 200 and "Estado do SPRain" in pagina.text
    assert app.openapi()["paths"]["/api/v1/health/manutencao"]["get"]["security"] == []
