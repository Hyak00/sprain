# Caminhoes, pedagios e restricoes na torre existente

Base: `ad6add8` (atualizacao do Git em 12/10/2026). Esta entrega conserva
login, abas Rotas & Operacoes / Minha Frota / Corredor, despacho por endereco,
autocomplete, filtros, tabela, comparativo no mapa, CSV, auditoria e decisoes.
O CSS original e os IDs da interface foram preservados. Os complementos usam
MapLibre existente; nao acrescentam frameworks nem dependencias de producao.

## Usar

1. Entre pela tela de login existente.
2. Em Minha Frota, abra **Medidas e custos do caminhao**, informe as cinco medidas
   reais e, opcionalmente, custos por km/hora, atraso contratual e perda potencial.
   Para atualizar um caminhao, use **Medidas e custos** no seu card e o botao
   original de salvar. Campos vazios preservam o cadastro existente.
3. Despache pelo fluxo de endereco existente. O despacho herda dados da frota;
   o complemento **Medidas e custos desta viagem** aceita valores especificos
   da carga/viagem. Uma copia fica na operacao para manter suas premissas.
4. Clique em Simular. Pedagios conhecidos entram nos custos e uma restricao
   fisica conhecida pode exigir desvio mesmo sem chuva. Limites ausentes nao
   equivalem a passagem autorizada. Quando nenhuma alternativa existe, a
   recomendacao informa isso e nao atribui economia de uma rota inexistente.
5. Abra uma operacao: original, alternativa, trechos criticos e decisoes continuam
   no inspector. **Pedagios, caminhao e restricoes** acrescenta fontes, medidas,
   tarifas pendentes, diferenca de pedagios e economia liquida potencial.
6. No corredor, a demonstracao fixa anterior continua disponivel. Selecione um
   caminhao, confira categoria/eixos e medidas e avalie o caminho sobre a malha
   regional importada. Os pontos do corredor sao referencias rodoviarias; para
   enderecos reais, use o despacho.
7. ADMIN pode manter dados no complemento **Administrar pedagios e pontes** da
   frota. Escolha o local no mapa, confira a pista no seletor de proximidade,
   informe fonte/data/validade e salve. Referencia OSM exige fonte consultada
   antes de virar cadastro confirmado. Desativar preserva o historico.

## Calculo

O custo conhecido de um caminho soma km x custo por km, tempo x custos horarios,
pedagios confirmados para o numero de eixos e custo contratual de atraso quando
a duracao excede a janela inicio/fim cadastrada. Datas do despacho sao normalizadas
em UTC. Custo por km e uma premissa variavel independente dos custos horarios;
nao preencha novamente despesas ja incluidas em outra premissa.

`custo_desvio_brl = custo_alternativa_conhecido - custo_original_conhecido`.
Pode ser negativo: o caminho alternativo pode custar menos. A perda potencial
por alagamento so e atribuida quando a rota original apresenta risco climatico
e a alternativa nao conserva trechos em risco no mesmo modelo. Com risco residual,
a parcela evitada adotada e zero, em vez de supor que todo o prejuizo foi eliminado.
`economia_liquida_potencial = perda_potencial_informada - custo_desvio`.
Isso nao mede economia realizada ou probabilidade de sinistro calibrada.

Premissas da viagem prevalecem sobre a simulacao geral; o despacho herda as da
frota e mescla substituicoes parciais. A API de decisao economica mantem seu modelo
heuristico anterior, agora com dimensoes, custos da frota e pedagios conhecidos.
Ela identifica explicitamente que o modelo de risco ainda e heuristico.

Simulacao, D-1, central de frota, despacho, importacao em lote e decisao economica
usam o mesmo motor com restricoes. O D-1 mantem seu criterio de exposicao existente,
mas calcula o caminho em vez de presumir desvio de 35%. O recalculo nao atualiza
automaticamente o planejamento nem aprova uma viagem. A decisao humana permanece;
uma rota fisicamente incompativel ou alternativa que mudou exige novo calculo.

## Dados e limites

O snapshot em dados/referencia contem 15.941 segmentos OSM e 29 referencias de
pedagio, sem tarifas ficticias. Registros podem representar pistas diferentes ou
precisar de revisao. Nao e inventario oficial de 29 pracas. A associacao a um trecho
e aproximada e exige conferencia, especialmente em vias paralelas.

Altura, largura, comprimento e peso total sao comparados com limites cadastrados.
Peso em toneladas inclui a carga. Peso por eixo, autorizacoes especiais,
restricoes condicionais de horario e sinalizacao local ainda precisam de
validacao operacional e nao sao deduzidos do peso total. Ponte sem medidas do
caminhao e trecho com limite conhecido excedido nao entram como passagem liberada.
Fontes/tarifas vencidas ficam pendentes; limite conhecido excedido continua
conservador. Tarifas por eixo nao modelam todos os descontos/categorias/sentidos.

Sem dados oficiais completos, a comparacao monetaria permanece parcial, mesmo
quando todos os pedagios cadastrados no caminho possuem tarifa. Cadastro precisa
ser mantido por responsavel; nao existe atualizacao automatica de fontes oficiais.
Ausencia de caminho na cobertura nao produz rota artificial em outra regiao.

## Codigo e contrato para continuar

- `api/static/b2b.html`: somente chamadas de integracao nos fluxos existentes.
- `api/static/infraestrutura-caminhoes.js` e `.css`: campos, marcadores e detalhes
  isolados; sem regras globais de layout.
- `api/static/infraestrutura-cadastro.js`: manutencao ADMIN isolada.
- `api/app/services/viagem_caminhao.py`: contexto de lote, comparacao e snapshot.
- `api/app/services/routing_engine.py`: limites e sentidos antes do roteamento;
  cache inclui medidas/bloqueios e reavalia tarifas. Chuva conserva os pesos do Git.
- `api/app/routers/infraestrutura.py`: cadastro/historico/importacao/avaliacao.
- `api/app/routers/malha.py`: importacao de geometria real, validacao previa,
  deduplicacao, substituicao/desativacao sem apagar a base urbana.
- `db/ci/03_infraestrutura_viaria.sql`: migracao aditiva, idempotente, sem apagar dados.

Campos opcionais `dimensoes` e `custos_operacionais` foram acrescentados aos
cadastros existentes. Contratos anteriores continuam aceitos. A simulacao mantem
`resumo_operacional`/`recomendacoes` e acrescenta `infraestrutura`, custos com sinal,
economia potencial e indicador de alternativa disponivel. A explicacao mantem
campos/geometrias anteriores e acrescenta `infraestrutura`. A recomendacao salva
as premissas do calculo; editar tarifas depois requer nova simulacao.

Consulta/calculo: ADMIN/OPERATOR/VIEWER. Despacho/frota: ADMIN/OPERATOR.
Pontos/malha: ADMIN. Cadastros, custos e malhas privadas sao isolados por empresa.

O contexto le cadastro/limites uma vez por lote. Nao busca sites externos durante
o calculo. O snapshot de recomendacao nao duplica sua geometria principal.

## Executar demonstracao e verificar

Com Docker Desktop e Python:

```sh
python scripts/iniciar_demo_caminhoes.py
```

O inicializador cria schema somente em banco vazio, aplica migracoes adicionais
e carrega a demonstracao via API em ambiente de desenvolvimento. Preserva bases
existentes e nao reativa referencias desativadas. O bootstrap recusa producao.
Site: http://localhost:8000/static/b2b.html. Contrato: http://localhost:8000/docs.

Testes de integracao usam banco PostgreSQL/PostGIS. A fixture sintetica de ponte,
tarifa e caminhao e revertida no final. A suite anterior tambem foi executada,
incluindo login, autocomplete, CSV, decisoes, isolamento e simulacao.
