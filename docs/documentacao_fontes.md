DOCUMENTACAO DAS FONTES DE DADOS - SPRAIN B2B
===========================================

Complemento atualizado: [arquitetura-e-fontes.md](arquitetura-e-fontes.md).
As frequencias abaixo descrevem publicacao dos fornecedores, nao garantem coleta
ativa. O worker precisa estar implantado. Revalidar licencas/termos especificos;
disponibilidade publica nao implica permissao irrestrita de redistribuicao.

1. ARTESP (Acidentes Rodoviarios)
---------------------------------
- Origem: Portal de Dados Abertos da ARTESP (concessionarias do estado de Sao Paulo).
- Licenca e Restricoes: Dados abertos governamentais de uso publico com rastreabilidade obrigatoria de URL e hash.
- Frequencia de Atualizacao: Anual / Periodica conforme publicacao oficial.
- Cobertura: Rodovias concedidas do Estado de Sao Paulo (com destaque para corredores como SP-310 e SP-255).
- Limitacoes Conhecidas: Nao contem registros de alagamento ou interdicao direta; condicao meteorologica e informada apenas quando anotada no boletim do acidente.

2. ANP (Precos e Cadastro de Postos)
-----------------------------------
- Origem: Agencia Nacional do Petroleo, Gas Natural e Biocombustiveis (dados abertos e API cadastral).
- Licenca e Restricoes: Uso publico restrito a conformidade de procedencia e data de coleta.
- Frequencia_de_Atualizacao: Semanal / Mensal.
- Cobertura: Postos revendedores mapeados no Estado de Sao Paulo.
- Limitacoes Conhecidas: Coordenadas obtidas da API cadastral sao candidatas aproximadas e exigem validacao presencial ou por fonte secundaria para navegacao fina.

3. SSP (Estatisticas de Roubo de Carga)
--------------------------------------
- Origem: Secretaria da Seguranca Publica do Estado de Sao Paulo (relatorios trimestrais disjuntos).
- Licenca e Restricoes: Dados oficiais agregados por regiao policial e municipio.
- Frequencia de Atualizacao: Trimestral.
- Cobertura: Estado de Sao Paulo dividido em regioes policiais sem sobreposicao.
- Limitacoes Conhecidas: Agregados por area; nao localizam o roubo em uma rua ou ponto especifico de um trecho viario.

4. CGE e Open-Meteo (Meteorologia)
--------------------------------
- Origem: Centro de Gerenciamento de Emergencias de Sao Paulo (CGE) e API Open-Meteo.
- Licenca e Restricoes: Uso operacional condicionado a tolerancia de atraso e validade temporal.
- Frequencia de Atualizacao: Horaria / D-1.
- Cobertura: Estacoes representativas na regiao metropolitana e corredores logísticos.
- Limitacoes Conhecidas: Ausencia de leitura de estacao nao equivale a ausencia de chuva; fontes desativadas retornam limitacao explicita sem substituição silenciosa.
