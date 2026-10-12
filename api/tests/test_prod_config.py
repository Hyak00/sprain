import pytest
from fastapi import HTTPException
from app import seguranca

def test_producao_recusa_sem_segredos(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DB_PASSWORD", "enchentes")
    with pytest.raises(RuntimeError):
        seguranca.validar_configuracao_producao()

def test_producao_recusa_chave_demo(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DB_PASSWORD", "senha_forte_exclusiva_prod_2026")
    monkeypatch.setenv("WEBHOOK_SECRET_KEY", "chave_fernet_valida_prod_2026_123456")
    monkeypatch.setenv("TENANT_API_KEYS", "key_admin_demo:ADMIN:demo_corp")
    with pytest.raises(RuntimeError):
        seguranca.validar_configuracao_producao()

def test_producao_sem_tenant_keys_bloqueia_fallback_demo(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("TENANT_API_KEYS", raising=False)
    with pytest.raises(HTTPException) as exc:
        seguranca.carregar_chaves_tenants()
    assert exc.value.status_code == 503
