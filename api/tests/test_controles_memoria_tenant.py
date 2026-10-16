"""Operações administrativas em memória não podem afetar outra empresa."""

import httpx
import pytest

from app.main import app
from app.services.rate_limiter import TenantRateLimiter
from app.services.routing_engine import RoutingEngine


BASE = "/api/v1/logistica"
ADMIN_DEMO = {"X-API-Key": "key_admin_demo"}
ADMIN_EXPRESS = {"X-API-Key": "key_admin_express"}
VIEWER_DEMO = {"X-API-Key": "key_viewer_demo"}


@pytest.mark.asyncio
async def test_cache_administrativo_isolado_por_tenant():
    RoutingEngine.clear_cache()
    RoutingEngine._set_cache("demo_corp:teste", {"origem": "demo"})
    RoutingEngine._set_cache("log_express:teste", {"origem": "express"})
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            demo = await client.get(f"{BASE}/performance/cache", headers=ADMIN_DEMO)
            express = await client.get(f"{BASE}/performance/cache", headers=ADMIN_EXPRESS)
            assert demo.status_code == express.status_code == 200
            assert demo.json()["total_entradas"] == 1
            assert express.json()["total_entradas"] == 1

            forbidden = await client.post(f"{BASE}/performance/cache/limpar", headers=VIEWER_DEMO)
            assert forbidden.status_code == 403
            cross_tenant = await client.post(
                f"{BASE}/performance/cache/limpar?tenant_id=log_express", headers=ADMIN_DEMO
            )
            assert cross_tenant.status_code == 403

            cleared = await client.post(f"{BASE}/performance/cache/limpar", headers=ADMIN_DEMO)
            assert cleared.status_code == 200
            assert RoutingEngine.cache_stats("demo_corp")["total_entradas"] == 0
            assert RoutingEngine.cache_stats("log_express")["total_entradas"] == 1
    finally:
        RoutingEngine.clear_cache()


@pytest.mark.asyncio
async def test_reset_da_quota_administrativa_isolado_por_tenant():
    TenantRateLimiter.reset("demo_corp")
    TenantRateLimiter.reset("log_express")
    TenantRateLimiter.check_rate_limit("demo_corp")
    TenantRateLimiter.check_rate_limit("log_express")
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            forbidden = await client.post(f"{BASE}/rate-limit/reset", headers=VIEWER_DEMO)
            assert forbidden.status_code == 403
            cross_tenant = await client.post(
                f"{BASE}/rate-limit/reset?tenant_id=log_express", headers=ADMIN_DEMO
            )
            assert cross_tenant.status_code == 403

            cleared = await client.post(f"{BASE}/rate-limit/reset", headers=ADMIN_DEMO)
            assert cleared.status_code == 200
            assert "demo_corp" not in TenantRateLimiter._history
            assert len(TenantRateLimiter._history["log_express"]) == 1
    finally:
        TenantRateLimiter.reset("demo_corp")
        TenantRateLimiter.reset("log_express")
