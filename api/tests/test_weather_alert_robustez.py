from app.services.weather_alert_engine import SevereWeatherEngine

avaliar = SevereWeatherEngine.parse_alert_severity


def test_limiares_de_fronteira():
    assert avaliar(0.0, 10.0)["nivel_alerta"] == "VERDE_ESTAVEL"
    assert avaliar(24.9, 10.0)["nivel_alerta"] == "VERDE_ESTAVEL"
    assert avaliar(25.0, 10.0)["nivel_alerta"] == "AMARELO_ATENCAO"
    assert avaliar(49.9, 10.0)["nivel_alerta"] == "AMARELO_ATENCAO"
    assert avaliar(50.0, 10.0)["nivel_alerta"] == "LARANJA_SEVERO"
    assert avaliar(79.9, 10.0)["nivel_alerta"] == "LARANJA_SEVERO"
    assert avaliar(80.0, 10.0)["nivel_alerta"] == "VERMELHO_EXTRAORDINARIO"
    assert avaliar(10.0, 55.0)["nivel_alerta"] == "LARANJA_SEVERO"
    assert avaliar(10.0, 75.0)["nivel_alerta"] == "VERMELHO_EXTRAORDINARIO"


def test_vento_ausente_nao_vira_zero():
    res = avaliar(30.0, None)
    assert res["nivel_alerta"] == "AMARELO_ATENCAO"
    assert res["telemetria"]["rajada_vento_kmh"] is None
    assert res["dados_parciais"] is True


def test_vento_invalido_nao_esconde_chuva_extrema():
    for lixo in (float("nan"), float("inf"), -5.0, 1500.0, "texto"):
        res = avaliar(90.0, lixo)
        assert res["nivel_alerta"] == "VERMELHO_EXTRAORDINARIO"
        assert res["dados_parciais"] is True


def test_sem_chuva_valida_nunca_vira_verde():
    for lixo in (None, float("nan"), float("inf"), float("-inf"), -1.0, 1500.0, "texto", True):
        res = avaliar(lixo, 10.0)
        assert res["nivel_alerta"] == "INDISPONIVEL"
        assert res["telemetria"]["precipitacao_mm"] is None


def test_vento_forte_sem_chuva_ainda_alerta():
    assert avaliar(None, 80.0)["nivel_alerta"] == "VERMELHO_EXTRAORDINARIO"
