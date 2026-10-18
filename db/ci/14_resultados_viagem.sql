-- Resultados informados de viagens. Cada correcao gera um novo registro.
-- Chaves compostas impedem vinculos entre empresas ou operacoes diferentes.
CREATE UNIQUE INDEX IF NOT EXISTS operacoes_resultados_identidade
    ON operacoes (id_operacao, tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS decisoes_resultados_identidade
    ON decisoes_gestor_operacao (id_decisao, tenant_id, id_operacao);

CREATE TABLE IF NOT EXISTS resultados_viagem (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    id_operacao TEXT NOT NULL,
    id_decisao INTEGER,
    substitui_id UUID,
    finalizada_em TIMESTAMPTZ NOT NULL,
    registrada_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    usuario_id UUID,
    rota_executada TEXT NOT NULL CHECK (rota_executada IN ('ORIGINAL', 'DESVIO', 'OUTRA', 'NAO_INFORMADA')),
    duracao_real_min NUMERIC(12, 2) CHECK (duracao_real_min BETWEEN 0 AND 1000000),
    distancia_real_km NUMERIC(12, 2) CHECK (distancia_real_km BETWEEN 0 AND 1000000),
    custo_real_brl NUMERIC(12, 2) CHECK (custo_real_brl BETWEEN 0 AND 1000000000),
    fonte TEXT NOT NULL CHECK (fonte IN ('RELATO_OPERADOR', 'TELEMETRIA', 'DOCUMENTO')),
    referencia_evidencia TEXT,
    observacoes TEXT,
    CONSTRAINT resultado_com_medicao CHECK (
        duracao_real_min IS NOT NULL OR distancia_real_km IS NOT NULL OR custo_real_brl IS NOT NULL
    ),
    CONSTRAINT resultado_operacao_fk FOREIGN KEY (id_operacao, tenant_id)
        REFERENCES operacoes (id_operacao, tenant_id),
    CONSTRAINT resultado_decisao_fk FOREIGN KEY (id_decisao, tenant_id, id_operacao)
        REFERENCES decisoes_gestor_operacao (id_decisao, tenant_id, id_operacao),
    CONSTRAINT resultado_identidade UNIQUE (id, tenant_id, id_operacao),
    CONSTRAINT resultado_anterior_fk FOREIGN KEY (substitui_id, tenant_id, id_operacao)
        REFERENCES resultados_viagem (id, tenant_id, id_operacao),
    CONSTRAINT resultado_correcao_unica UNIQUE (substitui_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS resultados_viagem_primeiro
    ON resultados_viagem (tenant_id, id_operacao) WHERE substitui_id IS NULL;
CREATE INDEX IF NOT EXISTS resultados_viagem_historico
    ON resultados_viagem (tenant_id, id_operacao, registrada_em DESC);
