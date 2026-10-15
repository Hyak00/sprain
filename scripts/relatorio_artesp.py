import os
import psycopg2

def tabela(cabecalho, linhas, larguras):
    formato = " | ".join(f"{{:<{l}}}" for l in larguras)
    print(formato.format(*cabecalho))
    for linha in linhas:
        print(formato.format(*[str(v) for v in linha]))

def secao(titulo):
    print("\n" + titulo)
    print("-" * 60)

def main():
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"], port=os.environ["DB_PORT"],
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"]
    )
    cursor = conn.cursor()

    print("RELATORIO DE QUALIDADE DA IMPORTACAO ARTESP")
    print("-" * 60)
    cursor.execute("SELECT nome, registros_importados, ultimo_sucesso_em FROM fontes_dados_externos WHERE nome LIKE 'ARTESP%' ORDER BY nome")
    for nome, importados, ultimo in cursor.fetchall():
        print(f"Fonte: {nome} | Importados: {importados} | Ultimo sucesso: {ultimo}")

    secao("COBERTURA POR ANO (ACIDENTES COM CAMINHAO)")
    cursor.execute("""
        SELECT EXTRACT(YEAR FROM data_ocorrencia)::int AS ano,
               COUNT(*) AS acidentes,
               SUM(caminhoes_envolvidos) AS caminhoes,
               COUNT(*) FILTER (WHERE classe = 'TOMBAMENTO') AS tombamentos,
               COUNT(DISTINCT DATE_TRUNC('month', data_ocorrencia)) AS meses,
               MIN(data_ocorrencia), MAX(data_ocorrencia)
        FROM tombamentos_caminhao
        WHERE ativo = true
        GROUP BY ano
        ORDER BY ano
    """)
    tabela(("ANO", "ACIDENTES", "CAMINHOES", "TOMBAMENTOS", "MESES", "PRIMEIRA", "ULTIMA"),
           cursor.fetchall(), (6, 10, 10, 12, 6, 10, 10))

    secao("ACIDENTES COM CAMINHAO POR RODOVIA (10 MAIORES)")
    cursor.execute("""
        SELECT rodovia, COUNT(*) AS total,
               COUNT(*) FILTER (WHERE classe = 'TOMBAMENTO') AS tombamentos,
               MIN(data_ocorrencia), MAX(data_ocorrencia),
               COUNT(DISTINCT km) AS kms_afetados
        FROM tombamentos_caminhao
        WHERE ativo = true
        GROUP BY rodovia
        ORDER BY total DESC
        LIMIT 10
    """)
    tabela(("RODOVIA", "TOTAL", "TOMBAMENTOS", "PRIMEIRA", "ULTIMA", "KMS AFETADOS"),
           cursor.fetchall(), (10, 7, 12, 10, 10, 12))

    secao("CORREDOR SP-310 E SP-255 POR CLASSE")
    cursor.execute("""
        SELECT rodovia, classe, COUNT(*) AS total
        FROM tombamentos_caminhao
        WHERE ativo = true AND rodovia IN ('SP-310', 'SP-255')
        GROUP BY rodovia, classe
        ORDER BY rodovia, total DESC
    """)
    tabela(("RODOVIA", "CLASSE", "TOTAL"), cursor.fetchall(), (10, 34, 7))

    secao("TRECHOS CRITICOS GERAL (POR KM, ARREDONDADO A 0,1)")
    cursor.execute("""
        SELECT rodovia, ROUND(km::numeric, 1) AS km_arredondado, COUNT(*) AS repeticoes
        FROM tombamentos_caminhao
        WHERE ativo = true AND km IS NOT NULL
        GROUP BY rodovia, km_arredondado
        ORDER BY repeticoes DESC
        LIMIT 5
    """)
    tabela(("RODOVIA", "KM", "REPETICOES"), cursor.fetchall(), (10, 8, 10))

    secao("TRECHOS CRITICOS NO CORREDOR SP-310 E SP-255")
    cursor.execute("""
        SELECT rodovia, ROUND(km::numeric, 1) AS km_arredondado, COUNT(*) AS repeticoes
        FROM tombamentos_caminhao
        WHERE ativo = true AND km IS NOT NULL AND rodovia IN ('SP-310', 'SP-255')
        GROUP BY rodovia, km_arredondado
        ORDER BY repeticoes DESC
        LIMIT 5
    """)
    tabela(("RODOVIA", "KM", "REPETICOES"), cursor.fetchall(), (10, 8, 10))

    print("\nLIMITACOES DA FONTE:")
    print("- Base de acidentes das concessionarias: nao traz alagamento nem interdicao.")
    print("- Duracao mediana e maxima nao calculadas (campo ausente na origem).")
    print("- Caminhao identificado pelo campo de veiculos (caminhao, carreta, bitrem).")
    print("- Acidentes com veiculo nao informado ficam fora da contagem.")
    print("- Cobre apenas rodovias com concessionaria.")
    print("- Registros duplicados ou sem coordenada valida sao descartados na importacao.")
    conn.close()

if __name__ == '__main__':
    main()