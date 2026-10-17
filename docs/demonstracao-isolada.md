# Demonstração isolada (3.4)

Execute na raiz, com Python 3.9+ e Docker Desktop/Compose:

```text
python scripts/iniciar_demo_caminhoes.py
python scripts/verificar_portal.py
```

O inicializador aceita somente `compose.demo.yml`. Alternativamente, execute
`docker compose -f compose.demo.yml up -d --build` e depois
`python scripts/preparar_demonstracao.py`. Abra
http://127.0.0.1:18000/static/b2b.html, entre pelo acesso de demonstração
da empresa demo_corp e abra Central de trabalho → Demonstração.

## Referência e limites

O evento pretendido pelo colega não foi identificado. Usei uma referência
pesquisada e rastreável: [ARTESP/CCM, OC17928](https://ccm.artesp.sp.gov.br/rodovias/oc17928),
SP-310, km 205, Itirapina, sentido sul, em 19/01/2026. O manifesto versionado
`dados/demonstracao/evento-historico.json` registra fonte, consulta, atualização,
marcos publicados e incógnitas. Não reproduz uma fonte recebida do colega.

A linha do tempo histórica fica separada do exercício. Quatro ligações e suas
coordenadas são sintéticas, sem associação espacial comprovada com o km 205.
Caminhão, dimensões e custos são exemplos. Chuva zero é parâmetro matemático
neutro, não uma medição daquele evento. Não há reconstrução histórica de vias,
pedágios, pontes, tráfego ou despesas reais. Nenhuma economia é comprovada.
Se a equipe fornecer outra referência, substitua o manifesto com evidência e
revise o roteiro; isso não valida automaticamente uma geometria histórica.

## Roteiro reproduzível

1. Confira a faixa permanente de DEMONSTRAÇÃO, inclusive antes do login.
2. Leia a fonte, os horários literais publicados e as incógnitas.
3. Prepare os dados com ADMIN de demo_corp ou pelo script.
4. Reproduza sem bloqueio, com bloqueio ilustrativo e após liberação.
5. Compare distância, tempo nominal e custo estimado calculados pelo motor
   existente. Exiba as linhas roxa e laranja no mapa: são sintéticas.
6. Se não houver rota, mantenha as medidas e valores desconhecidos.
7. Limpe as camadas, abra uma operação normal ou saia; o exercício sai do mapa.

ADMIN prepara; ADMIN, OPERATOR e VIEWER reproduzem (consulta sem gravação).
Outra empresa não prepara nem reproduz o cenário reservado. O painel bloqueia
ações enquanto calcula e descarta respostas de sessão encerrada.

## Isolamento e preservação

Compose próprio, banco sprain_demo, volume/rede próprios, API somente loopback
18000. Além da flag SPRAIN_DEMO_ENABLED=1, a inicialização e cada chamada de
exercício verificam ambiente não produtivo e nome real do banco reservado.
Os scripts verificam o estado da API antes de escrever e recusam redirects.
As chaves do Compose são públicas de demonstração; não use em produção.

A preparação usa transação e trava, cria identificadores reservados e é
idempotente. Não reativa importação desativada nem sobrescreve cadastro existente
incompatível. O bloqueio é passado somente à consulta do motor: não grava nem
altera alertas globais. O agendador climático automático fica desligado somente
no modo explicitamente isolado; a execução operacional é preservada.

GET `/api/v1/demonstracao/estado` é público e não divulga credenciais.
GET `/referencia`, POST `/preparar` e POST `/reproduzir` usam o mesmo prefixo.
POST `/cenario-historico-sp310` permanece como entrada ADMIN de compatibilidade,
agora restrita ao banco dedicado, sem inventar alerta confirmado.
Relatórios do ambiente usam a classificação DEMONSTRACAO_ISOLADA.

Não execute testes destrutivos no banco de apresentação/operacional. Os testes
de integração usam banco exclusivo da suíte e rollback; confira também a sonda
de leitura e o roteiro visual. Para parar, use Compose stop; não apague volumes.
