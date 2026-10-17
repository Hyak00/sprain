-- Administração aditiva; segredos de recuperação nunca são persistidos em texto.
CREATE TABLE IF NOT EXISTS painel_financeiro (
    tenant_id TEXT PRIMARY KEY, dados JSONB NOT NULL DEFAULT '{}',
    versao INTEGER NOT NULL DEFAULT 1, atualizado_por UUID NOT NULL,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS painel_admin_auditoria (
    id BIGSERIAL PRIMARY KEY, tenant_id TEXT NOT NULL, ator_id UUID NOT NULL,
    acao TEXT NOT NULL, alvo_id UUID, dados JSONB NOT NULL DEFAULT '{}',
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS painel_admin_auditoria_empresa ON painel_admin_auditoria(tenant_id, criado_em DESC);
CREATE TABLE IF NOT EXISTS painel_recuperacoes (
    id UUID PRIMARY KEY, usuario_id UUID NOT NULL REFERENCES painel_usuarios(id),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(), expira_em TIMESTAMPTZ NOT NULL,
    token_hash TEXT UNIQUE, liberado_por UUID, liberado_em TIMESTAMPTZ,
    consumido_em TIMESTAMPTZ, cancelado_em TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS painel_recuperacoes_usuario ON painel_recuperacoes(usuario_id, criado_em DESC);
CREATE TABLE IF NOT EXISTS painel_recuperacao_tentativas (
    id BIGSERIAL PRIMARY KEY, conta_hash TEXT NOT NULL, ip_hash TEXT NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS painel_recuperacao_limite ON painel_recuperacao_tentativas(criado_em);
