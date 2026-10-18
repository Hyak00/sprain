# Resultados informados de viagens do piloto

Depois de executar uma operação, um ADMIN ou OPERATOR pode informar a rota
percorrida, o horário de conclusão e ao menos uma medida real: duração,
distância ou custo. A API guarda a fonte declarada, uma referência de evidência
opcional e o usuário da sessão quando disponível. VIEWER pode ler o histórico.

```text
POST /api/v1/logistica/operacoes/{id_operacao}/resultados-viagem
GET  /api/v1/logistica/operacoes/{id_operacao}/resultados-viagem?offset=0
```

Exemplo de corpo do primeiro registro:

```json
{
  "finalizada_em": "2026-10-17T16:30:00-03:00",
  "rota_executada": "DESVIO",
  "duracao_real_min": "135.50",
  "distancia_real_km": "92.20",
  "custo_real_brl": "480.75",
  "fonte": "RELATO_OPERADOR",
  "referencia_evidencia": "viagem-interna-123",
  "id_decisao": 42
}
```

`id_decisao` é opcional e, quando enviado, deve pertencer à mesma operação e
empresa. `finalizada_em` exige fuso horário. Custos aceitam zero, mas não
valores negativos, não finitos ou mais de duas casas decimais. A fonte pode ser
`RELATO_OPERADOR`, `TELEMETRIA` ou `DOCUMENTO`; para `DOCUMENTO`, informe uma
referência. A API não busca nem valida o documento externo.

Correções são novos registros: consulte o histórico e envie novamente todos os
campos com `substitui_id` igual ao `id` do resultado atual. Uma correção baseada
em resultado antigo recebe HTTP 409. O histórico permanece legível e o piloto
usa apenas o último registro de cada operação.

O JSON de `GET /api/v1/painel/relatorios/piloto` inclui agora
`amostra.viagens_com_resultado`, `amostra.viagens_com_custo_informado`,
`indicadores.custo_informado` e `indicadores.desvios_informados`. São informações
**autodeclaradas e não verificadas**. `custo_observado` e
`economia_comprovada` permanecem indisponíveis: custo informado não prova
pagamento e uma viagem realizada não estabelece qual teria sido o resultado da
rota que não foi escolhida. O piloto seleciona operações pela data de criação,
inclusive ao aplicar filtro de período.

O resumo sem filtro de período em `GET /api/v1/logistica/relatorios/sumario-executivo`
também mostra `viagens_com_resultado_informado`, `viagens_com_custo_informado`,
`custo_informado_brl` e `desvios_informados`. A marca
`natureza_resultados=AUTODECLARADO_NAO_VERIFICADO` diferencia essas medidas
das recomendações de planejamento. Os campos legados `custo_observado_brl`,
`economia_comprovada_brl` e `desvios_realizados` continuam `null`.

O esquema `db/ci/14_resultados_viagem.sql` é aditivo e aplicado na inicialização
após as tabelas de operações e decisões. O teste de integração usa transação
revertida, cobre correção, vínculo com decisão, separação entre empresas e os
valores exibidos no piloto.
