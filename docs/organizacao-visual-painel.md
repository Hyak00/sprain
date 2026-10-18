# Organização visual do painel

A reorganização usa a paleta azul escuro aprovada e os componentes do painel real. A proposta isolada não substitui o produto e seus dados ilustrativos não são importados para a operação.

## Onde encontrar cada recurso

| Recurso anterior | Caminho atual |
| --- | --- |
| Lista, busca, críticos, desvios e viagens sem decisão | Operações; todos os filtros foram mantidos |
| Total monitorado, desvio, custo e perda potencial | Cenário e indicadores → Indicadores e impacto potencial |
| Chuva e custo de retenção | Cenário e indicadores → Simular cenário de chuva |
| Exportação de contingência CSV | Cenário e indicadores → Exportar CSV; mantém a permissão anterior |
| Cadastro e despacho por endereço | Despachar Nova Rota; mesmos campos, autocomplete, medidas e premissas |
| Caminhões, medidas, combustível e custos | Frota; mesmos cadastros e formulários |
| Administração de pedágios e pontes | Frota → Administrar pedágios e pontes, para ADMIN |
| Escolha da localização de estrutura | Escolher localização no mapa; o mapa reaparece na frota, recebe a coordenada e retorna ao cadastro |
| Corredores e recorrências da empresa | Corredores |
| Corredor regional de referência | Configurações → Consultar corredor existente |
| Mapa, fontes, legenda e camadas | Operações → Legenda e camadas do mapa |
| Comparação, justificativa, confiança e limitações | Selecionar viagem → Comparar rotas |
| Pedágios, dimensões, pontes e restrições | Comparar rotas → Pedágios, caminhão e restrições |
| Postos, preços, histórico e cobertura | Comparar rotas → Postos, historico e atualizacao dos dados |
| Fontes, validade, natureza e consequências dos alertas | Comparar rotas → Alertas: fonte, validade e relação com a rota |
| Custos conhecidos, estimativas e tarifas pendentes | Comparar rotas; resumo financeiro e comparação detalhada mantidos |
| Recálculo por premissas | Comparar rotas → Editar premissas e recalcular esta operação |
| Espera e motor econômico | Comparar rotas → Comparar um cenário de espera |
| Aprovar desvio, manter, aguardar e histórico da decisão | Comparar rotas → Supervisão do Gestor |
| PDF, CSV, JSON e relatório individual compartilhável | Relatórios |
| Usuários, recuperação e padrões financeiros | Configurações e Central de trabalho → Navegar entre ferramentas |
| Primeiro cliente e medição persistente | Configurar primeiro cliente, no rodapé da navegação |
| Importação JSON, consultas, relatos e demonstração | Central de trabalho → Navegar entre ferramentas |
| Qualidade, importações, fontes e serviços internos | Central de trabalho → Navegar entre ferramentas; painel interno mantém acesso ADMIN |
| Troca de conta e logout | Cabeçalho → Trocar Conta |

## Limites da alteração

`painel-layout.js` move os nós existentes e adapta sua apresentação. Não troca endpoints, modelos, política de acesso, fontes, geometria de rotas ou fórmulas financeiras. `painel-layout.css` concentra a organização visual. O carregamento de arquivos foi versionado para evitar misturar scripts antigos do cache.

A comparação usa um diálogo nativo, com fechamento por Escape e retorno ao botão de origem. O mapa fica disponível sem o painel de auditoria permanentemente sobreposto. Os detalhes completos continuam na comparação; valores não são resumidos substituindo a resposta da API. Ao consultar outra viagem, carregar ou falhar, a comparação anterior fica indisponível. Logout fecha os diálogos e limpa a seleção.

O modo de demonstração continua explicitamente identificado. Custos estimados, parcelas conhecidas e dados ausentes não passam a ser economia comprovada ou autorização de passagem. O tempo exibido no resumo é identificado como horário de cálculo, sem inventar atualização da fonte.

## Verificação de regressões

- Os 69 IDs existentes no documento anterior são conferidos pelo navegador, exatamente uma vez cada. A lista de referência está em `api/tests/e2e/controles-preservados.json`.
- Os testes anteriores mantêm as verificações de autenticação, papéis, relatórios reais, recorrência, despacho idempotente, demonstração, usuários, recálculo, decisões, relatos, onboarding e espera.
- Cenários adicionais verificam navegação única, acesso a infraestrutura e postos, oito camadas, indicadores, escolha de ponte no mapa em desktop/celular, ausência de transbordamento da comparação em 360 px, limpeza no logout e recusa de reutilizar comparação após falha de consulta.
- Os testes de navegador usam a API real e banco sintético isolado. Os assets externos do mapa são substituídos pela mesma versão local e um estilo vazio para não depender de tiles da Internet. A conferência visual manual usa o mapa externo normal.
- A suíte de API e a suíte de DOM continuam sendo executadas. A preservação de controles complementa os testes funcionais; ela sozinha não comprova cada combinação possível de dados reais.

Não foi feito cadastro de cliente real nem alteração da base operacional. Avaliar apresentação com operadores e comprovar cobertura e qualidade das fontes no corredor de implantação continua sendo parte da validação do produto.

Validação local em 17/10/2026: 315 testes de API e 3 subtestes, 89 testes DOM e 14 cenários Chromium aprovados em bancos isolados. CI executa novamente as mesmas suítes no commit publicado.
