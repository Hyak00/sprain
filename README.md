# SPRain • Inteligência Climática e Resiliência para Operações Logísticas

Plataforma corporativa B2B que ajuda transportadoras a identificar riscos climáticos em seus corredores rodoviários e urbanos, avaliar rotas alternativas sobre malha PostGIS/pgRouting e documentar o impacto operacional de eventos de chuva e alagamento.

---

## Posicionamento Operacional e Escopo Validado

- **Apoio à Decisão Logística (`/static/b2b.html`):** Identificação de trechos vulneráveis (IVI), plotagem de rota alternativa recomendada, cálculo transparente de custo de desvio e registro auditável da decisão do gestor.
- **Corredor Regional e Urbano:** 245,0 km mapeados no eixo Araraquara ↔ São Paulo (SP-310 / SP-330 / SP-348) com praças de pedágio por categoria e malha urbana indexada na Zona Leste de São Paulo (2.978 trechos).
- **Governança Multi-Tenant e Segurança:** Segregação por `tenant_id` em banco, relatórios e cache; controle de acesso RBAC (`ADMIN`, `OPERATOR`, `VIEWER`); proteção SSRF e webhooks assinados via HMAC-SHA256.
- **Homologação:** a suíte automatizada roda no CI. O relatório de 56 testes é
  um registro histórico; veja o [diagnóstico técnico atual](docs/diagnostico-pessoa2.md).

---

## Como Executar

Para começar em **demonstração local isolada**, com o esquema e a base de testes:

```bash
docker compose -f compose.demo.yml up -d --build
python scripts/preparar_demonstracao.py
python scripts/verificar_portal.py
```

Abra http://127.0.0.1:18000/static/b2b.html e use os acessos rápidos de
demonstração. A **Central de trabalho** reúne relatórios PDF/CSV, qualidade,
prévia/importação de operações e orientações. Dados do CI são exemplos, não
evidências históricas ou viagens reais. Esse Compose usa banco, volume e rede
próprios; não reaproveita o banco operacional e não configura produção.

A aba Demonstração separa uma referência oficial pesquisada da ARTESP de um
exercício sintético de bloqueio e desvio. Fonte, limites e roteiro estão em
[Demonstração isolada](docs/demonstracao-isolada.md).

Para gestão de usuários, premissas financeiras, recuperação assistida de acesso e
exportação privada, veja [Administração na interface](docs/administracao-interface.md).
As funções administrativas exigem ADMIN com acesso individual.

ADMIN também pode consultar fontes, falhas de importação, serviços e métricas
na central: [Painel operacional interno](docs/painel-operacional-interno.md).

Os formatos PDF/CSV/HTML e os critérios de custos, fontes e fotografias históricas
estão descritos em [Relatórios na interface](docs/relatorios-painel.md).

Pré-requisitos: Git, Docker com Compose v2 e Python 3.11+ para as ferramentas
locais; Node.js 22+ para testes de interface. O runtime da API usa Python 3.11.
Instruções completas, limitações e dependências estão no
[guia da central](docs/central-operacional.md) e no
[roteiro de instalação e demonstração](docs/instalacao-demonstracao.md).

O comando abaixo mantém o ambiente operacional existente. Ele exige que a base
e as variáveis de ambiente tenham sido provisionadas; não substitui o bootstrap
isolado acima:

```bash
docker compose up --build -d
```

Execute a suíte de testes somente em um banco isolado, como no CI: alguns
testes podem modificar dados. Para criar e verificar um backup do PostGIS,
consulte o [guia de backup e restauração](docs/backup-restauracao-postgis.md).

---

## Endpoints Principais B2B

- `GET /api/v1/health/readiness` — Verificação de prontidão e latência da malha PostGIS.
- `POST /api/v1/logistica/simular-impacto` — Simulação parametrizada de impacto pluviométrico nas operações do tenant.
- `GET /api/v1/logistica/operacoes/{id_operacao}/explicacao` — Auditoria detalhada com geometria GeoJSON da alternativa e limitações operacionais.
- `POST /api/v1/logistica/operacoes/{id_operacao}/decisao` — Registro formal da decisão do gestor operacional.
- `GET /api/v1/rotas/intermunicipal` — Referência geográfica e financeira do corredor SP-310 / SP-348, com cobertura e limitações explícitas.
- `GET /api/v1/logistica/exportar-contingencia/csv` — Exportação tabular de contingência para TMS/ERP.

## Caminhoes e infraestrutura na torre existente

Consulte [o guia de integracao](docs/integracao-caminhoes.md) para medidas, custos, pedagios, pontes, dados de referencia e execucao da demonstracao. Login, abas, filtros, despacho e auditoria existentes foram preservados.

O [complemento de dados e custos automaticos](docs/integracao-dados-viagem.md) descreve consumo de referencia, preco semanal ANP, fontes no mapa, tarifas conferidas e limites de cobertura.

## Testes e operação

- [Instalação e suítes API, DOM e Chromium](docs/testes-e-instalacao.md).
- [Contratos do painel e Swagger](docs/api-painel.md): `/docs` e `/openapi.json`.
- [Onboarding técnico de um cliente](docs/onboarding-tecnico-cliente.md).
- [Arquitetura, fontes e frequência efetiva](docs/arquitetura-e-fontes.md).
- [Runbook de deploy, rollback, backup e incidentes](docs/runbook-operacao.md).
- [Evidências e limites da validação](docs/evidencias-validacao-3-6.md).
- [Quadro de seis áreas e modelo de issue](docs/quadro-github.md).

O Docker instala versões Python fixadas em `requirements.lock.txt`. O CI
executa testes de API e interface em ambientes isolados; o navegador usa backend
real e banco reservado. Testes automatizados não comprovam condições atuais de
estrada, economia realizada ou homologação de produção.
