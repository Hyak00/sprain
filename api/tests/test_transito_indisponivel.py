import io
import json
import urllib.error
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers.transito import TransitoRequest, comparar_tempo_transito
from app.services.transit_client import TransitClient


def test_transito_indisponivel_devolve_limitacao(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    TransitClient._cache.clear()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Timeout de rede")):
        res = TransitClient.consultar_transito(-23.542, -46.468, -23.535, -46.452)
    assert res["status"] == "INDISPONIVEL"
    assert "Limitacao explicita" in res["motivo"]
    assert res["tempo_observado_min"] is None
    assert res["tempo_estimado_min"] is None
    assert res["custo_consulta_usd"] is None


def test_osrm_demo_retorna_estimativa_sem_custo_inventado(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    TransitClient._cache.clear()
    resposta = io.BytesIO(json.dumps({
        "code": "Ok",
        "routes": [{"distance": 1234.0, "duration": 180.0}],
    }).encode("utf-8"))
    with patch("urllib.request.urlopen", return_value=resposta) as urlopen:
        primeira = TransitClient.consultar_transito(-23.542, -46.468, -23.535, -46.452)
        segunda = TransitClient.consultar_transito(-23.542, -46.468, -23.535, -46.452)

    assert primeira["status"] == "ESTIMATIVA_DISPONIVEL"
    assert primeira["tempo_estimado_min"] == 3.0
    assert primeira["tempo_observado_min"] is None
    assert primeira["custo_consulta_usd"] is None
    assert primeira["origem_cache"] is False
    assert segunda["origem_cache"] is True
    urlopen.assert_called_once()


def test_osrm_demo_nao_e_consultado_em_producao_mesmo_com_cache(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    TransitClient._cache["-23.542,-46.468:-23.535,-46.452"] = (
        10**15, {"status": "ESTIMATIVA_DISPONIVEL"}
    )
    with patch("urllib.request.urlopen") as urlopen:
        resposta = TransitClient.consultar_transito(-23.542, -46.468, -23.535, -46.452)
    assert resposta["status"] == "INDISPONIVEL"
    assert resposta["tempo_observado_min"] is None
    assert "producao" in resposta["motivo"]
    urlopen.assert_not_called()
    TransitClient._cache.clear()


def test_resposta_osrm_incompleta_nao_vira_tempo_zero(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    TransitClient._cache.clear()
    resposta = io.BytesIO(json.dumps({"code": "Ok", "routes": [{"distance": 1234.0}]}).encode("utf-8"))
    with patch("urllib.request.urlopen", return_value=resposta):
        resultado = TransitClient.consultar_transito(-23.542, -46.468, -23.535, -46.452)
    assert resultado["status"] == "INDISPONIVEL"
    assert resultado["tempo_estimado_min"] is None


@pytest.mark.asyncio
async def test_endpoint_nao_anuncia_transito_ao_vivo(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    TransitClient._cache.clear()
    resposta = io.BytesIO(json.dumps({
        "code": "Ok", "routes": [{"distance": 1234.0, "duration": 180.0}]
    }).encode("utf-8"))
    entrada = TransitoRequest(
        origem_lat=-23.542, origem_lon=-46.468,
        destino_lat=-23.535, destino_lon=-46.452,
    )
    with patch("urllib.request.urlopen", return_value=resposta), \
         patch("app.routers.transito.reservar_osrm", new_callable=AsyncMock, return_value=uuid4()) as reservar, \
         patch("app.routers.transito.concluir", new_callable=AsyncMock) as concluir:
        resultado = await comparar_tempo_transito(entrada, tenant_id="demo_corp", conn=object())
    reservar.assert_awaited_once()
    concluir.assert_awaited_once()
    assert resultado["status"] == "ESTIMATIVA"
    assert resultado["transito"]["tempo_observado_min"] is None
    assert "sem transito observado" in resultado["aviso"]


@pytest.mark.asyncio
async def test_cache_nao_reserva_chamada_externa(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    TransitClient._cache.clear()
    entrada = TransitoRequest(
        origem_lat=-23.542, origem_lon=-46.468,
        destino_lat=-23.535, destino_lon=-46.452,
    )
    TransitClient._cache["-23.542,-46.468:-23.535,-46.452"] = (
        10**15, {"status": "ESTIMATIVA_DISPONIVEL", "tempo_observado_min": None}
    )
    with patch("app.routers.transito.reservar_osrm", new_callable=AsyncMock) as reservar:
        resultado = await comparar_tempo_transito(entrada, tenant_id="demo_corp", conn=object())
    assert resultado["transito"]["origem_cache"] is True
    reservar.assert_not_awaited()
    TransitClient._cache.clear()


@pytest.mark.asyncio
async def test_endpoint_em_producao_responde_indisponivel_sem_rede(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    entrada = TransitoRequest(
        origem_lat=-23.542, origem_lon=-46.468,
        destino_lat=-23.535, destino_lon=-46.452,
    )
    with patch("urllib.request.urlopen") as urlopen:
        with pytest.raises(HTTPException) as erro:
            await comparar_tempo_transito(entrada, tenant_id="demo_corp", conn=object())
    assert erro.value.status_code == 502
    urlopen.assert_not_called()
