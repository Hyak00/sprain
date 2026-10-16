# Integrações ainda necessárias

Atualização de 16/10/2026: corredores/recorrências, premissas da viagem, consultas persistidas, vínculo da decisão e relatos foram implementados em `/api/v1/painel`. Consulte [fluxo-mvp-painel.md](fluxo-mvp-painel.md). A tabela abaixo mantém necessidades adicionais e indica explicitamente quando o backend já existe. A interface não simula sucesso nem usa armazenamento do navegador como substituto de persistência. As rotas finais e os schemas devem ser definidos com os responsáveis do backend/dados.

| Recurso | Operações e dados mínimos | Condições de aceite |
|---|---|---|
| Recuperação e extensão de acesso | Login individual e revogação implementados em /api/v1/acesso; falta fluxo de recuperação e eventual renovação | Recuperação sem enumeração, token de uso único; não confundir com login/sessão já disponíveis |
| Usuários no painel | Backend de listagem/criação/desativação/troca de papel e auditoria disponível em `/api/v1/acesso/usuarios`; falta integrar a tela | ADMIN com sessão individual da própria empresa; não permitir ação com chave compartilhada; consultar [gestão de usuários](gestao-usuarios.md) |
| Resultado financeiro observado | Custos observados, evidência de execução, contrafactual/metodologia e período | Distinguir observado, estimado, potencial e economia comprovada; não inferir comprovação da perda potencial |
| Espera | Duração, custos/premissas e resultado comparável ao desvio | Mesmo contexto temporal/financeiro, sem somar modelos incompatíveis no navegador |
| Qualidade completa | Última tentativa/sucesso, falhas/histórico, periodicidade por fonte, cobertura e critérios | Sem prazo genérico de 48 h apresentado como regra validada para todas as fontes |
| Exportação integral | Solicitação, autorização, escopo e arquivo com dados do titular/empresa | Sem dados de outra empresa, credenciais ou afirmação de completude a partir do CSV de contingência |
| Onboarding | Registrar início e primeiro resultado útil de novo cliente, IDs e timestamp do servidor | Evento idempotente/persistido, métrica reprodutível; tempo em memória não substitui o evento |
| Histórico da demonstração | Fonte primária, data, geometria/trechos e dados reproduzíveis | Sem distâncias substitutas quando o roteador falha; demo identificada e isolada de produção |
| Importação condicional | Validação/transação por item, identificador idempotente, modo criar-sem-sobrescrever e resultados por ID | Proteger inclusive colisão na mesma empresa entre prévia e envio; não depender só da checagem do navegador |

Cada contrato deve definir métodos/rotas, erros de validação/conflito, limites/paginação, matriz ADMIN/OPERATOR/VIEWER e exemplos em OpenAPI. Depois de implementado: conectar a tela, testar falha/permissão/troca de empresa e anexar evidência antes de encerrar o item correspondente.

Além disso: premissas globais da empresa e identidade individual continuam fora do fluxo 3.1. Decisões anteriores à migração permanecem sem fotografia quando ela nunca foi registrada. Não é possível reconstruir retroativamente dados que não foram persistidos.
