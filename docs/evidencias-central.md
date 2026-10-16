# Evidências da central — 15/10/2026

Base inspecionada: main `4c63696`. As verificações abaixo se referem à entrega desta branch e não certificam toda a lista técnica.

- `npm test`: 38 testes passaram, incluindo transporte/sessão, alertas/custos e 17 novos testes de dados/PDF/fluxos DOM. A dependência DOM é apenas de desenvolvimento.
- `python -m pytest tests -q`: 151 testes passaram em API e banco de validação separados. Cinco testes novos verificam três perfis de leitura e colisão de identificadores sequencial/concorrente. A concorrência é sincronizada por trava de teste para que ambas as tentativas passem pela verificação inicial antes da inserção.
- Bootstrap: `docker compose -f compose.demo.yml up -d --build` criou rede/volume/banco novos; `python scripts/verificar_portal.py` retornou oito sucessos. Isso não é validação independente em máquina limpa.
- PDF: geração paginada, offsets e escapes verificados por testes; extração com pypdf preservou acentos/identificação/limitações; páginas renderizadas para inspeção visual. Download real da interface produziu relatório da operação de demonstração em duas páginas.
- Navegador: operador abriu central/resumo/relatório, consultou qualidade e importou uma operação sintética identificada como teste em banco de demonstração separado. Registrou uma decisão de teste de aguardar; histórico e relatório individual retornaram o mesmo registro, motivo e horário. VIEWER viu o importador sem gravação habilitada. Sessão e dados da empresa são limpos ao sair nos testes e na conferência dos fluxos.
- Largura de celular: verificada em viewport de 390 px (375 px úteis com rolagem vertical), sem transbordamento horizontal da página/central. A regra de disposição mobile foi ajustada para prevalecer sobre o CSS original. Não equivale a homologação de todos os dispositivos ou fluxos.
- Preservação: os 69 IDs e o bloco CSS inline de main foram mantidos; os estilos adicionais reorganizam as telas menores. Sintaxe JavaScript e `git diff --check` verificados.
- GitHub Projects: API recusou a operação por `INSUFFICIENT_SCOPES`; quadro não criado. Template de issue e seis áreas propostas estão em `.github/ISSUE_TEMPLATE/entrega.yml` e `quadro-entregas.md`.

Revisão humana cruzada, E2E completo automatizado de navegador, instalação por terceiro, runbooks conjuntos testados e integrações listadas em `contratos-interface-pendentes.md` continuam pendentes. Não marcar esses itens como concluídos por esta evidência.
