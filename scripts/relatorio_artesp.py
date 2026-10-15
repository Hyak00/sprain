import os
import psycopg2

CHUVA = "(condicao_meteorologica IN ('CHUVA', 'GAROA', 'GRANIZO') OR condicao_meteorologica LIKE 'CHUVA %')"
CANCELA = "COALESCE(subclasse, '') ILIKE '%CANCELA%'"

def tabela(cabecalho, linhas, larguras):
    formato = " | ".join(f"{{:<{l}}}" for l in larguras)
    print(formato.format(*cabecalho))
    for linha in linhas:
        print(formato.format(*[str(v) for v in linha]))

def secao(titulo):
    print("\n" + titulo)
    print("-" * 70)

def consultar(cursor, sql):
    cursor.execute(sql)
    return cursor.fetchall()

def main():
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"], port=os.environ["DB_PORT"],
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"]
    )
    cursor = conn.cursor()

    print("RELATORIO DE QUALIDADE DA IMPORTACAO ARTESP")
    print("-" * 70)
    for nome, importados, ultimo in consultar(cursor, "SELECT nome, registros_importados, ultimo_sucesso_em FROM fontes_dados_externos WHERE nome LIKE 'ARTESP%' ORDER BY nome"):
        print(f"Fonte: {nome} | Importados: {importados} | Ultimo sucesso: {ultimo}")

    secao("COBERTURA POR ANO (ACIDENTES COM CAMINHAO)")
    tabela(("ANO", "ACIDENTES", "CAMINHOES", "TOMBAMENTOS", "MESES", "PRIMEIRA", "ULTIMA"), consultar(cursor, """
        SELECT EXTRACT(YEAR FROM data_ocorrencia)::int AS ano,
               COUNT(*),
               SUM(caminhoes_envolvidos),
               COUNT(*) FILTER (WHERE classe = 'TOMBAMENTO'),
               COUNT(DISTINCT DATE_TRUNC('month', data_ocorrencia)),
               MIN(data_ocorrencia), MAX(data_ocorrencia)
        FROM tombamentos_caminhao
        WHERE ativo = true
        GROUP BY ano
        ORDER BY ano
    """), (6, 10, 10, 12, 6, 10, 10))

    secao("CONDICAO METEOROLOGICA REGISTRADA NO ACIDENTE (TODAS AS RODOVIAS)")
    tabela(("CONDICAO", "ACIDENTES", "PERCENTUAL"), consultar(cursor, """
        SELECT COALESCE(condicao_meteorologica, 'SEM REGISTRO') AS condicao,
               COUNT(*),
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)
        FROM tombamentos_caminhao
        WHERE ativo = true
        GROUP BY condicao
        ORDER BY COUNT(*) DESC
    """), (16, 10, 10))

    secao("ACIDENTES COM CAMINHAO POR RODOVIA (10 MAIORES)")
    tabela(("RODOVIA", "TOTAL", "TOMBAMENTOS", "PRIMEIRA", "ULTIMA", "KMS AFETADOS"), consultar(cursor, """
        SELECT rodovia, COUNT(*),
               COUNT(*) FILTER (WHERE classe = 'TOMBAMENTO'),
               MIN(data_ocorrencia), MAX(data_ocorrencia),
               COUNT(DISTINCT km)
        FROM tombamentos_caminhao
        WHERE ativo = true
        GROUP BY rodovia
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """), (10, 7, 12, 10, 10, 12))

    secao("CORREDOR SP-310 E SP-255 POR CLASSE")
    tabela(("RODOVIA", "CLASSE", "TOTAL"), consultar(cursor, """
        SELECT rodovia, classe, COUNT(*)
        FROM tombamentos_caminhao
        WHERE ativo = true AND rodovia IN ('SP-310', 'SP-255')
        GROUP BY rodovia, classe
        ORDER BY rodovia, COUNT(*) DESC
    """), (10, 34, 7))

    secao("CORREDOR SP-310 E SP-255: ACIDENTES E TOMBAMENTOS SOB CHUVA")
    tabela(("RODOVIA", "ACIDENTES", "SOB CHUVA", "% CHUVA", "TOMBAMENTOS", "TOMB. CHUVA", "% TOMB."), consultar(cursor, f"""
        SELECT rodovia,
               COUNT(*),
               COUNT(*) FILTER (WHERE {CHUVA}),
               ROUND(100.0 * COUNT(*) FILTER (WHERE {CHUVA}) / COUNT(*), 1),
               COUNT(*) FILTER (WHERE classe = 'TOMBAMENTO'),
               COUNT(*) FILTER (WHERE classe = 'TOMBAMENTO' AND {CHUVA}),
               ROUND(100.0 * COUNT(*) FILTER (WHERE classe = 'TOMBAMENTO' AND {CHUVA})
                     / NULLIF(COUNT(*) FILTER (WHERE classe = 'TOMBAMENTO'), 0), 1)
        FROM tombamentos_caminhao
        WHERE ativo = true AND rodovia IN ('SP-310', 'SP-255')
        GROUP BY rodovia
        ORDER BY rodovia
    """), (10, 10, 10, 8, 12, 12, 8))

    secao("TRECHOS CRITICOS GERAL (POR KM, SEM CANCELAS DE PEDAGIO)")
    tabela(("RODOVIA", "KM", "REPETICOES"), consultar(cursor, f"""
        SELECT rodovia, ROUND(km::numeric, 1) AS km_arredondado, COUNT(*)
        FROM tombamentos_caminhao
        WHERE ativo = true AND km IS NOT NULL AND NOT {CANCELA}
        GROUP BY rodovia, km_arredondado
        ORDER BY COUNT(*) DESC
        LIMIT 5
    """), (10, 8, 10))

    secao("TRECHOS CRITICOS NO CORREDOR SP-310 E SP-255 (SEM CANCELAS DE PEDAGIO)")
    tabela(("RODOVIA", "KM", "REPETICOES"), consultar(cursor, f"""
        SELECT rodovia, ROUND(km::numeric, 1) AS km_arredondado, COUNT(*)
        FROM tombamentos_caminhao
        WHERE ativo = true AND km IS NOT NULL AND NOT {CANCELA}
              AND rodovia IN ('SP-310', 'SP-255')
        GROUP BY rodovia, km_arredondado
        ORDER BY COUNT(*) DESC
        LIMIT 5
    """), (10, 8, 10))

    secao("ACIDENTES EM CANCELAS DE PEDAGIO (5 MAIORES CONCENTRACOES)")
    tabela(("RODOVIA", "KM", "ACIDENTES"), consultar(cursor, f"""
        SELECT rodovia, ROUND(km::numeric, 1) AS km_arredondado, COUNT(*)
        FROM tombamentos_caminhao
        WHERE ativo = true AND km IS NOT NULL AND {CANCELA}
        GROUP BY rodovia, km_arredondado
        ORDER BY COUNT(*) DESC
        LIMIT 5
    """), (10, 8, 10))

    print("\nLIMITACOES DA FONTE:")
    print("- Base de acidentes das concessionarias: nao traz alagamento nem interdicao.")
    print("- A condicao meteorologica e a anotada no acidente; chuva nao confirma alagamento.")
    print("- Percentual sob chuva sem horas de chuva por trecho nao mede risco por si so.")
    print("- Trechos com poucos casos nao permitem conclusao; conferir as contagens.")
    print("- O ano corrente cobre apenas os meses ja publicados pela ARTESP.")
    print("- Duracao mediana e maxima nao calculadas (campo ausente na origem).")
    print("- Caminhao identificado pelo campo de veiculos (caminhao, carreta, bitrem).")
    print("- Acidentes com veiculo nao informado ficam fora da contagem.")
    print("- Cancelas de pedagio ficam fora do ranking de trechos criticos.")
    print("- Cobre apenas rodovias com concessionaria.")
    print("- Registros duplicados ou sem coordenada valida sao descartados na importacao.")
    conn.close()

if __name__ == '__main__':
    main()