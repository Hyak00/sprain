CREATE TABLE IF NOT EXISTS painel_usuarios (
    id UUID PRIMARY KEY, email TEXT NOT NULL UNIQUE, empresa TEXT NOT NULL,
    tenant_id TEXT NOT NULL, papel TEXT NOT NULL CHECK(papel IN ('ADMIN','OPERATOR','VIEWER')),
    senha_hash TEXT NOT NULL, ativo BOOLEAN NOT NULL DEFAULT true,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS painel_sessoes (
    token_hash TEXT PRIMARY KEY, usuario_id UUID NOT NULL REFERENCES painel_usuarios(id),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(), expira_em TIMESTAMPTZ NOT NULL,
    revogado_em TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS painel_sessoes_usuario ON painel_sessoes(usuario_id);
CREATE TABLE IF NOT EXISTS painel_login_tentativas (
    id BIGSERIAL PRIMARY KEY, conta_hash TEXT NOT NULL, ip_hash TEXT NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS painel_login_conta ON painel_login_tentativas(conta_hash,criado_em);
CREATE INDEX IF NOT EXISTS painel_login_ip ON painel_login_tentativas(ip_hash,criado_em);
ALTER TABLE decisoes_gestor_operacao ADD COLUMN IF NOT EXISTS usuario_id UUID;
