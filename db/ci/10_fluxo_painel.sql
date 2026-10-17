-- Complemento aditivo do painel. Nao altera dados ou regras de roteamento existentes.
CREATE TABLE IF NOT EXISTS painel_corredores (
    id UUID PRIMARY KEY, tenant_id TEXT NOT NULL, dados JSONB NOT NULL,
    geometria JSONB NOT NULL, versao INTEGER NOT NULL DEFAULT 1,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(), atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS painel_corredores_tenant ON painel_corredores(tenant_id, atualizado_em DESC);
CREATE TABLE IF NOT EXISTS painel_recorrencias (
    id UUID PRIMARY KEY, corredor_id UUID NOT NULL REFERENCES painel_corredores(id),
    tenant_id TEXT NOT NULL, dados JSONB NOT NULL, versao INTEGER NOT NULL DEFAULT 1,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(), atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS painel_recorrencias_tenant ON painel_recorrencias(tenant_id, corredor_id);
CREATE TABLE IF NOT EXISTS painel_despachos (
    tenant_id TEXT NOT NULL, chave UUID NOT NULL, recorrencia_id UUID NOT NULL REFERENCES painel_recorrencias(id),
    data_local DATE NOT NULL, id_operacao TEXT NOT NULL, criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(tenant_id, chave)
);
CREATE UNIQUE INDEX IF NOT EXISTS painel_despachos_agenda_data ON painel_despachos(tenant_id,recorrencia_id,data_local);
CREATE TABLE IF NOT EXISTS painel_consultas (
    id UUID PRIMARY KEY, tenant_id TEXT NOT NULL, id_operacao TEXT NOT NULL,
    perfil TEXT NOT NULL, snapshot JSONB NOT NULL, criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS painel_consultas_tenant ON painel_consultas(tenant_id, criado_em DESC, id);
CREATE TABLE IF NOT EXISTS painel_relatos (
    id UUID PRIMARY KEY, tenant_id TEXT NOT NULL, dados JSONB NOT NULL,
    perfil TEXT NOT NULL, criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS painel_relatos_tenant ON painel_relatos(tenant_id, criado_em DESC);
CREATE TABLE IF NOT EXISTS decisoes_gestor_operacao (
    id_decisao SERIAL PRIMARY KEY, id_operacao TEXT NOT NULL, tenant_id TEXT NOT NULL,
    decisao TEXT NOT NULL, motivo_gestor TEXT NOT NULL, registrado_em TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE decisoes_gestor_operacao ADD COLUMN IF NOT EXISTS consulta_id UUID;
ALTER TABLE decisoes_gestor_operacao ADD COLUMN IF NOT EXISTS perfil_registro TEXT;
ALTER TABLE decisoes_gestor_operacao ADD COLUMN IF NOT EXISTS snapshot JSONB;
