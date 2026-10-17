-- Migracao 004: Segregacao multi-tenant para alertas operacionais e auditoria de acuracia
-- Nao destrutiva e compativel com dados preexistentes

ALTER TABLE alertas_operacionais ADD COLUMN IF NOT EXISTS tenant_id TEXT DEFAULT 'GLOBAL';
ALTER TABLE alertas_operacionais ADD COLUMN IF NOT EXISTS escopo TEXT DEFAULT 'GLOBAL' CHECK (escopo IN ('GLOBAL', 'TENANT'));
CREATE INDEX IF NOT EXISTS idx_alertas_tenant ON alertas_operacionais (tenant_id, escopo);

ALTER TABLE auditoria_previsao_realidade ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_auditoria_tenant ON auditoria_previsao_realidade (tenant_id);
