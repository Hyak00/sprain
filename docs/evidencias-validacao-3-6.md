# Evidências da entrega 3.6

Data: 17/10/2026. Base: main `2eb0d3c`; branch
`feat/testes-documentacao-mvp`. Windows com Docker Desktop/Linux, Python 3.11
nos contêineres e Chromium instalado pelo Playwright 1.64.1.

## Automação

| Verificação | Resultado local |
| --- | --- |
| API, banco exclusivo de validação | 296 testes + 3 subtestes passaram |
| Interface unitária/DOM, `npm test` | 89 testes passaram |
| Chromium com API/banco e2e exclusivos | 7 cenários passaram |
| Bootstrap e sonda da instalação isolada | 24 endpoints/assets responderam HTTP 200 |
| Dependências Python | `pip check` sem conflito no runtime validado |

Os sete cenários verificam login/logout, RBAC de VIEWER e downloads PDF/CSV;
corredor/recorrência/despacho idempotente; premissas versionadas/monitor interno;
demonstração e geometria real; criação/papel/desativação de usuário; comparação,
recálculo, decisão vinculada, histórico e relato; central a 360 px e Escape/foco.
MapLibre roda de verdade com sua versão local. Tiles externos são bloqueados;
respostas de negócio vêm do backend real, não de mocks.

A suíte da API cobre leituras do painel, inventário dos caminhos escritos no
JavaScript, exemplos Pydantic/OpenAPI, administração, isolamento, conflitos,
fontes, custos, decisões e demais regressões existentes. A primeira execução
detectou um exemplo que violava a regra de constantes fictícias; corrigido o
exemplo, a suíte completa passou. Não se alterou a regra para silenciar a falha.

## Instalação nova

Cópia dos arquivos versionáveis sem `.env`, `node_modules` ou ambiente Python
local, projeto Compose `sprain-clean36`, volume e rede novos, banco
`sprain_demo`, porta local 18003 (para não interromper a demo em 18000).
Build e startup saudáveis; preparação idempotente e as 24 sondas passaram.
O build usa camadas Docker previamente baixadas; a resolução do lock Python
também foi instalada do registro na construção do runtime e2e.

É prova de instalação em contêiner Linux e banco novos neste computador.
Repetição por outra pessoa em máquina independente ainda não foi realizada.

## Backup, restore e retorno de imagem

Backup `pg_dump --format=custom`, manifesto SHA-256 e listagem `pg_restore`
verificados pelo script existente. Restore final em banco novo
`sprain_restore_36_final`, preservando `sprain_demo_e2e`.

Comparação após o ensaio: **105 operações, 8 usuários e 2.982 trechos** em
ambos os bancos. Extensões conferidas: PostGIS 3.5.2 e pgRouting 3.7.3.
Dados são sintéticos; não foram publicados dumps, senhas ou sessões.

Imagem do commit anterior `2eb0d3c` construída com `git archive`. API isolada
em 18004 sobre a cópia restaurada: readiness, operações e relatório piloto HTTP
200. Subida da imagem nova na mesma porta/banco, readiness HTTP 200; retorno
à imagem anterior, com as três leituras HTTP 200 e contagens preservadas.
Não houve alteração de esquema nesta entrega. O ensaio comprova compatibilidade
de aplicação neste caso; não homologa downgrade de uma migration futura.

## Entrega e limites

O CI executa API, DOM e Chromium e publica artefatos de falha por sete dias.
As [seis áreas e issues](quadro-github.md) estão preparadas no repositório oficial;
o quadro na conta do proprietário continua pendente e o quadro pessoal não o
substitui. [Runbook](runbook-operacao.md) preparado para revisão com
`yanpefnsc`; aprovação conjunta não foi recebida nesta validação.

Não comprovados por estes testes: condições reais de rodovia/ponte/tarifa,
economia realizada, evento histórico originalmente fornecido pela equipe,
acessibilidade WCAG integral, homologação de produção e revisão independente em
outra máquina. Esses limites não devem virar “perfeito” por contagem de testes.
