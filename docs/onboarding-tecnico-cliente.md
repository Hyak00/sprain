# Onboarding técnico de uma empresa

Responsável técnico deve ter acesso autorizado à infraestrutura. O administrador
do cliente recebe somente sua empresa. Dados de demonstração não ativam cliente
real; medidas de frota e condições de viagem devem vir do cliente.

## 1. Escopo e identificação

Definir nome da empresa, identificador `tenant_id` exclusivo, administrador,
corredores e finalidade do piloto. Conferir cobertura da malha, fontes, datas,
pedágios e restrições conhecidas antes de prometer operação. Não reaproveitar
`demo_corp` ou `log_express`. O modelo atual usa o identificador da empresa nos
usuários e registros; não existe tela/API autônoma de cadastro de pessoa jurídica.

## 2. Primeiro administrador

No contêiner da API do ambiente correto, executar interativamente:

```sh
docker compose exec api python /app/scripts/cadastrar_acesso_painel.py --email admin@cliente.example --empresa "Cliente exemplo" --tenant cliente_exemplo --papel ADMIN
```

Substituir todos os exemplos. O script pede senha sem eco; não passar senha por
argumento, chat, issue ou arquivo versionado. Conferir o banco antes de executar.
O ADMIN entra com seu e-mail e cria os demais usuários em **Central de trabalho →
Administração da empresa**, escolhendo VIEWER ou OPERATOR conforme necessidade.
Não usar chave compartilhada para gestão de identidade. Testar desativação e
mudança de papel com uma conta de ensaio da própria empresa; preservar o último
administrador ativo.

## 3. Premissas financeiras e frota

Em **Premissas financeiras**, salvar padrões da empresa com versão atual. Custo
total por km tem prioridade e já inclui combustível; não somar duas vezes.
Campos vazios seguem a precedência descrita na interface e no
[guia de custos](integracao-dados-viagem.md). Defaults novos não reescrevem
silenciosamente fotografias históricas nem todas as viagens existentes.

Cadastrar caminhões com altura/largura/comprimento em metros, peso total
carregado em toneladas e eixos. Consumo em km/L deve corresponder ao uso com
carga; referência de modelo é estimativa. Não tratar limite desconhecido de
ponte como autorização de passagem. Conferir cadastro e sinalização.

## 4. Corredores, recorrências e primeira viagem

Em **Corredores e recorrências**, informar coordenadas válidas, nomes e medidas
de referência quando conhecidas. Salvar, recarregar e conferir persistência.
Cadastrar recorrência com dias, horário de São Paulo, janela e caminhão.
**Preparar despacho** cria explicitamente uma viagem na data escolhida; não há
robô que despacha sozinho. Repetir a mesma chave/data deve reutilizar a viagem.

Também é possível importar operações pela central com prévia. Importação em
lote é parcial: guardar o resultado por item e consultar o cadastro antes de
reenviar falhas de resposta. Não anexar arquivos privados do cliente a issues.

## 5. Aceite do primeiro resultado

- Login/logout e papéis testados, incluindo outra empresa sem acesso aos dados.
- Operação aparece na tabela e no mapa, com origem/destino e malha compatíveis.
- Comparação mostra distância, tempo, restrições, fontes/datas, parcelas de custo
  e limitações. Conferir pedágio e combustível sem duplicação.
- Premissas editadas recalculam a operação; selo antigo retorna conflito, sem
  sobrescrever edição concorrente.
- Decisão registrada com motivo e consulta vinculada, visível no histórico e
  no relatório individual. PDF/CSV abrem e identificam limitações.
- Ocorrência relatada aparece como pendente, sem virar confirmação automática.
- Exportação privada da empresa e recuperação assistida testadas por ADMIN.

Recuperação não envia e-mail automaticamente: ADMIN confere identidade e libera
código de uso único, entregue em canal privado. Expiração/cancelamento e nova
senha revogam acessos conforme o contrato. Ver [administração](administracao-interface.md).

Guardar aceite, responsável, data e fontes validadas. Economia comprovada e custo
observado exigem evidências de execução; cálculo de planejamento não basta.
Na interface, Configurar primeiro cliente reúne as etapas. Iniciar configuração
começa a medição persistente; após abrir uma comparação calculada, Confirmar
primeiro resultado útil registra a consulta e o tempo pelo relógio do servidor.
O critério, permissões e limites estão em [experiência do operador](experiencia-operador.md).
Na saída do cliente, desativar usuários e aplicar retenção/exportação acordadas
com infraestrutura; não apagar bases públicas compartilhadas.
