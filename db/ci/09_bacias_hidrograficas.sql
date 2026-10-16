CREATE TABLE IF NOT EXISTS bacias_hidrograficas (
    id_bacia BIGSERIAL PRIMARY KEY,
    codigo_otto TEXT NOT NULL UNIQUE,
    nome TEXT,
    area_km2 DOUBLE PRECISION,
    tempo_concentracao_min DOUBLE PRECISION,
    geom geometry(Polygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bacias_geom ON bacias_hidrograficas USING gist (geom);