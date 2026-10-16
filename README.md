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
- `GET /api/v1/rotas/intermunicipal` — Análise preditiva e financeira do corredor rodoviário SP-310 / SP-348.
- `GET /api/v1/logistica/exportar-contingencia/csv` — Exportação tabular de contingência para TMS/ERP.

## Caminhoes e infraestrutura na torre existente

Consulte [o guia de integracao](docs/integracao-caminhoes.md) para medidas, custos, pedagios, pontes, dados de referencia e execucao da demonstracao. Login, abas, filtros, despacho e auditoria existentes foram preservados.

O [complemento de dados e custos automaticos](docs/integracao-dados-viagem.md) descreve consumo de referencia, preco semanal ANP, fontes no mapa, tarifas conferidas e limites de cobertura.
