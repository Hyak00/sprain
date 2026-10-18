"""Identificacao da revisao embutida na imagem de deploy."""

import os
import re


API_VERSION = "1.1.0"


def informacao_versao():
    revisao = os.getenv("SPRAIN_BUILD_COMMIT", "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", revisao):
        revisao = None
    return {
        "versao_api": API_VERSION,
        "revisao": revisao,
        "revisao_identificada": revisao is not None,
    }
