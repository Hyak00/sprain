# Coleta meteorológica no piloto comercial

A [licença gratuita da Open-Meteo](https://open-meteo.com/en/terms) é apenas para
uso não comercial. O [plano contratado](https://open-meteo.com/en/pricing)
fornece uma chave e o endereço `customer-api.open-meteo.com`; os parâmetros de
previsão permanecem os mesmos. Este código **não contrata** o serviço e ainda
não foi testado com uma chave real.
O fornecedor também [exige atribuição dos dados](https://open-meteo.com/en/pricing);
confirmar a apresentação do crédito no produto antes de ativar a fonte para clientes.

## Configuração

No `.env.prod` fora do Git, defina `OPEN_METEO_API_KEY` somente depois de a
equipe adquirir uma licença comercial. O Compose de produção repassa a chave
à API. O serviço opcional `sprain_chuva` do Compose da VPS também precisa recebê-la
antes de ser ativado. Nunca inclua a chave em URL de diagnóstico, captura de
tela, log, chamado ou arquivo versionado.

Sem a chave em `ENVIRONMENT=production`, o agendador interno não inicia e os
três caminhos de consulta Open-Meteo retornam indisponibilidade sem acessar o
endpoint gratuito. O corredor não usa `wttr.in` como substituto em produção,
pois essa fonte ainda não foi aprovada para o piloto. Com a chave, todas as
consultas Open-Meteo usam o endpoint comercial; falhas de rede preservam o
último dado existente e não são interpretadas como chuva zero.

## Verificação antes de ativar

1. Em ambiente isolado, confirme que a API inicia sem chave e não faz chamadas
   à Open-Meteo gratuita quando `ENVIRONMENT=production`.
2. Com chave sintética e transporte HTTP simulado, confirme o host comercial e
   o parâmetro `apikey` nos testes automatizados. A chave não deve aparecer
   nos logs de erro.
3. Após a contratação, em homologação, faça uma consulta real com a chave
   guardada fora do Git. Confira uma leitura recente, a procedência, o estado
   da fonte e o consumo registrado pelo fornecedor antes de habilitar o coletor
   para viagens reais.

O bloqueio de chamadas gratuitas em produção é verificável agora. A qualidade,
cobertura, latência e disponibilidade da fonte contratada ainda dependem do
teste real em homologação.
