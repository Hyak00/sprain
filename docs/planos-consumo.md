# Planos e consumo por empresa — primeira etapa

O esquema `db/ci/16_planos_empresa.sql` cria um catálogo de planos e o registro
da assinatura atual de cada empresa. A migração é aditiva e repetível. Ela não
cria planos, assinaturas, preços ou limites por conta própria e não altera
contas existentes. A configuração comercial deve ser definida pela equipe e
registrada por um operador autorizado do banco, fora da API pública.

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
limites configurados e três contagens persistidas: usuários ativos, corredores
ativos e consultas do mês em `America/Sao_Paulo`. Sem assinatura, informa
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

**Limite desta etapa:** o status `SUSPENSA` não revoga acesso; isso será tratado
na etapa final de segurança. Chamadas a provedores externos e custo de servir
retornam `null`, pois não há medição confiável de custo contratado. `null` não
representa custo zero. O limite de chamadas externas ainda não é aplicado.

Para concluir o item 2.6 da lista técnica, faltam: definir os planos e valores
com a equipe; medir chamadas externas por empresa sem
inventar preço; e aplicar suspensão/reativação de forma controlada. Esta última
parte será tratada na etapa final de segurança, com aviso prévio ao usuário.
