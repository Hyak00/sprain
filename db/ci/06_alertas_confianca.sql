CREATE TABLE IF NOT EXISTS alertas_operacionais (
    id_evento TEXT PRIMARY KEY,
    categoria TEXT NOT NULL,
    fonte TEXT NOT NULL,
    primeira_deteccao TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultima_atualizacao TIMESTAMPTZ NOT NULL DEFAULT now(),
    expiracao_em TIMESTAMPTZ NOT NULL,
    confianca NUMERIC(3,2) NOT NULL,
    status_evento TEXT NOT NULL DEFAULT 'INCERTO',
    o_que_nao_sabemos TEXT,
    trechos_afetados INTEGER[] NOT NULL,
    falso_alerta BOOLEAN NOT NULL DEFAULT false,
    evento_nao_detectado BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX idx_alertas_trechos ON alertas_operacionais USING GIN (trechos_afetados);