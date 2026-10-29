# Infraestrutura brasileira para o piloto

Referência pesquisada em 29/10/2026. A equipe escolheu hospedar a VPS no Brasil,
com cobrança mensal. Este documento ajuda na escolha; não registra uma compra nem
comprova que o SPRain já foi publicado.

## Dimensionamento inicial

Uma VM Linux x86_64 com **2 vCPU e 4 GB de RAM é uma opção de ensaio**, não
uma capacidade já comprovada para viagens reais. **8 GB é a alternativa com
mais folga**, não um requisito mínimo demonstrado. Os limites individuais do
Compose permitem até 4 GB para o banco, 2 GB para a API e 1 GB para o coletor;
eles são tetos por contêiner, não consumo medido nem uma garantia de que todos
caibam juntos em 4 GB. O sistema operacional, Caddy, imagens e cache do banco
também precisam de recursos. Evite presumir que 2 GB bastem.

Escolha o disco após medir a malha inicial, o crescimento de viagens, os logs
e o espaço temporário de atualização e restauração. Confirme IPv4 público,
acesso administrativo, Docker Engine/Compose e entrada TCP 80/443. O banco não
precisa de porta pública. Antes de aceitar uma VM de 4 GB para o piloto,
execute a verificação abaixo e tenha um caminho de ampliação para 8 GB.

### Como decidir entre 4 e 8 GB

1. Em uma VM Linux **descartável de 4 GB**, suba PostGIS, API e Caddy com dados
   sintéticos. Não copie viagens nem credenciais de transportadoras. Execute o
   [ensaio do Compose](homologacao-vps.md) e o [teste básico de carga](teste-carga-basico.md)
   em uma instalação de demonstração isolada nessa mesma classe de VM.
2. Registre `free -h`, `df -h` e `docker stats --no-stream` durante a partida,
   importação e testes. Confira também reinícios, eventos de falta de memória,
   estado dos healthchecks, p95 e erros HTTP. O artefato `carga-api.json` do CI
   mede latência, mas **não mede memória** e usa um runner de tamanho diferente.
3. Repita a verificação com a malha **sanitizada e aprovada** e com volume e
   simultaneidade próximos do primeiro piloto. Defina margem para picos,
   atualização e recuperação. Se houver falta de memória, reinícios, troca
   intensa para disco ou latência incompatível com o uso, passe para 8 GB antes
   da operação real. Dados sintéticos pequenos, sozinhos, não aprovam 4 GB.

## Opção mensal de referência

A [calculadora oficial da Locaweb Cloud](https://www.locaweb.com.br/locaweb-cloud/calculadora-de-precos/)
mostra a VM **Medium** com 2 vCPU, 4 GB de RAM e 80 GB SSD por **R$ 80/mês**,
e a **Large** com 2 vCPU, 8 GB e 160 GB por **R$ 160/mês**. Ela lista ainda
IP público por R$ 5/mês e NAT Gateway por R$ 30/mês, ambos obrigatórios no
simulador: **R$ 115/mês para 4 GB ou R$ 195/mês para 8 GB**, como referência
de infraestrutura antes de eventuais impostos, domínio, backup externo e
provedores de dados. A
[página do serviço](https://www.locaweb.com.br/cloud/) informa cobrança pós-paga
por hora para o Cloud e localização no Brasil. Confirmar região, configuração,
valor final, política de cancelamento e disponibilidade no checkout antes de
contratar; páginas comerciais e preços mudam. Não usar a configuração de 4 GB
em viagens reais antes de validar sua capacidade para a carga do piloto.

A [oferta da Hostinger](https://www.hostinger.com/br/servidor-vps) exibe valores
equivalentes a R$ 29,99/mês para 4 GB/1 vCPU e R$ 42,99/mês para 8 GB/2 vCPU,
mas informa pagamento **integral de 24 meses** (R$ 719,76 e R$ 1.031,76 no
checkout anunciado). Esses números não são uma contratação mensal avulsa;
obtenha o preço do ciclo de um mês antes de compará-los com uma VM mensal.

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
