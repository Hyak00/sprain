# Fluxo do MVP no painel (3.1)

Base: main `8c2c188`, 16/10/2026. Esta entrega complementa o painel existente. Não substitui o motor de roteamento, o cálculo de custos, a simulação de chuva, a frota, o corredor de referência, a manutenção de pontes/pedágios ou as exportações.

## Uso

1. Entre, confira empresa e papel. OPERATOR e ADMIN podem gravar; VIEWER pode consultar e registrar a fotografia da própria consulta, sem alterar o planejamento. Login permanece o demonstrativo existente; não há identidade individual ou recuperação de senha de produção nesta entrega.
2. Abra uma operação. A API salva a fotografia integral da explicação, incluindo geometria, fontes disponíveis, premissas, cenário e instante do cálculo. O instante de consulta é separado do instante do cálculo. Ausência de recomendação não recebe confiança fictícia ou rota alternativa inventada.
3. Expanda **Editar premissas e recalcular esta operação**. Valores em branco removem a sobrescrita da viagem e usam as referências/frota aplicáveis. O custo total/km tem prioridade; combustível não é somado duas vezes. Informe explicitamente a chuva simulada, inclusive zero. A API usa os motores existentes, registra um cenário SIMULAÇÃO e atualiza a comparação, tabela e totais. Edição é permitida somente em operações PLANNED. Não se trata de chuva observada.
4. Confira **Comparação detalhada de custos**, **Pedágios, caminhão e restrições** e as fontes. Valores estimados com parcelas conhecidas não são custo integral garantido; tarifa pendente pode alterar a comparação. Perda potencial evitada não comprova economia real. Sem geometria alternativa, o painel informa que a comparação está indisponível.
5. Registre desviar, manter ou aguardar e o motivo. A decisão fica vinculada à consulta persistida. Alterações de premissas, frota ou recomendação invalidam a consulta para nova decisão; atualize antes de registrar. Decisões antigas permanecem disponíveis, inclusive as anteriores a esse vínculo.
6. Em **Histórico de consultas**, abra as fotografias antigas somente para leitura ou consulte a situação atual. A fotografia integral pode ser copiada do JSON exibido; os relatórios atuais usam a consulta persistida. Credencial compartilhada identifica empresa/papel, não pessoa física.
7. Em **Corredores e recorrências**, cadastre origem/destino por coordenadas ou use a operação selecionada. Informe medidas de referência opcionais. A API valida conectividade e restrições conhecidas. Cadastre dias da semana, partida no fuso de São Paulo, janela, veículo e premissas. É possível editar e inativar corredores/agendas com controle de versão.
8. Abra **Preparar despacho**, escolha uma data compatível e crie a viagem. A malha é reavaliada com o caminhão informado pelo fluxo original de criação. Repetir o envio não duplica uma viagem da mesma agenda/data. A agenda é persistida, mas o despacho é explícito: não foi acrescentado um agendador em segundo plano.
9. Abra os alertas para conferir o que foi detectado, trecho/local disponível, fonte, horários, validade, confiança, consequência possível e incógnitas. Histórico, previsão, simulação, trânsito observado, ocorrência confirmada e relato não validado têm identificação por texto e cor. Consequência genérica é marcada como possibilidade, não impacto confirmado naquela viagem.
10. Use o feedback do alerta para reportar falso alerta. Para evento ausente, use **Reportar ocorrência não detectada**: descrição, categoria, coordenadas e horário observado. O relato fica privado na empresa e aparece como PENDENTE_VALIDACAO. Não cria alerta público ou interdição automática.

## Fontes e atualização

Ocorrências públicas continuam vindo do serviço de alertas existente. A interface complementar associa seus IDs de trechos às geometrias disponíveis da malha autorizada. Relatos têm a coordenada informada pelo usuário. Nunca se cria ponto aproximado como se fosse localização confirmada. Registros sem geometria permanecem legíveis no detalhe, com a limitação declarada.

O endpoint retorna até 50 ocorrências públicas e 50 relatos recentes, com o recorte declarado. A camada usa cache de até dez segundos entre leituras; atualização explícita consulta o servidor. Falha limpa a camada anterior e informa indisponibilidade, sem concluir que não existe risco. Ao sair, dados e requisições pendentes são descartados. Data/fonte ausente é apresentada como não informada, não substituída pela hora atual. Dados financeiros e físicos continuam sujeitos à cobertura e validade de suas fontes originais.

Trechos vermelhos/lista de trechos críticos representam vulnerabilidade física IVI. A classificação da malha não desaparece com chuva zero. A recomendação inclui o cenário meteorológico e as restrições do caminhão. O IVI não é uma confirmação de ocorrência ou uma probabilidade calibrada.

## Integração e persistência

`db/ci/10_fluxo_painel.sql` cria tabelas complementares de corredores, recorrências, despachos, consultas e relatos e acrescenta campos opcionais à tabela de decisões. É aditiva e repetível; não apaga dados. No início da API, `garantir_schema` aplica essa migração também a volumes existentes. Instalações com a atualização hidráulica precisam aplicar previamente `09_bacias_hidrograficas.sql`, conforme o bootstrap existente.

| API complementar | Papéis | Resultado |
|---|---|---|
| GET/POST /api/v1/painel/corredores; PUT /corredores/{id} | Todos leem; ADMIN/OPERATOR gravam | Cadastro da empresa, geometria e versão; listagem paginada |
| POST /corredores/{id}/recorrencias; PUT /recorrencias/{id} | ADMIN/OPERATOR | Agenda validada/versionada; inativação preserva histórico |
| POST /recorrencias/{id}/despachar | ADMIN/OPERATOR | Criação pelo serviço original, idempotência por envio e agenda/data |
| POST /consultas; GET /consultas e /consultas/{id} | Todos | Fotografia do servidor, isolamento por empresa, paginação |
| PUT /operacoes/{id}/premissas | ADMIN/OPERATOR | Controle de conflito, recálculo transacional com chuva explícita |
| POST /relatos | ADMIN/OPERATOR | Relato privado pendente, sem alterar bloqueios globais |
| GET /eventos | Todos | Natureza, metadados e GeoJSON autorizado |

As decisões continuam em POST `/api/v1/logistica/operacoes/{id}/decisao`, com `consulta_id` opcional para clientes antigos e enviado pelo painel novo. O histórico existente ganha o vínculo quando disponível. A listagem de alertas ativos consulta somente a recomendação mais recente de cada operação, evitando ressuscitar alertas antigos após recálculo. A busca de trechos próximos no cadastro administrativo usa `/api/v1/infraestrutura/malha/trechos-proximos`.

## Verificação

- `npm test`: 45 testes de sessão, DOM, custos, formulários, cache, cancelamento, importação e relatórios. `linkedom` é dependência somente de desenvolvimento, não pacote carregado pelo usuário.
- `python -m pytest tests -q`: 173 testes aprovados no ambiente isolado. Executar somente em API/banco de testes. Inclui isolamento por empresa e papel, migração repetível, versão de edição, despacho sem duplicação, custo recalculado, consulta obsoleta, decisão vinculada, fotografia preservada, relato privado, ausência de dados e contratos do OpenAPI usados pelo painel.
- Conferência manual no navegador: login/logout, operador/leitor/admin de outra empresa, simulação, edição de custos e chuva zero, corredor, recorrência, despacho, histórico e relato exibido no mapa. Breakpoint móvel de 390 pixels CSS conferido; diálogos mantêm foco e campos nativos têm rótulos. Isso não é certificação integral WCAG ou homologação de campo.
- Preservação: os 69 IDs e o CSS inline anteriores permanecem; estilos e módulos adicionais se adaptam ao painel. Nenhum serviço externo ou dependência de produção nova.

## Limites concretos

O item 3.1 não resolve gestão/recuperação de usuários de produção (3.2), confirmação humana de uma ponte ou tarifa ausente, histórico primário que a fonte não fornece ou prova de economia em viagens reais. Essas ausências são visíveis. A agenda não é um despachante automático e relatos ainda exigem validação operacional. O código e testes locais não substituem revisão do PR e homologação da equipe.
