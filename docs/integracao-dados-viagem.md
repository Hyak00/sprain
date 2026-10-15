# Complemento de dados e custos da viagem

A base desta entrega e `ffaa51d` (main, depois do merge dos PRs #2 e #3). A torre, as abas, o despacho, a simulacao de chuva, os filtros, a auditoria e o CSV foram mantidos. A integracao acrescenta um arquivo de interface e pequenas chamadas ao painel existente. Nao ha nova dependencia de producao.

## Uso

1. O cliente informa as cinco medidas reais: altura, largura, comprimento, peso TOTAL com carga e eixos. O sistema nao inventa medidas de cadastro a partir do nome/modelo do veiculo.
2. Custos sao opcionais. Sem custo variavel por km informado, o sistema usa a media amostral recente do diesel S10 pesquisado pela ANP em SP e um consumo estatistico de referencia. Consumo real pode ser informado para substituir a referencia.
3. No corredor existente, informe medidas, escolha categoria com os mesmos eixos e clique em **Avaliar corredor para este caminhao**. No despacho, use os campos existentes. A simulacao, D-1, central de frota e auditoria usam o mesmo calculo de viagem.
4. Na auditoria ou no resultado do corredor, abra **Postos, historico e atualizacao dos dados**. O mapa mostra acidentes historicos e postos com localizacao conferida. A opcao de incluir coordenadas aproximadas ANP e desmarcada por padrao; esses pontos sao explicitamente identificados e nao servem para confirmar acesso.
5. O painel ADMIN anterior continua permitindo revisar tarifas, limites, fontes e validade. Um grupo de cobranca identifica cabines da mesma praca para evitar soma duplicada. Nao agrupe pracas distintas.

## Como o custo automatico funciona

`custo conhecido = km * custo variavel/km + horas * (motorista/h + veiculo/h) + pedagios conhecidos + atraso contratual`

`custo variavel/km automatico = diesel por litro / consumo km/L + outros custos variaveis/km informados`

O custo medio conhecido por km divide o custo da viagem pela distancia, incluindo as parcelas de tempo e pedagios conhecidos. O custo variavel/km exibido separadamente nao inclui essas parcelas. Tarifa pendente nao e tratada como custo confirmado zero: permanece sinalizada e impede chamar a comparacao de completa.

- Referencia de consumo: [Inventario Nacional de Emissoes Rodoviarias 2025, tabela 5.3.3.a, pagina 60 do PDF](https://www.gov.br/transportes/pt-br/assuntos/sustentabilidade/mudanca-do-clima/0_ineavar_2025.pdf). Valores estatisticos de 2000-2011: 5,56 km/L (leves) e 3,45 km/L (semipesados/pesados). **Adaptacao do MVP**, nao classificacao oficial: tres ou mais eixos ou peso carregado acima de 16 t usa 3,45; demais usam 5,56. Sem medidas, a referencia conservadora e 3,45. Nao se infere ano do motor, PBT homologado, consumo individual, efeito exato da carga, relevo ou aerodinamica. Preferir consumo medido quando disponivel.
- Preco automatico: media dos ultimos precos por CNPJ pesquisados em SP nos sete dias que terminam na coleta mais recente. O retorno contem fonte, data, quantidade de postos e premissas. Nao e o preco garantido de um posto da rota.
- Precos com coleta acima de 14 dias ou futura nao substituem a premissa anterior de custo variavel/km (padrao legado R$ 4,50), e o retorno avisa o motivo. Ausencia de preco tambem usa essa premissa; nao inventa tarifa atual.
- Os valores horarios padrao ja existentes (R$ 35 motorista + R$ 50 veiculo/h) sao premissas do MVP, nao pesquisa de custo da transportadora. No modo automatico, os demais custos operacionais sao representados pela parcela horaria do veiculo; nao se acrescenta novamente o antigo R$ 4,50/km ao diesel. A empresa deve calibrar esses valores para a sua operacao.
- Custo variavel/km informado pelo cliente tem prioridade, incluindo combustivel; nao se soma diesel novamente. Se o cliente escolher calcular combustivel separadamente, informe consumo e/ou preco e outros custos sem combustivel. Valores ausentes sao completados com referencia quando disponivel.
- O despacho guarda uma fotografia das premissas. A recomendacao guarda sua propria fotografia. Ao recalcular, referencias automaticas de preco sao atualizadas; precos manuais nao sao substituidos. A auditoria historica nao e reescrita.
- Economia operacional admite sinal: um desvio pode custar menos. Perda climatica evitada continua sendo potencial; nao ha perda evitada atribuida quando a alternativa ainda tem risco residual no modelo. Historico ARTESP e contagem regional SSP nao se convertem em probabilidade de sinistro, fechamento de rua ou prejuizo financeiro inventado.

## Fontes e atualizacao

O trabalhador de dados roda fora da API, a cada 24 horas por padrao. Cada fonte e isolada, inclusive em timeout de 10 minutos; dados anteriores continuam disponiveis se a atualizacao falhar. O importador remove registros ARTESP identicos antes de gravar, preservando a importacao repetivel.

```powershell
docker compose --profile dados up -d --build dados-publicos
# Para conferir uma rodada sem agendar:
docker compose --profile dados run --rm dados-publicos python -B /app/scripts/worker_dados_publicos.py --once
```

O trabalhador inclui `anp-semanal`, que descobre a planilha mais recente na [pagina oficial das pesquisas semanais](https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas). O leitor restrito usa apenas a biblioteca padrao Python, valida as colunas esperadas e limita tamanho descompactado. Uma mudanca de formato gera falha explicita e preserva a versao anterior. O CSV mensal e mantido como historico complementar.

Para pedágios, `dados/referencia/tarifas-autoban-conferidas.json` registra a tabela comercial por eixo [Autoban 2026](https://rodovias.motiva.com.br/content/dam/conteudo-multicanal/rodovias/concessoes/autoban/rodovias/pdf/tabela_tarifas_autoban_2026.pdf), sua impressao SHA-256 e os pontos OSM associados. Sao oito pracas, 17 referencias de cabines/pistas. A verificacao foi feita em 14/10/2026, com revisao ate 21/10/2026. Tarifa cheia, sem TAG/descontos. O importador so atualiza referencias OSM existentes e inequivocas; preserva cadastros ja revisados por pessoas, valida o hash do documento e rejeita manifesto vencido. Nao renova prazo sozinho:

```powershell
# SPRAIN_API_KEY deve conter uma chave ADMIN da empresa; nao a salve no repositorio.
python scripts/aplicar_tarifas_conferidas.py --arquivo dados/referencia/tarifas-autoban-conferidas.json
# Depois de conferir o resumo, a mesma chamada com --aplicar grava as referencias.
```

Outras concessionarias e limites oficiais de pontes permanecem pendentes quando nao ha fonte conferida. O manifesto nao comprova que a malha tem todas as pracas, pontes ou restricoes. O sistema bloqueia medidas acima dos limites conhecidos, mas nao autoriza automaticamente uma viagem sem inventario completo e validacao operacional.

## Contrato para o colega do frontend

- `POST /api/v1/infraestrutura/rota-caminhao`: conserva campos anteriores; `custos` acrescenta combustivel, litros e custo medio conhecido/km. Custos no pedido sao opcionais.
- `GET /api/v1/infraestrutura/pendencias`: totais da empresa autenticada para cadastros sem medidas, tarifas e limites vigentes; nao e medida de cobertura geografica.
- `POST /api/v1/dados-publicos/consultar-rota`: aceita LineString **ou MultiLineString**, ate 100.000 pontos. Use um segmento por geometria da FeatureCollection existente; nao una segmentos criando retas artificiais. Retorno limitado a 200 acidentes e 200 postos, com indicador `truncado`.
- `incluir_postos_nao_verificados` e opcional e falso por padrao. Retorno informa `localizacao_confirmada`, `preco_recente`, `idade_preco_dias` e `acesso_viario_confirmado=false`. Distancia ao tracado nao e distancia dirigivel nem autoriza acesso por caminhao.
- Consultas complementares sao locais e feitas ao abrir uma viagem; nao ha chamada ANP/ARTESP/SSP por aresta ou por veiculo na simulacao. A referencia de preco e carregada uma unica vez por lote. Falhas complementares sao mostradas sem apagar o restante do painel; respostas antigas sao descartadas quando muda a selecao/sessao.
- `api/static/dados-viagem.js` usa texto DOM em vez de HTML fornecido pelas fontes. `limpar()` aborta consultas anteriores; os modulos anteriores continuam disponiveis.

## Validacao e limites da entrega

### Fechamento do corredor em 14/10/2026

As tarifas de Rio Claro e Itirapina foram conferidas nas imagens da [pagina oficial da Eixo SP](https://eixosp.com.br/tarifas/). Os manifestos `tarifas-eixo-p1-rio-claro.json` e `tarifas-eixo-p2-itirapina.json` guardam a tabela comercial exata de 2 a 9 eixos e o SHA-256 da fonte. Por exemplo, 5 eixos custam R$ 58,30 em Rio Claro e R$ 35,30 em Itirapina. Nao se multiplica a tarifa de passeio nem se arredonda uma tarifa por eixo inventada. Categoria nao publicada continua pendente. `tarifas_por_eixos` e opcional no cadastro/API e tem um campo adicional no painel ADMIN; o modelo linear anterior continua disponivel para fontes que o utilizem.

O inventario versionado `estruturas-corredor-osm.json.gz` identifica 349 vias com pontes, viadutos ou tuneis. A anotacao e aplicada exclusivamente a segmentos ativos da empresa com a mesma referencia OSM; nao associa uma ponte a uma pista proxima por distancia nem confunde trafegar sobre a ponte com passar embaixo dela. A tela apresenta as estruturas pertencentes a rota, sua fonte e os limites ausentes. Nao altera geometria nem cria novas conexoes.

```powershell
python scripts/sincronizar_estruturas_corredor.py --tenant demo_corp --snapshot --aplicar
# Consulta somente as vias OSM ja presentes na malha da empresa:
python scripts/sincronizar_estruturas_corredor.py --tenant demo_corp --aplicar
```

`SPRAIN_INFRA_TENANT=demo_corp` no trabalhador de dados ativa a atualizacao diaria do inventario e de limites numericos publicados para essas vias. Cadastros conferidos manualmente sao preservados. Limites importados podem ficar mais restritivos; um aumento de limite ou desaparecimento de tag nao libera um trecho automaticamente. Interpretacoes desconhecidas/condicionais nao viram numeros. Falhas de rede preservam a base anterior. Anotacoes de mapa podem levar ate o TTL existente de cinco minutos para aparecer em rotas em cache; novos limites excedidos ja participam da chave de bloqueios do recalculo.

Foi consultado tambem o [inventario oficial de OAE do DER-SP](https://dadosabertos.sp.gov.br/dataset/obras-de-arte-especiais-oae). A planilha publicada informa localizacao, comprimento e largura de referencia da obra. **Essas medidas nao sao comprimento maximo do caminhao, largura livre de passagem ou capacidade de carga**, e nao foram convertidas em restricoes. Nao foi localizada, nas fontes consultadas, uma base publica completa dos quatro limites operacionais para todas as estruturas do corredor. A cobertura permanece explicitamente parcial; o inventario nao concede autorizacao de trafego. Completar valores nao publicados depende de informacao do responsavel pela estrutura, nao de deducao a partir do tamanho da ponte.

Suite anterior: 84 testes. Novos testes cobrem consumo/preco automaticos, prioridade do custo informado, preco vencido, economia sem dupla contagem, valores invalidos, geometria longa/descontinua, timeout por fonte, duplicata ARTESP, leitor semanal, configuracao com GITHUB_ACTIONS e cabines duplicadas. Fixtures SQL anteriores validam limites de pontes, chuva, indisponibilidade de alternativa e isolamento entre empresas.

Foi usada a malha regional existente no teste de corredor (261,53 km), sem substituir dados de frota por medidas supostamente reais. A cobertura de pontes continua parcial. Antes de usar como orientacao operacional, confirmar inventario de restricoes, enderecos, tempos, tarifas faltantes e premissas da empresa. O tempo do roteador atual continua uma estimativa com velocidade de referencia de 35 km/h.

## Limites oficiais DER associados à malha

O manifesto `dados/referencia/restricoes-der-conferidas.json` registra a linha completa do relatório público DER/SIGRR e a geometria OSM conferida. Foram associados a passagem sul do pedágio Valinhos (SP-330, km 81, largura 4,40 m, way 721173861) e o trecho sob a SP-330 na ligação norte para a SP-310 (altura 5,20 m, way 877397553). A primeira associação corresponde a dois segmentos e a segunda a um segmento na malha regional atual. A restrição de altura não se aplica ao tabuleiro da Anhanguera ou à pista oposta da SP-310.

Executar com as variáveis de banco já usadas pelos importadores:

```powershell
python scripts/aplicar_restricoes_der.py --tenant demo_corp
python scripts/aplicar_restricoes_der.py --tenant demo_corp --aplicar
```

Sem `--aplicar`, a execução apenas mostra o plano. O importador relê o relatório oficial e exige a mesma seção e linha completa; alterações na publicação impedem a aplicação. Confere também a referência OSM, o sentido da geometria e a cobertura de cada segmento com tolerância de 20 cm. Não busca a via mais próxima. Cadastros já verificados, IDs duplicados, outra empresa, geometrias diferentes e limites mais restritivos são preservados. A gravação é atômica e usa `malha_limites_revisoes` para registrar fonte, evidência, dados anteriores e SHA-256 da resposta consultada. Não há novo esquema, biblioteca ou consulta externa durante o cálculo das rotas.

Os limites alimentam os mesmos campos utilizados pelo mapa, pelas rotas alternativas e pelos custos existentes. Uma nova incompatibilidade altera a chave do cache imediatamente; metadados de uma rota ainda compatível podem permanecer no cache por até cinco minutos. A validade inicial para revisão é de sete dias e não se renova sozinha. Exceder um limite conhecido continua bloqueando o trecho mesmo após o vencimento, como já ocorre no projeto.

O manifesto mantém pendências explícitas: passagem da Mutinga fora do recorte regional atual, pistas da SPA 276/310 ainda sem associação exata na malha, divergência de 5,39/5,45 m na SP-310 km 206,6, divergência DER/OSM na ligação oposta e ausência de pesos admissíveis publicados. Nenhum desses casos autoriza passagem nem é cadastrado em uma via vizinha. A listagem não representa cobertura completa de pontes. O prejuízo por bater em uma estrutura não é inventado: a comparação considera o custo do caminho permitido e mantém as premissas de perdas climáticas existentes.
