"""Mede consultas de rota e risco somente na demonstracao local isolada."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ENDPOINTS = {
    "rota": "/api/v1/rotas/intermunicipal",
    "risco": "/api/v1/dados-publicos/tombamentos?bbox=-48.5,-23.5,-46.0,-21.0&limite=20",
}


class SemRedirecionamento(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(SemRedirecionamento)


def validar_url_local(valor: str) -> str:
    url = urllib.parse.urlsplit(valor)
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}):
        raise ValueError("Use apenas a URL HTTP raiz de uma API local isolada, sem credenciais na URL.")
    if url.port is None:
        raise ValueError("Informe explicitamente a porta da API de teste.")
    return valor.rstrip("/")


def consultar(base_url: str, caminho: str, chave: str, timeout: float) -> tuple[int, object, float]:
    inicio = time.perf_counter()
    req = urllib.request.Request(base_url + caminho, headers={"X-API-Key": chave})
    try:
        with OPENER.open(req, timeout=timeout) as resposta:
            corpo = resposta.read(2_000_001)
            if len(corpo) > 2_000_000:
                raise ValueError("Resposta excedeu 2 MB.")
            return resposta.status, json.loads(corpo), (time.perf_counter() - inicio) * 1000
    except urllib.error.HTTPError as erro:
        erro.close()
        return erro.code, None, (time.perf_counter() - inicio) * 1000


def conferir_demo(base_url: str, timeout: float) -> None:
    req = urllib.request.Request(base_url + "/api/v1/demonstracao/estado")
    with OPENER.open(req, timeout=timeout) as resposta:
        estado = json.load(resposta)
    if estado.get("modo") != "DEMONSTRACAO_ISOLADA" or estado.get("demo_isolada") is not True:
        raise ValueError("A API nao confirmou demonstracao isolada; carga cancelada.")


def resposta_valida(tipo: str, corpo: object) -> bool:
    if not isinstance(corpo, dict):
        return False
    if tipo == "rota":
        return isinstance(corpo.get("resumo"), dict) and isinstance(corpo.get("segmentos"), list)
    return corpo.get("type") == "FeatureCollection" and isinstance(corpo.get("features"), list)


def medir(base_url: str, tipo: str, chave: str, quantidade: int, concorrencia: int, timeout: float) -> dict:
    caminho = ENDPOINTS[tipo]
    inicio = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concorrencia) as pool:
        futures = [pool.submit(consultar, base_url, caminho, chave, timeout) for _ in range(quantidade)]
        resultados = []
        for future in as_completed(futures):
            try:
                status, corpo, duracao = future.result()
                resultados.append((status, resposta_valida(tipo, corpo), duracao))
            except (OSError, ValueError, json.JSONDecodeError) as erro:
                resultados.append(("ERRO_REDE_OU_RESPOSTA", False, None))
    tempo_total = time.perf_counter() - inicio
    duracoes = sorted(item[2] for item in resultados if item[2] is not None)
    status = Counter(str(item[0]) for item in resultados)
    validas = sum(item[0] == 200 and item[1] for item in resultados)
    return {
        "endpoint": tipo,
        "requisicoes": quantidade,
        "concorrencia": concorrencia,
        "respostas_validas": validas,
        "status": dict(sorted(status.items())),
        "p50_ms": round(duracoes[math.ceil(len(duracoes) * 0.50) - 1], 2) if duracoes else None,
        "p95_ms": round(duracoes[math.ceil(len(duracoes) * 0.95) - 1], 2) if duracoes else None,
        "max_ms": round(duracoes[-1], 2) if duracoes else None,
        "requisicoes_por_segundo": round(quantidade / tempo_total, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18002")
    parser.add_argument("--requisicoes", type=int, default=20, help="Por endpoint, entre 1 e 100")
    parser.add_argument("--concorrencia", type=int, default=4, help="Entre 1 e 8")
    parser.add_argument("--timeout", type=float, default=15.0, help="Segundos por chamada, entre 1 e 30")
    parser.add_argument("--saida", type=Path, help="Arquivo JSON opcional para guardar a medicao")
    args = parser.parse_args()
    if not 1 <= args.requisicoes <= 100 or not 1 <= args.concorrencia <= 8 or not 1 <= args.timeout <= 30:
        parser.error("Limites: 1 a 100 requisicoes, 1 a 8 concorrentes, timeout de 1 a 30 segundos.")
    try:
        base_url = validar_url_local(args.base_url)
        chave = os.environ.get("SPRAIN_API_KEY", "")
        if not chave:
            raise ValueError("Configure SPRAIN_API_KEY para a chave do ambiente isolado.")
        conferir_demo(base_url, args.timeout)
        # Uma resposta válida por endpoint verifica a fixture antes de medir.
        for tipo, caminho in ENDPOINTS.items():
            status, corpo, _ = consultar(base_url, caminho, chave, args.timeout)
            if status != 200 or not resposta_valida(tipo, corpo):
                raise ValueError(f"Pré-verificação de {tipo} falhou (HTTP {status}).")
        resultados = [medir(base_url, tipo, chave, args.requisicoes, args.concorrencia, args.timeout)
                      for tipo in ENDPOINTS]
        relatorio = {"ambiente": "DEMONSTRACAO_ISOLADA", "base_url": base_url,
                     "resultados": resultados, "aprovado": all(r["respostas_validas"] == args.requisicoes for r in resultados)}
        conteudo = json.dumps(relatorio, ensure_ascii=False, indent=2)
        print(conteudo)
        if args.saida:
            args.saida.parent.mkdir(parents=True, exist_ok=True)
            args.saida.write_text(conteudo + "\n", encoding="utf-8")
        return 0 if relatorio["aprovado"] else 1
    except (OSError, ValueError, urllib.error.URLError) as erro:
        print(f"Medicao cancelada: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
