"""A medicao de carga deve recusar destinos e ambientes inadequados."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest


CAMINHO = Path(__file__).resolve().parents[2] / "scripts" / "medir_carga_api.py"
SPEC = importlib.util.spec_from_file_location("medir_carga_api", CAMINHO)
modulo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(modulo)


@pytest.mark.parametrize("url", [
    "https://api.exemplo.com:443", "http://127.0.0.1:18002/caminho",
    "http://usuario:senha@127.0.0.1:18002", "http://127.0.0.1:18002?alvo=outro",
])
def test_destinos_inadequados_sao_recusados(url):
    with pytest.raises(ValueError):
        modulo.validar_url_local(url)


def test_nao_dispara_carga_se_api_nao_confirma_demo_isolada(monkeypatch):
    chamadas = []

    class Resposta:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, *_):
            return json.dumps({"modo": "DESENVOLVIMENTO", "demo_isolada": False}).encode()

    class Opener:
        def open(self, req, timeout):
            chamadas.append(req.full_url)
            return Resposta()

    monkeypatch.setattr(modulo, "OPENER", Opener())
    monkeypatch.setenv("SPRAIN_API_KEY", "chave-sintetica")
    monkeypatch.setattr(sys, "argv", ["medir_carga_api.py"])
    assert modulo.main() == 1
    assert chamadas == ["http://127.0.0.1:18002/api/v1/demonstracao/estado"]
