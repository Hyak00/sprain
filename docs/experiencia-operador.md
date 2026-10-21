# Navegação e primeira análise do cliente

Base desta entrega: main `548e7f7`, incluindo as atualizações de observação
meteorológica, comparação econômica/espera e resumo do piloto sem economia
fictícia. A experiência continua no painel `/static/b2b.html`, com os mesmos
cadastros, filtros, mapa, contratos de decisão e motores do servidor.

## Navegação

O menu lateral reúne Operações, Frota, Corredor de referência, corredores do
cliente, relatórios, configuração e demonstração. O painel interno aparece
somente para ADMIN. A central continua reunindo todas as seções existentes.
Em celular, Menu expande a navegação; Escape a recolhe. Indicadores completos,
simulação de chuva e legenda/camadas são expansíveis, preservando espaço para
a lista e o mapa. Não há dependência JavaScript ou framework novo.

O resumo inicial conta as viagens do cenário carregado e as críticas. O filtro
Sem decisão no histórico consulta o servidor para as viagens exibidas (até 500);
uma decisão passada não autoriza o cenário atual. Falha de consulta não é
interpretada como ausência de decisão. Atualizar decisões refaz essa leitura.

## Comparação

Os cartões de distância/tempo e a tabela lado a lado exibem os valores da
fotografia retornada pela API. Valores ausentes permanecem não informados e
tarifas pendentes ficam explícitas. Os detalhes completos de restrições, fontes,
premissas e custos permanecem disponíveis.

Comparar um cenário de espera chama o endpoint existente
`POST /api/v1/logistica/decisao-economica`, com tempo e chuva informados e
premissas compatíveis da consulta. A API retorna os custos original, alternativo
e de espera, mais as premissas efetivamente aplicadas. É um exercício separado:
não substitui a fotografia vinculada à decisão. A espera não comprova liberação
da via, reavaliação futura do risco ou economia realizada. Defaults do serviço
ficam visíveis nas premissas do exercício.

## Onboarding do cliente (3.7)

Abra Configurar primeiro cliente para conferir:

1. Empresa e premissas financeiras.
2. Caminhões e medidas reais.
3. Corredores/recorrências.
4. Primeira viagem, pelo despacho ou importação JSON com prévia e erros por item.
5. Consulta, comparação e confirmação do primeiro resultado útil.

As etapas mostram os cadastros observados; existência de um cadastro não
comprova qualidade, cobertura ou homologação do cliente. VIEWER acompanha sem
iniciar nem confirmar. ADMIN e OPERATOR podem iniciar e confirmar.

A medição começa explicitamente em Iniciar configuração do cliente, pelo
relógio do servidor. Abra uma viagem após esse início, confira a comparação e
clique Confirmar primeiro resultado útil nos detalhes. O evento guarda empresa,
início, primeiro resultado, consulta e usuário individual quando disponível.
Repetições não reiniciam o prazo nem substituem o primeiro resultado.

O critério é **primeira comparação calculada e confirmada como útil pelo
usuário**, com geometria original e distância positiva. Não é detecção automática
de valor comercial, duração ativa de trabalho ou comprovação de viagem/resultado
financeiro. O tempo inclui pausas entre início e confirmação. Consultas antigas,
de outra empresa ou sem rota calculada são rejeitadas.

## Contratos e atualização de banco

- `GET /api/v1/painel/onboarding`: progresso e medição da própria empresa.
- `POST /api/v1/painel/onboarding/iniciar`: início idempotente.
- `POST /api/v1/painel/onboarding/primeiro-resultado`: recebe `consulta_id`;
  409 sem início, 404 fora da empresa, 422 para consulta antiga/sem rota.
- `POST /api/v1/painel/acompanhamento`: leitura para todos os papéis, com lista
  de até 500 operações; retorna somente registros da empresa.

Schema aditivo: `db/ci/15_onboarding_cliente.sql`, aplicado no bootstrap e no
startup do serviço. Sem remoção de dados ou mudança dos cálculos existentes.
O evento integra a exportação ZIP privada da empresa. Readiness inclui sua
tabela. Não é necessário apagar volumes para atualizar.

## Verificação

Testes HTTP cobrem medição/idempotência, consulta antiga, ausência de geometria,
autorização e isolamento por empresa. Chromium verifica navegação, primeiro
resultado persistido após novo login, custos reais retornados pela API na espera,
avisos de limitação e menu em celular, além dos fluxos anteriores.
Revisão com operadores de transportadora continua sendo necessária para
avaliar compreensão e esforço de uso; testes funcionais não a substituem.

Validação local em 17/10/2026: 315 testes de API + 3 subtestes em banco novo de
validação com demonstração desativada; 89 testes DOM; 10 cenários Chromium em
outro banco reservado à demonstração/E2E. Todos passaram. A primeira execução
completa da API foi feita na base E2E já alterada pelos formulários e revelou
duas expectativas incompatíveis com aquele ambiente; a conferência completa
foi repetida no ambiente separado equivalente ao CI, sem alterar essas regras.

A reorganização azul escuro e o mapa dos caminhos de todos os recursos estão em
[Organização visual do painel](organizacao-visual-painel.md).

Em 20/10/2026, a navegação passou a usar páginas diretas e seis abas na viagem. O mapa atual dos recursos está em [Organização visual do painel](organizacao-visual-painel.md); os resultados datados acima descrevem a revisão anterior.
