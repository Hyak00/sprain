-- Progresso de ativação por empresa. Não altera cadastros ou cálculos existentes.
CREATE TABLE IF NOT EXISTS painel_onboarding (
    tenant_id text PRIMARY KEY,
    iniciado_em timestamptz NOT NULL DEFAULT now(),
    primeiro_resultado_em timestamptz,
    consulta_id uuid REFERENCES painel_consultas(id) ON DELETE SET NULL,
    usuario_id uuid,
    criterio text NOT NULL DEFAULT 'COMPARACAO_CONFIRMADA_PELO_USUARIO',
    CHECK (primeiro_resultado_em IS NULL OR primeiro_resultado_em >= iniciado_em)
);
