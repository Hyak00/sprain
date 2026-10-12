RELATORIO DE HOMOLOGACAO TECNICA - SPRAIN B2B

Data de Execucao: 2026-10-12 23:10:52 UTC
Commit de Referencia: 6c545ab
Ambiente: Docker Compose (sprain_api + sprain_db PostGIS 15 / pgRouting)

1. RESULTADO DA SUITE DE TESTES AUTOMATIZADOS
- Total de Testes Executados: 56
- Aprovados: 56 (100%)
- Falhos: 0
- Ignorados: 0

2. BLOQUEADORES CRITICOS VERIFICADOS (P0.1 a P0.5)
- P0.1 (Credenciais e Producao): Validado. Inicializacao em modo production recusa senhas padrao, exige WEBHOOK_SECRET_KEY e bloqueia chaves de demonstracao (test_prod_config.py).
- P0.2 (Isolamento Multi-Tenant): Validado. Identidade extraida da API Key, cache do RoutingEngine isolado por prefixo de tenant_id e sumario executivo corrigido com LATERAL JOIN sem acumulo duplicado (test_isolamento_cache_sumario.py).
- P0.3 (Transparencia Meteorologica): Validado. Endpoint de alertas explicita modo de avaliacao parametrizada e preserva estado anterior caso a fonte CGE falhe.
- P0.4 (Utilizacao de Rota e Decisao Supervisionada): Validado. Endpoint de explicacao retorna geometria GeoJSON da alternativa, limitacoes de malha e auditoria de decisao humana (test_decisao_gestor_rota.py).
- P0.5 (Pipeline CI e Reprodutibilidade): Validado. Workflow CI atualizado com sonda explicita em /api/v1/health/readiness.

3. METRICAS REAIS EXTRAIDAS DO AMBIENTE
- Trechos Viarios Indexados (PostGIS): 2978
- Latencia de Readiness do Banco: 2.97 ms
- Corredor Regional Validado: 245.0 km (SP-310 / SP-330 / SP-348)
