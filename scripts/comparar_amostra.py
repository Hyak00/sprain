import csv
import io
import os
import re
import sys
import urllib.request

import psycopg2

from sincronizar_dados_publicos import _data_artesp, _numero, caminhoes_envolvidos, texto_csv

def normalizar_rodovia(texto):
    return re.sub(r"[^A-Z0-9]", "", (texto or "").upper())

def divergencias(linha, classe, caminhoes, lat, lon):
    motivos = []
    if (linha["CLASSE"] or "").strip().upper() != classe:
        motivos.append("classe_diferente")
    if caminhoes_envolvidos(linha["VEICULOS_ENVOLVIDOS"] or "") != caminhoes:
        motivos.append("caminhoes_diferentes")
    try:
        if abs(_numero(linha["LATITUDE"]) - lat) > 1e-6 or abs(_numero(linha["LONGITUDE"]) - lon) > 1e-6:
            motivos.append("coordenada_diferente")
    except (ValueError, TypeError):
        motivos.append("coordenada_diferente")
    return motivos

def main():
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    tamanho = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    conn = psycopg2.connect(host=os.environ["DB_HOST"], port=os.environ["DB_PORT"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], dbname=os.environ["DB_NAME"])
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM fontes_dados_externos WHERE nome = %s", (f"ARTESP_{ano}",))
    fonte = cursor.fetchone()
    if not fonte:
        raise SystemExit(f"fonte ARTESP_{ano} nao encontrada")
    url = fonte[0]
    pedido = urllib.request.Request(url, headers={"User-Agent": "SPRain-dados-publicos/1.0"})
    with urllib.request.urlopen(pedido, timeout=60) as resposta:
        dados = resposta.read()
    leitor = csv.DictReader(io.StringIO(texto_csv(dados), newline=""))
    indice = {}
    total = com_caminhao = 0
    for linha in leitor:
        total += 1
        if caminhoes_envolvidos(linha["VEICULOS_ENVOLVIDOS"] or "") > 0:
            com_caminhao += 1
        try:
            chave = (_data_artesp(linha["DATA"] or ""), (linha["HORA"] or "").strip(), normalizar_rodovia(linha["RODOVIA"]), round(_numero(linha["KM"]), 3))
        except (ValueError, TypeError):
            continue
        indice.setdefault(chave, []).append(linha)
    cursor.execute("SELECT count(*) FROM tombamentos_caminhao WHERE ativo AND url_fonte = %s", (url,))
    no_banco = cursor.fetchone()[0]
    cursor.execute("SELECT rodovia, km, data_ocorrencia, hora_ocorrencia, classe, caminhoes_envolvidos, ST_Y(geom), ST_X(geom) FROM tombamentos_caminhao WHERE ativo AND url_fonte = %s ORDER BY random() LIMIT %s", (url, tamanho))
    amostra = cursor.fetchall()
    resultado = {"conferem": 0, "sem_par_no_csv": 0, "classe_diferente": 0, "caminhoes_diferentes": 0, "coordenada_diferente": 0}
    for rodovia, km, data, hora, classe, caminhoes, lat, lon in amostra:
        chave = (data, hora.isoformat() if hora else "", normalizar_rodovia(rodovia), round(km, 3))
        candidatas = indice.get(chave)
        if not candidatas:
            resultado["sem_par_no_csv"] += 1
            continue
        melhor = min((divergencias(c, classe, caminhoes, lat, lon) for c in candidatas), key=len)
        if not melhor:
            resultado["conferem"] += 1
        for motivo in melhor:
            resultado[motivo] += 1
    print(f"ARTESP_{ano}")
    print(f"linhas no CSV: {total} | com caminhao: {com_caminhao} | ativos no banco: {no_banco} | diferenca: {com_caminhao - no_banco}")
    print(f"amostra de {len(amostra)} registros do banco comparada ao CSV oficial:")
    for nome, valor in resultado.items():
        print(f"  {nome}: {valor}")
    conn.close()

if __name__ == "__main__":
    main()