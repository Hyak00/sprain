-- Reservas de chamadas feitas a provedores externos por empresa.
CREATE TABLE IF NOT EXISTS chamadas_api_externa (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    provedor TEXT NOT NULL,
    operacao TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'RESERVADA'
        CHECK (status IN ('RESERVADA', 'SUCESSO', 'FALHA')),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    concluido_em TIMESTAMPTZ,
    custo_brl NUMERIC(14,6) CHECK (custo_brl >= 0)
);
CREATE INDEX IF NOT EXISTS chamadas_api_externa_tenant_mes
    ON chamadas_api_externa(tenant_id, criado_em DESC);
