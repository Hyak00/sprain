# Fontes públicas: evidência de coleta e limites

Verificação em **19/10/2026**. Esta página registra o resultado de uma execução
sem `--aplicar`; nenhum banco foi alterado. Os números descrevem arquivos
baixados e aceitos pelo importador naquela execução, não a quantidade atualmente
armazenada em qualquer instalação do SPRain. As fontes podem corrigir arquivos
ou publicar novos períodos depois desta data.

Comando reproduzível:

```sh
python scripts/sincronizar_dados_publicos.py todas --anos 2024 2025 2026 --anos-ssp 2025 2026
```

As 13 tarefas retornaram `gravado=false` e nenhuma falhou. A data abaixo é a
mais recente **dentro dos registros aceitos**, não o horário da verificação nem
uma promessa de atualização em tempo real.

| Fonte | Registros aceitos | Data de registro mais recente | Cobertura e interpretação |
| --- | ---: | --- | --- |
| ARTESP 2024 | 9.091 acidentes com caminhão envolvido | 31/12/2024 | Rodovias estaduais concedidas de SP; nem todos são tombamentos. |
| ARTESP 2025 | 9.416 acidentes com caminhão envolvido | 31/12/2025 | Mesmo recorte. |
| ARTESP 2026 | 6.748 acidentes com caminhão envolvido | 18/09/2026 | Ano parcial na fonte consultada. |
| ANP diesel, arquivo mensal | 5.897 preços válidos em SP | 30/09/2026 | Pesquisa em postos da amostra; inclui produtos diesel do arquivo. |
| ANP gasolina, arquivo mensal | 14.920 preços válidos em SP | 30/09/2026 | Pesquisa em postos da amostra. |
| ANP, arquivo semanal | 5.563 preços válidos em SP | 09/10/2026 | Todos os combustíveis aceitos; não são 5.563 preços de diesel. |
| ANP, cadastro de revendedores | 8.382 postos em SP | Não definida | 6.992 coordenadas candidatas **não validadas** pela ANP; data de obtenção da coordenada não é data de publicação do cadastro. |
| SSP-SP 2025, quatro trimestres | 13 agregados por trimestre | 31/12/2025 | Um total estadual e 12 regiões policiais por trimestre. |
| SSP-SP 2026, dois trimestres | 13 agregados por trimestre | 30/06/2026 | Último trimestre encontrado foi o segundo; não há pontos por via. |

As contagens ARTESP indicam acidentes **com** caminhão, carreta ou bitrem
envolvido. O endpoint de tombamentos filtra a classe depois da importação;
envolvimento de caminhão não prova que esse veículo tombou. Os totais regionais
de roubo são contagens, sem denominador de viagens e sem localização por rua.
O preço ANP foi observado na data de coleta, não garante o valor cobrado hoje.
Coordenada candidata de posto não comprova acesso para caminhão.

## Origem e condições de uso

- **ARTESP:** [conjunto de acidentes](https://dadosabertos.artesp.sp.gov.br/dataset/acidentes),
  [metadados do recurso 2026](https://dadosabertos.artesp.sp.gov.br/dataset/acidentes/resource/7aee242c-8be1-43ea-a2e7-d9525ec926d9)
  e [termos do portal](https://dadosabertos.artesp.sp.gov.br/terms). O recurso
  identifica licença Creative Commons Attribution. Os termos exigem crédito,
  preservação do significado e ausência de endosso atribuído à ARTESP. A URL
  exata do arquivo e seu hash são guardados na procedência quando importados.
- **ANP preços:** [levantamento e arquivos recentes](https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas),
  [metodologia da pesquisa](https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/precos-revenda-e-de-distribuicao-combustiveis/informacoes-levantamento-de-precos-de-combustiveis)
  e [série histórica aberta](https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/serie-historica-de-precos-de-combustiveis).
  O levantamento é amostral e sua publicação segue a pesquisa da ANP.
- **ANP cadastro:** [apresentação oficial da API de Revendedores](https://www.gov.br/anp/pt-br/centrais-de-conteudo/paineis-dinamicos-da-anp/paineis-dinamicos-do-abastecimento/painel-dinamico-de-relatorio-de-revenda).
  A API retorna postos em operação e coordenadas quando disponíveis. O SPRain
  preserva a condição de coordenada não validada e não a usa como localização
  confirmada na consulta de proximidade da rota.
- **SSP-SP:** [estatísticas trimestrais](https://www.ssp.sp.gov.br/estatistica/dados-trimestrais).
  O importador confere a soma das 12 regiões contra o total do estado e não
  cria ocorrências pontuais a partir desse agregado.

Os conjuntos da ANP e da SSP são publicamente acessíveis, mas **não foi
confirmada nesta verificação uma licença específica de redistribuição dos
arquivos e da API**. A licença indicada no rodapé do portal da ANP se refere ao
conteúdo do site e não deve ser presumida como licença de cada conjunto.
Antes de redistribuir uma cópia integral dos dados em produto comercial,
confirmar os termos aplicáveis com as fontes e registrar a revisão. A
disponibilidade pública, sozinha, não resolve essa questão.

Este ensaio não valida CGE/Open-Meteo, dados privados de clientes, a cobertura
completa das rodovias de SP ou uma instalação de produção. Para a diferença
entre verificação do worker e idade dos registros, veja
[arquitetura e atualização](arquitetura-e-fontes.md) e
[dados de riscos e combustíveis](dados-riscos-combustiveis.md).
