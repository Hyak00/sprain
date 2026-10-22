# Homologacao isolada

`compose.homolog.yml` define um projeto Compose chamado `sprain-homolog`, com
volume e rede proprios. Apenas a API ocupa a porta local `127.0.0.1:18001`;
o PostgreSQL nao publica porta no host. O ambiente executa as validacoes da
configuracao de producao, mas usa somente credenciais e banco exclusivos da
homologacao. Nao use credenciais, dumps ou dados de clientes de producao.

Crie `.env.homolog` fora do controle de versao (`.env.*` esta no `.gitignore`)
com valores distintos dos outros ambientes para:

```text
HOMOLOG_DB_NAME
HOMOLOG_DB_USER
HOMOLOG_DB_PASSWORD
HOMOLOG_API_KEYS
HOMOLOG_TENANT_API_KEYS
HOMOLOG_WEBHOOK_SECRET_KEY
HOMOLOG_BUILD_COMMIT
HOMOLOG_CORS_ORIGINS
```

`HOMOLOG_BUILD_COMMIT` deve ser o SHA completo do commit candidato. As chaves
devem apontar para uma empresa de ensaio e cumprir a validacao normal da API.
O arquivo Compose desliga a demonstracao e nao inicia o importador por padrao.

Use sempre `-p sprain-homolog`: essa opcao prevalece mesmo se a maquina tiver
`COMPOSE_PROJECT_NAME` definido para outro ambiente. Antes de subir, confira
o nome do projeto, a porta e o destino do volume:

```text
docker compose -p sprain-homolog --env-file .env.homolog -f compose.homolog.yml config --quiet
docker compose -p sprain-homolog --env-file .env.homolog -f compose.homolog.yml up -d --build --wait db api
```

Em um volume novo, o PostgreSQL aplica os arquivos versionados de `db/ci`.
Os dados que constam do repositorio servem para ensaio; nao sao uma copia de
producao nem validam a cobertura das fontes reais. Em volume existente, esses
scripts de inicializacao nao rodam outra vez; a API aplica as migracoes
aditivas previstas no startup. Antes de testar uma versao nova, faca backup
do proprio ambiente de homologacao e confira a compatibilidade do esquema.

Verifique `http://127.0.0.1:18001/api/v1/health/readiness` e, com chave
ADMIN exclusiva da homologacao, `GET /api/v1/operacional/versao` para
comparar o SHA da imagem aprovada. Depois, execute os fluxos essenciais e
registre o resultado. Para parar sem apagar o banco:

```text
docker compose -p sprain-homolog --env-file .env.homolog -f compose.homolog.yml stop
```

Nao execute `down -v`: isso removeria o volume de homologacao. O Compose
isolado ainda nao constitui um ambiente implantado. E preciso fornecer
host, chaves, backup, monitoramento e responsavel para uma homologacao real.
