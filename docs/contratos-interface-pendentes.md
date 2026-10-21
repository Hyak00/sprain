# Integrações e limites da interface

Atualização de 17/10/2026: administração, recuperação assistida, exportação privada,
monitor interno e onboarding persistente estão integrados. Veja
[experiência do operador](experiencia-operador.md) e os guias específicos.
A tabela distingue funcionalidades entregues de limites ainda dependentes de
dados e homologação. A interface não usa memória local como substituto do banco.

| Recurso | Operações e dados mínimos | Condições de aceite |
|---|---|---|
| Recuperação e extensão de acesso | Recuperação assistida implementada em administração; não há envio automático de e-mail | Identidade conferida por ADMIN, código de uso único, resposta pública genérica |
| Usuários no painel | Gestão e auditoria integradas à tela de administração | ADMIN individual da própria empresa; não permitir ação com chave compartilhada; consultar [gestão de usuários](gestao-usuarios.md) |
| Resultado financeiro observado | Registro/correção da execução autodeclarada e histórico integrados à aba Decisão; custo informado e cobertura incluídos nos relatórios. Auditoria de despesas e contrafactual ainda dependem de evidência | Distinguir observado, estimado, potencial e economia comprovada; não inferir comprovação da perda potencial |
| Espera | Exercício financeiro integrado ao motor existente, com tempo, chuva e premissas visíveis | Não substitui a fotografia da decisão nem reavalia risco futuro após espera |
| Qualidade completa | Monitor interno integrado; histórico começa na instrumentação | Cobertura e qualidade precisam de evidência; não reconstrói falhas antigas |
| Exportação integral | ZIP privado com manifesto/limites e dados autorizados da empresa, incluindo onboarding | Sem dados de outra empresa ou credenciais; não é parecer de conformidade legal |
| Onboarding | Início e primeira comparação confirmada pelo usuário persistidos por empresa | Relógio do servidor, consulta vinculada posterior ao início; não comprova ativação produtiva ou economia |
| Histórico da demonstração | Fonte primária, data, geometria/trechos e dados reproduzíveis | Sem distâncias substitutas quando o roteador falha; demo identificada e isolada de produção |
| Importação condicional | Validação/transação por item, identificador idempotente, modo criar-sem-sobrescrever e resultados por ID | Proteger inclusive colisão na mesma empresa entre prévia e envio; não depender só da checagem do navegador |

Cada contrato deve definir métodos/rotas, erros de validação/conflito, limites/paginação, matriz ADMIN/OPERATOR/VIEWER e exemplos em OpenAPI. Depois de implementado: conectar a tela, testar falha/permissão/troca de empresa e anexar evidência antes de encerrar o item correspondente.

Decisões anteriores à migração permanecem sem fotografia quando ela nunca foi
registrada. Não é possível reconstruir retroativamente dados não persistidos.
