"""Metadados internos de fontes públicas e jobs; sem ações de escrita remotas."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Response
from app.database import get_connection
from app.seguranca import require_role, resolver_tenant_autenticado
from app.versao import informacao_versao

router=APIRouter(prefix='/api/v1/operacional',tags=['Painel operacional interno'],
    dependencies=[Depends(require_role(['ADMIN']))])


@router.get('/versao')
async def versao(response: Response):
    response.headers['Cache-Control']='no-store'
    return informacao_versao()


def idade(data, agora):
    if data is None or data.tzinfo is None:return None
    minutos=(agora-data).total_seconds()/60
    return round(minutos,1) if minutos>=0 else None


@router.get('/fontes')
async def fontes(response:Response,conn=Depends(get_connection)):
    response.headers['Cache-Control']='no-store'
    agora=datetime.now(timezone.utc)
    publicas=await conn.fetch('SELECT nome,ultimo_sucesso_em,registros_importados FROM fontes_dados_externos ORDER BY nome')
    meteorologia=await conn.fetch('''SELECT f.id_fonte,f.nome,f.tipo,f.frequencia_minutos,
        count(e.id_estacao)::int AS estacoes,
        count(l.data_referencia)::int AS com_leitura,
        min(l.data_referencia) AS referencia_mais_antiga,max(l.coletado_em) AS ultima_coleta,
        min(l.validade_ate) AS validade_mais_curta
        FROM fontes_meteorologicas f LEFT JOIN estacoes_meteorologicas e ON e.id_fonte=f.id_fonte AND e.ativa
        LEFT JOIN LATERAL (SELECT data_referencia,coletado_em,validade_ate FROM leituras_meteorologicas
            WHERE id_estacao=e.id_estacao ORDER BY data_referencia DESC LIMIT 1) l ON true
        GROUP BY f.id_fonte ORDER BY f.nome''')
    itens=[]
    for f in publicas:
        minutos=idade(f['ultimo_sucesso_em'],agora)
        itens.append({'id':f['nome'],'nome':f['nome'],'tipo':'DADOS_PUBLICOS','referencia_em':f['ultimo_sucesso_em'],
            'idade_minutos':minutos,'criterio':'Última importação bem-sucedida; critério agregado de 48 h, não SLA homologado.',
            'limite_minutos':2880,'status':'SEM_DATA_VALIDA' if minutos is None else 'ATRASADA' if minutos>2880 else 'NO_CRITERIO',
            'registros':f['registros_importados']})
    for f in meteorologia:
        minutos=idade(f['referencia_mais_antiga'],agora)
        limite=f['frequencia_minutos']
        expirou=f['validade_mais_curta'] is not None and f['validade_mais_curta']<agora
        status='SEM_DATA_VALIDA' if minutos is None else 'ATRASADA' if expirou or limite<=0 or minutos>limite else 'NO_CRITERIO'
        if f['com_leitura']<f['estacoes'] or not f['estacoes']:status='COBERTURA_INCOMPLETA'
        itens.append({'id':f['id_fonte'],'nome':f['nome'],'tipo':f['tipo'],'referencia_em':f['referencia_mais_antiga'],
            'ultima_coleta_em':f['ultima_coleta'],'validade_mais_curta':f['validade_mais_curta'],
            'idade_minutos':minutos,'limite_minutos':limite,'status':status,'estacoes':f['estacoes'],'com_leitura':f['com_leitura'],
            'criterio':'Referência mais antiga entre as últimas leituras de cada estação ativa; frequência cadastrada e validade explícita.'})
    corredor=await conn.fetchrow('''SELECT count(c.id_trecho)::int AS total,count(d.atualizado_em)::int AS com_leitura,
        min(d.atualizado_em) AS mais_antiga FROM corredor_sp_araraquara c
        LEFT JOIN condicoes_corredor d ON d.id_trecho=c.id_trecho''')
    minutos=idade(corredor['mais_antiga'],agora)
    itens.append({'id':'OPEN_METEO_CORREDOR','nome':'Open-Meteo / corredor de referência','tipo':'MODELO_METEOROLOGICO',
        'referencia_em':corredor['mais_antiga'],'idade_minutos':minutos,'limite_minutos':60,
        'status':'COBERTURA_INCOMPLETA' if not corredor['total'] or corredor['com_leitura']<corredor['total'] else
            'SEM_DATA_VALIDA' if minutos is None else 'ATRASADA' if minutos>60 else 'NO_CRITERIO',
        'criterio':'Atualização mais antiga entre os segmentos; critério de 60 min do relatório intermunicipal. Não é observação em campo.',
        'segmentos':corredor['total'],'com_leitura':corredor['com_leitura']})
    return {'consultado_em':agora,'fontes':itens,'escopo':'METADADOS_DE_FONTES_PUBLICAS',
        'integracoes':[{'nome':'Escrita automática CGE','status':'DESATIVADA','motivo':'Associação geográfica ainda não validada; endpoint de sincronização retorna 503.'}],
        'aviso':'Idade da importação não informa a idade de cada ocorrência. Dentro do critério não comprova cobertura ou segurança.'}


@router.get('/importacoes')
async def importacoes(response:Response,status:str|None=Query(None,pattern='^(EM_EXECUCAO|CONCLUIDO|PARCIAL|FALHA)$'),
    offset:int=Query(0,ge=0,le=100000),limite:int=Query(25,ge=1,le=100),
    tenant_id=Depends(resolver_tenant_autenticado),conn=Depends(get_connection)):
    response.headers['Cache-Control']='no-store'
    rows=await conn.fetch('''SELECT id,fonte,iniciado_em,encerrado_em,status,registros,falhas,motivo_codigo
        FROM monitor_importacoes WHERE ($1::text IS NULL OR status=$1) AND (tenant_id IS NULL OR tenant_id=$4)
        ORDER BY iniciado_em DESC,id DESC LIMIT $2 OFFSET $3''',status,limite+1,offset,tenant_id)
    inicio=await conn.fetchval('SELECT min(iniciado_em) FROM monitor_importacoes WHERE tenant_id IS NULL OR tenant_id=$1',tenant_id)
    return {'items':[dict(r) for r in rows[:limite]],'proximo_offset':offset+limite if len(rows)>limite else None,
        'primeiro_registro_em':inicio,'consultado_em':datetime.now(timezone.utc),
        'aviso':'Jobs públicos e lotes de operações desta empresa instrumentados a partir desta versão. Falhas anteriores não foram reconstruídas. EM_EXECUCAO sem término não confirma que o processo ainda está ativo. Importações de malha concluídas e erros HTTP têm registros separados.'}
