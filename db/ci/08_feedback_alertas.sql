CREATE TABLE IF NOT EXISTS feedback_alertas_operacionais (
    id_feedback SERIAL PRIMARY KEY,
    id_evento TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    falso_alerta BOOLEAN NOT NULL DEFAULT false,
    evento_nao_detectado BOOLEAN NOT NULL DEFAULT false,
    motivo_reporte TEXT,
    reportado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);