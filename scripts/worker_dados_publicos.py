from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

IMPORTADOR = Path(__file__).with_name("sincronizar_dados_publicos.py")
FONTES = ("artesp", "anp", "anp-cadastro", "ssp-roubo")

def disparar_alerta(fonte: str, erro: str) -> None:
    webhook_url = os.getenv("WEBHOOK_ALERTA_DADOS")
    if not webhook_url:
        return
    payload = {
        "evento": "FALHA_IMPORTACAO_DADOS_PUBLICOS",
        "fonte": fonte,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "erro": erro[-1000:]
    }
    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Falha ao enviar alerta para webhook: {e}", file=sys.stderr, flush=True)

def executar_rodada() -> bool:
    sucesso = True
    for fonte in FONTES:
        resultado = subprocess.run(
            [sys.executable, "-B", str(IMPORTADOR), fonte, "--aplicar"],
            timeout=600,
            capture_output=True,
            text=True
        )
        if resultado.returncode:
            sucesso = False
            msg_erro = f"Erro na fonte {fonte}:\n{resultado.stderr}"
            print(f"{datetime.now(timezone.utc).isoformat()} {msg_erro}", file=sys.stderr, flush=True)
            disparar_alerta(fonte, resultado.stderr)
        else:
            print(resultado.stdout.strip(), flush=True)
    return sucesso

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Executa uma rodada e termina")
    args = parser.parse_args()
    horas = int(os.getenv("DADOS_PUBLICOS_INTERVALO_HORAS", "24"))
    if not 1 <= horas <= 168:
        parser.error("DADOS_PUBLICOS_INTERVALO_HORAS deve estar entre 1 e 168.")
    while True:
        print(f"{datetime.now(timezone.utc).isoformat()} Iniciando rodada de importacao...", flush=True)
        sucesso = executar_rodada()
        print(f"{datetime.now(timezone.utc).isoformat()} Rodada concluida.", flush=True)
        if args.once:
            raise SystemExit(0 if sucesso else 1)
        time.sleep(horas * 3600)

if __name__ == "__main__":
    main()