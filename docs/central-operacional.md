# Central de trabalho

Entrega complementar ao painel existente; fluxo 3.1 atualizado sobre main `8c2c188` em 16/10/2026. Consulte [o fluxo integrado](fluxo-mvp-painel.md) para corredores, recorrências, premissas editáveis, consultas e relatos. O botão **Central de trabalho**, no cabeçalho, abre um diálogo com navegação própria. As abas de operações, frota e corredor continuam disponíveis.

## Uso

1. Entre com a conta apropriada e confira empresa/perfil. Há acesso individual provisionado no servidor e atalhos demo fora de produção. Consulte [a verificação do fluxo](homologacao-fluxo-painel.md).
2. Em **Relatórios e exportações**, consulte o resumo do piloto ou selecione uma operação e carregue consulta e decisões.
3. Baixe o PDF, CSV, JSON integral ou HTML compartilhável. Os arquivos contêm informações da empresa; encaminhe somente a destinatários autorizados. O código não envia relatórios a terceiros.
4. Em **Qualidade e serviços**, atualize a situação da API/banco, idade das fontes, feedback e métricas permitidas ao perfil. Falhas são indicadas individualmente; a tela não transforma falta de dados em ausência de risco.
5. Em **Importar rotas**, baixe o modelo JSON, preencha coordenadas e janelas com fuso, valide e confira a prévia. Operador/admin podem importar; VIEWER apenas valida. A prévia recusa identificadores existentes na empresa. A gravação não é atômica; baixe somente as falhas para corrigir. Em resultado incerto, consulte as operações antes de reenviar.
6. **Acesso e configurações** reúne os caminhos de cadastro e administração. **Configurar primeiro cliente** guia a ativação e registra o primeiro resultado útil no servidor. **Demonstração** e **Primeiros passos** fornecem roteiro, natureza dos dados e limitações. Veja [experiência do operador](experiencia-operador.md).

## Relatórios e interpretação

- O PDF é gerado localmente com texto paginado e fonte padrão. Não instala biblioteca de PDF no navegador ou servidor. O gerador limita documentos a 300 mil caracteres para evitar processamento excessivo; use JSON integral quando necessário.
- O relatório individual mostra operação, percurso, tempos, recomendação, custos retornados, premissas, limites/fontes disponíveis e histórico de decisões. A data de recebimento da consulta não é apresentada como data do cálculo.
- Medidas efetivas atuais não são apresentadas como fotografia histórica. Novas consultas são persistidas e vinculáveis às decisões. Autoria individual e fotografias de decisões anteriores que nunca foram gravadas continuam não fornecidas.
- Economia comprovada, custo observado e desvios realizados aparecem como **não disponíveis** até haver registros de execução e evidências. O impacto potencial do cenário e os custos de planejamento não comprovam dinheiro economizado. O resumo cobre todo o histórico disponível, sem filtro de período, usando somente a recomendação mais recente de cada operação. Contagens de decisões registradas não significam viagens executadas. `status_sla` e o antigo índice de resiliência ficam sem medição; a taxa nova mede apenas sugestões de alternativa nas operações com risco.
- PDF/HTML listam no máximo 100 pontos físicos por rota, explicitando o recorte; o JSON integral mantém a resposta completa. O CSV de decisões representa o histórico retornado; o CSV de consulta representa a consulta carregada, não uma exportação agregada de todas as fotografias persistidas; elas estão em Histórico de consultas.
- CSV escapa separadores, aspas e quebras; neutraliza início de fórmula em texto. Valores numéricos negativos mantêm o sinal.

## Contratos consumidos

| Recurso | Método/endpoint | Perfil |
|---|---|---|
| Operações | GET /api/v1/logistica/operacoes | ADMIN/OPERATOR/VIEWER |
| Resumo | GET /api/v1/logistica/relatorios/sumario-executivo | Todos |
| Operação/histórico | POST /api/v1/painel/consultas e GET /api/v1/logistica/operacoes/{id}/decisoes | Todos |
| Importação parcial | POST /api/v1/logistica/operacoes/importar-lote | ADMIN/OPERATOR |
| Fontes globais | GET /api/v1/dados-publicos/fontes e /api/v1/indicadores/qualidade | Todos |
| Saúde | GET /api/v1/health/liveness e /readiness | Público; central exige sessão |
| Feedback da empresa | GET /api/v1/alertas/precisao | Todos |
| Métricas da empresa | GET /api/v1/logistica/observabilidade/metricas | ADMIN/OPERATOR |

Não há sondagem periódica nem fornecedor externo novo. A central usa `PainelSessao.request`, cancela leituras ao fechar/trocar seção/sessão e descarta respostas antigas. Arquivos selecionados não são enviados antes da validação e do clique de importação. Credenciais não entram nos relatórios, arquivos de exemplo ou armazenamento do navegador.

## Preservação e correção necessária

Os 69 IDs e o CSS inline de main foram preservados. CSS adicional adapta a disposição em telas menores, mantém mapa e detalhes acessíveis, permite rolagem das tabelas e limita a altura dos diálogos. Rótulos, foco do despacho, navegação por teclado nas operações, sugestões de endereço como botões e controle das camadas complementam os fluxos existentes.

Na criação de operações, a checagem de titularidade já existia antes do cálculo. Foi adicionada uma segunda verificação dentro de transação e trava por identificador antes de apagar os vínculos de rota. Isso impede colisão entre duas criações simultâneas de empresas distintas. O comportamento de atualização na mesma empresa permanece; a prévia do importador evita sobrescrita acidental comum, mas não substitui criação condicional/atômica no servidor.

## Verificação e limites de conclusão

```text
npm ci --ignore-scripts --no-audit --no-fund
npm test
```

Os testes DOM usam `linkedom` somente como dependência de desenvolvimento, excluída da imagem. Cobrem relatórios, downloads, texto não interpretado como HTML, permissão de importação, lote parcial/incerto, qualidade parcial, troca de empresa e limpeza. Não são equivalentes a uma suíte automatizada completa de navegador. A inspeção manual de navegador complementa esses testes.

Os testes Python devem rodar somente em banco/API de testes: verificam os contratos de leitura e a preservação da rota em colisão sequencial e concorrente. O CI continua executando a suíte existente.

Consulte [o checklist rastreável](checklist-interface.md), [as dependências de integração](contratos-interface-pendentes.md), [instalação e demonstração](instalacao-demonstracao.md) e [onboarding/arquitetura/operação](onboarding-arquitetura-operacao.md). Esta entrega não certifica todo o MVP nem encerra itens dependentes.
