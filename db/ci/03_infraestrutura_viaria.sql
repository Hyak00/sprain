-- Cadastro por empresa; sem tarifas ou limites ficticios.
CREATE TABLE IF NOT EXISTS infraestrutura_viaria (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('PEDAGIO', 'PONTE')),
    nome TEXT NOT NULL,
    -- A malha legada nao possui chave unica em id_trecho; a API valida a associacao.
    id_trecho BIGINT NOT NULL,
    geom geometry(Point, 4326) NOT NULL,
    fonte TEXT NOT NULL,
    verificado_em TIMESTAMPTZ NOT NULL,
    valido_ate TIMESTAMPTZ NOT NULL CHECK (valido_ate > verificado_em),
    altura_max_m DOUBLE PRECISION CHECK (altura_max_m > 0),
    largura_max_m DOUBLE PRECISION CHECK (largura_max_m > 0),
    comprimento_max_m DOUBLE PRECISION CHECK (comprimento_max_m > 0),
    peso_max_t DOUBLE PRECISION CHECK (peso_max_t > 0),
    tarifa_por_eixo NUMERIC(10,2) CHECK (tarifa_por_eixo >= 0),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS infraestrutura_tenant_trecho_idx
    ON infraestrutura_viaria (tenant_id, id_trecho);
CREATE INDEX IF NOT EXISTS infraestrutura_geom_idx
    ON infraestrutura_viaria USING gist (geom);
ALTER TABLE infraestrutura_viaria ADD COLUMN IF NOT EXISTS grupo_cobranca TEXT;
ALTER TABLE infraestrutura_viaria ADD COLUMN IF NOT EXISTS tarifas_por_eixos JSONB;
ALTER TABLE trechos_osm ADD COLUMN IF NOT EXISTS estrutura_malha JSONB;

ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS dimensoes JSONB;
ALTER TABLE operacoes ADD COLUMN IF NOT EXISTS dimensoes JSONB;
ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS custos_operacionais JSONB;
ALTER TABLE operacoes ADD COLUMN IF NOT EXISTS custos_operacionais JSONB;
ALTER TABLE recomendacoes_operacao ADD COLUMN IF NOT EXISTS analise_infraestrutura JSONB;
ALTER TABLE operacoes ADD COLUMN IF NOT EXISTS perfil_rota TEXT NOT NULL DEFAULT 'FASTEST';
ALTER TABLE trechos_osm ADD COLUMN IF NOT EXISTS sentido TEXT
    CHECK (sentido IN ('AMBOS', 'DIRETO', 'INVERSO'));
ALTER TABLE trechos_osm ADD COLUMN IF NOT EXISTS tenant_malha TEXT;
CREATE INDEX IF NOT EXISTS trechos_source_empresa_idx ON trechos_osm(source,tenant_malha);
CREATE INDEX IF NOT EXISTS trechos_target_empresa_idx ON trechos_osm(target,tenant_malha);
CREATE INDEX IF NOT EXISTS trechos_vertices_geom_idx ON trechos_osm_vertices_pgr USING gist(the_geom);
CREATE TABLE IF NOT EXISTS malha_importacoes (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    fonte TEXT NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id,sha256)
);
ALTER TABLE malha_importacoes ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE trechos_osm ADD COLUMN IF NOT EXISTS importacao_malha_id BIGINT REFERENCES malha_importacoes(id);
ALTER TABLE trechos_osm ADD COLUMN IF NOT EXISTS limites_malha JSONB;
ALTER TABLE trechos_osm ADD COLUMN IF NOT EXISTS fonte_malha TEXT;
ALTER TABLE trechos_osm ADD COLUMN IF NOT EXISTS limites_verificado_em TIMESTAMPTZ;
ALTER TABLE trechos_osm ADD COLUMN IF NOT EXISTS limites_valido_ate TIMESTAMPTZ;
CREATE TABLE IF NOT EXISTS malha_limites_revisoes (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    id_trecho BIGINT NOT NULL,
    cadastro JSONB NOT NULL,
    registrado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE infraestrutura_viaria ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE infraestrutura_viaria ADD COLUMN IF NOT EXISTS origem_dados TEXT NOT NULL DEFAULT 'CADASTRO_MANUAL'
    CHECK (origem_dados IN ('CADASTRO_MANUAL','REFERENCIA_OSM'));
CREATE TABLE IF NOT EXISTS infraestrutura_revisoes (
    id BIGSERIAL PRIMARY KEY,
    ponto_id BIGINT NOT NULL,
    tenant_id TEXT NOT NULL,
    acao TEXT NOT NULL,
    cadastro JSONB NOT NULL,
    registrado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS infraestrutura_revisoes_empresa_idx
    ON infraestrutura_revisoes(tenant_id,ponto_id);
