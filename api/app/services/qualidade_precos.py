from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from statistics import median


def analisar_qualidade_precos(
    registros: list[dict],
    data_referencia: date | None = None,
    dias_maximos: int = 14,
    amostra_minima: int = 5,
    desvio_relativo_minimo: Decimal = Decimal("0.30"),
) -> list[dict]:
    if dias_maximos < 0:
        raise ValueError("dias_maximos não pode ser negativo")
    if amostra_minima < 3:
        raise ValueError("amostra_minima deve ser pelo menos 3")
    if desvio_relativo_minimo < 0:
        raise ValueError("desvio_relativo_minimo não pode ser negativo")

    hoje = data_referencia or date.today()
    grupos = defaultdict(list)
    alertas = []

    for indice, registro in enumerate(registros):
        data = registro.get("data")
        preco = registro.get("preco")

        if not isinstance(data, date) or isinstance(data, datetime):
            continue
        if not isinstance(preco, Decimal) or not preco.is_finite() or preco <= 0:
            continue

        idade = (hoje - data).days

        if idade > dias_maximos:
            alertas.append({
                "indice": indice,
                "tipo": "DADO_DESATUALIZADO",
                "motivo": f"Coleta tem {idade} dias.",
                "preco_original": preco,
                "url_fonte": registro.get("url_fonte"),
            })

        uf = str(registro.get("uf") or "").strip().upper()
        municipio = " ".join(str(registro.get("municipio") or "").upper().split())
        produto = " ".join(str(registro.get("produto") or "").upper().split())

        if uf and municipio and produto:
            grupos[(uf, municipio, produto, data)].append((indice, preco))

    for observacoes in grupos.values():
        if len(observacoes) < amostra_minima:
            continue

        referencia = median([preco for _, preco in observacoes])

        if referencia <= 0:
            continue

        for indice, preco in observacoes:
            desvio = abs(preco - referencia) / referencia

            if desvio >= desvio_relativo_minimo:
                registro = registros[indice]
                alertas.append({
                    "indice": indice,
                    "tipo": "PRECO_ATIPICO",
                    "motivo": (
                        f"Desvio de {desvio:.0%} da mediana "
                        f"do grupo (R${referencia:.3f})."
                    ),
                    "preco_original": preco,
                    "url_fonte": registro.get("url_fonte"),
                })

    return alertas
