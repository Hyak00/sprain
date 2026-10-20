-- Historico de alteracoes manuais de planos e assinaturas.
CREATE TABLE IF NOT EXISTS planos_auditoria (
    id BIGSERIAL PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('PLANO', 'ASSINATURA')),
    chave TEXT NOT NULL,
    ator TEXT NOT NULL CHECK (length(trim(ator)) BETWEEN 3 AND 150),
    motivo TEXT NOT NULL CHECK (length(trim(motivo)) BETWEEN 5 AND 1000),
    anterior JSONB,
    posterior JSONB NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS planos_auditoria_chave
    ON planos_auditoria(tipo, chave, criado_em DESC, id DESC);
