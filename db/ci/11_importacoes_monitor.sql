CREATE TABLE IF NOT EXISTS monitor_importacoes (
    id UUID PRIMARY KEY,
    fonte TEXT NOT NULL,
    tenant_id TEXT,
    iniciado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    encerrado_em TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('EM_EXECUCAO','CONCLUIDO','PARCIAL','FALHA')),
    registros INTEGER CHECK (registros >= 0),
    falhas INTEGER CHECK (falhas >= 0),
    motivo_codigo TEXT
);
CREATE INDEX IF NOT EXISTS monitor_importacoes_data ON monitor_importacoes(iniciado_em DESC,id);
CREATE INDEX IF NOT EXISTS monitor_importacoes_empresa ON monitor_importacoes(tenant_id,iniciado_em DESC);
