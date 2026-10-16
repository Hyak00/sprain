# Checklist rastreável da interface

Referência: seções 3.1–3.7 da lista técnica enviada, páginas 9–11. Base `4c63696`, 15/10/2026. **Implementado** significa o comportamento descrito existe; não equivale à homologação de todo o MVP. **Parcial** e **dependência** não devem ser encerrados como concluídos.

| Item | Situação | Evidência / próximo aceite |
|---|---|---|
| 3.1 APIs chamadas pelo painel | Parcial | Contratos centrais testados; inventário nos guias de sessão/central; falta cobertura de todos os módulos e falhas |
| 3.1 Login/logout/papéis | Implementado no acesso demo | Testes de sessão/DOM e conferência manual; identidade real depende do backend |
| 3.1 Corredores/rotas recorrentes | Dependência | Backend só consulta corredor de referência; contrato em contratos-interface-pendentes.md |
| 3.1 Mapa/vulnerabilidade/camadas | Parcial | Camadas existentes preservadas e controles adicionados; eventos sem geometria não viram pontos inventados |
| 3.1 Fontes/datas/legenda | Parcial | Alertas, infraestrutura, contexto e central mostram metadados disponíveis; há campos não fornecidos |
| 3.1 Detalhe do alerta | Parcial | Fonte, validade, estado, confiança, incógnitas e associação; falta consequência/localização específica no contrato |
| 3.1 Natureza da informação | Parcial | Explicação e aviso de demonstração; falta classificação uniforme fornecida por todas as fontes |
| 3.1 Indisponível/antigo/sem alternativa | Parcial | Estados nos complementos e central; ampliar verificação a todos os módulos legados |
| 3.1 Comparação de rotas/custos | Implementado no contrato atual | Cards, infraestrutura e comparação detalhada; espera/observado/comprovado não fornecidos |
| 3.1 Premissas editáveis | Parcial | Frota e novo despacho; comparação em leitura. Alterar custo de viagem existente/global depende do backend |
| 3.1 Conhecido/estimado | Implementado nos relatórios/complementos | Valores ausentes não viram zero; potencial não vira economia comprovada |
| 3.1 Decisão e histórico | Parcial | Fluxos existentes preservados e CSV/PDF; falta autoria individual/fotografia histórica |
| 3.1 Reporte de erro/evento ausente | Parcial | Feedback de evento existente funciona; relato novo depende de endpoint |
| 3.1 Estados em todas as telas | Parcial | Central com carregamento/erro/vazio/parcial; revisar telas legadas restantes |
| 3.1 Responsividade/acessibilidade | Parcial | CSS, rótulos, teclado, diálogo e camadas; validar todos os fluxos/breakpoints antes de homologar |
| 3.2 Gestão de usuários | Dependência | Não existe CRUD de identidade; tela explica indisponibilidade, sem simular gravação |
| 3.2 Premissas da empresa | Dependência | Formulários por frota/despacho existentes; persistência global ausente |
| 3.2 Recuperação de acesso | Dependência | Login atual é demo; não há recuperação |
| 3.2 Exportação de dados do cliente | Parcial | Resumo/consulta/decisões exportáveis; não é exportação integral administrativa/LGPD |
| 3.3 PDF | Implementado | Download local do piloto e consulta/decisões, texto extraído e renderizado para QA |
| 3.3 CSV de consultas/decisões | Parcial | Consulta carregada e histórico retornado; histórico persistente de consultas ausente |
| 3.3 Relatório do piloto | Parcial | Modelo separa observado/comprovado/estimado/potencial; observado/comprovado não disponíveis |
| 3.3 Decisão compartilhável | Parcial | PDF/HTML com histórico; relatório histórico auditável exige fotografia/autoria no backend |
| 3.4 Dados isolados | Implementado para base sintética | compose.demo.yml, bootstrap CI, rede/volume/porta separados |
| 3.4 Evento histórico | Dependência | Fonte primária/trechos a conferir; endpoint atual possui substitutos |
| 3.4 Identificação da demo | Implementado na central | Banner explícito e roteiro; login demonstrativo bloqueado em produção |
| 3.5 Idade/fontes/saúde/qualidade | Parcial | Central consome endpoints; histórico de falhas/periodicidade por fonte não fornecido |
| 3.6 Testes de interface | Parcial | Testes DOM/sessão e navegador manual; falta automação completa de navegador |
| 3.6 Testes de endpoints | Parcial | Suíte existente + leitura da central + concorrência; não é cobertura de todos os endpoints |
| 3.6 Swagger | Parcial | Exemplo de operação e semântica de importação documentados; revisão integral pendente |
| 3.6 Instalação limpa | Parcial | Bootstrap em volume novo validado; máquina independente e outra pessoa pendentes |
| 3.6 Onboarding técnico | Documentado | Fluxo e lacunas em onboarding-arquitetura-operacao.md; ativação real depende do backend |
| 3.6 Arquitetura/fontes | Documentado | Diagrama e módulos, referências às fontes existentes e limitações |
| 3.6 Runbooks conjuntos | Parcial | Roteiro e scripts existentes referenciados; revisão conjunta e simulado de restauração/rollback pendentes |
| 3.6 GitHub Projects/modelo de issue | Parcial | Template com seis áreas propostas; API recusou Projects por INSUFFICIENT_SCOPES, quadro não criado |
| 3.7 Importar arquivo/premissas | Parcial | JSON validado com prévia e resultados por item; criação condicional/atômica e recorrência ainda ausentes |
| 3.7 Primeiro resultado útil | Dependência | Tempo local de sessão não substitui evento persistido de onboarding |
| Compartilhado: corredor/piloto | Pendente de equipe | Escolha com dados reais, não apenas corredor de referência |
| Compartilhado: revisão cruzada | Pendente de equipe | Revisão humana do PR, especialmente proteção de concorrência |
| Compartilhado: E2E/checklist de lançamento | Parcial | Fluxos verificáveis existentes; Parte 12 completa não fornecida, e há bloqueadores de contrato |

Critério de conclusão geral: fechar cada linha parcial/dependente com integração e evidência. Nenhuma contagem de testes, screenshot ou checklist antigo autoriza marcar toda a lista como pronta.
