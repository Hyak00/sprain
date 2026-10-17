# Instalação local e demonstração isolada

Pré-requisitos: Git e Docker Desktop/Engine com Compose. Python 3.9+ executa a sonda opcional. Node/npm são necessários apenas para testes de interface. Execute na raiz do repositório.

```text
docker compose -f compose.demo.yml up -d --build
python scripts/preparar_demonstracao.py
python scripts/verificar_portal.py
```

Abra `http://127.0.0.1:18000/static/b2b.html`; Swagger: `/docs`. Use os botões de acesso rápido de demonstração. O Compose carrega os scripts de `db/ci` somente na primeira inicialização do volume próprio. A API aplica as migrações aditivas de meteorologia, alertas, validação espacial, feedback, bacias e auditoria ao iniciar, inclusive em volumes existentes. Não usa volumes, banco, rede, chaves ou portas do ambiente operacional.

Dados do CI são exemplos/sintéticos e não evidência de eventos históricos, viagens de clientes ou retorno financeiro realizado. As chaves e senha do Compose são públicas de demonstração, inadequadas para produção. Somente a API é publicada em loopback; o banco permanece na rede Docker. O agendador climático automático fica desligado somente neste modo de demonstração explicitamente isolado. A demonstração não implica fontes públicas completas ou atualizadas.

A métrica de acurácia considera apenas registros de `auditoria_previsao_realidade` com `tenant_id` igual à empresa autenticada. Registros antigos sem empresa identificada são preservados, mas não entram na métrica; a origem deles precisa ser comprovada antes de atribuir um `tenant_id`.

Para parar sem apagar os dados:

```text
docker compose -f compose.demo.yml stop
```

Para reiniciar:

```text
docker compose -f compose.demo.yml up -d
```

Não use `down -v` ou apague volumes operacionais para repetir uma demonstração. Para testar uma instalação realmente nova, escolha outro projeto/volume explicitamente isolado. Uma atualização de imagem não reaplica automaticamente scripts de inicialização em volume antigo.

Confira `/api/v1/health/readiness` depois da atualização: a sonda retorna 503 se faltar uma tabela operacional, a extensão PostGIS ou a malha viária. Uma resposta 200 confirma a estrutura necessária, não a atualidade ou a cobertura dos dados externos.

## Roteiro de apresentação

1. Diga explicitamente que o ambiente e as operações são de demonstração.
2. Operador: abra operações, chuva e detalhes; confira original/alternativa, pedágios, restrições, fontes e incógnitas.
3. Frota/despacho: mostre campos de medidas e custos; use somente dados de teste identificados. Não apresente medidas de exemplo como cadastro real.
4. Alterne cenários de chuva e explique que simulação não é observação. Confira ausência de alternativa quando ocorrer e não aprove caminho indisponível.
5. Registre uma decisão de teste com motivo. Confira o histórico e baixe o relatório individual.
6. Na central, mostre o relatório do piloto, idade das fontes e serviço indisponível/sem dados quando aplicável.
7. Entre como VIEWER: consultas funcionam; cadastro, simulação de escrita, decisão e importação não ficam disponíveis.
8. Saia/troque empresa e confirme a limpeza da tela.

A aba Demonstração usa uma referência oficial pesquisada da ARTESP, separada de um exercício sintético. O evento pretendido pelo colega não foi identificado; não há reconstrução geográfica histórica homologada. Veja [fonte, isolamento e roteiro](demonstracao-isolada.md).

## Evidência da instalação

O Compose foi verificado em banco/volume novos no host de desenvolvimento, e a sonda deve retornar 23 sucessos. Isso comprova bootstrap isolado em contêiner; **não** equivale à validação por outra pessoa em máquina limpa. A revisão independente continua no checklist.

Falha no bootstrap: veja `docker compose -f compose.demo.yml logs --tail 100 db api`, sem publicar credenciais/logs privados. Confirme disponibilidade da porta 18000, Docker em execução e conexão ao registro de imagens. Nunca resolva falha apagando dados de outro projeto.
