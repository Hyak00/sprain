# Alertas e comparação de custos no painel

Base desta entrega: `d5433c9`, consultada em 15/10/2026. O complemento fica no inspector de uma operação, em duas seções recolhidas. As abas, simulação de chuva, mapa, frota, despacho, pedágios, restrições físicas, decisões, histórico e CSV existentes foram mantidos. Nenhum cálculo, router, esquema de banco ou dependência de produção foi alterado.

## Comportamento

- **Comparação detalhada de custos:** mostra os valores da fotografia financeira da recomendação, sem refazer as contas no navegador. Separa custos estimados conhecidos, diferença com sinal, pedágios, combustível, economia operacional estimada, perda potencial e economia líquida potencial. Mostra custo médio por km e tarifas pendentes quando informados.
- **Premissas:** mostra medidas efetivas atuais retornadas pela API e premissas financeiras da fotografia. Não afirma que as medidas atuais eram as medidas da recomendação antiga. Expõe método, custo/km aplicado, fontes e data da referência de combustível, quando fornecidos. Os formulários existentes continuam responsáveis por informar medidas e recalcular.
- **Sem alternativa:** exige indicação positiva da API e geometria de linha. Sem ambas, apresenta indisponibilidade nos cartões da alternativa e não trata valores substitutos do contrato legado como um desvio real.
- **Alertas:** consulta somente ao abrir a seção ou acionar atualizar. Usa o endpoint público de ocorrências, limitado a 50 registros. Identifica a fonte, status, detecção, atualização, expiração, confiança informada e incógnitas. Associa eventos às rotas apenas pela interseção dos IDs dos trechos. Ausência de associação não significa distância segura.
- **Tempo:** datas incluem fuso de Brasília. Horário sem fuso, campo ausente ou data futura não aparecem como atualização válida. A validade é reavaliada localmente a cada minuto, sem novas chamadas de rede e sem apagar o texto que o operador estiver digitando. O horário de recebimento da consulta é separado da atualização do evento.
- **Feedback:** operador/admin podem registrar correspondência ou falso alerta, com motivo obrigatório de até 500 caracteres. O registro pertence à empresa autenticada e não modifica o evento público. Não há formulário de gravação para VIEWER. Envio repetido enquanto a gravação está pendente é bloqueado; evento expirado exige nova consulta.
- **Falhas e sessão:** erro de consulta limpa a lista anterior e informa que não é possível concluir que a rota está livre. Nova seleção, saída e troca de conta cancelam a consulta e descartam respostas atrasadas. Dados da API são inseridos como texto, sem interpretação de HTML.

O módulo usa o cliente autenticado existente e duas chamadas: `GET /api/v1/ocorrencias/ativas` e `POST /api/v1/alertas/feedback`. As informações financeiras já vêm de `GET /api/v1/logistica/operacoes/{id}/explicacao`. Não adiciona consultas a fornecedores externos, bibliotecas ou processamento de rotas no navegador.

## Limitações explícitas

- Ocorrências são contexto público, não a lista privada de uma empresa. O contrato não informa paginação, total, endereço/km/sentido, geometria do evento ou consequência operacional específica. Não foram inventados pontos no mapa nem endereços a partir de IDs.
- Confiança e estado são declarações do backend/fonte, sem validação estatística independente nesta tela. A confiança heurística da recomendação permanece identificada separadamente. A exibição não converte simulação, previsão ou registro histórico em observação confirmada.
- A resposta financeira não informa data da fotografia. A comparação tem cobertura parcial; tarifa desconhecida não é zero, e economia potencial não é dinheiro efetivamente economizado.
- Espera, economia comprovada e custos observados não possuem comparação equivalente nesse contrato. Não foram calculados a partir da perda potencial.
- Reporte de um evento inexistente depende de outro contrato; o feedback existente exige identificador cadastrado. Não criamos identificadores fictícios nem alteramos o cadastro público para contornar isso.
- Este incremento não conclui relatórios PDF/piloto, administração de usuários, importação/onboarding, indicadores internos, demonstração histórica ou responsividade completa do painel.

## Verificação

```text
node --test api/tests/interface/*.test.cjs
```

Nesta entrega: 21 testes JS passaram (13 de sessão e 8 de normalização/apresentação). Cobrem associação, validade, fuso, confiança fora do domínio, valores ausentes versus zero, sinais financeiros, ausência de alternativa e ausência de evidências.

Os 146 testes Python existentes passaram em API e banco exclusivos de validação. A suíte altera eventos; não executá-la no banco operacional.

Conferência manual de navegador em ambiente isolado: consulta vazia, comparação com resultado real da API de teste, evento sintético identificado como tal, associação por trecho, envio de feedback de operador, perfil somente leitura e limpeza ao sair. Os IDs existentes e o CSS inline original foram preservados. Esses checks não constituem homologação de viagens reais ou garantia de cobertura dos dados.

Roteiro de revisão: entrar como operador, selecionar operação, abrir as duas seções no inspector, conferir valores e fontes; registrar feedback somente em evento de teste; sair e entrar como VIEWER para confirmar ausência de gravação. Verificar também operações sem alternativa, resultado vazio e falha de consulta. Manter o banco de validação separado do operacional.
