-- Registros anteriores sem origem conhecida permanecem sem tenant e nao entram
-- nas metricas de nenhuma empresa. Atribua tenant_id apenas com prova da origem.
ALTER TABLE public.auditoria_previsao_realidade
    ADD COLUMN IF NOT EXISTS tenant_id TEXT;

CREATE INDEX IF NOT EXISTS idx_auditoria_previsao_realidade_tenant
    ON public.auditoria_previsao_realidade (tenant_id);
