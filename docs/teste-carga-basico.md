# Medição básica de carga: rotas e riscos

O CI executa `scripts/medir_carga_api.py` contra o `compose.e2e.yml`, depois de
preparar as contas sintéticas. O script só aceita URL HTTP local e confirma que
`/api/v1/demonstracao/estado` responde `DEMONSTRACAO_ISOLADA` antes de iniciar.
Ele não grava viagens, não importa dados e não consulta provedor externo.

São medidas duas consultas de leitura: o corredor de referência em
`GET /api/v1/rotas/intermunicipal` e tombamentos em
`GET /api/v1/dados-publicos/tombamentos`. Cada endpoint recebe uma chamada de
pré-verificação e, por padrão, 20 chamadas medidas com até quatro simultâneas.
O teto é 100 por endpoint e oito simultâneas. Todas precisam retornar HTTP 200
com o formato esperado. O relatório mostra contagens, p50, p95, máximo e
requisições por segundo. O CI guarda `carga-api.json` como artefato.

Execução local **somente** após iniciar o ambiente isolado de E2E:

```powershell
$env:SPRAIN_API_KEY = 'key_viewer_demo'
python scripts/medir_carga_api.py --base-url http://127.0.0.1:18002 --saida test-results/carga-api.json
```

As latências do runner são uma linha de base, não um SLA nem prova de capacidade
produtiva. A fixture sintética não mede grandes volumes de dados, picos longos,
gravações concorrentes, serviços externos ou múltiplas réplicas. Comparar novas
medições no mesmo tipo de ambiente antes de definir metas de latência. Nunca
apontar esta carga para o banco ou a API de um cliente.
