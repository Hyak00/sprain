# SPRain B2B — guia de operação e deploy

Este guia resume os comandos. Antes de um deploy real, siga o
[runbook operacional](docs/runbook-operacao.md), incluindo backup restaurado em
banco novo, revisão da configuração e plano de rollback. O Compose de produção
faz build local da API; para uma release com imagem imutável, a equipe ainda
precisa publicar e fixar uma imagem por digest.

## Requisitos

- Docker Engine/Desktop com Compose v2 e contêineres Linux.
- Recursos recomendados: 4 vCPUs e 8 GB de RAM.
- Arquivo de ambiente próprio do destino, fora do Git, com valores aprovados.
  Não copie as credenciais da demonstração para produção.

## Identificar o código da imagem

Em uma árvore de trabalho limpa, defina o SHA completo do commit aprovado.
No PowerShell:

```powershell
$env:SPRAIN_BUILD_COMMIT = (git rev-parse HEAD).Trim()
git status --short
docker compose --env-file .env.prod -f docker-compose.prod.yml config --quiet
```

O `docker-compose.prod.yml` exige `SPRAIN_BUILD_COMMIT` e o inclui no build da
API. O campo informa a revisão declarada pela imagem; confirme também seu
digest e que o checkout não contém alterações locais antes do build.

## Inicialização após aprovação operacional

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
.\scripts\check_deploy.ps1 -ComposeFile docker-compose.prod.yml -EnvFile .env.prod
```

O script confere a configuração Compose e a prontidão da API/PostGIS. Consulte
`GET /api/v1/operacional/versao` com uma sessão ADMIN e compare `revisao` com
`SPRAIN_BUILD_COMMIT`; uma revisão ausente ou diferente impede afirmar qual
código está em execução. O procedimento não substitui testes de fluxos reais,
verificação de fontes ou a restauração de backup.

## Endpoints de verificação

- Liveness: `GET /api/v1/health/liveness`
- Readiness: `GET /api/v1/health/readiness`
- Versão: `GET /api/v1/operacional/versao` (ADMIN)
- Swagger UI: `GET /docs`
- OpenAPI: `GET /openapi.json`
