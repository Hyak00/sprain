"""Aplica as migracoes operacionais que nao fazem parte do dump inicial."""

from pathlib import Path

from app import database


_DIRETORIO = Path(__file__).resolve().parents[3] / "db" / "ci"
ARQUIVOS = tuple(_DIRETORIO / f"{numero:02d}_{nome}.sql" for numero, nome in (
    (5, "meteorologia"),
    (6, "alertas_confianca"),
    (7, "validacao_espacial"),
    (8, "feedback_alertas"),
    (9, "bacias_hidrograficas"),
))


async def aplicar(conn):
    for arquivo in ARQUIVOS:
        await conn.execute(arquivo.read_text(encoding="utf-8"))


async def garantir_schema():
    async with database.db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
                "sprain:esquema_operacional",
            )
            await aplicar(conn)
