# Planos e consumo por empresa

O esquema `db/ci/16_planos_empresa.sql` cria um catálogo de planos e o registro
da assinatura atual de cada empresa. A migração é aditiva e repetível. O
catálogo inicial `db/ci/19_seed_planos_servico.sql` cadastra três planos
ilustrativos e uma assinatura da empresa de demonstração se não existirem.
Reiniciar a API não sobrescreve alterações manuais nesses registros. Valores,
funcionalidades e limites comerciais devem ser aprovados pela equipe e
registrados por um operador autorizado do banco, fora da API pública. O seed
não cria preços nem representa uma oferta comercial aprovada.

## Cadastro manual com prévia e histórico

O comando `scripts/gerenciar_planos.py` lê um arquivo JSON completo, mostra o
estado atual e o proposto e, por padrão, **não grava nada**. Depois de conferir,
repita o comando com `--aplicar`. Cada mudança efetiva registra operador, motivo,
valor anterior e novo valor em `planos_auditoria`, na mesma transação da mudança.
Repetir exatamente a mesma configuração não cria um novo registro.

Exemplo de `plano.json` (valores ilustrativos, não são oferta comercial):

```json
{"codigo":"TESTE_INTERNO","nome":"Teste interno","funcionalidades":["PAINEL"],"limite_usuarios_ativos":3,"limite_corredores_ativos":2,"limite_consultas_mes":10,"limite_chamadas_externas_mes":null}
```

Exemplo de `assinatura.json`:

```json
{"tenant_id":"empresa_exemplo","plano_codigo":"TESTE_INTERNO","status":"ATIVA","inicio_em":"2026-10-01T00:00:00-03:00","fim_em":null}
```

No ambiente que executa a API, use `python /app/scripts/gerenciar_planos.py plano
--arquivo plano.json --ator operador@empresa --motivo "Contrato aprovado"` e depois
o mesmo comando com `--aplicar`. Cadastre o plano antes da assinatura. O arquivo
deve informar todos os campos; `null` significa limite não definido, e o comando
não aceita preços. Não coloque configurações contratuais reais nem dados secretos
no repositório. A migração de auditoria é `db/ci/17_auditoria_planos.sql`.

`GET /api/v1/operacional/plano` exige ADMIN e usa a empresa da credencial.
Mostra plano, status registrado, início/fim, funcionalidades declaradas,
limites configurados e quatro contagens persistidas: usuários ativos, corredores
ativos, consultas e reservas de chamadas externas do mês em `America/Sao_Paulo`. Sem assinatura, informa
`SEM_ASSINATURA_CONFIGURADA` e continua mostrando o uso observado. O endpoint
não aceita uma empresa escolhida pelo cliente para consultar outra conta.

Quando uma empresa tem assinatura com limite numérico, a API recusa com HTTP 429
a criação de um usuário ativo, a ativação de um corredor ou uma nova consulta
que ultrapassaria o respectivo limite. Empresas sem assinatura configurada ou
com limite `null` continuam sem bloqueio por cota. A verificação e a gravação
ocorrem na mesma transação; um bloqueio por empresa/recurso no PostgreSQL
serializa chamadas simultâneas de diferentes réplicas da API. Consultas usam
o mês civil em `America/Sao_Paulo`. Um cadastro inativo não consome cota de
corredores. Operações diretas no banco, fora da API, devem ser coordenadas pelo
operador para respeitar as cotas.

As consultas ao OSRM de demonstração são a chamada externa por empresa
atualmente identificada na API. Antes de sair para o provedor, a API grava
uma reserva no banco e verifica a cota mensal configurada. Falhas de envio ou
resposta também contam como tentativa; acertos de cache não fazem chamada e
não consomem cota. Em produção, o OSRM de demonstração permanece desativado.
O painel informa quantas reservas houve, mesmo sem assinatura. Importações
globais e entregas de webhook não são atribuídas a clientes nessa contagem.

**Limite desta etapa:** o status `SUSPENSA` não revoga acesso; isso será tratado
na etapa final de segurança. O custo de servir continua `null`: não há contrato
de provedor nem tarifa verificável para calcular valor por chamada. `null` não
representa custo zero. A reserva pode ficar com status `RESERVADA` se o processo
parar antes de registrar o resultado; ela continua contando de forma conservadora
na cota até uma reconciliação operacional.

Para concluir o item 2.6 da lista técnica, faltam: definir os planos e valores
com a equipe; medir custos contratados e processamento por empresa; e aplicar suspensão/reativação de forma controlada. Esta última
parte será tratada na etapa final de segurança, com aviso prévio ao usuário.
