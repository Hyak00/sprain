# Fluxo 3.1 na versão atual

Base revisada: main `e450ec5`. Esta revisão preserva as atualizações de gestão de usuários, auditoria por empresa, webhooks seguros, backup e inicialização/readiness. A matriz completa dos 18 requisitos permanece em [homologacao-fluxo-painel.md](homologacao-fluxo-painel.md); este documento registra a nova validação e as correções adicionais.

## Correções verificadas

1. **Histórico:** a resposta de uma fotografia aberta anteriormente não substitui a seleção mais recente. Falha substitui o carregamento por mensagem recuperável. Fotografias e decisões persistidas continuam preservadas.
2. **Relato salvo e mapa indisponível:** a interface confirma a gravação e impede reenviar o mesmo formulário. Há uma ação separada para tentar atualizar somente o mapa.
3. **Resposta incerta no envio:** o formulário conserva sua chave de idempotência ao repetir os mesmos dados. O servidor retorna o relato já gravado, em vez de duplicá-lo. A chave é isolada por empresa; a mesma chave em outra empresa não consulta nem sobrescreve o relato anterior. Reutilização com conteúdo diferente retorna conflito. Clientes anteriores que não enviam a chave continuam funcionando.
4. **Validade no mapa:** as geometrias carregam a expiração da ocorrência. O navegador agenda sua retirada, atualiza a validade ao retomar foco/visibilidade e remove o popup correspondente. A limpeza também acontece ao reutilizar o cache. Não existe sondagem adicional periódica ao servidor. Relatos sem prazo informado não recebem validade fictícia.
5. **Atualização explícita:** se uma consulta antiga ainda está em andamento, o comando aguarda e faz uma leitura nova; não apresenta o resultado anterior como atualização posterior à gravação.
6. **Interpretação:** a legenda identifica rota original, alternativa calculada e vulnerabilidade física; não transforma IVI em bloqueio confirmado. A lista é denominada vulnerabilidade da rota original, sem afirmar que todos os trechos foram evitados. A parcela financeira é identificada como perda potencial evitada, sem afirmar economia comprovada.

## Evidências

- API: 197 testes aprovados em banco/API isolados, incluindo os novos módulos de main e os contratos usados pelo painel. O caso de relato verifica reenvio, conflito e isolamento entre empresas; o GeoJSON é conferido contra a data de expiração da ocorrência.
- Interface: 58 testes aprovados, incluindo sete novas regressões: seleção histórica concorrente, falha da fotografia, expiração no cache, expiração por temporizador sem nova chamada, atualização explícita após consulta pendente, mapa indisponível após gravação e repetição após resposta incerta.
- Navegador: login VIEWER, bloqueio de despacho, corredores existentes e alertas com fonte/data/natureza; ocorrência sintética com validade curta retirada do mapa e aviso de expiração exibido. Dados sintéticos ficaram exclusivamente na base isolada de validação.
- Preservação: os 69 IDs e o CSS inline anteriores continuam presentes. Nenhuma dependência nova ou alteração de esquema do banco nesta revisão. Os motores de rotas e custos não foram substituídos.

## Reexecução

Execute `npm test` na raiz e `python -m pytest tests -q` em `/app/api` da instância de testes, depois de `/api/v1/health/readiness` responder 200. A suíte Python faz escritas e não deve rodar no banco operacional. O CI executa ambas as suítes com bootstrap do banco. Para os ambientes locais atualizados, `scripts/verificar_portal.py` faz somente leituras.

O cadastro/agenda, comparação de rotas e custos, premissas, três decisões, relatos, histórico, estados da interface, login/logout/papéis e acessibilidade básica continuam cobertos pelos testes existentes e pela matriz de homologação. Gestão de usuários na interface é o item 3.2; seu backend novo foi preservado.

Informações que a fonte não fornece continuam identificadas como desconhecidas. Não se atribuem retrospectivamente datas de atualização, confirmação de passagem ou economia real a uma simulação.
