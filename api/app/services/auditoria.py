"""Migracao aditiva para manter as metricas de acuracia por empresa."""

from pathlib import Path

from app import database


SCHEMA = Path(__file__).resolve().parents[3] / "db/ci/10_auditoria_tenant.sql"


async def garantir_schema():
    async with database.db_pool.acquire() as conn:
        await conn.execute(SCHEMA.read_text(encoding="utf-8"))
