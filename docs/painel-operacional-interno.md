# Painel operacional interno (3.5)

Entre como ADMIN e abra Central de trabalho → Painel operacional interno.
O acesso interno usa a autorização existente de administrador da empresa:
metadados de fontes públicas são compartilhados, enquanto lotes e métricas
operacionais são restritos à empresa autenticada. Não concede visão dos dados
de outros clientes. OPERATOR e VIEWER conservam a seção Qualidade e serviços.

## Telas e contratos

- Fontes e atualização: `/api/v1/operacional/fontes`, complementando o catálogo
  `/api/v1/dados-publicos/fontes`. Inclui fontes externas já importadas, fontes
  meteorológicas cadastradas e o corredor Open-Meteo. Exibe natureza, referência,
  idade na consulta, prazo, cobertura e critérios. Sem data/fuso válido ou data
  futura não vira zero de idade. Estações sem leitura geram cobertura incompleta.
- Importações e falhas: `/api/v1/operacional/importacoes`, com filtro por estado
  e paginação de 25 registros; `/api/v1/infraestrutura/malha/importacoes` mostra
  até 100 importações concluídas da empresa, com estado ativo/desativado.
- Serviços: `/api/v1/health/liveness`, `/api/v1/health/readiness` e
  `/api/v1/logistica/observabilidade/metricas`. Mostra erros HTTP recentes,
  contagem, latência e a integração CGE explicitamente desativada no código atual.
  Não consulta diretamente provedores externos nem realiza escrita para testá-los.
- Qualidade: consome `/api/v1/indicadores/qualidade`,
  `/api/v1/dados-publicos/qualidade-precos` e `/api/v1/alertas/precisao`.
  Distingue ausência de amostra de resultado zero e informa fonte e consulta.

A atualização é manual, sem polling. Chamadas independentes executam em paralelo,
com timeout de 15 segundos por consulta. Falha parcial preserva as demais áreas.
Filtro novo, troca de seção ou logout descartam respostas antigas. O histórico
oferece nova tentativa sem reexecutar importação. Nenhuma credencial é exportada.

## Auditoria persistente

`db/ci/11_importacoes_monitor.sql` é aditiva e aplicada na inicialização, inclusive
em volumes existentes. Registra UUID, fonte, início, término, estado, contagens
quando conhecidas e código seguro de diagnóstico. Não salva arquivo, URL,
conteúdo privado, stack trace, senha ou mensagem bruta de exceção.

Foram instrumentados:

- `scripts/sincronizar_dados_publicos.py ... --aplicar`: um registro por execução
  do pipeline (download, validação e gravação). A execução com várias fontes pode
  ter gravado fontes anteriores quando outra falha. Não declara atomicidade.
  O modo de validação sem `--aplicar` continua sem conexão/escrita de auditoria.
- `scripts/sincronizar_clima_corredor.py`: distingue conclusão, falha total e
  parcial. As condições anteriores permanecem preservadas quando a coleta falha.
  Aceita URL_BANCO ou as variáveis DB_* já usadas pela API.
- POST `/api/v1/logistica/operacoes/importar-lote`: resumo persistente dos
  sucessos/falhas, restrito à empresa. Mantém o contrato e resultado por item.

Uma falha de auditoria inicial impede o job de começar. Se o banco cair depois
do início, o registro pode ficar sem término; isso é apresentado como encerramento
desconhecido, sem afirmar que o processo continua ativo. Falhas de acesso ou
validação HTTP anteriores à execução aparecem nas métricas em memória. Erros
de importação de malha anteriores à gravação só aparecem nesse histórico HTTP;
não se inventam tentativas persistentes que o importador não registrou.

O histórico nasce nesta versão: falhas antigas, execuções não instrumentadas e
falhas ocorridas antes de conseguir conexão não são reconstruídas. Ausência de
registros não significa ausência de falhas. A lista é paginada; não é um total
histórico de incidentes. Não há limpeza automática ou exclusão de registros.

## Interpretação

O prazo de 48 h das fontes externas é o critério agregado já usado pela API,
nunca um SLA homologado de cada provedor. Open-Meteo usa atualização mais antiga
dos segmentos e o limite de 60 min do relatório existente. Para meteorologia,
considera-se a referência mais antiga entre as últimas leituras por estação
ativa, a frequência cadastrada e a menor validade explícita. Uma coleta recente
não torna recente uma referência antiga.

Dentro do critério não comprova segurança, completude nem qualidade de cada
ocorrência. Idade da importação não é idade de cada evento. Preços atípicos são
itens para revisão; não são removidos. Percentuais de feedback são os declarados
pelo endpoint, com a amostra visível, sem alegar homologação independente.
Métricas HTTP são por empresa/processo em memória e podem reiniciar; não medem
disponibilidade histórica de toda a infraestrutura.

## Verificação

Execute os testes em banco exclusivo da suíte; nunca no banco operacional.
Confira permissões, fontes sem leitura ou vencidas, falha parcial de serviço,
auditoria de erro sem segredos, filtro/paginação e isolamento de empresas.
As sondas de leitura de `scripts/verificar_portal.py` incluem o novo arquivo JS;
os endpoints internos requerem chave ADMIN, sem mudar o padrão VIEWER da sonda.
