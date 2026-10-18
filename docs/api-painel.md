# API utilizada pelo painel

Swagger em `/docs`, especificação em `/openapi.json`. Clique **Authorize** e
informe o valor da sessão individual ou chave autorizada no cabeçalho
`X-API-Key`. Nunca coloque a chave em URL, issue, captura de tela ou relatório.
Os exemplos são sintéticos: substitua identificadores e confirme empresa,
datas e versões. A autorização é aplicada pelo backend, não só pelos botões.

## Acesso e contratos

| Fluxo | Contrato principal | Observação |
| --- | --- | --- |
| Login individual | `POST /api/v1/acesso/login` | Use o corpo exibido no Swagger; sessão revogável |
| Usuários | `/api/v1/acesso/usuarios` | ADMIN individual da mesma empresa |
| Premissas e recuperação | `/api/v1/administracao/*` | Escritas e dados sensíveis exigem ADMIN individual |
| Corredores e recorrências | `/api/v1/painel/corredores`, `/api/v1/painel/recorrencias/*` | Persistência por empresa; despacho explícito |
| Consultar operação | `POST /api/v1/painel/consultas` | Também permitido a VIEWER; grava fotografia histórica |
| Editar premissas | `PUT /api/v1/painel/operacoes/{identificador}/premissas` | Exige selo atual; conflito 409 |
| Decisão | `POST /api/v1/logistica/operacoes/{id_operacao}/decisao` | Vincula consulta; revalida alternativa para aprovação |
| Importar operações | `POST /api/v1/logistica/operacoes/importar-lote` | Parcial, não atômico: sucesso por item |
| Relatos | `/api/v1/painel/relatos` | Pendentes de validação, sem bloquear automaticamente a malha |
| Relatórios | `/api/v1/painel/relatorios/*` | Dados e fotografias da empresa, com limites explícitos |
| Fontes e importações | `/api/v1/operacional/*` | ADMIN; histórico começa na instrumentação |
| Exportação privada | `GET /api/v1/administracao/exportacao` | ZIP, manifesto e JSON Lines, sem credenciais |
| Saúde | `/api/v1/health/liveness`, `/api/v1/health/readiness` | Pública; readiness não homologa fornecedores |
| Estimativa de percurso | `POST /api/v1/transito/comparar` | Somente desenvolvimento/testes; OSRM demo, sem trânsito observado |

Use o Swagger para os caminhos completos e os schemas de cada método. A tabela
agrupa contratos, não substitui o inventário executável. PDF e HTML são gerados
localmente pelo cliente com os dados retornados pela API; não há endpoint que
retorne o PDF. Downloads CSV usam `text/csv`; ZIP usa `application/zip`.

## Respostas e repetição

- `401`: autenticação ausente/expirada; voltar ao login, sem repetir escrita
  automaticamente. `403`: papel, empresa ou tipo de acesso insuficiente.
- `404`: registro não disponível para o contexto autorizado; não procurar em
  outra empresa. `409`: conflito/versão; consultar novamente antes de editar.
- `422`: validação; conferir campos e unidades. `429`: limite; aguardar a
  orientação da resposta. `503`: serviço/fonte não disponível; não converter
  para ausência de risco.
- Em lotes, conferir sucessos e falhas antes de reenviar. No despacho e relato,
  reutilizar a chave de idempotência para a mesma tentativa; não gerar outra
  chave só porque a resposta se perdeu.
- Páginas usam `items`, `limit`/`offset` e `proximo_offset` quando previstos no
  contrato. Limites de exportação constam no manifesto/retorno; CSV não implica
  que todo o histórico ilimitado foi exportado.

## Interpretação

`null`/não informado não significa zero. Custos conhecidos, estimados, perda
potencial e economia comprovada são categorias diferentes. Fotografias guardam
o resultado de uma consulta passada; não autorizam decisão atual. Chuva simulada
não é previsão nem observação. Ausência de limite de ponte não garante passagem.

O endpoint de trânsito retorna `tempo_estimado_min` e `tempo_observado_min: null`
quando obtém uma rota do OSRM demo. A duração é uma estimativa de percurso, não
uma medição de trânsito ao vivo; `custo_consulta_usd: null` indica que não há
tarifa conhecida para lançar em custos. O contador em `/api/v1/transito/metricas`
mede tentativas de acesso ao demo neste processo, não uso faturado. Em produção,
`/comparar` responde `502` sem acessar o demo, até existir integração adequada
para trânsito observado. O [contrato de rotas do OSRM](https://project-osrm.org/docs/v5.24.0/api/)
define `duration` como tempo estimado; o [servidor demo](https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server)
é restrito a uso razoável e não comercial, sem garantia de disponibilidade.

O OpenAPI acrescenta descrições, segurança, exemplos de corpos e tipos de
download sem alterar handlers, validação ou cálculo. Seus exemplos de entrada
são validados automaticamente contra os modelos do backend.
