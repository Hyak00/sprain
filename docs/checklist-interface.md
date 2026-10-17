# Checklist rastreável da interface

Atualização 3.6 em 17/10/2026, sobre main `2eb0d3c`. Evidências atuais em [validação](evidencias-validacao-3-6.md). Registros anteriores continuam no histórico Git e nos guias específicos.

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
| 3.2 Gestão de usuários | Implementado e testado | CRUD permitido, papel e desativação por ADMIN individual; API/DOM/Chromium. Ver administracao-interface.md |
| 3.2 Premissas da empresa | Implementado e testado | Padrões financeiros versionados e conflitos; não reescrevem fotografias antigas |
| 3.2 Recuperação de acesso | Implementado | Recuperação assistida, liberação por ADMIN e código de uso único; sem envio automático de e-mail |
| 3.2 Exportação de dados do cliente | Implementado | ZIP privado com manifesto/JSON Lines, limites explícitos e sem credenciais; não constitui parecer de conformidade LGPD |
| 3.3 PDF | Implementado e testado | PDF piloto e decisão individual, gerado localmente; assinatura de arquivo verificada no Chromium |
| 3.3 CSV de consultas/decisões | Implementado e testado | Históricos persistentes via endpoints CSV por empresa, limites de exportação explícitos |
| 3.3 Relatório do piloto | Implementado com lacunas de evidência explícitas | Modelo separa observado/comprovado/estimado/potencial. Observado e comprovado exigem viagens reais |
| 3.3 Decisão compartilhável | Implementado e testado | PDF/HTML individual com fotografia vinculada e identificação disponível; não inventa autoria antiga |
| 3.4 Dados isolados | Implementado para base sintética | compose.demo.yml, bootstrap CI, rede/volume/porta separados |
| 3.4 Evento histórico | Referência pesquisada; evento da equipe pendente | Referência primária ARTESP identificada separadamente do exercício sintético. Evento originalmente fornecido não foi identificado; não alegar sua reprodução |
| 3.4 Identificação da demo | Implementado na central | Banner explícito e roteiro; login demonstrativo bloqueado em produção |
| 3.5 Idade/fontes/saúde/qualidade | Implementado e testado | ADMIN consulta fontes, falhas auditadas, serviços e qualidade; não reconstrói histórico anterior à instrumentação |
| 3.6 Testes de interface | Automação implementada | 89 testes DOM e sete cenários Chromium com backend real e banco reservado; ver evidencias-validacao-3-6.md |
| 3.6 Testes de endpoints | Contratos e regressões automatizados | Rotas de leitura usadas pelo painel, inventário de prefixos e testes de escrita/RBAC/isolamento; cobertura não equivale a prova de todo cenário possível |
| 3.6 Swagger | Implementado e testado | Descrições, segurança, exemplos validados contra modelos reais e tipos CSV/ZIP; sem mudar handlers |
| 3.6 Instalação limpa | Validado em ambiente isolado novo | Cópia de trabalho sem dependências locais, volume/rede novos e sondas. Repetição por outra pessoa em máquina limpa permanece pendente |
| 3.6 Onboarding técnico | Documentado | onboarding-tecnico-cliente.md: empresa lógica, primeiro ADMIN, usuários, frota, corredores, premissas e aceite |
| 3.6 Arquitetura/fontes | Documentado | arquitetura-e-fontes.md: módulos, origem, frequência de tentativa/publicação e limites |
| 3.6 Runbooks conjuntos | Procedimentos e ensaio; revisão humana pendente | runbook-operacao.md e backup/restore em banco novo; yanpefnsc indicado para revisão conjunta, sem presumir aceite |
| 3.6 GitHub Projects/modelo de issue | Modelo e issues prontos; quadro oficial pendente | Seis áreas e issues #46–#51 no repositório yanpefnsc/sprain; quadro pessoal não substitui o quadro da equipe. Veja quadro-github.md |
| 3.7 Importar arquivo/premissas | Parcial | JSON validado com prévia e resultados por item; recorrência agora disponível; importação condicional/atômica permanece pendente |
| 3.7 Primeiro resultado útil | Dependência | Tempo local de sessão não substitui evento persistido de onboarding |
| Compartilhado: corredor/piloto | Pendente de equipe | Escolha com dados reais, não apenas corredor de referência |
| Compartilhado: revisão cruzada | Pendente de equipe | Revisão humana do PR, especialmente proteção de concorrência |
| Compartilhado: E2E/checklist de lançamento | Parcial | Fluxos verificáveis existentes; Parte 12 completa não fornecida, e há bloqueadores de contrato |

Critério de conclusão geral: fechar cada linha parcial/dependente com integração e evidência. Nenhuma contagem de testes, screenshot ou checklist antigo autoriza marcar toda a lista como pronta.
