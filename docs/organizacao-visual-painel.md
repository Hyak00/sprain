# Painel com páginas diretas e detalhes por abas

Atualização de 20/10/2026, sobre `252f75c`. A revisão considera as mudanças de meteorologia, custos, resultados, planos e importação de manifesto incorporadas pela equipe. Não altera o motor de rotas, os contratos de dados nem as permissões do backend.

## Organização

A navegação lateral permanece disponível enquanto uma página está aberta. Em celular, um único botão Menu mostra as mesmas páginas, agrupadas por assunto. Não existe mais o caminho Central de trabalho → Navegar entre ferramentas para chegar a uma função.

| Área | Acessos diretos |
| --- | --- |
| Operação | Viagens, Importar viagens, Corredores, Frota, Corredor de referência |
| Análise | Relatórios, Histórico, Reportar ocorrência, Fontes e serviços, Simulação de chuva |
| Empresa | Custos da empresa, Plano e consumo (ADMIN), Equipe e acesso, Primeiro cliente, Minha empresa |
| Apoio | Demonstração, Guia de uso, Operação interna (ADMIN) |

Viagens mostra os quatro indicadores existentes sem recolhê-los. Cadastro de viagem, importação CSV e exportação de contingência ficam visíveis no cabeçalho. Busca, filtros, diferença estimada, caminhão e identificador permanecem na lista. A legenda básica do mapa está aberta; camadas e explicações complementares continuam disponíveis.

As páginas usam `dialog.show()` sem modalidade para reutilizar o ciclo de abertura/fechamento dos componentes. Não usam `showModal()` nem backdrop para navegação normal, e a lateral continua interativa. Despacho e recuperação de acesso continuam sendo tarefas temporárias em seus formulários próprios.

## Viagem selecionada

O resumo no mapa tem três ações: comparar, conferir pedágios/pontes e registrar decisão. Os detalhes abrem como página com seis abas:

| Aba | Conteúdo preservado |
| --- | --- |
| Resumo | Recomendação, confiança declarada, rota original e alternativa, distância, tempo, diferença de custo, perda potencial, justificativa e limitações |
| Pedágios e pontes | Dimensões do veículo, peso, eixos, referências de pedágio, tarifas pendentes, pontes, limites e incompatibilidades |
| Postos e histórico | Postos e preços próximos, referências da ANP, sinistros, roubos, cobertura, fontes e atualização |
| Custos e recálculo | Comparação financeira, premissas editáveis, recálculo, espera, detalhes financeiros e dados de referência |
| Alertas e fontes | Eventos, sua natureza/validade/relação com trechos, atualização explícita e lista de vulnerabilidades |
| Decisão | Motivo, aprovar desvio/manter/aguardar, confirmação do servidor e histórico da decisão; resultado informado da viagem e correções |

Os blocos de conteúdo dos componentes anteriores são movidos, não copiados. Os mesmos IDs, formulários, funções e closures continuam ativos. As seções da aba selecionada são abertas; não exigem abrir um acordeão dentro de outro. JSON integral de consultas históricas permanece opcional por conter dados brutos extensos. As abas têm associação ARIA, estado selecionado e navegação por setas/Home/End.

O cadastro ADMIN de pedágios e pontes mantém a escolha por clique no mapa, inclusive no celular. Ao concluir ou mudar de área, a captura de coordenadas é cancelada, preservando os valores preenchidos.

## Manifesto CSV

A importação adicionada pela equipe tem página própria e preserva modelo, exemplo de Araraquara, envio/arrastar arquivo, prévia, erros por linha, rejeitadas, confirmação e resultado. A importação JSON permanece disponível por botão explícito na mesma página.

A prévia e a gravação passam pelo transporte autenticado já utilizado pelo painel. Respostas são conferidas contra a geração do arquivo e da sessão; cancelar, trocar arquivo ou sair impede que uma resposta antiga preencha outro estado. A confirmação possui bloqueio de envio simultâneo. Resultado parcial é identificado e permite baixar as rejeitadas. O logout limpa o arquivo e seu conteúdo. Não há nova persistência de credenciais ou do CSV em armazenamento local. Sair da página descarta a resposta visual pendente; uma confirmação já enviada pode continuar no servidor, e o painel orienta conferir as viagens antes de reenviar.

O parser, as regras de validação, as cotas e os endpoints de gravação não foram alterados. A tela informa o resultado efetivamente devolvido pela API; importação não comprova execução de viagem nem economia.

## Preservação e validação

- `api/tests/e2e/controles-preservados.json` lista os 91 IDs anteriores à revisão, incluindo os controles novos do manifesto. Cada um deve continuar presente uma única vez.
- As oito camadas originais, acessos por papel, fontes, dados ausentes, custos conhecidos/estimados e avisos de simulação continuam preservados.
- Os testes existentes de cadastro, recorrência, despacho, chuva, espera, custos, decisão, relato, exportação, demonstração, recuperação, isolamento e administração continuam ativos.
- Cenários adicionais verificam navegação direta sem modais, seis abas com ações abertas, importação CSV real, rejeição de resposta atrasada após trocar de empresa e bloqueio de importação por VIEWER.
- A suíte usa API real e banco sintético isolado. O teste de CSV usa outra empresa sintética para não concentrar toda a suíte na cota de uma empresa; as proteções permanecem ativas. A fixture reinicia somente a medição de onboarding sintética reservada.
- O navegador automatizado usa a mesma versão local de MapLibre e estilo vazio, sem depender de tiles externos. A revisão visual manual usa o mapa normal e verifica desktop e celular.

Não foram inseridos dados de teste na base operacional ou alterados arquivos de dados oficiais. Dados e exemplos comerciais recebidos do Git foram preservados, com suas limitações existentes. Esta revisão de interface não equivale à homologação das fontes em um corredor de cliente.

Validação desta revisão (20/10/2026): 436 testes de API e 3 subtestes, 93 testes de interface e 20 testes de navegador aprovados. A suíte de navegador foi executada uma vez em um banco novo exclusivo de teste, com as cotas e proteções reais ativas.

Em 21/10/2026, a aba Decisão passou a incluir o registro pós-viagem, com correções aditivas e histórico paginado. Veja [Resultados de viagem](resultados-viagem-piloto.md). Relatórios passou a expor os indicadores autodeclarados já existentes na API, separados de custos observados e economia comprovada.
