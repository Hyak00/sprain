"""A comparacao financeira deve distinguir custo, premissa e risco ausente."""

import pytest
from pydantic import ValidationError

from app.schemas_economic import ParametrosDecisaoEconomica
from app.services.economic_engine import EconomicDecisionEngine


def avaliar(**alteracoes):
    dados = {
        "distancia_km": 10,
        "tempo_min": 60,
        "probabilidade_atraso": None,
        "probabilidade_bloqueio": None,
        "consumo_km_l": 2,
        "preco_diesel_litro": 6,
        "custo_hora_veiculo": 20,
        "custo_hora_motorista": 30,
        "valor_frete": 200,
        "valor_carga": 1000000,
        "multa_por_hora_atraso": 60,
        "janela_limite_min": 45,
        "custo_pedagio_conhecido": 10,
    }
    return EconomicDecisionEngine.evaluate_route_tradeoff(**(dados | alteracoes))


def test_custo_total_por_km_nao_e_rotulado_como_combustivel_nem_somado_duas_vezes():
    resultado = avaliar(custo_por_km=5)
    assert resultado["custo_variavel_brl"] == 50
    assert resultado["custo_combustivel_brl"] is None
    assert resultado["custo_total_estimado_brl"] == 110
    assert resultado["resultado_liquido_brl"] == 90
    assert resultado["origem_custo_variavel"] == "CUSTO_POR_KM_INFORMADO"


def test_consumo_e_outros_custos_por_km_sao_separados():
    resultado = avaliar(custo_por_km_sem_combustivel=1.5)
    assert resultado["custo_combustivel_brl"] == 30
    assert resultado["custo_outros_variaveis_brl"] == 15
    assert resultado["custo_variavel_brl"] == 45
    assert resultado["custo_total_estimado_brl"] == 105
    assert "CUSTOS_OPERACIONAIS_POR_KM_ALEM_DO_COMBUSTIVEL" not in resultado["componentes_nao_calculados"]


def test_custos_por_km_conflitantes_sao_rejeitados():
    with pytest.raises(ValidationError):
        ParametrosDecisaoEconomica(custo_por_km=5, custo_por_km_sem_combustivel=1)


def test_valor_da_carga_nao_gera_prejuizo_ficticio():
    base = avaliar(probabilidade_bloqueio=0.5, valor_carga=100)
    caro = avaliar(probabilidade_bloqueio=0.5, valor_carga=10000000)
    assert base["risco_perda_alagamento_brl"] is None
    assert base["valor_carga_usado_como_prejuizo"] is False
    assert base["custo_total_estimado_brl"] == caro["custo_total_estimado_brl"]
    assert "RISCO_DE_BLOQUEIO" in base["componentes_nao_calculados"]
    informado = avaliar(probabilidade_bloqueio=0.5, prejuizo_por_bloqueio_brl=200)
    assert informado["risco_perda_alagamento_brl"] == 100
    assert informado["custo_total_estimado_brl"] == base["custo_total_estimado_brl"] + 100


def test_comparacao_informa_delta_tarifas_pendentes_e_riscos_ausentes():
    direta = {"distancia_km": 10, "tempo_min": 60, "custo_pedagio_conhecido": 10,
              "tarifas_pendentes": 1}
    alternativa = {"distancia_km": 20, "tempo_min": 60, "custo_pedagio_conhecido": 0}
    premissas = {"custo_por_km": 5, "valor_carga": 500000}
    resultado = EconomicDecisionEngine.compare_and_recommend(direta, alternativa, premissas)
    assert resultado["tradeoff"]["custo_desvio_brl"] == 40
    assert resultado["recomendacao"] == "ROTA_DIRETA_ORIGINAL"
    assert resultado["decisao_operacional_automatica"] is False
    assert resultado["premissas_aplicadas"]["custo_por_km"] == 5
    assert resultado["premissas_aplicadas"]["consumo_km_l"] == 3
    assert "TARIFAS_DE_PEDAGIO_PENDENTES" in resultado["tradeoff"]["rota_direta"]["componentes_nao_calculados"]
    assert "RISCO_DE_ATRASO" in resultado["tradeoff"]["rota_alternativa"]["componentes_nao_calculados"]
    assert "sinistro" not in resultado["justificativa_financeira"].lower()


def test_probabilidade_fora_da_faixa_e_rejeitada():
    with pytest.raises(ValueError):
        avaliar(probabilidade_bloqueio=1.1, prejuizo_por_bloqueio_brl=100)


def test_espera_informada_compara_tempo_e_multa_sem_inventar_reducao_de_risco():
    direta = {"distancia_km": 10, "tempo_min": 30, "custo_pedagio_conhecido": 0}
    alternativa = {"distancia_km": 20, "tempo_min": 45, "custo_pedagio_conhecido": 0}
    parametros = {"custo_por_km": 2, "custo_hora_veiculo": 20, "custo_hora_motorista": 40,
                  "janela_limite_min": 60, "multa_por_hora_atraso": 120, "tempo_espera_min": 60}
    resultado = EconomicDecisionEngine.compare_and_recommend(direta, alternativa, parametros)
    aguardar = resultado["tradeoff"]["aguardar"]
    assert aguardar["custo_tempo_espera_brl"] == 60
    assert aguardar["multa_atraso_adicional_brl"] == 60
    assert aguardar["custo_aguardar_brl"] == 170
    assert resultado["tradeoff"]["rota_alternativa"]["custo_total_estimado_brl"] == 85
    assert aguardar["delta_desviar_menos_aguardar_brl"] == -85
    assert "nao foi reavaliado" in aguardar["aviso"]


def test_sem_tempo_de_espera_nao_inventa_cenario_aguardar():
    rota = {"distancia_km": 10, "tempo_min": 30}
    resultado = EconomicDecisionEngine.compare_and_recommend(rota, rota, {})
    assert resultado["tradeoff"]["aguardar"] is None


@pytest.mark.parametrize("valor", [-1, float("inf"), float("nan")])
def test_prejuizo_por_bloqueio_invalido_e_rejeitado(valor):
    with pytest.raises(ValidationError):
        ParametrosDecisaoEconomica(prejuizo_por_bloqueio_brl=valor)


@pytest.mark.parametrize("campo", ["preco_diesel_litro", "custo_hora_veiculo", "valor_frete", "valor_carga"])
def test_valores_financeiros_nao_finitos_sao_rejeitados(campo):
    with pytest.raises(ValidationError):
        ParametrosDecisaoEconomica(**{campo: float("inf")})
