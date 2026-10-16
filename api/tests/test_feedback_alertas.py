import pytest
import httpx
import asyncpg
from uuid import uuid4
from app.config import settings

BASE_URL = "http://127.0.0.1:8000/api/v1/alertas"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
HEADERS_ADMIN = {"X-API-Key": "key_admin_demo"}

@pytest.mark.asyncio
async def test_feedback_e_precisao_alertas():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers=HEADERS_ADMIN) as client:
        resp_prec = await client.get("/precisao")
        assert resp_prec.status_code == 200
        data = resp_prec.json()
        assert "metricas_precisao" in data
        assert "precisao_alertas_pct" in data["metricas_precisao"]


@pytest.mark.asyncio
async def test_feedback_nao_muda_alerta_global_nem_metricas_de_outra_empresa():
    id_evento = f"TESTE_ISOLAMENTO_{uuid4().hex}"
    conn = await asyncpg.connect(settings.database_url)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        try:
            await conn.execute("""
                INSERT INTO alertas_operacionais
                (id_evento, categoria, fonte, expiracao_em, confianca, status_evento, trechos_afetados)
                VALUES ($1, 'OCORRENCIA_CONFIRMADA', 'TESTE', now() + interval '1 hour', 0.9,
                        'CONFIRMADO', ARRAY[]::integer[])
            """, id_evento)
            demo_antes = (await client.get("/precisao", headers=HEADERS_ADMIN)).json()
            outra_antes = (await client.get("/precisao", headers={"X-API-Key": "key_admin_express"})).json()

            resposta = await client.post("/feedback", headers=HEADERS_ADMIN, json={
                "id_evento": id_evento,
                "falso_alerta": True,
                "motivo_reporte": "Relato incorreto no teste de isolamento",
            })
            assert resposta.status_code == 200

            alerta = await conn.fetchrow("SELECT status_evento, falso_alerta FROM alertas_operacionais WHERE id_evento = $1", id_evento)
            assert alerta["status_evento"] == "CONFIRMADO"
            assert alerta["falso_alerta"] is False

            demo_depois = (await client.get("/precisao", headers=HEADERS_ADMIN)).json()
            outra_depois = (await client.get("/precisao", headers={"X-API-Key": "key_admin_express"})).json()
            assert demo_depois["total_eventos_analisados"] == demo_antes["total_eventos_analisados"] + 1
            assert outra_depois == outra_antes
        finally:
            await conn.execute("DELETE FROM feedback_alertas_operacionais WHERE id_evento = $1", id_evento)
            await conn.execute("DELETE FROM alertas_operacionais WHERE id_evento = $1", id_evento)
            await conn.close()
