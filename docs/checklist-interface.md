# Checklist rastreável da interface

Revalidação de 3.1 sobre main `e450ec5`: [correções e evidências atuais](validacao-painel-atual.md), com 197 testes da API e 58 da interface aprovados. Os estados das demais seções abaixo não são encerrados por esta validação.

Referência: seções 3.1–3.7 da lista técnica enviada, páginas 9–11. Atualização do fluxo 3.1 sobre main `8c2c188`, 16/10/2026. Aceites e limites em [fluxo-mvp-painel.md](fluxo-mvp-painel.md). **Implementado** significa o comportamento descrito existe; não equivale à homologação de todo o MVP. **Parcial** e **dependência** não devem ser encerrados como concluídos.

| Item | Situação | Evidência / próximo aceite |
|---|---|---|
| 3.1 APIs chamadas pelo painel | Validado localmente | Inventário de contratos no OpenAPI, testes HTTP e fluxos manuais; corrigida busca de trechos próximos |
| 3.1 Login/logout/papéis | Implementado e verificado | Login individual com hash de senha e sessão revogável/expirável; empresa/papel atuais e autoria; demo preservada fora de produção. Ver homologacao-fluxo-painel.md |
| 3.1 Corredores/rotas recorrentes | Implementado | CRUD/versionamento, inativação, agenda persistida e despacho explícito idempotente; sem agendador automático |
| 3.1 Mapa/vulnerabilidade/camadas | Implementado | Malha e rotas preservadas; ocorrências com geometria autorizada e relatos privados; ausência de geometria explícita |
| 3.1 Fontes/datas/legenda | Implementado com ausência explícita | Cenário/cálculo/consulta separados; fontes disponíveis exibidas, valores ausentes não são fabricados |
| 3.1 Detalhe do alerta | Implementado | Detecção, trecho/local, fonte, horários, confiança, possível consequência e incógnitas; consequência genérica identificada |
| 3.1 Natureza da informação | Implementado | Texto/cor para histórico, previsão, simulação, trânsito observado, confirmado e relato pendente; desconhecido explícito |
| 3.1 Indisponível/antigo/sem alternativa | Implementado | Validade, falha, camada limpa, ausência de geometria, comparação indisponível e consulta obsoleta |
| 3.1 Comparação de rotas/custos | Implementado | Motor original; distância/tempo, restrições, pedágios/combustível, custos estimados, cobertura e limitações |
| 3.1 Premissas editáveis | Implementado | Custo por operação no inspector; selo de conflito, cenário explícito e recálculo transacional; tabela/totais sincronizados |
| 3.1 Conhecido/estimado | Implementado | Parcelas conhecidas versus estimativas; potencial não comprova economia; ausência não vira zero |
| 3.1 Decisão e histórico | Implementado e verificado | Consulta persistida e fotografia vinculada; usuário individual nas novas sessões, empresa/papel nas credenciais compartilhadas; registros antigos sem dados não são reconstruídos |
| 3.1 Reporte de erro/evento ausente | Implementado | Feedback existente e relato privado georreferenciado pendente; não bloqueia rotas automaticamente |
| 3.1 Estados em todas as telas | Implementado nos fluxos do painel | Central, frota, corredor, operações e novos formulários têm carregamento/erro/vazio ou validação; falha não mantém comparação anterior como atual |
| 3.1 Responsividade/acessibilidade | Implementado em nível básico | Rótulos, foco, teclado/Escape, fundo do despacho inerte, texto além de cor; 320/768/1280 px verificados; não equivale a auditoria WCAG integral |
| 3.2 Gestão de usuários | Dependência | Não existe CRUD de identidade; tela explica indisponibilidade, sem simular gravação |
| 3.2 Premissas da empresa | Dependência | Formulários por frota/despacho existentes; persistência global ausente |
| 3.2 Recuperação de acesso | Dependência | Login atual é demo; não há recuperação |
| 3.2 Exportação de dados do cliente | Parcial | Resumo/consulta/decisões exportáveis; não é exportação integral administrativa/LGPD |
| 3.3 PDF | Implementado | Download local do piloto e consulta/decisões, texto extraído e renderizado para QA |
| 3.3 CSV de consultas/decisões | Parcial | Consulta carregada e histórico retornado; consultas agora persistidas, exportação agregada de todas as fotografias ainda não criada |
| 3.3 Relatório do piloto | Parcial | Modelo separa observado/comprovado/estimado/potencial; observado/comprovado não disponíveis |
| 3.3 Decisão compartilhável | Parcial | PDF/HTML da consulta e histórico; fotografia vinculada agora existe, identidade individual depende de 3.2 |
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
| 3.7 Importar arquivo/premissas | Parcial | JSON validado com prévia e resultados por item; recorrência agora disponível; importação condicional/atômica permanece pendente |
| 3.7 Primeiro resultado útil | Dependência | Tempo local de sessão não substitui evento persistido de onboarding |
| Compartilhado: corredor/piloto | Pendente de equipe | Escolha com dados reais, não apenas corredor de referência |
| Compartilhado: revisão cruzada | Pendente de equipe | Revisão humana do PR, especialmente proteção de concorrência |
| Compartilhado: E2E/checklist de lançamento | Parcial | Fluxos verificáveis existentes; Parte 12 completa não fornecida, e há bloqueadores de contrato |

Critério de conclusão geral: fechar cada linha parcial/dependente com integração e evidência. Nenhuma contagem de testes, screenshot ou checklist antigo autoriza marcar toda a lista como pronta.
