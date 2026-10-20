import argparse
import html
import math
import os
import re
import sys
import urllib.request
from datetime import time

URL_ESTACAO = "https://www.cgesp.org/v3/estacao.jsp?POSTO={posto}"
TETO_MM = 1000.0
PADRAO_ATUAL = re.compile(r"Per\S{0,8}\s*Atual:?\s*([\d.,]+)\s*mm", re.I)
PADRAO_ANTERIOR = re.compile(r"Per\S{0,8}\s*Anterior:?\s*([\d.,]+)\s*mm", re.I)
PADRAO_ZERAMENTO = re.compile(r"Zeramento:?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?", re.I)


def para_numero(bruto):
    texto = bruto.strip().strip(".,")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    valor = float(texto)
    if not math.isfinite(valor) or valor < 0 or valor > TETO_MM:
        raise ValueError(f"Valor de chuva fora do aceitavel: {bruto}")
    return valor


def ler_zeramento(texto):
    encontrado = PADRAO_ZERAMENTO.search(texto)
    if not encontrado:
        return None
    try:
        return time(int(encontrado.group(1)), int(encontrado.group(2)), int(encontrado.group(3) or 0))
    except ValueError:
        return None


def extrair_periodos(conteudo_html):
    texto = re.sub(r"<[^>]+>", " ", conteudo_html)
    texto = re.sub(r"\s+", " ", html.unescape(texto))
    atual = PADRAO_ATUAL.search(texto)
    anterior = PADRAO_ANTERIOR.search(texto)
    if not atual or not anterior:
        raise ValueError("Pagina do CGE sem os dois periodos de chuva.")
    return {
        "periodo_atual_mm": para_numero(atual.group(1)),
        "periodo_anterior_mm": para_numero(anterior.group(1)),
        "horario_zeramento": ler_zeramento(texto),
    }


def baixar(posto):
    pedido = urllib.request.Request(
        URL_ESTACAO.format(posto=posto),
        headers={"User-Agent": "SPRain-coleta/1.0"},
    )
    with urllib.request.urlopen(pedido, timeout=20) as resposta:
        return resposta.read(2_000_000).decode("utf-8", errors="replace")


def gravar(id_estacao, leitura):
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL

    destino = os.getenv("URL_BANCO") or URL.create(
        "postgresql+psycopg2",
        username=os.getenv("DB_USER", "enchentes"),
        password=os.getenv("DB_PASSWORD", "enchentes"),
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "enchentes"),
    )
    motor = create_engine(destino)
    try:
        with motor.begin() as conexao:
            cadastrada = conexao.execute(
                text("SELECT 1 FROM estacoes_meteorologicas WHERE id_estacao = :id AND ativa"),
                {"id": id_estacao},
            ).first()
            if cadastrada is None:
                raise RuntimeError(f"Estacao {id_estacao} nao cadastrada ou inativa.")
            conexao.execute(
                text(
                    "INSERT INTO leituras_cge_brutas "
                    "(id_estacao, periodo_atual_mm, periodo_anterior_mm, horario_zeramento) "
                    "VALUES (:id, :atual, :anterior, :zeramento)"
                ),
                {
                    "id": id_estacao,
                    "atual": leitura["periodo_atual_mm"],
                    "anterior": leitura["periodo_anterior_mm"],
                    "zeramento": leitura["horario_zeramento"],
                },
            )
    finally:
        motor.dispose()


def main():
    leitor = argparse.ArgumentParser()
    leitor.add_argument("--estacao", default="CGE_ITAQUERA")
    leitor.add_argument("--posto", default="1000864")
    argumentos = leitor.parse_args()
    try:
        leitura = extrair_periodos(baixar(argumentos.posto))
        gravar(argumentos.estacao, leitura)
    except Exception as erro:
        print(f"FALHA NA COLETA CGE: {erro}", file=sys.stderr)
        return 1
    print(
        f"Coleta CGE gravada: atual={leitura['periodo_atual_mm']} mm, "
        f"anterior={leitura['periodo_anterior_mm']} mm."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())