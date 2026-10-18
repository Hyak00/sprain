"""Instala o cadastro aditivo de resultados informados de viagens."""

from pathlib import Path

from app import database


SCHEMA = Path(__file__).resolve().parents[3] / "db" / "ci" / "14_resultados_viagem.sql"


async def garantir_schema():
    async with database.db_pool.acquire() as conn:
        await conn.execute(SCHEMA.read_text(encoding="utf-8"))
