-- Agregado diario por template de rota. Nunca armazena URL concreta ou parametros.
CREATE TABLE IF NOT EXISTS metricas_endpoint_diario (
    tenant_id TEXT NOT NULL,
    dia_local DATE NOT NULL,
    metodo TEXT NOT NULL CHECK (length(metodo) BETWEEN 1 AND 12),
    rota_template TEXT NOT NULL CHECK (length(rota_template) BETWEEN 1 AND 240),
    requisicoes BIGINT NOT NULL DEFAULT 0 CHECK (requisicoes >= 0),
    erros BIGINT NOT NULL DEFAULT 0 CHECK (erros >= 0),
    tempo_resposta_total_ms NUMERIC(20,3) NOT NULL DEFAULT 0
        CHECK (tempo_resposta_total_ms >= 0),
    tempo_resposta_max_ms NUMERIC(12,3) NOT NULL DEFAULT 0
        CHECK (tempo_resposta_max_ms >= 0),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, dia_local, metodo, rota_template)
);
