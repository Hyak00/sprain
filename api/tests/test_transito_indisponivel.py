import pytest
from unittest.mock import patch
from app.services.transit_client import TransitClient

def test_transito_indisponivel_devolve_limitacao():
    with patch("urllib.request.urlopen", side_effect=Exception("Timeout de rede")):
        res = TransitClient.consultar_transito(-23.542, -46.468, -23.535, -46.452)
        assert res["status"] == "INDISPONIVEL"
        assert "Limitacao explicita" in res["motivo"]
        assert res["tempo_observado_min"] is None