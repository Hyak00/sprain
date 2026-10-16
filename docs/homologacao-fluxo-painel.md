# Verificação do fluxo 3.1

Revisão sobre main `797a071`, em 16/10/2026. O painel existente foi complementado sem remover seus 69 IDs ou o CSS inline. Não há nova dependência de produção.

## Critérios e evidências

| Requisito | Implementação e verificação |
|---|---|
| APIs existem e respondem | Inventário de métodos/caminhos no OpenAPI; sondagem HTTP real dos módulos de operações, frota, corredor, infraestrutura, dados públicos, qualidade, saúde, feedback, consultas e acesso. Escritas exercitadas pelos testes de domínio. Permissão negada é verificada com o papel apropriado. |
| Fluxos integrados | Navegador com banco isolado: login incorreto/correto, frota, despacho por sugestões da malha, comparação, edição de custos/chuva zero, três decisões, histórico, corredor/agenda/despacho, feedback de alerta e relato ausente. |
| Login/logout/papéis | Acesso individual persistido, sessão com expiração de oito horas e revogação no servidor. API consulta o papel/empresa atuais. Testes de usuário inativo, mudança de papel, expiração, revogação e isolamento. Atalhos demo preservados somente fora de produção. |
| Corredores/recorrências | Cadastro e edição com versão; medidas/veículo; agenda persistida; inativação; despacho explícito. Reenvio confirmado no navegador sem duplicação. Não se acrescentou execução automática de viagens. |
| Mapa | Malha, vulnerabilidade e rotas preservadas; geometrias autorizadas das ocorrências e pontos privados dos relatos. Falha de consulta limpa ocorrências anteriores. |
| Fonte/data | Metadados nos detalhes e indicação de ausência. Novos cadastros da frota registram atualização real; migração não atribui data fictícia aos antigos. Consulta e cálculo têm horários diferentes. Janela de novo despacho mantém o fuso UTC no envio. |
| Legenda/risco | Cores acompanhadas por texto; explicação de NORMAL/RISCO/CRÍTICO e IVI. Vulnerabilidade física não é confirmação de alagamento ou probabilidade de acidente. |
| Detalhe do alerta | Categoria, IDs/trecho/local disponível, fonte, detecção, atualização, expiração, confiança, consequência possível e incógnitas. Consequência genérica explicitada como possibilidade. |
| Natureza da informação | Histórico, previsão, trânsito observado, ocorrência confirmada, simulação, relato pendente e natureza desconhecida. Quatro naturezas públicas exercitadas com registros sintéticos na base isolada, identificados como tais. |
| Indisponível/antigo/sem alternativa | API de testes desligada: tela informou indisponibilidade e não declarou pista livre. Reinício e atualização recuperaram a consulta. Validade/expiração e ausência de geometria alternativa cobertas pelos testes. |
| Comparação | Distância, tempo, caminhão, restrições conhecidas, pedágios e parcelas financeiras continuam usando o servidor. Cálculo selecionado sincroniza tabela/totais; respostas antigas da mesma seleção são descartadas. |
| Premissas editáveis | Campos na comparação; controle de conflito; recálculo transacional em operação planejada; chuva explicitamente informada. Chuva zero testada no navegador. |
| Conhecido/estimado | Valores ausentes não viram zero, custo parcial não vira custo integral e potencial não vira economia comprovada. Confiança zero preservada como zero. |
| Decisão | Desviar, manter e aguardar exercitados no navegador; restrições/alternativa reavaliadas no servidor. Consulta vinculada e identificação individual quando disponível. |
| Histórico | Fotografias persistidas por empresa e decisões com consulta, usuário e horário; registros antigos sem autoria continuam explícitos. |
| Reportes | Feedback de falso alerta confirmado no navegador; relato não detectado registrado e exibido como privado/não validado, sem bloqueio automático da malha. |
| Carregamento/erro/vazio | Estados nos módulos e formulários, falha de login/rede, empresa sem corredores, carregamento e recuperação; lote parcial/incerto e cancelamentos cobertos nos testes DOM. |
| Responsividade/acessibilidade básica | Larguras CSS 320, 768 e 1280 conferidas sem rolagem horizontal do documento; diálogo sem excesso horizontal em 320. Teclado/Escape, foco, bloqueio do fundo do despacho, rótulos e movimento reduzido. Não é certificação WCAG. |

## Execução reproduzível

`npm ci --ignore-scripts --no-audit --no-fund` e `npm test`: 51 testes JavaScript aprovados. `python -m pytest tests -q` em `/app/api`, somente na API/banco isolados: 180 testes aprovados. O CI usa bootstrap de todos os arquivos `db/ci/*.sql`, testes Python e os testes JavaScript.

Os testes de API fazem escritas e podem simular operações: não executar em banco operacional. A sonda `python scripts/verificar_portal.py --base-url http://127.0.0.1:18000` é somente de leitura e inclui 16 verificações. Os dados e acessos usados na conferência manual ficaram exclusivamente na base de validação; não há conta individual padrão ou senha de produção semeada no repositório.

## Acesso individual e instalação

Migrações 11 e 12 são aditivas e repetíveis, aplicadas pela inicialização da API. Mantêm compatibilidade com as chaves das integrações e o endpoint demo anterior. O login do painel usa `/api/v1/acesso/login`; a configuração pública informa se os atalhos demo podem aparecer.

Provisionamento administrativo, em terminal confiável conectado ao banco correto:

```text
docker exec -it <container-api> python /app/scripts/cadastrar_acesso_painel.py --email <email> --empresa "<empresa>" --tenant <tenant> --papel OPERATOR
```

A senha é lida interativamente, confirmada e nunca enviada como argumento. Contas existentes não são sobrescritas. O hash usa scrypt (N=2^17, r=8, p=1), sal aleatório e comparação de tempo constante; a derivação roda fora do event loop, com duas execuções concorrentes. Referências: [Python hashlib](https://docs.python.org/3/library/hashlib.html#hashlib.scrypt) e [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#scrypt).

Sessões usam segredo aleatório, somente seu hash persiste no banco. O navegador mantém o segredo em memória, sem localStorage. A API limita tentativas de login individual por conta/IP; não confia no X-Forwarded-For enviado pelo cliente. Logout offline limpa a tela e informa quando a revogação não pôde ser confirmada. Para desativar uma conta no procedimento administrativo, marcar `painel_usuarios.ativo=false` invalida suas sessões imediatamente. Gestão pela interface e recuperação de senha pertencem ao item 3.2.

Em produção, usar HTTPS e as configurações seguras já exigidas pelo projeto; não habilitar contas demo. Fazer manutenção de registros de tentativas/sessões conforme a política de retenção do ambiente. O código local e os testes não representam uma implantação em infraestrutura de produção.

## Interpretação de conclusão

Os comportamentos listados têm implementação e evidências descritas acima. Isso não cria dados que fontes externas não publicam e não garante ausência de todo defeito possível. Informações sem fonte, data ou cobertura são apresentadas como desconhecidas; não são preenchidas por suposição. Homologação de campo e confirmação operacional de passagem/tarifas não são substituídas por uma simulação.
