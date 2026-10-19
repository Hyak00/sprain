from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.weather import WeatherService


class ConexaoFalsa:
    def __init__(self, linha):
        self.linha = linha

    async def fetchrow(self, consulta, *argumentos):
        return self.linha


def montar_linha(**campos):
    base = {
        "estacao": "Itaquera",
        "fonte": "CGE",
        "tipo": "OBSERVACAO",
        "frequencia_minutos": 30,
        "distancia_m": 1200.0,
        "cobertura_m": 5000,
        "precipitacao_mm": Decimal("12.5"),
        "data_referencia": datetime.now(timezone.utc),
        "idade_minutos": 10.0,
        "expirada": False,
    }
    base.update(campos)
    return base


async def consultar(**campos):
    servico = WeatherService(ConexaoFalsa(montar_linha(**campos)))
    return await servico.obter_clima_trecho(1)


@pytest.mark.asyncio
async def test_sem_estacao_proxima():
    resultado = await WeatherService(ConexaoFalsa(None)).obter_clima_trecho(1)
    assert resultado["status"] == "DESCONHECIDO"
    assert resultado["precipitacao_mm"] is None


@pytest.mark.asyncio
async def test_leitura_valida():
    resultado = await consultar()
    assert resultado["status"] == "VALIDO"
    assert resultado["precipitacao_mm"] == 12.5


@pytest.mark.asyncio
async def test_fora_de_cobertura_nao_entrega_chuva():
    resultado = await consultar(distancia_m=8000.0)
    assert resultado["status"] == "FORA_DE_COBERTURA"
    assert resultado["precipitacao_mm"] is None


@pytest.mark.asyncio
async def test_leitura_expirada_pela_fonte():
    resultado = await consultar(expirada=True)
    assert resultado["status"] == "DESATUALIZADO"
    assert resultado["precipitacao_mm"] is None


@pytest.mark.asyncio
async def test_tolerancia_na_fronteira():
    assert (await consultar(idade_minutos=60.0))["status"] == "VALIDO"
    assert (await consultar(idade_minutos=61.0))["status"] == "DESATUALIZADO"


@pytest.mark.asyncio
@pytest.mark.parametrize("lixo", [Decimal("-1"), Decimal("1500"), float("nan"), float("inf"), "texto"])
async def test_valor_invalido_vindo_do_banco(lixo):
    resultado = await consultar(precipitacao_mm=lixo)
    assert resultado["status"] == "INDISPONIVEL"
    assert resultado["precipitacao_mm"] is None


@pytest.mark.asyncio
async def test_data_de_referencia_no_futuro():
    resultado = await consultar(idade_minutos=-30.0)
    assert resultado["status"] == "INDISPONIVEL"


@pytest.mark.asyncio
async def test_estacao_sem_leitura():
    resultado = await consultar(precipitacao_mm=None)
    assert resultado["status"] == "INDISPONIVEL"
