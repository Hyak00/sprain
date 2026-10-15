"""Atualiza fontes oficiais fora do processo HTTP, com falhas isoladas por fonte."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


IMPORTADOR = Path(__file__).with_name("sincronizar_dados_publicos.py")
FONTES = ("artesp", "anp", "anp-semanal", "anp-cadastro", "ssp-roubo")


def executar_rodada() -> bool:
    sucesso = True
    tarefas=[(fonte,[sys.executable,'-B',str(IMPORTADOR),fonte,'--aplicar']) for fonte in FONTES]
    tenant=os.getenv('SPRAIN_INFRA_TENANT','').strip()
    if tenant:
        tarefas.append(('estruturas-osm',[sys.executable,'-B',str(IMPORTADOR.with_name('sincronizar_estruturas_corredor.py')),'--tenant',tenant,'--aplicar']))
    for fonte,comando in tarefas:
        try:
            resultado = subprocess.run(
                comando,
                timeout=600,
                check=False,
            )
            falhou = resultado.returncode != 0
        except (subprocess.TimeoutExpired, OSError):
            falhou = True
        if falhou:
            sucesso = False
            print(f"{datetime.now(timezone.utc).isoformat()} fonte={fonte} falhou; outras fontes continuam.",
                  file=sys.stderr, flush=True)
    return sucesso


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Executa uma rodada e termina")
    args = parser.parse_args()
    horas = int(os.getenv("DADOS_PUBLICOS_INTERVALO_HORAS", "24"))
    if not 1 <= horas <= 168:
        parser.error("DADOS_PUBLICOS_INTERVALO_HORAS deve estar entre 1 e 168.")
    while True:
        sucesso = executar_rodada()
        if args.once:
            raise SystemExit(0 if sucesso else 1)
        time.sleep(horas * 3600)


if __name__ == "__main__":
    main()
