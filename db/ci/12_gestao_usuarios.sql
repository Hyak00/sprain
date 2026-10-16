CREATE TABLE IF NOT EXISTS painel_usuarios_auditoria (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    ator_id UUID NOT NULL,
    usuario_id UUID NOT NULL,
    acao TEXT NOT NULL CHECK (acao IN ('CRIADO', 'PAPEL_ALTERADO', 'DESATIVADO')),
    papel_anterior TEXT,
    papel_novo TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_painel_usuarios_auditoria_tenant
    ON painel_usuarios_auditoria (tenant_id, criado_em DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_painel_usuarios_tenant_email
    ON painel_usuarios (tenant_id, email);
