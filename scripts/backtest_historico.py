import os
import psycopg2

def main():
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"], port=os.environ["DB_PORT"],
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"]
    )
    cursor = conn.cursor()

    print("RELATORIO DE BACKTEST HISTORICO (CORREDOR PRIORITARIO)")
    print("-" * 70)

    cursor.execute("""
        SELECT 
            rodovia,
            COUNT(*) AS total_acidentes,
            COUNT(*) FILTER (WHERE classe = 'TOMBAMENTO') AS total_tombamentos
        FROM tombamentos_caminhao
        WHERE ativo = true AND rodovia IN ('SP-310', 'SP-255', 'SP-330', 'SP-348')
        GROUP BY rodovia
        ORDER BY total_acidentes DESC
    """)
    
    print(f"{'RODOVIA':<10} | {'ACIDENTES':<10} | {'TOMBAMENTOS'}")
    print("-" * 70)
    for row in cursor.fetchall():
        print(f"{row[0]:<10} | {row[1]:<10} | {row[2]}")

    print("\nCONCLUSAO DO BACKTEST:")
    print("- Consulta otimizada executada com sucesso sobre o corredor principal.")

    conn.close()

if __name__ == "__main__":
    main()