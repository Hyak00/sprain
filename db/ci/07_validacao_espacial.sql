CREATE TABLE IF NOT EXISTS auditoria_qualidade_espacial (
    id_auditoria SERIAL PRIMARY KEY,
    fonte TEXT NOT NULL,
    total_analisado INTEGER NOT NULL,
    rejeitados_fora_sp INTEGER NOT NULL,
    rejeitados_longe_via INTEGER NOT NULL,
    registros_validos INTEGER NOT NULL,
    executado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);