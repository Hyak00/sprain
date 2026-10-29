"""A produção só pode consultar a API comercial de clima."""

from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.open_meteo_endpoint import fonte_disponivel, url_previsao
from app.services.weather import OpenMeteoProvider


def test_ambiente_de_ensaio_pode_usar_endpoint_gratuito(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.delenv("OPEN_METEO_API_KEY", raising=False)
    url = url_previsao({"latitude": -21.9, "longitude": -48.0})
    assert urlsplit(url).hostname == "api.open-meteo.com"
    assert "apikey" not in parse_qs(urlsplit(url).query)


def test_producao_sem_chave_recusa_coleta_antes_da_rede(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("OPEN_METEO_API_KEY", raising=False)
    assert not fonte_disponivel()
    with pytest.raises(RuntimeError, match="OPEN_METEO_API_KEY"):
        url_previsao({"latitude": -21.9})
    with patch("urllib.request.urlopen") as abrir:
        assert OpenMeteoProvider().get_forecast_rainfall(-21.9, -48.0) is None
        abrir.assert_not_called()


def test_producao_com_chave_usa_endpoint_comercial(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OPEN_METEO_API_KEY", "chave-sintetica")
    assert fonte_disponivel()
    url = url_previsao({"latitude": -21.9, "longitude": -48.0})
    assert urlsplit(url).hostname == "customer-api.open-meteo.com"
    assert parse_qs(urlsplit(url).query)["apikey"] == ["chave-sintetica"]


def test_worker_nao_faz_chamada_sem_licenca_e_nao_imprime_chave(monkeypatch, caplog):
    from scripts.worker_chuva import coletar_open_meteo

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("OPEN_METEO_API_KEY", raising=False)
    with patch("urllib.request.urlopen") as abrir:
        assert coletar_open_meteo("ARQ", -21.9, -48.0) is None
        abrir.assert_not_called()

    monkeypatch.setenv("OPEN_METEO_API_KEY", "segredo-sintetico")
    with patch("urllib.request.urlopen", side_effect=OSError("segredo-sintetico")):
        assert coletar_open_meteo("ARQ", -21.9, -48.0) is None
    assert "segredo-sintetico" not in caplog.text


def test_worker_recusa_iniciar_em_producao_sem_chave(monkeypatch):
    from scripts import worker_chuva

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("OPEN_METEO_API_KEY", raising=False)
    with patch.object(worker_chuva, "executar_rodada") as rodada:
        with pytest.raises(SystemExit, match="OPEN_METEO_API_KEY"):
            worker_chuva.main()
        rodada.assert_not_called()


def test_corredor_producao_nao_usa_wttr_sem_autorizacao(monkeypatch):
    from scripts import sincronizar_clima_corredor as corredor

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OPEN_METEO_API_KEY", "chave-sintetica")
    monkeypatch.setattr(corredor, "_consultar_open_meteo_primario", lambda *_: None)
    monkeypatch.setattr(corredor, "_consultar_open_meteo_gfs", lambda *_: None)
    with patch.object(corredor, "_consultar_wttr_in") as wttr:
        assert corredor.consultar_precipitacao_resiliente(-21.9, -48.0) == (None, "INDISPONIVEL")
        wttr.assert_not_called()

    monkeypatch.delenv("OPEN_METEO_API_KEY", raising=False)
    with patch.object(corredor, "_consultar_open_meteo_primario") as primario:
        assert corredor.consultar_precipitacao_resiliente(-21.9, -48.0) == (None, "INDISPONIVEL")
        primario.assert_not_called()
