# Infraestrutura brasileira para o piloto

Referência pesquisada em 27/10/2026. A equipe escolheu hospedar a VPS no Brasil,
com cobrança mensal. Este documento ajuda na escolha; não registra uma compra nem
comprova que o SPRain já foi publicado.

## Dimensionamento inicial

Para a primeira transportadora, procurar uma VM Linux x86_64 com pelo menos
2 vCPU, 8 GB de RAM, 100 GB de disco persistente e IPv4 público. É uma hipótese
inicial para os contêineres de PostgreSQL/PostGIS, API, coletor e Caddy; medir
memória, CPU, disco e tempo de resposta nas viagens reais antes de aceitar mais
empresas. Confirmar acesso administrativo, Docker Engine/Compose e entrada TCP
80/443. O banco não precisa de porta pública.

## Opção mensal de referência

A [calculadora oficial da Locaweb Cloud](https://www.locaweb.com.br/locaweb-cloud/calculadora-de-precos/)
mostra a VM **Large** com 2 vCPU, 8 GB de RAM e 160 GB SSD por **R$ 160/mês**.
Ela lista ainda IP público por R$ 5/mês e NAT Gateway por R$ 30/mês, ambos com
quantidade mínima de um no simulador: **R$ 195/mês como referência**, antes de
eventuais impostos ou outros serviços. A
[página do serviço](https://www.locaweb.com.br/cloud/) informa cobrança pós-paga
por hora para o Cloud e localização no Brasil. Confirmar região, configuração,
valor final, política de cancelamento e disponibilidade no checkout antes de
contratar; páginas comerciais e preços mudam.

O [VPS Linux de 8 GB da Locaweb](https://www.locaweb.com.br/servidor-vps/)
também tem 4 vCPU e 200 GB. O valor promocional exibido ali é equivalente
mensal de **contrato de 24 meses**, portanto não é o preço de contratação por
um mês. Só comparar essa alternativa após obter o preço final do ciclo mensal.

Um domínio próprio pode ser registrado pelo
[Registro.br](https://registro.br/dominio/) (a página informa R$ 40/ano para
`.br`), ou a equipe pode usar um subdomínio de um domínio que já controla.

## O que falta para a primeira publicação

1. Escolher e contratar a VM e disponibilizar IP, acesso administrativo e nome
   de domínio para a equipe técnica.
2. Mesclar o código aprovado na `main` e receber da Pessoa 1 o procedimento de
   carga **sanitizada** da malha inicial. O dump em `db/ci` contém dados de
   ensaio e não serve como carga automática de uma empresa real.
3. Escolher armazenamento de backup fora da VM e destino dos alertas. Testar
   envio, restauração, queda e recuperação com os serviços escolhidos.
4. Executar o [roteiro de homologação](homologacao-vps.md) numa VM nova,
   inclusive HTTPS público, banco, rotas e tela por outra rede.

Até essas verificações passarem, os testes locais e de CI não constituem
homologação da operação com viagens reais.
