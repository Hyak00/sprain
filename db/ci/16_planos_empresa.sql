-- Cadastro aditivo. Nenhum plano ou assinatura e criado automaticamente.
CREATE TABLE IF NOT EXISTS planos_servico (
    codigo TEXT PRIMARY KEY CHECK (codigo ~ '^[A-Z0-9_]{2,64}$'),
    nome TEXT NOT NULL CHECK (length(trim(nome)) BETWEEN 2 AND 120),
    funcionalidades TEXT[] NOT NULL DEFAULT '{}'::text[],
    limite_usuarios_ativos INTEGER CHECK (limite_usuarios_ativos >= 0),
    limite_corredores_ativos INTEGER CHECK (limite_corredores_ativos >= 0),
    limite_consultas_mes INTEGER CHECK (limite_consultas_mes >= 0),
    limite_chamadas_externas_mes INTEGER CHECK (limite_chamadas_externas_mes >= 0),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS assinaturas_empresa (
    tenant_id TEXT PRIMARY KEY CHECK (length(trim(tenant_id)) BETWEEN 1 AND 150),
    plano_codigo TEXT NOT NULL REFERENCES planos_servico(codigo),
    status TEXT NOT NULL CHECK (status IN ('ATIVA', 'SUSPENSA', 'ENCERRADA')),
    inicio_em TIMESTAMPTZ NOT NULL,
    fim_em TIMESTAMPTZ,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (fim_em IS NULL OR fim_em > inicio_em)
);

CREATE INDEX IF NOT EXISTS assinaturas_empresa_plano ON assinaturas_empresa(plano_codigo);
