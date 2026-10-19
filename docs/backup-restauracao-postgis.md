# Backup e restauração de PostgreSQL/PostGIS

O script `scripts/postgres_backup.py` usa `pg_dump` e `pg_restore` dentro de um
contêiner PostgreSQL existente. Ele grava o arquivo em formato customizado e um
manifesto com tamanho e SHA-256. Não requer porta do banco exposta nem coloca
senha na linha de comando. Requer Python 3.9+ e Docker funcionando.

Antes de usá-lo, confirme o nome do contêiner, do banco e do usuário com quem
administra **esse ambiente**. Os exemplos abaixo são para um ambiente de teste;
substitua os valores pelos seus. Escolha uma pasta fora do repositório para os
backups e mantenha cópias em armazenamento seguro separado do computador.

```powershell
python scripts/postgres_backup.py backup `
  --container sprain_audit_20261014_db `
  --database enchentes `
  --user enchentes `
  --output-dir "$HOME\sprain-backups"
```

O comando imprime o caminho do arquivo `.dump` e do manifesto `.dump.json`.
Se ocorrer falha durante a criação, um arquivo `.partial` pode permanecer na
pasta; ele **não** é um backup válido. O script nunca sobrescreve um arquivo
existente.

Para uma checagem automatizável da cópia completa mais recente, use:

```powershell
python scripts/postgres_backup.py verify-latest `
  --database enchentes `
  --output-dir "$HOME\sprain-backups" `
  --max-age-hours 36
```

O comando retorna código 0 se o manifesto, o tamanho, o SHA-256 e a idade
estiverem corretos; retorna 1 caso contrário. Ele não acessa Docker nem o banco,
não modifica arquivos e não considera um `.partial` como backup. Configure seu
monitor para alertar quando o código for 1. Essa checagem não substitui o teste
de restauração: um hash válido só confirma que o arquivo ainda corresponde ao
manifesto criado no backup.

## Testar a restauração

Restaure sempre primeiro em **um banco novo**, de nome distinto. O script
confere o manifesto, a integridade do arquivo e se o banco de destino já
existe. Se existir, ele para sem alterá-lo. Se a restauração falhar, o banco
novo permanece para diagnóstico; ele nunca executa `DROP DATABASE`.

```powershell
python scripts/postgres_backup.py restore `
  --container sprain_audit_20261014_db `
  --new-database sprain_restore_test `
  --user enchentes `
  --backup "$HOME\sprain-backups\sprain-enchentes-ARQUIVO.dump"
```

Depois compare tabelas e extensões entre origem e cópia, por exemplo:

```powershell
docker exec sprain_audit_20261014_db psql -U enchentes -d sprain_restore_test -c "SELECT PostGIS_Version();"
docker exec sprain_audit_20261014_db psql -U enchentes -d sprain_restore_test -c "SELECT count(*) FROM trechos_osm;"
```

O backup inclui a estrutura e os dados do banco especificado. Ele não inclui
arquivos `.env`, imagens Docker, segredos, nem outros bancos/volumes. Para uma
rotina de produção ainda faltam agendamento, retenção, cópia externa protegida,
destino para os alertas e testes periódicos de restauração. Não considere um
backup operacional até verificar uma restauração com dados reais do ambiente.

O CI executa `backup`, `verify-latest` e `restore` após os testes de API, em um
banco novo chamado `sprain_restore_ci` no PostgreSQL descartável do runner.
Compara a contagem de `trechos_osm` entre origem e cópia e consulta a extensão
PostGIS restaurada. Esse ensaio verifica o caminho básico a cada PR; não valida
retenção, cópia externa ou restauração do banco de produção.

`scripts/check_deploy.ps1` faz apenas verificações básicas de Compose e
readiness. Ele não roda testes contra um banco em uso nem afirma que uma
implantação está pronta para produção.
