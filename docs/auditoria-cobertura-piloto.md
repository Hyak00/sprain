# Auditoria da cobertura de dados do piloto

Esta auditoria consulta o banco em modo somente leitura. Ela ajuda a conferir o
recorte municipal de acidentes da ARTESP, postos e preços da ANP e, quando
informada, uma região policial da SSP-SP. Não valida uma rota nem autoriza
navegação com coordenadas candidatas.

Execute no contêiner API do ambiente **isolado** que contém as cargas oficiais:

```sh
docker compose exec -T api python scripts/auditar_cobertura_piloto.py \
  --municipio Araraquara --uf SP --regiao-roubo 'DEINTER 3'
```

A relação entre Araraquara e DEINTER 3 consta na
[Polícia Civil de SP](https://www.policiacivil.sp.gov.br/portal/ShowProperty?dID=dID%3A+98544&nodeId=%2FdipolContent%2FUCM_071416%2F%2FidcPrimaryFile&revision=latestreleased).
O total de roubo abrange toda essa região policial, não a cidade ou uma via.

## Fotografia local de 21/10/2026

Consulta no banco isolado `sprain-p2-check-20261021`, após importar as fontes
oficiais descritas em [dados de risco e combustíveis](dados-riscos-combustiveis.md):

| Indicador | Resultado |
| --- | ---: |
| Acidentes ARTESP em Araraquara com caminhão envolvido | 205 |
| Desses, classificados como tombamento | 22 |
| Tombamentos na SP-310 / SP-255 / acessos | 18 / 2 / 2 |
| Postos cadastrados na ANP em Araraquara | 74 |
| Postos com coordenada candidata / coordenada verificada | 51 / 0 |
| Postos com alguma coleta de preço de diesel S10 | 24 |
| Postos com coleta de diesel S10 nos últimos 14 dias | 0 |
| Coleta mais recente de diesel S10 no município | 06/10/2026 |
| Roubos de carga no DEINTER 3 no trimestre mais recente (abr–jun/2026) | 7 |

Esses números são uma fotografia do banco local nessa data. O processo de
importação pode atualizá-los. Dados ARTESP cobrem rodovias concedidas; o filtro
indica caminhão envolvido, sem identificar necessariamente o veículo que
tombou. O preço da ANP é histórico; o cadastro não confirma acesso rodoviário.
O número regional da SSP não serve para apontar roubo em um trecho.
O JSON também lista as fontes carregadas e denuncia fontes ausentes para que
um banco vazio não pareça um município sem ocorrências.

## Critério para o piloto com viagens reais

1. Confirmar os primeiros trajetos, incluindo destino e rodovias; a cidade
   sozinha não define a cobertura da rota.
2. Atualizar as fontes no banco do ambiente do piloto e repetir a auditoria.
3. Conferir em campo os postos que serão usados na rota e importar somente
   coordenadas verificadas, com fonte e data.
4. Mostrar a data da coleta dos preços e não tratá-los como preço atual.
5. Validar os endpoints e uma viagem completa no ambiente do piloto antes de
   marcar a cobertura operacional como concluída.
