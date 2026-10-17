"""Compara custos de rotas sem apresentar riscos desconhecidos como perdas certas."""

from typing import Any, Dict


class EconomicDecisionEngine:
    @staticmethod
    def evaluate_route_tradeoff(
        distancia_km: float,
        tempo_min: float,
        probabilidade_atraso: float | None,
        probabilidade_bloqueio: float | None,
        consumo_km_l: float,
        preco_diesel_litro: float,
        custo_hora_veiculo: float,
        custo_hora_motorista: float,
        valor_frete: float,
        valor_carga: float,
        multa_por_hora_atraso: float,
        janela_limite_min: float,
        custo_pedagio_conhecido: float = 0.0,
        custo_por_km: float | None = None,
        custo_por_km_sem_combustivel: float | None = None,
        origem_custo_por_km: str | None = None,
        prejuizo_por_bloqueio_brl: float | None = None,
        tarifas_pendentes: int = 0,
    ) -> Dict[str, Any]:
        # O valor da carga e informativo. Bloqueio nao equivale a perda da carga.
        for probabilidade in (probabilidade_atraso, probabilidade_bloqueio):
            if probabilidade is not None and not 0 <= probabilidade <= 1:
                raise ValueError("Probabilidade deve estar entre zero e um.")
        custo_combustivel = (
            round(distancia_km / consumo_km_l * preco_diesel_litro, 2)
            if custo_por_km is None else None
        )
        custo_outros_por_km = (
            round(distancia_km * custo_por_km_sem_combustivel, 2)
            if custo_por_km is None and custo_por_km_sem_combustivel is not None else None
        )
        custo_variavel = (
            round(distancia_km * custo_por_km, 2) if custo_por_km is not None
            else round(custo_combustivel + (custo_outros_por_km or 0), 2)
        )
        custo_tempo = round(tempo_min / 60 * (custo_hora_veiculo + custo_hora_motorista), 2)

        custo_atraso = None
        if probabilidade_atraso is not None:
            minutos_atraso = max(0.0, tempo_min - janela_limite_min) * probabilidade_atraso
            custo_atraso = round(minutos_atraso / 60 * multa_por_hora_atraso, 2)

        custo_bloqueio = None
        if probabilidade_bloqueio is not None and prejuizo_por_bloqueio_brl is not None:
            custo_bloqueio = round(probabilidade_bloqueio * prejuizo_por_bloqueio_brl, 2)

        componentes = [custo_variavel, custo_tempo, custo_pedagio_conhecido]
        componentes.extend(c for c in (custo_atraso, custo_bloqueio) if c is not None)
        custo_total = round(sum(componentes), 2)
        nao_calculados = []
        if custo_por_km is None and custo_por_km_sem_combustivel is None:
            nao_calculados.append("CUSTOS_OPERACIONAIS_POR_KM_ALEM_DO_COMBUSTIVEL")
        if probabilidade_atraso is None:
            nao_calculados.append("RISCO_DE_ATRASO")
        if probabilidade_bloqueio is None or prejuizo_por_bloqueio_brl is None:
            nao_calculados.append("RISCO_DE_BLOQUEIO")
        if tarifas_pendentes:
            nao_calculados.append("TARIFAS_DE_PEDAGIO_PENDENTES")

        if custo_por_km is not None:
            origem_variavel = origem_custo_por_km or "CUSTO_POR_KM_INFORMADO"
        elif custo_outros_por_km is not None:
            origem_variavel = "COMBUSTIVEL_E_OUTROS_CUSTOS"
        else:
            origem_variavel = "COMBUSTIVEL_ESTIMADO"

        return {
            "distancia_km": round(distancia_km, 2),
            "tempo_estimado_min": round(tempo_min, 1),
            "custo_variavel_brl": custo_variavel,
            "custo_combustivel_brl": custo_combustivel,
            "custo_outros_variaveis_brl": custo_outros_por_km,
            "origem_custo_variavel": origem_variavel,
            "custo_tempo_operacional_brl": custo_tempo,
            "custo_multa_atraso_brl": custo_atraso,
            "risco_perda_alagamento_brl": custo_bloqueio,
            "valor_carga_usado_como_prejuizo": False,
            "subtotal_pedagios_conhecidos_brl": custo_pedagio_conhecido,
            "tarifas_pedagio_pendentes": tarifas_pendentes,
            "cobertura_pedagios_completa": False,
            "componentes_nao_calculados": nao_calculados,
            "custo_total_estimado_brl": custo_total,
            "resultado_liquido_brl": round(valor_frete - custo_total, 2),
        }

    @classmethod
    def compare_and_recommend(
        cls,
        rota_direta: Dict[str, Any],
        rota_segura: Dict[str, Any],
        parametros: Dict[str, Any],
    ) -> Dict[str, Any]:
        aplicados = {
            "consumo_km_l": 3.0,
            "preco_diesel_litro": 6.20,
            "custo_hora_veiculo": 50.0,
            "custo_hora_motorista": 35.0,
            "valor_frete": 600.0,
            "valor_carga": 25000.0,
            "multa_por_hora_atraso": 150.0,
            "janela_limite_min": 45.0,
            "custo_por_km": None,
            "custo_por_km_sem_combustivel": None,
            "origem_custo_por_km": None,
            "prejuizo_por_bloqueio_brl": None,
            "tempo_espera_min": None,
        } | parametros

        def avaliar(rota):
            return cls.evaluate_route_tradeoff(
                distancia_km=rota["distancia_km"],
                tempo_min=rota["tempo_min"],
                probabilidade_atraso=rota.get("probabilidade_atraso"),
                probabilidade_bloqueio=rota.get("probabilidade_bloqueio"),
                consumo_km_l=aplicados["consumo_km_l"],
                preco_diesel_litro=aplicados["preco_diesel_litro"],
                custo_hora_veiculo=aplicados["custo_hora_veiculo"],
                custo_hora_motorista=aplicados["custo_hora_motorista"],
                valor_frete=aplicados["valor_frete"],
                valor_carga=aplicados["valor_carga"],
                multa_por_hora_atraso=aplicados["multa_por_hora_atraso"],
                janela_limite_min=aplicados["janela_limite_min"],
                custo_pedagio_conhecido=rota.get("custo_pedagio_conhecido", 0.0),
                custo_por_km=aplicados["custo_por_km"],
                custo_por_km_sem_combustivel=aplicados["custo_por_km_sem_combustivel"],
                origem_custo_por_km=aplicados["origem_custo_por_km"],
                prejuizo_por_bloqueio_brl=aplicados["prejuizo_por_bloqueio_brl"],
                tarifas_pendentes=rota.get("tarifas_pendentes", 0),
            )

        direta_eval, segura_eval = avaliar(rota_direta), avaliar(rota_segura)
        custo_desvio = round(
            segura_eval["custo_total_estimado_brl"] - direta_eval["custo_total_estimado_brl"], 2
        )
        escolha_segura = custo_desvio <= 0
        vantagem = abs(custo_desvio)
        rota_escolhida = "alternativa" if escolha_segura else "direta"
        comparacao = (
            "Os custos calculados das rotas sao iguais. " if custo_desvio == 0 else
            f"A rota {rota_escolhida} tem custo calculado R$ {vantagem:.2f} menor. "
        )
        justificativa = (
            comparacao + "A comparacao e parcial: consulte os componentes nao calculados e a cobertura dos pedagios."
        )

        aguardar = None
        if aplicados["tempo_espera_min"] is not None:
            espera_min = aplicados["tempo_espera_min"]
            custo_tempo_espera = round(
                espera_min / 60 * (aplicados["custo_hora_veiculo"] + aplicados["custo_hora_motorista"]), 2
            )
            atraso_original = max(0.0, rota_direta["tempo_min"] - aplicados["janela_limite_min"])
            atraso_com_espera = max(0.0, rota_direta["tempo_min"] + espera_min - aplicados["janela_limite_min"])
            multa_adicional = round(
                (atraso_com_espera - atraso_original) / 60 * aplicados["multa_por_hora_atraso"], 2
            )
            custo_aguardar = round(
                direta_eval["custo_total_estimado_brl"] + custo_tempo_espera + multa_adicional, 2
            )
            aguardar = {
                "tempo_espera_informado_min": espera_min,
                "custo_tempo_espera_brl": custo_tempo_espera,
                "multa_atraso_adicional_brl": multa_adicional,
                "custo_aguardar_brl": custo_aguardar,
                "delta_desviar_menos_aguardar_brl": round(
                    segura_eval["custo_total_estimado_brl"] - custo_aguardar, 2
                ),
                "aviso": "Risco apos a espera nao foi reavaliado; o tempo de espera e uma premissa informada.",
            }

        return {
            "recomendacao": "ROTA_ALTERNATIVA_SEGURA" if escolha_segura else "ROTA_DIRETA_ORIGINAL",
            "base_recomendacao": "CUSTOS_CALCULAVEIS_PARCIAIS",
            "decisao_operacional_automatica": False,
            "aviso": "Menor custo calculado nao autoriza viagem; riscos e cobertura viaria exigem avaliacao humana.",
            "justificativa_financeira": justificativa,
            "premissas_aplicadas": aplicados,
            "tradeoff": {
                "rota_direta": direta_eval,
                "rota_alternativa": segura_eval,
                "custo_desvio_brl": custo_desvio,
                "vantagem_economica_brl": vantagem,
                "aguardar": aguardar,
            },
        }
