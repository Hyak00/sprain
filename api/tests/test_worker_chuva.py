import importlib.util
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

raiz = Path(__file__).resolve().parents[2]
scripts_dir = raiz / "scripts"
api_dir = raiz / "api"

if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))


def _carregar(nome, caminho):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

worker = _carregar("worker_chuva", raiz / "scripts" / "worker_chuva.py")
status_mod = _carregar("worker_chuva_status", raiz / "scripts" / "worker_chuva_status.py")
limiares = _carregar("limiares_chuva", raiz / "api" / "app" / "services" / "limiares_chuva.py")


def test_open_meteo_retorna_valor_valido():
    html_fake = json.dumps({
        "current": {"precipitation": 12.5}
    }).encode("utf-8")
    resposta = MagicMock()
    resposta.read.return_value = html_fake
    resposta.__enter__ = lambda s: s
    resposta.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=resposta):
        valor = worker.coletar_open_meteo("OPEN_METEO_ARQ", -21.79, -48.17)
    assert valor == pytest.approx(12.5)


def test_open_meteo_retorna_none_em_erro_de_rede():
    with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
        valor = worker.coletar_open_meteo("OPEN_METEO_ARQ", -21.79, -48.17)
    assert valor is None


def test_open_meteo_rejeita_valor_negativo():
    html_fake = json.dumps({"current": {"precipitation": -1.0}}).encode("utf-8")
    resposta = MagicMock()
    resposta.read.return_value = html_fake
    resposta.__enter__ = lambda s: s
    resposta.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=resposta):
        valor = worker.coletar_open_meteo("OPEN_METEO_ARQ", -21.79, -48.17)
    assert valor is None


def test_open_meteo_rejeita_nan():
    html_fake = json.dumps({"current": {"precipitation": float("nan")}}).encode("utf-8")
    resposta = MagicMock()
    resposta.read.return_value = html_fake
    resposta.__enter__ = lambda s: s
    resposta.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=resposta):
        valor = worker.coletar_open_meteo("OPEN_METEO_ARQ", -21.79, -48.17)
    assert valor is None


def test_open_meteo_rejeita_sem_bloco_current():
    html_fake = json.dumps({"daily": {"precipitation_sum": [5.0]}}).encode("utf-8")
    resposta = MagicMock()
    resposta.read.return_value = html_fake
    resposta.__enter__ = lambda s: s
    resposta.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=resposta):
        valor = worker.coletar_open_meteo("OPEN_METEO_ARQ", -21.79, -48.17)
    assert valor is None


def test_write_e_check_status_ok(tmp_path):
    arquivo = tmp_path / "status.json"
    agora = time.time()
    status_mod.write_chuva_status("sleeping", 600, last_result="ok", path=arquivo, now=agora)
    ok, msg = status_mod.check_chuva(path=arquivo, now=agora + 10)
    assert ok, msg


def test_check_status_falha_quando_last_result_failed(tmp_path):
    arquivo = tmp_path / "status.json"
    agora = time.time()
    status_mod.write_chuva_status("sleeping", 600, last_result="failed", path=arquivo, now=agora)
    ok, msg = status_mod.check_chuva(path=arquivo, now=agora + 10)
    assert not ok


def test_check_status_falha_quando_arquivo_ausente(tmp_path):
    ok, msg = status_mod.check_chuva(path=tmp_path / "nao_existe.json")
    assert not ok


def test_check_status_falha_quando_atrasado(tmp_path):
    arquivo = tmp_path / "status.json"
    agora = time.time()
    status_mod.write_chuva_status("sleeping", 600, last_result="ok", path=arquivo, now=agora)
    ok, msg = status_mod.check_chuva(path=arquivo, now=agora + 600 + 301)
    assert not ok


def test_limiares_critico():
    nivel, _ = limiares.classificar(80.0)
    assert nivel == "VERMELHO_EXTRAORDINARIO"


def test_limiares_severo():
    nivel, _ = limiares.classificar(50.0)
    assert nivel == "LARANJA_SEVERO"


def test_limiares_atencao():
    nivel, _ = limiares.classificar(25.0)
    assert nivel == "AMARELO_ATENCAO"


def test_limiares_pista_molhada():
    nivel, _ = limiares.classificar(5.0)
    assert nivel == "PISTA_MOLHADA"


def test_limiares_verde():
    nivel, _ = limiares.classificar(0.0)
    assert nivel == "VERDE_ESTAVEL"


def test_impacto_corredor_critico():
    status, fator = limiares.impacto_corredor(55.0)
    assert status == "RISCO_CRITICO_ALAGAMENTO"
    assert fator == 2.5


def test_impacto_corredor_liberada():
    status, fator = limiares.impacto_corredor(0.0)
    assert status == "LIBERADA"
    assert fator == 1.0
