INSERT INTO planos_servico (codigo, nome, funcionalidades, limite_usuarios_ativos, limite_corredores_ativos, limite_consultas_mes, limite_chamadas_externas_mes)
VALUES
    ('PILOTO_POC', 'Plano Piloto PoC', ARRAY['ROTAS_CORREDOR', 'PREVISAO_TEMPO', 'AUDITORIA_BASICA'], 3, 1, 500, 200),
    ('TRANSPORTADORA_PRO', 'Plano Transportadora Pro', ARRAY['ROTAS_CORREDOR', 'PREVISAO_TEMPO', 'PEDAGIOS_ARTESP', 'WEBHOOK_ALERTAS', 'AUDITORIA_AVANCADA'], 10, 3, 5000, 2000),
    ('ENTERPRISE_FROTA', 'Plano Enterprise Frota', ARRAY['ROTAS_CORREDOR', 'PREVISAO_TEMPO', 'PEDAGIOS_ARTESP', 'WEBHOOK_ALERTAS', 'AUDITORIA_AVANCADA', 'DOSSIE_BACKTEST', 'SLA_DEDICADO'], 50, 10, 50000, 20000)
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO assinaturas_empresa (tenant_id, plano_codigo, status, inicio_em, fim_em)
VALUES ('demo_corp', 'TRANSPORTADORA_PRO', 'ATIVA', now(), now() + interval '365 days')
ON CONFLICT (tenant_id) DO NOTHING;
