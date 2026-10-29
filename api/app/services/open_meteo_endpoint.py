"""Seleciona o endpoint Open-Meteo conforme a licença do ambiente."""

from __future__ import annotations

import os
from urllib.parse import urlencode


def producao() -> bool:
    return os.getenv("ENVIRONMENT", "").strip().lower() == "production"


def fonte_disponivel() -> bool:
    return not producao() or bool(os.getenv("OPEN_METEO_API_KEY", "").strip())


def url_previsao(parametros: dict[str, object]) -> str:
    chave = os.getenv("OPEN_METEO_API_KEY", "").strip()
    if producao() and not chave:
        raise RuntimeError("Coleta Open-Meteo em produção exige OPEN_METEO_API_KEY comercial.")

    host = "customer-api.open-meteo.com" if chave else "api.open-meteo.com"
    consulta = dict(parametros)
    if chave:
        consulta["apikey"] = chave
    return f"https://{host}/v1/forecast?{urlencode(consulta)}"
