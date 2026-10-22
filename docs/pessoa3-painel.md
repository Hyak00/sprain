# Pessoa 3 — acompanhamento e contratos do painel

**Registro histórico da primeira entrega.** Para o estado revisado das seções
3.1 a 3.6, consulte [revisão de 21/10/2026](revisao-painel-20261021.md).
As pendências abaixo descrevem a entrega de 15/10 e não devem ser lidas como
inventário atual de funcionalidades ausentes.

Referência desta entrega: main `2b4e575`, consultada em 15/10/2026. Escopo de responsabilidade: seções 3.1–3.7 da “Lista técnica completa do Sprain”. Este arquivo acompanha entregas incrementais; não declara toda a Pessoa 3 ou o MVP concluídos.

## Atualizações incorporadas dos colegas

Foram preservados os novos clientes de trânsito, bloqueios/penalidades por alertas, feedback por empresa, indicadores de qualidade, avaliação meteorológica, scripts de backtest, isolamento de monitoramento/cache/telemetria, backup/restauração e execução sem privilégios do container. Os limites oficiais DER da entrega anterior já estão em main.

Nenhum router, cálculo financeiro, motor de rotas, pipeline, esquema ou dependência de produção é modificado nesta entrega do painel. Os 68 IDs e o bloco de CSS original foram preservados. O complemento visual se limita a foco, controles desabilitados e mensagens de estado.

## Entrega inicial: sessão, permissões e falhas

- Login usa o contrato existente; credencial incorreta, indisponibilidade e falha de comunicação possuem mensagens diferentes.
- Chaves permanecem apenas em memória da página. Nenhuma credencial é persistida pelo código do painel em localStorage/sessionStorage ou escrita em relatório/log.
- Sair ou trocar de conta cancela consultas e limpa listas, seleção, frota, custos, campos, decisões, detalhes, mapas e marcadores. Uma resposta antiga não pode encerrar ou preencher a nova sessão, inclusive quando seu corpo chega depois dos cabeçalhos.
- Tela privada fica inerte para teclado/leitores de tela enquanto o diálogo de acesso está aberto. Login possui rótulos associados, foco e ação por Enter.
- ADMIN/OPERATOR mantêm suas ações existentes. VIEWER usa GET de alertas ativos, pode consultar rotas e não tenta POST de simulação ou gravação. A proteção definitiva continua no backend.
- Para VIEWER, o contador é identificado como alertas carregados: o endpoint existente retorna no máximo 50 e não informa a frota/total de operações monitoradas. A interface não apresenta esse recorte como total da empresa.
- Campos de escrita e ações de decisão/cadastro/despacho são desabilitados no perfil de consulta. Cliques repetidos em uma gravação em andamento não duplicam o envio.
- O cliente centraliza timeout, cancelamento, 401/403/404/409/422/429/503 e falhas de rede. Não apresenta o corpo de um erro interno como mensagem ao usuário.
- Erro ao consultar operações/frota não mantém um resultado anterior aparentando estar atualizado. Há orientação para tentar novamente. Histórico é mostrado integralmente conforme a resposta existente, sem o corte visual arbitrário de três registros e sem interpretar justificativa como HTML.
- CSV de contingência só é baixado após resposta bem-sucedida e formato CSV; a URL temporária é liberada. Uma resposta JSON de erro não vira arquivo CSV.

O cliente não concede novas permissões. POSTs de consulta já autorizados pelo backend (rota-caminhao, avaliar-mapa, consultar-rota e comparar trânsito) continuam possíveis para VIEWER. Nenhuma chamada a fornecedor externo foi adicionada.

## Contratos existentes utilizados nesta etapa

| Recurso | Endpoint | Uso do painel |
| --- | --- | --- |
| Login demo | POST /api/v1/logistica/auth/login | Resposta precisa conter api_key, tenant_id e role reconhecido |
| Frota | GET/POST /api/v1/logistica/veiculos | Consulta por sessão; gravação para operador/admin |
| Busca de vias | GET /api/v1/logistica/vias/buscar | Autocomplete existente |
| Despacho | POST /api/v1/logistica/operacoes | Gravação existente, sem duplicar envio |
| Simulação | POST /api/v1/logistica/simular-impacto | Operador/admin; chuva controlada não vira observação |
| Alertas consultáveis | GET /api/v1/logistica/alertas/ativos | Atualização para VIEWER sem tentativa de simulação |
| Inspeção e histórico | GET /api/v1/logistica/operacoes/{id}/explicacao e /decisoes | Resposta só aparece se sessão e operação ainda forem as selecionadas |
| Decisão | POST /api/v1/logistica/operacoes/{id}/decisao | Mantém validações e proteção do servidor; trata conflito como necessidade de atualização |
| Corredor legado | GET /api/v1/rotas/intermunicipal | Preservado; não equivale a cadastro persistente de corredor |
| Avaliação de caminhão | POST /api/v1/infraestrutura/rota-caminhao e /avaliar-mapa | Consultas com os dados/limites existentes |
| Contexto da viagem | POST /api/v1/dados-publicos/consultar-rota | Preserva datas, procedência e limites do módulo existente |
| CSV | GET /api/v1/logistica/exportar-contingencia/csv | Verifica sucesso/formato antes de baixar |
| Manutenção de infraestrutura | /api/v1/infraestrutura/pontos e /trechos/{id}/limites | Formulário administrativo existente preservado |

## Novos contratos disponíveis para as próximas entregas

- GET /api/v1/ocorrencias/ativas: eventos com fonte, confiança, status, atualização e expiração. Apresentar natureza da informação e limitações; não substituir por um percentual fixo da interface.
- POST /api/v1/alertas/feedback e GET /api/v1/alertas/precisao: feedback/indicadores por empresa. O POST exige ID de evento já existente; não resolve sozinho o reporte de um evento que nunca foi cadastrado.
- GET /api/v1/indicadores/qualidade e /api/v1/dados-publicos/fontes: fontes e informações de atualização. Prazo/cobertura retornados não devem ser apresentados como homologação completa de todas as fontes.
- POST /api/v1/transito/comparar: em desenvolvimento/testes retorna apenas estimativa de percurso do OSRM (`tempo_estimado_min`), sem trânsito observado (`tempo_observado_min: null`); em produção pode devolver 502. Não substituir por “trânsito livre”.
- POST/GET /api/v1/cliente/operacoes: registro de viagens/atrasos; não equivale ao cadastro roteável de corredor com geometria e recorrência.
- POST /api/v1/demonstracao/cenario-historico-sp310: protegido para ADMIN e bloqueado em produção. Antes da apresentação como reconstrução histórica, confirmar com a Pessoa 1 a fonte primária do evento, associação dos trechos e ausência de distâncias substitutas quando o roteador não retorna caminho. O endpoint atual contém valores de fallback; a interface ainda não o oferece como demonstração homologada.

## Situação das partes da Pessoa 3

| Parte | Situação nesta entrega | Próximo trabalho/dependência |
| --- | --- | --- |
| 3.1 Painel | Sessão/permissões/falhas implementadas; fluxo geral ainda parcial | Alertas completos, comparação/espera, estados restantes, corredores recorrentes, responsividade completa |
| 3.2 Administração | Cadastro de infraestrutura existente preservado | Gestão real de usuários, recuperação, premissas persistentes e exportação integral dependem de contratos da Pessoa 2 |
| 3.3 Relatórios | CSV existente tratado; PDF/piloto ainda pendentes | Contrato de consulta/decisão, autoria e distinção entre observado/comprovado/estimado/potencial |
| 3.4 Demonstração | Scripts/cenários dos colegas preservados | Fonte histórica e geometria confirmadas antes de expor a demonstração; identificação e roteiro da interface |
| 3.5 Painel interno | Indicadores/endpoints identificados | Implementar a apresentação com permissões e estados de falha |
| 3.6 Testes/docs | Cliente JS com testes, contrato e roteiro de verificação; CI ampliado | Suíte automatizada completa de navegador, Swagger/README/manuais e runbooks com Pessoa 2 |
| 3.7 Onboarding | Contratos parciais identificados | Modelo/importação validada de rotas e eventos persistentes do primeiro resultado útil |

## Pendências que exigem contrato dos outros responsáveis

1. Login real em produção, credenciais revogáveis, usuários e recuperação: Pessoa 2. O login disponível é de demonstração e é recusado em produção.
2. CRUD de corredores/rotas recorrentes e premissas da empresa: Pessoa 2. Não substituí-lo por armazenamento privado do navegador.
3. Autoria individual e fotografia auditável de consulta/decisão: Pessoa 2. Usuário mostrado no cabeçalho não comprova quem gravou uma decisão antiga.
4. Reporte de evento ainda inexistente: Pessoas 1/2. O feedback atual exige evento cadastrado.
5. Economia comprovada/custos observados e espera: Pessoa 2. Não derivar esses valores de perda potencial.
6. Evidência histórica e limitações do dataset de demonstração: Pessoa 1.
7. Evento persistente de onboarding e formato definitivo de importação: Pessoa 2, com campos da Pessoa 1.

## Verificação reproduzível

Testes do cliente, com Node disponível:

```text
node --test api/tests/interface/*.test.cjs
```

São testes do transporte/sessão, não uma suíte completa de navegador. O workflow existente executa esse comando além da suíte de API. Na validação inicial, 13 testes JS e 146 testes Python passaram; essa contagem registra esta execução e deve ser atualizada a partir dos resultados, nunca usada como promessa fixa de homologação.

Validar a interface em API/banco exclusivos de teste. Não executar testes que resetam eventos contra o banco operacional. Roteiro:

1. Login inválido: mensagem de credencial; painel privado não recebe foco.
2. Operador: listar operações, selecionar detalhes e abrir frota sem erros; manter funções originais.
3. Logout: listas/campos/mapas e credenciais limpos; respostas pendentes descartadas.
4. Visualizador: alertas via GET; cadastro/despacho/decisão desabilitados; consultas e CSV preservados.
5. Troca para outra empresa: não exibir frota, seleção ou histórico da sessão anterior.
6. Administrador: manutenção existente acessível; troca de papel não mantém esse formulário aberto.
7. Sessão inválida/401: retornar ao login; erro interno não vaza conteúdo; conexão/timeout têm mensagens recuperáveis.

O checklist de lançamento de main e os relatórios antigos não dispensam evidências para os itens desta lista. Cada próxima entrega deve ter tarefa, branch, PR, critério de aceite e revisão independentes.
