# Planos e consumo por empresa — primeira etapa

O esquema `db/ci/16_planos_empresa.sql` cria um catálogo de planos e o registro
da assinatura atual de cada empresa. A migração é aditiva e repetível. Ela não
cria planos, assinaturas, preços ou limites por conta própria e não altera
contas existentes. A configuração comercial deve ser definida pela equipe e
registrada por um operador autorizado do banco, fora da API pública.

`GET /api/v1/operacional/plano` exige ADMIN e usa a empresa da credencial.
Mostra plano, status registrado, início/fim, funcionalidades declaradas,
limites configurados e três contagens persistidas: usuários ativos, corredores
ativos e consultas do mês em `America/Sao_Paulo`. Sem assinatura, informa
`SEM_ASSINATURA_CONFIGURADA` e continua mostrando o uso observado. O endpoint
não aceita uma empresa escolhida pelo cliente para consultar outra conta.

**Limite desta etapa:** os campos do plano são informativos. Ainda não bloqueiam
cadastros ou consultas. O status `SUSPENSA` também não revoga acesso nesta
etapa. Chamadas a provedores externos e custo de servir retornam `null`, pois
não há medição confiável de custo contratado. `null` não representa custo zero.

Para concluir o item 2.6 da lista técnica, faltam: definir os planos e valores
com a equipe; configurar mudanças manuais com trilha de auditoria; impor cotas
de modo atômico em múltiplas réplicas; medir chamadas externas por empresa sem
inventar preço; e aplicar suspensão/reativação de forma controlada. Esta última
parte será tratada na etapa final de segurança, com aviso prévio ao usuário.
