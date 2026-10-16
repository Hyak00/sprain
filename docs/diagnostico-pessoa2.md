# Diagnóstico técnico da Pessoa 2 — 14/10/2026

Referência inicial: `main` em `ffaa51d`. Este documento registra o estado
observado, não declara o produto pronto para produção.

## O que já existe

- API FastAPI, PostgreSQL/PostGIS e painel B2B de demonstração.
- Operações, simulação de impacto, comparação de rotas e custos, registro de
  decisão, relatórios e webhooks assinados.
- Chaves por empresa e papel (`ADMIN`, `OPERATOR`, `VIEWER`) em várias rotas;
  filtros por empresa em consultas de operações, veículos e malha importada.
- CI com banco PostGIS e testes de integração.

## Validação isolada

O repositório coletou 84 testes no commit inicial. Em dois contêineres Docker
novos, sem portas publicadas e com banco próprio, os 84 passaram. Após as
correções de segurança desta branch, a mesma suíte ampliada passou com 92
testes. Nenhum teste foi direcionado ao banco ou à API de demonstração local.
Após integrar o `main` de 15/10/2026 e acrescentar as regressões de isolamento,
os 143 testes da suíte passaram;
a validação usa a mesma rede e o mesmo banco descartáveis.
O relatório `RELATORIO_HOMOLOGACAO.md` registra 56 testes de um commit anterior
e não descreve a contagem atual.

## Bloqueadores corrigidos nesta branch

| Gravidade | Situação anterior | Correção |
| --- | --- | --- |
| Crítica | Dois comandos públicos de monitoramento alteravam em massa o estado das vias. | Exigência de perfil operador ou administrador; painel envia a chave do operador. |
| Alta | GeoJSON público incluía trechos de malhas privadas importadas por empresas. | Consulta pública limitada à malha global e importações ativas; limite de resposta validado. |
| Alta | Com `API_KEYS` vazia fora de produção, qualquer chave não vazia era aceita. | Falha fechada quando não há chaves configuradas. |
| Alta | O reset global de ocorrências aceitava uma chave sem papel administrativo. | Exigência do papel administrador. |
| Alta | Login de demonstração devolvia chaves inúteis em produção; `ENVIRONMENT` só no `.env` não era reconhecido pela validação. | Login demo recusado em produção e ambiente lido também da configuração. |
| Média | CORS aceitava qualquer origem também em produção. | Em produção, apenas `CORS_ORIGINS` é aceito; sem configuração, chamadas entre origens diferentes ficam bloqueadas. |
| Alta | Feedback de uma empresa podia descartar um alerta global para todas as empresas; a precisão exibida como específica da empresa somava dados globais. | Feedback não altera a fonte global e a precisão considera apenas a avaliação mais recente de cada evento da empresa autenticada. |
| Média | Qualquer visualizador podia criar um evento global pelo cenário de demonstração, que usava uma empresa fixa. | Cenário restrito a administradores e indisponível em produção. |

## Trabalho restante antes de clientes reais

1. Substituir contas e chaves de demonstração por cadastro real de empresas,
   usuários, credenciais revogáveis e recuperação de acesso.
2. Auditar todas as rotas, consultas SQL, caches, relatórios e tarefas de fundo
   com testes de leitura e escrita entre duas empresas; avaliar RLS no banco.
3. Formalizar planos, cotas e custo de APIs externas por empresa. Os limites
   atuais são constantes em memória.
4. Implantar backup automatizado, cópia externa e restauração testada em
   ambiente separado.
5. Fixar dependências e preparar deploy com
   migração, monitoramento e rollback reproduzíveis.

Esses itens exigem evidência própria antes de serem marcados como concluídos.
