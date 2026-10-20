-- Agregado diario de resposta da API; sem URL, endereco IP ou dados de viagem.
CREATE TABLE IF NOT EXISTS tempo_api_empresa_diario (
    tenant_id TEXT NOT NULL,
    dia_local DATE NOT NULL,
    requisicoes BIGINT NOT NULL DEFAULT 0 CHECK (requisicoes >= 0),
    erros BIGINT NOT NULL DEFAULT 0 CHECK (erros >= 0),
    tempo_resposta_total_ms NUMERIC(20,3) NOT NULL DEFAULT 0
        CHECK (tempo_resposta_total_ms >= 0),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(tenant_id,dia_local)
);
