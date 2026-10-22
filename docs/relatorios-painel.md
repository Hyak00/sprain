# Relatórios na interface — seção 3.3

Acesse **Relatórios** no menu lateral. ADMIN, OPERATOR e VIEWER autenticados podem gerar os relatórios de sua própria empresa. A exportação administrativa integral da seção 3.2 permanece separada e com suas permissões originais.

| Item | Entrega |
|---|---|
| PDF | Relatório do piloto, consulta carregada e relatório de uma decisão individual. Cabeçalho, paginação A4 e aviso de uso interno; geração local, sem serviço externo. |
| CSV | Históricos de consultas e decisões, com período opcional, e exportação da consulta carregada por seu identificador exato. Autoria disponível, data, fonte, recomendação, confiança, distâncias, tempos, custos, impacto potencial, tarifas pendentes, premissas e limitações. |
| Modelo do piloto | Economia comprovada, custo observado, custo estimado da rota original, impacto potencial, amostra, cobertura, critérios, fontes e limitações. |
| Decisão individual | Registro, motivo, usuário/papel quando disponíveis e fotografia histórica vinculada. PDF, JSON e HTML autônomo para compartilhamento interno. |

## Interpretação financeira

- **Economia comprovada:** indisponível no cadastro atual. O sistema não registra uma medição auditada da execução nem um contrafactual validado. Aprovação de desvio não é comprovação de economia.
- **Custo observado comprovado:** indisponível. Os resultados de viagem agora aceitam custos informados, mas não verificam comprovantes de despesas; por isso o indicador anterior continua `null`.
- **Custo informado:** soma parcial dos custos declarados no último resultado de cada operação, com cobertura explícita e natureza `AUTODECLARADO_NAO_VERIFICADO`. Integrado ao JSON, à tela e ao PDF do piloto, sem virar custo comprovado.
- **Custo estimado:** soma dos valores finitos, não negativos e disponíveis em `operacoes.custo_estimado`, correspondentes às parcelas conhecidas da rota original na emissão. São mostrados os números de operações com e sem valor. Não se apresenta cobertura completa de pedágios/combustível por haver um valor cadastrado.
- **Impacto potencial:** soma de `prejuizo_potencial_evitado` somente da recomendação mais recente de cada operação selecionada, evitando duplicar recálculos. Também mostra cobertura. Não significa prejuízo realmente evitado.

Ausência é representada por `null` no JSON e célula vazia no CSV. Um zero registrado continua sendo zero; ausência de qualquer amostra não vira zero financeiro. Resultados informados são separados de planejamento e de economia comprovada. O fluxo de registro está em [resultados de viagem do piloto](resultados-viagem-piloto.md).

## Período, fotografia e fontes

As duas datas opcionais são inclusivas em **America/Sao_Paulo**, com limite de 366 dias. Sem ambas, usa-se todo o cadastro disponível. O piloto seleciona operações pela criação; consultas e decisões são contadas/exportadas pelo horário do registro. Para cada operação do piloto, considera-se a última recomendação na emissão. Não se anuncia que o período do piloto é uma reconstrução de todos os estados históricos desse intervalo.

Cada leitura agregada ou CSV usa transação de leitura com isolamento repeatable read. O relatório individual faz uma leitura da decisão e sua consulta vinculada. Os arquivos indicam empresa, emissão e ambiente de produção ou não produção. Os relatórios financeiros não recalculam rotas nem atualizam operações, custos ou decisões.

O relatório individual prefere `decisoes_gestor_operacao.snapshot`. Se ausente, aceita somente a fotografia da consulta expressamente vinculada por ID, empresa e operação. Se nenhuma existir, informa que as condições e valores da época são desconhecidos; não usa a consulta atual como substituta. O PDF da consulta atual identifica que sua lista histórica de decisões não atribui os custos atuais a decisões antigas.

Registros antigos sem autoria continuam assim identificados. Datas antigas sem fuso são mostradas literalmente, com a indicação de fuso não registrado; não se inventa um offset. Os filtros SQL seguem a interpretação dos timestamps legados pela sessão do banco, conforme o armazenamento existente. As datas de decisões/consultas são `timestamptz`.

## Formatos e limites

- CSV: UTF-8 com BOM, separador `;`, CRLF, aspas e campos multilinha. Textos que podem virar fórmulas em planilhas recebem proteção; valores numéricos negativos mantêm o sinal. Até 10 mil registros ou 8 MB por arquivo. Exceder o limite retorna 413, sem arquivo parcial; refinar o período ou usar a exportação por operação.
- JSON/HTML: preservam o texto UTF-8 integral. O HTML tem estilos próprios e política de conteúdo que bloqueia scripts, recursos e conexões externas; conteúdo do cliente é escapado como texto. Não contém chave de API ou sessão.
- PDF: até 300 mil caracteres na geração local; acima disso há mensagem, sem corte silencioso. A fonte padrão cobre o português; acentos decompostos são normalizados. Caracteres fora da fonte latina são representados explicitamente por seu código Unicode `[U+...]`, com nota no arquivo e referência ao original UTF-8. Não são silenciosamente substituídos por `?`. Cabeçalho e paginação são preservados em todas as páginas.
- Pontos de infraestrutura: o resumo herdado lista até 100 por rota com aviso explícito; o JSON da fotografia mantém os pontos integrais.

O fechamento da central/troca de sessão descarta respostas antigas e impede download dos dados da empresa anterior. Filtros inválidos não são aplicados silenciosamente. Falha do piloto não impede abrir decisões disponíveis; falhas de fotografia substituem o estado de carregamento por uma mensagem de recuperação.

## Endpoints novos, somente de leitura

```text
GET /api/v1/painel/relatorios/piloto
GET /api/v1/painel/relatorios/decisoes
GET /api/v1/painel/relatorios/decisoes/{identificador}
GET /api/v1/painel/relatorios/consultas.csv
GET /api/v1/painel/relatorios/decisoes.csv
```

Os filtros são `inicio`, `fim` e, nos históricos, `id_operacao`. O CSV de consultas também admite `id_consulta`. A lista individual tem páginas de 20 e `proximo_offset`. Respostas incluem `Cache-Control: no-store`.

O carregamento de uma consulta atual continua usando `POST /api/v1/painel/consultas`, que persiste a fotografia conforme o contrato existente da seção 3.1. Baixar um relatório individual ou agregado não registra uma nova decisão. Não há migração nem dependência nova de produção nesta seção.

## Evidências de validação

- API: suíte completa com 211 testes aprovados. Os casos novos verificam deduplicação, zero/ausência, fronteiras de data em Brasília, isolamento entre empresas, fotografias históricas/fallback vinculado, CSV com autoria real e proteção contra fórmulas, paginação e recusa de arquivo acima do limite sem entrega parcial.
- Interface: 76 testes JavaScript aprovados. Novos casos cobrem os três formatos, consulta exata, dados históricos, falta de fotografia, datas sem fuso, caracteres Unicode, HTML sem execução, filtros e descarte de exportação após logout.
- Navegador: downloads reais de PDF do piloto, PDF/HTML de uma decisão histórica e ambos os CSVs com VIEWER no banco isolado. Arquivos CSV conferidos com leitor CSV, inclusive contagem de registros. Largura de 320 pixels CSS sem excesso horizontal na central.
- PDFs: os exemplos de homologação foram renderizados com Poppler e todas as páginas revisadas visualmente; cabeçalho, corpo, acentuação, margens e rodapé legíveis.

Execute `npm test` na raiz e a suíte Python somente na API/banco isolados. As sondagens de implantação fazem somente leituras. Exemplos de homologação não representam viagens reais nem economia comprovada.
