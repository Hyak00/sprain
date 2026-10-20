INSERT INTO fontes_meteorologicas (id_fonte, nome, tipo, frequencia_minutos, url_referencia)
VALUES (
    'CGE',
    'CGE SP',
    'OBSERVACAO',
    60,
    'https://www.cgesp.org/v3/'
)
ON CONFLICT (id_fonte) DO NOTHING;

INSERT INTO fontes_meteorologicas (id_fonte, nome, tipo, frequencia_minutos, url_referencia)
VALUES (
    'OPEN_METEO',
    'Open-Meteo Previsao',
    'PREVISAO',
    60,
    'https://api.open-meteo.com/v1/forecast'
)
ON CONFLICT (id_fonte) DO NOTHING;

INSERT INTO estacoes_meteorologicas (id_estacao, id_fonte, nome, geom, distancia_maxima_cobertura_m, ativa)
VALUES (
    'CGE_ITAQUERA',
    'CGE',
    'Itaquera - CGE posto 1000864',
    ST_SetSRID(ST_MakePoint(-46.4584, -23.5389), 4326),
    15000,
    true
)
ON CONFLICT (id_estacao) DO UPDATE
    SET geom = EXCLUDED.geom,
        distancia_maxima_cobertura_m = EXCLUDED.distancia_maxima_cobertura_m;

INSERT INTO estacoes_meteorologicas (id_estacao, id_fonte, nome, geom, distancia_maxima_cobertura_m, ativa)
VALUES (
    'OPEN_METEO_ARARAQUARA',
    'OPEN_METEO',
    'Araraquara - Open-Meteo previsao',
    ST_SetSRID(ST_MakePoint(-48.1760, -21.7942), 4326),
    40000,
    true
)
ON CONFLICT (id_estacao) DO NOTHING;
