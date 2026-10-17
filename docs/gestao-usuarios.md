# Gestão de usuários da empresa

As telas e o fluxo de recuperação estão descritos em [Administração na interface](administracao-interface.md).

O primeiro acesso individual é provisionado pelo operador do ambiente com
`scripts/cadastrar_acesso_painel.py`. Depois, um ADMIN autenticado por **sessão
individual** pode administrar usuários da sua própria empresa. Chaves de API
compartilhadas, inclusive as de demonstração, não têm acesso a esta gestão.

Todas as chamadas usam `X-API-Key` com o token recebido de
`POST /api/v1/acesso/login`. A empresa e o autor vêm da sessão; o corpo não
aceita `tenant_id` nem `empresa`. Os resultados não contêm hash de senha e usam
`Cache-Control: no-store`.

| Método | Caminho | Resultado |
| --- | --- | --- |
| GET | `/api/v1/acesso/usuarios?limit=50&offset=0` | Lista paginada da própria empresa, inclusive contas inativas. |
| POST | `/api/v1/acesso/usuarios` | Cria conta com `email`, `senha` de 15 a 256 caracteres e `papel` (`ADMIN`, `OPERATOR`, `VIEWER`). |
| PATCH | `/api/v1/acesso/usuarios/{id}/papel` | Troca o papel e revoga sessões existentes do usuário. |
| POST | `/api/v1/acesso/usuarios/{id}/desativar` | Desativa sem apagar o registro e revoga sessões. |
| GET | `/api/v1/acesso/usuarios/auditoria?limit=50&offset=0` | Lista criação, troca de papel e desativação da própria empresa. |

A API impede alterar ou desativar a própria conta por este fluxo e impede
deixar a empresa sem ADMIN ativo. Mudanças são transacionais e registradas na
tabela `painel_usuarios_auditoria`, com IDs de autor e alvo, horário e papéis;
senhas não entram nessa trilha. Um usuário de outra empresa retorna 404.

A interface administrativa ainda precisa consumir esses endpoints. Recuperação
de senha e exportação integral de dados da empresa continuam pendentes. Ao
provisionar ou criar uma conta, entregue a senha ao titular por canal seguro;
ela não aparece na resposta nem nos logs desta API.
