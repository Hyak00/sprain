"""Enriquece o OpenAPI sem alterar handlers, validação ou autorização."""
from fastapi.openapi.utils import get_openapi

PUBLICOS={'/api/v1/health/liveness','/api/v1/health/readiness','/api/v1/acesso/configuracao',
    '/api/v1/acesso/login','/api/v1/logistica/auth/login','/api/v1/administracao/recuperacao/solicitar',
    '/api/v1/administracao/recuperacao/concluir','/api/v1/demonstracao/estado'}

MEDIDAS={'altura_m':3,'largura_m':2.4,'comprimento_m':8,'peso_total_t':10,'eixos':2}
EXEMPLOS={
 'PrimeiroResultado':{'consulta_id':'00000000-0000-4000-8000-000000000001'},
 'Acompanhamento':{'operacoes':['EXEMPLO_OP_001']},
 'Login':{'email':'operador@cliente.example','senha':'EXEMPLO_NAO_USAR_COMO_SENHA'},
 'LoginCorporativoRequest':{'email':'operacional@democorp.com.br','senha':'EXEMPLO_APENAS_AMBIENTE_DEMO'},
 'NovoUsuario':{'email':'leitor@cliente.example','senha':'EXEMPLO_NAO_USAR_COMO_SENHA','papel':'VIEWER'},
 'MudancaPapel':{'papel':'OPERATOR'},
 'Financeiro':{'versao':0,'custos':{'consumo_km_l':3,'custo_por_km_sem_combustivel':1.5}},
 'Email':{'email':'operador@cliente.example'},
 'Liberacao':{'identidade_conferida':True},
 'Recuperar':{'email':'operador@cliente.example','codigo':'EXEMPLO_CODIGO_INUTILIZAVEL','senha':'EXEMPLO_NAO_USAR_COMO_SENHA'},
 'Corredor':{'nome':'Corredor de exemplo','origem_nome':'Origem sintética','origem_lat':-22.25,'origem_lon':-47.84,
     'destino_nome':'Destino sintético','destino_lat':-22.25,'destino_lon':-47.82,'ativo':True,'dimensoes_referencia':MEDIDAS},
 'Recorrencia':{'nome':'Segundas de exemplo','dias_semana':[0],'horario_local':'08:00','janela_minutos':240,'dimensoes':MEDIDAS},
 'Despacho':{'data_local':'2026-10-19','chave_idempotencia':'00000000-0000-4000-8000-000000000001'},
 'Consulta':{'id_operacao':'EXEMPLO_OP_001'},
 'Premissas':{'selo_esperado':'0'*64,'custos_operacionais':{'custo_por_km':4.5},'precipitacao_mm':35},
 'Relato':{'categoria':'ALAGAMENTO','descricao':'Relato sintético pendente de verificação','ocorrido_em':'2026-10-17T08:00:00-03:00','latitude':-23.54,'longitude':-46.46},
 'Etapa':{'etapa':'BLOQUEIO'},
 'DecisaoGestorRequest':{'decisao':'AGUARDAR_MELHORA','motivo_gestor':'Exemplo: aguardar confirmação da fonte'},
 'SimulacaoB2BRequest':{'precipitacao_mm':35,'parametros_custo':{'prejuizo_potencial_alagamento':1250}},
 'VeiculoCreate':{'id_veiculo':'EXEMPLO_TRK','placa':'EXE0001','modelo':'Exemplo sintético','tipo_veiculo':'VUC','dimensoes':MEDIDAS},
}

GRUPOS={
 'acesso':'Acesso individual e gestão de usuários. Sessão revogável em memória no cliente; alterações de papel/desativação invalidam sessões. Gestão exige ADMIN individual da mesma empresa.',
 'administracao':'Configuração versionada, recuperação assistida e exportação privada da empresa. Não há envio automático de e-mail. Escritas administrativas exigem ADMIN individual; dados ausentes não são inventados.',
 'painel':'Fluxos persistentes por empresa: corredores, recorrências, consultas, relatos e relatórios. Despacho é explícito; não há agendamento automático. Valores financeiros são estimativas de planejamento.',
 'operacional':'Metadados de fontes públicas e auditoria das importações acessíveis a ADMIN. Registros privados permanecem restritos à empresa; histórico começa na instrumentação, sem reconstrução de falhas antigas.',
 'demonstracao':'Exercício sintético em banco reservado e ambiente não produtivo. Referência histórica pesquisada não equivale ao evento fornecido pela equipe. Sem alertas globais nem economia comprovada.',
 'dados-publicos':'Conjuntos importados de fontes oficiais. Histórico e contexto agregado não equivalem a condições ao vivo. Datas de coleta, origem e cobertura devem ser avaliadas antes de usar os dados.',
 'infraestrutura':'Malha e infraestrutura conhecidas, com restrições físicas, pedágios e cobertura parcial. Medidas reais do caminhão e sinalização vigente precisam ser conferidas; ausência de restrição não confirma passagem.',
 'logistica':'Operações e recomendações da empresa autenticada. Simulação de chuva não é observação; custos conhecidos, estimados e perdas potenciais devem ser distinguidos. Aprovação revalida a alternativa disponível.',
 'health':'Sondas de vivacidade e prontidão. Readiness verifica banco, extensão e estrutura/malha, sem garantir a atualidade dos provedores externos.',
 'indicadores':'Indicadores declarados pela base importada; prazo agregado não é SLA homologado. Sem amostra ou data válida não há comprovação de precisão/atualidade.',
 'alertas':'Feedback da empresa e métricas com amostra visível. Não representam validação independente nem probabilidade calibrada de um evento ocorrer.',
}

DETALHES={
 ('post','/api/v1/painel/consultas'):'Consulta com gravação de fotografia: permitida a ADMIN, OPERATOR e VIEWER. O retorno vincula consulta.id à explicação usada na decisão.',
 ('put','/api/v1/painel/operacoes/{identificador}/premissas'):'Recálculo transacional com selo de concorrência. Conflito retorna 409; não sobrescreva nem repita com selo antigo.',
 ('post','/api/v1/painel/recorrencias/{identificador}/despachar'):'Cria uma viagem na data local com chave de idempotência. Repetição da mesma chave/data reutiliza a viagem; confira o campo reutilizado.',
 ('post','/api/v1/logistica/operacoes/importar-lote'):'Importação não atômica com sucessos, falhas e detalhe por item. Uma resposta parcial pode ter gravado operações; consulte antes de reenviar. Auditoria registra contagens por empresa.',
 ('get','/api/v1/logistica/exportar-contingencia/csv'):'CSV de contingência restrito a ADMIN/OPERATOR. VIEWER pode exportar os históricos de consultas e decisões pelos endpoints de relatórios do painel.',
 ('get','/api/v1/administracao/exportacao'):'ZIP privado com manifesto e JSON Lines, limitado pela API. Inclui somente dados autorizados da empresa; exclui senhas, tokens, outras empresas e bases públicas compartilhadas.',
 ('post','/api/v1/administracao/recuperacao/solicitar'):'Resposta pública genérica para evitar enumeração de contas. ADMIN precisa conferir a identidade e liberar código de uso único, entregue por canal privado.',
}


def instalar(app):
    def documentacao():
        if app.openapi_schema:return app.openapi_schema
        schema=get_openapi(title=app.title,version=app.version,routes=app.routes,
            description=app.description+'\n\nUse Authorize com X-API-Key (sessão individual ou chave de integração). Exemplos são sintéticos; não execute mutações contra produção para testar. Consulte docs/api-painel.md no repositório.',tags=app.openapi_tags)
        schema.setdefault('components',{}).setdefault('securitySchemes',{})['SessaoOuChave']={
            'type':'apiKey','in':'header','name':'X-API-Key','description':'Sessão individual retornada no login ou chave de integração autorizada. Nunca coloque credenciais em URL, issues ou relatórios.'}
        modelos=schema['components'].get('schemas',{})
        for nome,exemplo in EXEMPLOS.items():
            if nome in modelos:modelos[nome]['examples']=[exemplo]
        for caminho,metodos in schema['paths'].items():
            if not caminho.startswith('/api/v1/'):continue
            grupo=caminho.split('/')[3]
            for metodo,operacao in metodos.items():
                if metodo not in ('get','post','put','patch','delete'):continue
                contexto=GRUPOS.get(grupo,'Contrato operacional do SPRain. Confira perfil, empresa, fonte, data e limites na resposta. Ausência de informação não confirma segurança ou custo zero.')
                extra=DETALHES.get((metodo,caminho),'')
                operacao['description']='\n\n'.join(filter(None,[operacao.get('description'),contexto,extra]))
                protegido=caminho not in PUBLICOS
                operacao['security']=[{'SessaoOuChave':[]}] if protegido else []
                if protegido:
                    for codigo,mensagem in [('401','Autenticação ausente, inválida ou sessão expirada.'),('403','Perfil, empresa ou tipo de acesso não autorizado.')]:
                        operacao['responses'].setdefault(codigo,{'description':mensagem,'content':{'application/json':{'example':{'detail':mensagem}}}})
                corpo=operacao.get('requestBody',{}).get('content',{}).get('application/json')
                if corpo:
                    ref=corpo.get('schema',{}).get('$ref','').split('/')[-1]
                    exemplos=modelos.get(ref,{}).get('examples')
                    if exemplos:corpo['examples']={'sintetico':{'summary':'Exemplo sintético; substitua IDs e confira versão/datas','value':exemplos[0]}}
                if caminho.endswith(('.csv','/csv')):
                    operacao['responses']['200']={'description':'CSV UTF-8 para download; confira separador e semântica no guia da API.',
                        'content':{'text/csv':{'schema':{'type':'string'}}}}
                if caminho=='/api/v1/administracao/exportacao':
                    operacao['responses']['200']={'description':'Arquivo ZIP privado com manifesto e JSON Lines. Sem credenciais ou dados de outras empresas.',
                        'content':{'application/zip':{'schema':{'type':'string','format':'binary'}}}}
        for caminho,exemplo in {
            '/api/v1/health/liveness':{'status':'UP','timestamp':1792234800,'servico':'sprain_api'},
            '/api/v1/health/readiness':{'status':'READY','banco':'sprain_db','postgis':'OPERACIONAL','total_trechos_osm':4,'latencia_db_ms':2.5},
            '/api/v1/demonstracao/estado':{'modo':'DEMONSTRACAO_ISOLADA','demo_isolada':True,'aviso':'Exemplo sintético, sem uso operacional.'},
            '/api/v1/painel/corredores':{'items':[],'proximo_offset':None},
            '/api/v1/operacional/importacoes':{'items':[],'proximo_offset':None,'primeiro_registro_em':None,'consultado_em':'2026-10-17T12:00:00Z','aviso':'Histórico começa na instrumentação.'},
        }.items():
            schema['paths'][caminho]['get']['responses']['200'].setdefault('content',{}).setdefault('application/json',{})['example']=exemplo
        app.openapi_schema=schema
        return schema
    app.openapi=documentacao
