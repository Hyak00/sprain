-- Fontes publicas: importacao aditiva e repetivel, sem alterar a malha existente.
CREATE TABLE IF NOT EXISTS fontes_dados_externos (
    nome TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    hash_sha256 TEXT NOT NULL,
    registros_importados INTEGER NOT NULL CHECK (registros_importados >= 0),
    ultimo_sucesso_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE fontes_dados_externos ADD COLUMN IF NOT EXISTS resumo_importacao JSONB;

CREATE TABLE IF NOT EXISTS tombamentos_caminhao (
    id_fonte TEXT PRIMARY KEY,
    data_ocorrencia DATE NOT NULL,
    hora_ocorrencia TIME,
    rodovia TEXT NOT NULL,
    km DOUBLE PRECISION,
    sentido TEXT,
    municipio TEXT,
    classe TEXT NOT NULL,
    subclasse TEXT,
    caminhoes_envolvidos INTEGER NOT NULL CHECK (caminhoes_envolvidos > 0),
    veiculos_envolvidos TEXT NOT NULL,
    geom geometry(Point, 4326) NOT NULL,
    url_fonte TEXT NOT NULL,
    importado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE tombamentos_caminhao ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE tombamentos_caminhao ADD COLUMN IF NOT EXISTS condicao_meteorologica TEXT;
ALTER TABLE tombamentos_caminhao ADD COLUMN IF NOT EXISTS visibilidade TEXT;
CREATE INDEX IF NOT EXISTS tombamentos_caminhao_geom_idx
    ON tombamentos_caminhao USING gist (geom);
CREATE INDEX IF NOT EXISTS tombamentos_caminhao_geog_idx
    ON tombamentos_caminhao USING gist ((geom::geography));
CREATE INDEX IF NOT EXISTS tombamentos_caminhao_rodovia_data_idx
    ON tombamentos_caminhao (rodovia, data_ocorrencia DESC);

CREATE TABLE IF NOT EXISTS postos_combustivel (
    cnpj TEXT PRIMARY KEY CHECK (cnpj ~ '^[0-9]{14}$'),
    nome TEXT NOT NULL,
    uf CHAR(2) NOT NULL,
    municipio TEXT NOT NULL,
    endereco TEXT NOT NULL,
    bairro TEXT,
    cep TEXT,
    geom geometry(Point, 4326),
    localizacao_fonte TEXT,
    localizacao_verificada_em TIMESTAMPTZ,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE postos_combustivel ADD COLUMN IF NOT EXISTS localizacao_obtida_em DATE;
ALTER TABLE postos_combustivel ADD COLUMN IF NOT EXISTS localizacao_acuracia_m NUMERIC(10, 2);
ALTER TABLE postos_combustivel ADD COLUMN IF NOT EXISTS localizacao_validacao TEXT;
CREATE INDEX IF NOT EXISTS postos_combustivel_geom_idx
    ON postos_combustivel USING gist (geom);
CREATE INDEX IF NOT EXISTS postos_combustivel_geog_idx
    ON postos_combustivel USING gist ((geom::geography));
CREATE INDEX IF NOT EXISTS postos_combustivel_municipio_idx
    ON postos_combustivel (uf, municipio);

CREATE TABLE IF NOT EXISTS precos_combustivel (
    cnpj TEXT NOT NULL REFERENCES postos_combustivel(cnpj),
    produto TEXT NOT NULL,
    data_coleta DATE NOT NULL,
    preco_litro NUMERIC(10, 3) NOT NULL CHECK (preco_litro > 0),
    url_fonte TEXT NOT NULL,
    importado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cnpj, produto, data_coleta)
);
CREATE INDEX IF NOT EXISTS precos_combustivel_produto_data_idx
    ON precos_combustivel (produto, data_coleta DESC);

-- Agregados de roubo nao sao geocodificados como ocorrencias pontuais.
CREATE TABLE IF NOT EXISTS roubo_carga_agregados (
    id_fonte TEXT PRIMARY KEY,
    nivel_geografico TEXT NOT NULL CHECK (nivel_geografico IN ('ESTADO', 'REGIAO', 'MUNICIPIO')),
    area TEXT NOT NULL,
    periodo_inicio DATE NOT NULL,
    periodo_fim DATE NOT NULL CHECK (periodo_fim >= periodo_inicio),
    ocorrencias INTEGER NOT NULL CHECK (ocorrencias >= 0),
    url_fonte TEXT NOT NULL,
    importado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS roubo_carga_area_periodo_idx
    ON roubo_carga_agregados (nivel_geografico, area, periodo_fim DESC);
