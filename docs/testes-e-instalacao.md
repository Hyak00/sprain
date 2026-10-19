# Instalação e testes reproduzíveis

Requisitos: Git, Docker Engine/Desktop com Compose v2 e contêineres Linux;
Python 3.11+ para ferramentas locais; Node.js 22+ e npm para testes de interface.
Execute os comandos na raiz do repositório. Não é necessário PostgreSQL instalado
no computador. O Docker baixa as imagens na primeira execução.

## Instalar uma demonstração nova

```sh
git clone https://github.com/yanpefnsc/sprain.git
cd sprain
docker compose -f compose.demo.yml up -d --build --wait
python scripts/preparar_demonstracao.py
python scripts/verificar_portal.py
```

Abra `http://127.0.0.1:18000/static/b2b.html`. Os acessos rápidos são públicos e
sintéticos. O banco, volume e rede são exclusivos da demonstração. Não copie
suas credenciais para produção. Portas ocupadas devem ser resolvidas antes de
iniciar; não pare outro ambiente sem identificar seu uso. `docker compose -f
compose.demo.yml down` para os serviços e preserva o volume. Não use `down -v`
para atualizar o projeto.

## Interface: testes unitários/DOM e navegador real

```sh
npm ci --ignore-scripts --no-audit --no-fund
npm test
npx playwright install chromium
docker compose -f compose.e2e.yml up -d --build --wait
docker compose -f compose.e2e.yml exec -T api python /app/scripts/seed_testes_painel.py
npm run test:e2e
docker compose -f compose.e2e.yml down
```

Em Linux sem bibliotecas de navegador: `npx playwright install --with-deps
chromium`. Os testes usam `127.0.0.1:18002`, banco reservado `sprain_demo_e2e`,
contas `@e2e.invalid` e backend real. O seed recusa qualquer outro banco/ambiente.
Os assets MapLibre da mesma versão são locais; tiles/fontes externos são
bloqueados, sem simular respostas da API. Assim os testes verificam os fluxos e
as geometrias, sem depender da disponibilidade do mapa externo. Não homologam
trânsito real, sinalização, cobertura geográfica ou precisão de tarifas.

Relatório HTML, screenshots e traces de falha ficam em `test-results/`, ignorado
pelo Git. Não publique traces de sessões reais: podem conter dados do cliente.
O CI executa as duas suítes e preserva falhas por sete dias.

## API e contratos

O workflow `.github/workflows/sprain_ci.yml` cria banco exclusivo no runner,
aplica `db/ci/*.sql`, instala ferramentas de teste e executa `pytest tests/ -v`
dentro de `/app/api`. Reproduza esse procedimento em ambiente descartável.
O CI também cria e verifica um dump desse banco descartável e o restaura em um
banco novo no runner, comparando uma contagem de dados e a extensão PostGIS.
**Não execute pytest no banco operacional nem no demo que alguém estiver usando:**
há testes que alteram eventos e cadastros.

`test_contratos_documentacao.py` verifica rotas utilizadas pelo painel via HTTP,
inventário dos caminhos do JavaScript, permissões e exemplos OpenAPI contra os
modelos Pydantic reais. Outros testes cobrem conflitos, sessões, isolamento de
empresas, custos, relatórios, demonstração e fontes.

## Dependências

`requirements.txt` e `api/requirements.txt` expressam as dependências diretas.
O Docker instala `requirements.lock.txt`, com versões transitivas exatas do
runtime validado em Python 3.11/Linux. `package-lock.json` fixa as ferramentas
JavaScript. Ao atualizar dependências, regenere o lock em ambiente isolado,
execute `python -m pip check`, build, API e interface antes do PR. Nunca inclua
credenciais ou caminhos locais no lock. As imagens base e pacotes de sistema
também precisam de atualização e validação; o lock Python não os congela.

## Critério de validação

Registrar commit, plataforma, versões, comandos, resultado e limites em
`docs/evidencias-validacao-3-6.md`. Instalar em contêiner e volume novos comprova
o bootstrap isolado. A repetição por outra pessoa em máquina limpa é uma
validação independente adicional; não deve ser marcada como realizada sem essa
pessoa fornecer a evidência.
