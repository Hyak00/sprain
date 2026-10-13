import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1/logistica"
TIMEOUT = httpx.Timeout(45.0, connect=10.0)
HEADERS_ADMIN = {"X-API-Key": "key_admin_demo"}
HEADERS_EXPRESS = {"X-API-Key": "key_admin_express"}

@pytest.mark.asyncio
async def test_fluxo_explicacao_geometria_e_decisao_gestor():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers=HEADERS_ADMIN) as client:
        sim = await client.post("/simular-impacto", json={"precipitacao_mm": 85.0})
        assert sim.status_code == 200
        recs = sim.json()["recomendacoes"]
        assert len(recs) > 0
        id_op = recs[0]["id_operacao"]

        exp = await client.get(f"/operacoes/{id_op}/explicacao")
        assert exp.status_code == 200
        exp_data = exp.json()
        assert "validacao_rota" in exp_data
        assert exp_data["validacao_rota"]["rota_alternativa_disponivel"] is True
        assert exp_data["geometrias"]["rota_alternativa_geojson"] is not None

        dec = await client.post(f"/operacoes/{id_op}/decisao", json={
            "decisao": "APROVAR_DESVIO",
            "motivo_gestor": "Chuva severa confirmada no corredor, autorizado desvio preventivo."
        })
        assert dec.status_code == 200
        assert dec.json()["decisao_registrada"] == "APROVAR_DESVIO"

        hist = await client.get(f"/operacoes/{id_op}/decisoes")
        assert hist.status_code == 200
        assert len(hist.json()) >= 1
        assert hist.json()[0]["decisao"] == "APROVAR_DESVIO"

        vazamento = await client.get(f"/operacoes/{id_op}/decisoes", headers=HEADERS_EXPRESS)
        assert vazamento.status_code == 200
        assert vazamento.json() == []
