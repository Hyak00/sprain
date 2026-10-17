import math


def validar_precipitacao_cenario(valor):
    if valor is None:
        raise ValueError(
            "Precipitacao indisponivel no cenario. Recalcule a operacao com dados climaticos validos antes de aprovar o desvio."
        )
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ValueError(
            "Precipitacao invalida no cenario. Recalcule a operacao antes de aprovar o desvio."
        )
    if not math.isfinite(numero) or numero < 0:
        raise ValueError(
            "Precipitacao invalida no cenario. Recalcule a operacao antes de aprovar o desvio."
        )
    return numero


def precipitacao_para_csv(valor):
    return "" if valor is None else valor
