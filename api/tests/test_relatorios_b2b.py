import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1/logistica"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

@pytest.mark.asyncio
async def test_exportacao_csv_auditoria():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers={"X-API-Key": "key_admin_demo"}) as client:
        headers = {"X-API-Key": "key_admin_demo"}
        resp = await client.get("/relatorios/auditoria.csv?tenant_id=demo_corp", headers=headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        assert "attachment; filename=auditoria_logistica_demo_corp.csv" in resp.headers.get("content-disposition", "")
        content = resp.text
        assert "id_veiculo;origem;destino;precipitacao_mm" in content

@pytest.mark.asyncio
async def test_relatorio_sumario_executivo_acesso_viewer():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers={"X-API-Key": "key_admin_demo"}) as client:
        headers = {"X-API-Key": "key_viewer_demo"}
        resp = await client.get("/relatorios/sumario-executivo?tenant_id=demo_corp", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "demo_corp"
        assert "kpis" in data
        assert "total_operacoes" in data["kpis"]
        assert "indice_resiliencia_pct" in data["kpis"]


RELATORIOS_URL = "http://127.0.0.1:8000/api/v1/relatorios"

@pytest.mark.asyncio
async def test_relatorio_backtest_comercial_json():
    async with httpx.AsyncClient(base_url=RELATORIOS_URL, timeout=TIMEOUT, headers={"X-API-Key": "key_admin_demo"}) as client:
        resp = await client.get("/backtest-comercial")
        assert resp.status_code == 200
        data = resp.json()
        assert "estatisticas_gerais" in data
        assert "distribuicao_rodovias" in data
        assert "principais_pontos_criticos_chuva" in data
        assert "proposta_valor_b2b" in data
        assert data["proposta_valor_b2b"]["reducao_esperada_sinistros_pct"] > 0
        total = data["estatisticas_gerais"]["total_sinistros_caminhao"]
        assert total >= 0
        assert data["estatisticas_gerais"]["sinistros_sob_chuva_ou_pista_molhada"] >= 0
        assert data["estatisticas_gerais"]["tombamentos_caminhao_sob_chuva"] >= 0
        if total > 0:
            assert data["estatisticas_gerais"]["total_sinistros_caminhao"] == 9068
            assert data["estatisticas_gerais"]["sinistros_sob_chuva_ou_pista_molhada"] == 741
            assert data["estatisticas_gerais"]["tombamentos_caminhao_sob_chuva"] == 97
            assert len(data["distribuicao_rodovias"]) == 3
            assert len(data["principais_pontos_criticos_chuva"]) == 5

@pytest.mark.asyncio
async def test_relatorio_backtest_comercial_csv():
    async with httpx.AsyncClient(base_url=RELATORIOS_URL, timeout=TIMEOUT, headers={"X-API-Key": "key_admin_demo"}) as client:
        resp = await client.get("/backtest-comercial?formato=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        assert "dossie_backtest_comercial_b2b.csv" in resp.headers.get("content-disposition", "")
        texto = resp.text
        assert "METRICA;VALOR;DETALHE" in texto
        assert "TOTAL_SINISTROS_CAMINHAO" in texto
        assert "SINISTROS_SOB_CHUVA" in texto


@pytest.mark.asyncio
async def test_relatorio_backtest_comercial_html():
    async with httpx.AsyncClient(base_url=RELATORIOS_URL, timeout=TIMEOUT, headers={"X-API-Key": "key_admin_demo"}) as client:
        resp = await client.get("/backtest-comercial?formato=html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        texto = resp.text
        assert "SPRain Intelligence" in texto
        assert "Sinistros Sob Chuva" in texto
        assert "Total Sinistros Caminhao" in texto
