# Revisão das seções 3.1 a 3.6

Base: `9643917`, de 21/10/2026. Esta revisão complementa os registros antigos;
as contagens de testes desses registros são evidências datadas, não o estado
atual do produto. Não declara homologação de produção ou ausência de defeitos.

| Seção | O que existe | Limite ou trabalho restante |
| --- | --- | --- |
| 3.1 Fluxo | Sessão individual, papéis, corredores e recorrências, mapa, alertas com natureza/fonte/data, comparação, premissas, decisões, histórico, relatos e estados. Testes de preservação dos controles e larguras de tela. | A cobertura real das fontes e a geometria do corredor precisam da validação descrita na auditoria do piloto. Informação ausente não confirma passagem. Acessibilidade é básica, sem certificação integral. |
| 3.2 Administração | Gestão de usuários, premissas versionadas, recuperação assistida e exportação privada. | Recuperação depende de conferência por ADMIN; não envia e-mail automaticamente. Esse é o fluxo implementado, não uma tela ausente. |
| 3.3 Relatórios | PDF do piloto/consulta/decisão; CSV de consultas/decisões e relatório individual compartilhável. Custos declarados e cobertura estão integrados. | Despesas informadas não são auditadas; economia comprovada permanece indisponível sem evidência e contrafactual. |
| 3.4 Demonstração | Script e banco isolados, faixa de demonstração e referência primária rastreável. | O evento originalmente solicitado ao colega não foi identificado. A referência ARTESP e o exercício sintético não são reconstrução histórica integral. O aceite dessa substituição continua com a equipe. |
| 3.5 Operação interna | Idade das fontes, tentativas/falhas de importação, serviços e métricas de qualidade. | Esta entrega conecta também o novo endpoint de métricas persistidas por rota. Medições em memória e mensais têm escopos distintos e permanecem identificadas. Não há monitoramento histórico anterior à instrumentação. |
| 3.6 Testes e documentação | Suítes de API, DOM e navegador; OpenAPI, instalação, onboarding, arquitetura/fontes, runbook e modelo de issue. | O quadro na conta oficial consta como pendente em `quadro-github.md`; não foi confirmado nesta revisão. O runbook ainda lista revisão conjunta por yanpefnsc, RPO/RTO e aceite do ambiente. A instalação foi ensaiada em contêiner e banco novos, não em outra máquina independente. |

## Organização do fluxo principal

O painel oferece quatro atalhos visíveis: selecionar viagem, entender alertas,
comparar rotas e registrar decisão. São atalhos de navegação, não confirmação
de que um alerta foi lido ou uma viagem aprovada. A seleção continua explícita
na lista e no mapa; a etapa selecionada usa texto e `aria-current`.

Os atalhos de detalhe ficam indisponíveis sem consulta válida, durante uma
consulta pendente ou recálculo. A primeira etapa devolve o foco à busca; as
demais abrem a aba correspondente. As seis abas, as páginas administrativas,
as importações, os relatórios e os controles anteriores continuam disponíveis.
Cada aba explica brevemente sua finalidade, sem substituir fonte ou dado.

A mudança não modifica APIs de escrita, autorização, algoritmos de rota,
custos, regras de decisão ou esquema. Não adiciona dependências ou consultas
periódicas. O monitor ADMIN faz uma leitura adicional de
`GET /api/v1/operacional/metricas-endpoints` ao abrir/atualizar a página e
preserva as outras seções em caso de falha desse endpoint.

## Verificação

- `npm test`: testes DOM, incluindo métricas mensais, zero, falha parcial e texto seguro.
- `npm run test:e2e`: fluxos com backend/banco exclusivos, os controles anteriores,
  seis abas, importações, permissões, relatórios e navegação pelos quatro passos;
  verificação de largura em 1280, 768 e 360 px e de foco ao voltar à busca.
- O CI executa também a suíte completa de API e o ensaio de backup/restauração.

Não executar testes de escrita contra banco de cliente ou operacional.

Referências: [contratos e limites](contratos-interface-pendentes.md),
[auditoria do piloto](auditoria-cobertura-piloto.md),
[demonstração](demonstracao-isolada.md), [evidências 3.6](evidencias-validacao-3-6.md),
[quadro oficial](quadro-github.md) e [runbook](runbook-operacao.md).
