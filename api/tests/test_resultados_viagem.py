"""Viagem informada e correcoes: persistencia real, sem inventar economia."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.config import settings
from app.database import get_connection
from app.routers.logistica import obter_sumario_executivo
from app.routers.relatorios_painel import router as relatorios_router
from app.routers.resultados_viagem import ResultadoViagemRequest, router as resultados_router
from app.seguranca import get_current_user_claims
from app.services.resultados_viagem import SCHEMA


def dados(**mudancas):
    return {
        "finalizada_em": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "rota_executada": "DESVIO",
        "custo_real_brl": "0.00",
        "fonte": "RELATO_OPERADOR",
    } | mudancas


@pytest.mark.parametrize("mudancas", [
    {"custo_real_brl": None},
    {"custo_real_brl": "NaN"},
    {"custo_real_brl": "-1"},
    {"custo_real_brl": "1.001"},
    {"finalizada_em": "2026-10-16T12:00:00"},
    {"finalizada_em": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()},
    {"fonte": "DOCUMENTO"},
])
def test_medidas_invalidas_sao_recusadas(mudancas):
    with pytest.raises(ValidationError):
        ResultadoViagemRequest.model_validate(dados(**mudancas))


@pytest.mark.asyncio
async def test_resultado_corrigido_e_piloto_separam_informado_de_comprovado():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction(isolation="repeatable_read")
    await tx.start()
    try:
        await conn.execute(SCHEMA.read_text(encoding="utf-8"))
        await conn.execute(SCHEMA.read_text(encoding="utf-8"))
        sufixo = uuid4().hex[:12]
        tenant, outro = "viagem_" + sufixo, "outra_" + sufixo
        operacao, op_outra = "VIAGEM_" + sufixo, "OUTRA_" + sufixo
        for op, empresa in ((operacao, tenant), (op_outra, outro)):
            await conn.execute("""
                INSERT INTO operacoes (id_operacao,tenant_id,origem_lat,origem_lon,destino_lat,destino_lon,
                    janela_inicio,janela_fim) VALUES ($1,$2,-23.5,-46.5,-23.6,-46.6,now(),now())
            """, op, empresa)
        decisao_outra = await conn.fetchval("""
            INSERT INTO decisoes_gestor_operacao (id_operacao,tenant_id,decisao,motivo_gestor)
            VALUES ($1,$2,'AGUARDAR_MELHORA','Teste') RETURNING id_decisao
        """, op_outra, outro)
        decisao_propria = await conn.fetchval("""
            INSERT INTO decisoes_gestor_operacao (id_operacao,tenant_id,decisao,motivo_gestor)
            VALUES ($1,$2,'MANTER_ROTA_ORIGINAL','Teste') RETURNING id_decisao
        """, operacao, tenant)

        claims = {"tenant_id": tenant, "role": "OPERATOR", "usuario_id": str(uuid4())}
        app = FastAPI()
        app.include_router(resultados_router)
        app.include_router(relatorios_router)

        async def identidade():
            return claims

        async def conexao():
            yield conn

        app.dependency_overrides[get_current_user_claims] = identidade
        app.dependency_overrides[get_connection] = conexao
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://teste") as cli:
            caminho = f"/api/v1/logistica/operacoes/{operacao}/resultados-viagem"
            resposta = await cli.post(caminho, json=dados(duracao_real_min="30.50"))
            assert resposta.status_code == 201, resposta.text
            primeiro = resposta.json()
            assert primeiro["custo_real_brl"] == 0
            assert primeiro["verificacao"] == "NAO_VERIFICADO"
            assert primeiro["usuario_id"] == claims["usuario_id"]

            assert (await cli.post(caminho, json=dados())).status_code == 409
            assert (await cli.post(caminho, json=dados(
                substitui_id=primeiro["id"], id_decisao=decisao_outra,
            ))).status_code == 422
            correcao = await cli.post(caminho, json=dados(
                substitui_id=primeiro["id"], id_decisao=decisao_propria,
                rota_executada="ORIGINAL", custo_real_brl="45.20",
            ))
            assert correcao.status_code == 201, correcao.text
            assert correcao.json()["substitui_id"] == primeiro["id"]
            assert correcao.json()["id_decisao"] == decisao_propria
            assert (await cli.post(caminho, json=dados(substitui_id=primeiro["id"]))).status_code == 409

            claims["role"] = "VIEWER"
            assert (await cli.post(caminho, json=dados())).status_code == 403
            historico = await cli.get(caminho)
            assert historico.status_code == 200
            assert len(historico.json()["items"]) == 2
            assert historico.json()["items"][0]["custo_real_brl"] == 45.2
            assert historico.headers["cache-control"] == "no-store"

            piloto = (await cli.get("/api/v1/painel/relatorios/piloto")).json()
            assert piloto["amostra"]["viagens_com_resultado"] == 1
            assert piloto["amostra"]["viagens_com_custo_informado"] == 1
            assert piloto["indicadores"]["custo_informado"]["valor_brl"] == 45.2
            assert piloto["indicadores"]["desvios_informados"]["quantidade"] == 0
            assert piloto["indicadores"]["custo_observado"]["valor_brl"] is None
            assert piloto["indicadores"]["economia_comprovada"]["valor_brl"] is None
            sumario = (await obter_sumario_executivo(tenant_id=tenant, conn=conn))["kpis"]
            assert sumario["viagens_com_resultado_informado"] == 1
            assert sumario["custo_informado_brl"] == 45.2
            assert sumario["desvios_informados"] == 0
            assert sumario["custo_observado_brl"] is None
            assert sumario["economia_comprovada_brl"] is None

            claims["tenant_id"] = outro
            assert (await cli.get(caminho)).status_code == 404
            claims["role"] = "OPERATOR"
            assert (await cli.post(caminho, json=dados())).status_code == 404
            assert (await cli.get("/api/v1/painel/relatorios/piloto")).json()["amostra"]["viagens_com_resultado"] == 0
            assert (await obter_sumario_executivo(tenant_id=outro, conn=conn))["kpis"]["custo_informado_brl"] is None
    finally:
        await tx.rollback()
        await conn.close()
