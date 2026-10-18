"""A revisao publicada deve corresponder ao build e ficar restrita ao monitor interno."""

import httpx
import pytest
from fastapi import FastAPI

from app.routers.operacional_interno import router
from app.seguranca import get_current_user_claims
from app.versao import API_VERSION, informacao_versao


@pytest.mark.asyncio
async def test_versao_usa_commit_do_build_e_perfil_admin(monkeypatch):
    revisao = "A" * 40
    monkeypatch.setenv("SPRAIN_BUILD_COMMIT", revisao)
    claims = {"role": "ADMIN", "tenant_id": "empresa_teste"}
    app = FastAPI()
    app.include_router(router)

    async def identidade():
        return claims

    app.dependency_overrides[get_current_user_claims] = identidade
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://teste") as cli:
        resposta = await cli.get("/api/v1/operacional/versao")
        assert resposta.status_code == 200
        assert resposta.json() == {
            "versao_api": API_VERSION,
            "revisao": revisao.lower(),
            "revisao_identificada": True,
        }
        assert resposta.headers["cache-control"] == "no-store"

        claims["role"] = "VIEWER"
        assert (await cli.get("/api/v1/operacional/versao")).status_code == 403


def test_revisao_invalida_nao_e_exposta(monkeypatch):
    monkeypatch.setenv("SPRAIN_BUILD_COMMIT", "valor-acidental-que-nao-e-commit")
    assert informacao_versao()["revisao"] is None
    assert informacao_versao()["revisao_identificada"] is False
