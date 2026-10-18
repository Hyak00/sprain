"""Consulta local de capacidade do PostgreSQL, sem alterar dados.

Execute na raiz do projeto: python scripts/monitorar_banco.py
Usa as variáveis DB_* do ambiente ou do arquivo .env local.
"""

import json
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from app.config import settings


CONSULTA = """
SELECT clock_timestamp() AS consultado_em,
       pg_database_size(current_database())::bigint AS tamanho_banco_bytes,
       (SELECT numbackends::int FROM pg_stat_database
        WHERE datname = current_database()) AS conexoes_banco,
       (SELECT count(*)::int FROM pg_stat_activity
        WHERE backend_type = 'client backend') AS conexoes_servidor,
       current_setting('max_connections')::int AS limite_global_conexoes
"""


def coletar() -> dict:
    conn = psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        dbname=settings.DB_NAME,
        connect_timeout=5,
        options="-c default_transaction_read_only=on",
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(CONSULTA)
            consultado_em, tamanho, conexoes_banco, conexoes_servidor, limite = cursor.fetchone()
        return {
            "consultado_em": consultado_em.isoformat(),
            "tamanho_banco_bytes": tamanho,
            "conexoes_banco": conexoes_banco,
            "conexoes_servidor": conexoes_servidor,
            "limite_global_conexoes": limite,
            "uso_global_conexoes_pct": round(100 * conexoes_servidor / limite, 1),
        }
    finally:
        conn.close()


def main() -> int:
    try:
        print(json.dumps(coletar(), ensure_ascii=False))
    except psycopg2.Error:
        print(json.dumps({"erro": "CONSULTA_BANCO_FALHOU"}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
