# Administração na interface — seção 3.2

As telas ficam em **Central de trabalho → Administração da empresa** e **Premissas financeiras**. A entrada contém **Recuperar acesso**. O painel, as simulações, rotas, custos por viagem e relatórios anteriores são preservados. Não há dependência nova de produção.

| Requisito | Comportamento |
|---|---|
| Usuários | ADMIN individual lista com paginação, cria conta, muda papel e desativa. A API existente continua responsável pelo isolamento, auditoria e revogação das sessões. Não se pode mudar ou desativar a própria conta; não há exclusão de usuários. |
| Premissas financeiras | Todos os papéis autenticados consultam; ADMIN individual salva. Configuração versionada por empresa, com data e autoria. Conflito de versão retorna 409. Campos vazios removem o padrão da empresa; zero explícito é preservado. |
| Recuperação | Solicitação pública com resposta genérica, fila da empresa para ADMIN individual, conferência de identidade por canal conhecido, código aleatório de uso único, validade de 30 minutos, definição de nova senha e revogação de todas as sessões anteriores. Pode-se cancelar um código e solicitar outro. |
| Exportação | ADMIN individual baixa ZIP com manifesto e JSON Lines, produzido em transação de leitura com fotografia consistente e arquivos temporários limitados. Dados de outras empresas e segredos ficam excluídos. |

## Premissas e motor de custos

Novas viagens mesclam campos nesta ordem: empresa, frota, valores explícitos da viagem. O resolvedor de combustível e o motor existentes calculam o resultado. A regra existente do custo total por km prevalece sobre seus componentes; combustível não é somado novamente. Referências gerais do sistema preenchem os campos sem premissa aplicável.

O resultado resolvido fica gravado no despacho, inclusive quando originado de importação ou recorrência. Alterar o padrão da empresa não reescreve operações, recomendações ou fotografias já existentes. Para revisar uma operação antiga, usa-se a edição e o recálculo explícitos da comparação, mantendo seu histórico.

## Recuperação assistida

1. Na entrada, o usuário informa seu e-mail e solicita recuperação. A resposta não revela cadastro nem envia e-mail automaticamente.
2. Um ADMIN individual abre a fila da empresa e confere a identidade por um canal previamente conhecido. A solicitação sem liberação vale 24 horas.
3. Após marcar a conferência, libera um código. O código aparece apenas nessa resposta e vale 30 minutos. O banco guarda somente SHA-256 do código aleatório de 256 bits; o código não vai para URLs, armazenamento do navegador, lista de solicitações ou auditorias.
4. O administrador entrega o código em particular. O usuário abre Recuperar acesso, informa e-mail, código e a nova senha duas vezes. Senha de 15 a 256 caracteres; espaços da senha não são removidos silenciosamente.
5. A troca consome o código e encerra todas as sessões anteriores. Nova autenticação é obrigatória. Código expirado, cancelado, reutilizado ou de outra conta não altera acesso.

Solicitar novamente não invalida um código já emitido e não cria solicitações pendentes duplicadas. Se o código for perdido, o administrador cancela a solicitação e orienta um novo pedido. Não há promoção de papel, reativação de conta desativada ou login automático nesse fluxo. Tentativas públicas são limitadas por conta e IP, sem confiar em X-Forwarded-For.

Se nenhum administrador conseguir entrar, o responsável pelo servidor, após conferir a identidade, executa em terminal confiável:

```text
docker exec -it <container-api> python /app/scripts/recuperar_acesso_painel.py --email <email-admin> --tenant <empresa> --identidade-conferida
```

O comando atende somente ADMIN ativo da empresa indicada. Não define nem pede a senha; gera o mesmo código temporário auditado para o usuário concluir na interface. Não redirecionar essa saída para logs/chamados. O primeiro administrador continua sendo provisionado pelo comando existente `cadastrar_acesso_painel.py`; nenhuma senha administrativa padrão é semeada pela migração.

## Exportação

O manifesto informa empresa, horário, contagens, módulos legados não utilizados e exclusões. Conjuntos: veículos, operações, segmentos das rotas, recomendações, cenários, decisões, corredores, recorrências, despachos, consultas, relatos, configuração financeira, usuários (campos permitidos), auditorias de usuários/administração/previsão, feedback, infraestrutura e revisões, importações/limites/malha privada e eventos configurados em webhooks. Viagens de `operacoes_cliente_frota` entram quando o módulo foi utilizado. Geometrias privadas são exportadas como GeoJSON em WGS84.

Não exporta hashes de senha, sessões, chaves, URLs/segredos de webhook, códigos/solicitações de recuperação nem bases públicas compartilhadas. A fila de recuperação continua disponível na tela administrativa, sem expor códigos emitidos. O ZIP não é criptografado: o usuário deve guardar o arquivo em local com acesso restrito.

Limites explícitos: 100 MB descompactados e 19 MB compactados; excedê-los retorna 413 e não entrega arquivo parcial. O limite compactado respeita o transporte existente do painel. Instalações acima desse volume exigem extração administrativa assistida. O temporário mantém até 2 MB em memória e depois usa disco; consultas usam cursor com lotes de 100 registros.

## Instalação e verificação

A inicialização aplica a migração aditiva e repetível `13_administracao_painel.sql` depois do acesso existente. O CI também a aplica no bootstrap do banco. Não há alteração destrutiva de tabela ou de dados anteriores.

- API: suíte completa com 204 testes aprovados, incluindo recuperação real, expiração/cancelamento/reuso, limites, revogação, isolamento, configuração com versão, padrões em despachos novos e leitura de ZIP real sem segredos.
- Interface: 66 testes JavaScript aprovados, incluindo permissões, confirmação de papel/desativação, envio único de criação, zero/versão nas premissas, limpeza dos campos de recuperação e descarte de resposta atrasada.
- Navegador em banco isolado: solicitação pública, login de conta sintética existente, lista de usuários/fila, download real do ZIP e gravação de premissa com versão/data. Administração e financeiro sem excesso horizontal em 320 pixels CSS. A definição de novas credenciais e a promoção de acesso foram exercitadas pelos testes de API, sem criar contas reais na interface.

Executar `npm test` na raiz e `python -m pytest tests -q` em `/app/api` da instância isolada após readiness. A suíte de API escreve no banco: não executá-la em base operacional. Contas de homologação ficam exclusivamente no banco isolado. Não usar os dados sintéticos como credenciais de produção.

Em produção, manter HTTPS e os controles já exigidos pelo projeto. A manutenção de retenção das tentativas de recuperação deve acompanhar a de tentativas/sessões de login; não remover códigos ainda válidos nem auditorias dentro do prazo de retenção da empresa.
