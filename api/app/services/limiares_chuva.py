from typing import Tuple

LIMIARES = {
    "critico":  {"mm": 80.0, "nivel": "VERMELHO_EXTRAORDINARIO"},
    "severo":   {"mm": 50.0, "nivel": "LARANJA_SEVERO"},
    "atencao":  {"mm": 25.0, "nivel": "AMARELO_ATENCAO"},
    "pista_molhada": {"mm": 5.0, "nivel": "PISTA_MOLHADA"},
}

UNIDADE = "mm por periodo (acumulado desde o ultimo zeramento ou hora corrente)"
FONTE_REFERENCIA = "motor_alertas v1.0 — definidos empiricamente, revisao prevista apos 30 dias de coleta real"


def classificar(precipitacao_mm: float) -> Tuple[str, str]:
    if precipitacao_mm >= LIMIARES["critico"]["mm"]:
        return "VERMELHO_EXTRAORDINARIO", "SUSPENDER_OPERACOES_OU_DESVIAR_TOTAL"
    if precipitacao_mm >= LIMIARES["severo"]["mm"]:
        return "LARANJA_SEVERO", "ROTEAMENTO_PREVENTIVO_OBRIGATORIO"
    if precipitacao_mm >= LIMIARES["atencao"]["mm"]:
        return "AMARELO_ATENCAO", "MONITORAMENTO_ATIVO_TELEMETRIA"
    if precipitacao_mm >= LIMIARES["pista_molhada"]["mm"]:
        return "PISTA_MOLHADA", "REDUCAO_VELOCIDADE_RECOMENDADA"
    return "VERDE_ESTAVEL", "FLUXO_NORMAL"


def impacto_corredor(precipitacao_mm: float) -> Tuple[str, float]:
    if precipitacao_mm >= LIMIARES["severo"]["mm"]:
        return "RISCO_CRITICO_ALAGAMENTO", 2.5
    if precipitacao_mm >= LIMIARES["atencao"]["mm"]:
        return "ALERTA_MODERADO", 1.5
    if precipitacao_mm >= LIMIARES["pista_molhada"]["mm"]:
        return "PISTA_MOLHADA", 1.15
    return "LIBERADA", 1.0
