"""Esquema aditivo para dados publicos; importacao roda fora da API."""

from pathlib import Path

from app import database


SCHEMA = Path(__file__).resolve().parents[3] / "db/ci/04_dados_riscos_combustiveis.sql"


async def garantir_schema():
    async with database.db_pool.acquire() as conn:
        await conn.execute(SCHEMA.read_text(encoding="utf-8"))
