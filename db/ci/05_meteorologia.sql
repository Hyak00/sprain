CREATE TABLE IF NOT EXISTS fontes_meteorologicas (
    id_fonte TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('OBSERVACAO', 'PREVISAO')),
    frequencia_minutos INTEGER NOT NULL,
    url_referencia TEXT
);

CREATE TABLE IF NOT EXISTS estacoes_meteorologicas (
    id_estacao TEXT PRIMARY KEY,
    id_fonte TEXT NOT NULL REFERENCES fontes_meteorologicas(id_fonte),
    nome TEXT NOT NULL,
    geom geometry(Point, 4326) NOT NULL,
    distancia_maxima_cobertura_m INTEGER NOT NULL DEFAULT 50000,
    ativa BOOLEAN NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS estacoes_geom_idx ON estacoes_meteorologicas USING gist (geom);

CREATE TABLE IF NOT EXISTS leituras_meteorologicas (
    id_estacao TEXT NOT NULL REFERENCES estacoes_meteorologicas(id_estacao),
    data_referencia TIMESTAMPTZ NOT NULL,
    coletado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    validade_ate TIMESTAMPTZ,
    precipitacao_mm NUMERIC(6,2),
    PRIMARY KEY (id_estacao, data_referencia)
);

CREATE TABLE IF NOT EXISTS historico_avaliacoes_risco (
    id_avaliacao BIGSERIAL PRIMARY KEY,
    id_trecho INTEGER NOT NULL,
    avaliado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    regra_versao TEXT NOT NULL,
    precipitacao_aplicada_mm NUMERIC(6,2) NOT NULL,
    risco_estimado TEXT NOT NULL,
    id_fonte TEXT NOT NULL,
    idade_dado_minutos INTEGER NOT NULL
);