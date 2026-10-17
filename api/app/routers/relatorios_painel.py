"""Relatórios da empresa: leituras consistentes, sem recalcular nem alterar decisões."""
import csv
import json
import math
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from app.database import get_connection
from app.seguranca import get_current_user_claims, require_role, is_production
from app.services.demonstracao import habilitada as demo_habilitada

router=APIRouter(prefix='/api/v1/painel/relatorios',tags=['Relatórios do painel'],
    dependencies=[Depends(require_role(['ADMIN','OPERATOR','VIEWER']))])


def ambiente_relatorio():
    return 'PRODUCAO' if is_production() else 'DEMONSTRACAO_ISOLADA' if demo_habilitada() else 'NAO_PRODUCAO'


def periodo(inicio, fim):
    if bool(inicio)!=bool(fim) or fim==date.max or (inicio and (fim<inicio or (fim-inicio).days>365)):
        raise HTTPException(422,'Informe início e fim, em ordem e com até 366 dias; ou deixe ambos vazios.')
    fuso=ZoneInfo('America/Sao_Paulo')
    return (datetime.combine(inicio,time.min,fuso) if inicio else None,
        datetime.combine(fim+timedelta(days=1),time.min,fuso) if fim else None)


def objeto(v):
    return json.loads(v) if isinstance(v,str) else (v or {})


def numero(v):
    return isinstance(v,(int,float,Decimal)) and not isinstance(v,bool) and math.isfinite(v)


def alternativa(s):
    geo=(s.get('geometrias') or {}).get('rota_alternativa_geojson') or {}
    return s.get('validacao_rota',{}).get('rota_alternativa_disponivel') is True and any(
        f.get('geometry',{}).get('type') in ('LineString','MultiLineString') and f['geometry'].get('coordinates')
        for f in geo.get('features',[]))


@router.get('/piloto')
async def piloto(response: Response,inicio: date|None=None,fim: date|None=None,
    claims=Depends(get_current_user_claims),conn=Depends(get_connection)):
    de,ate=periodo(inicio,fim)
    response.headers['Cache-Control']='no-store'
    async with conn.transaction(isolation='repeatable_read',readonly=True):
        r=await conn.fetchrow('''SELECT count(*)::int AS operacoes,
            count(o.custo_estimado) FILTER(WHERE o.custo_estimado>=0 AND o.custo_estimado::text NOT IN ('NaN','Infinity'))::int AS custos,
            SUM(o.custo_estimado) FILTER(WHERE o.custo_estimado>=0 AND o.custo_estimado::text NOT IN ('NaN','Infinity')) AS estimado,
            count(r.id_recomendacao)::int AS recomendacoes,
            count(r.prejuizo_potencial_evitado) FILTER(WHERE r.prejuizo_potencial_evitado>=0 AND r.prejuizo_potencial_evitado::text NOT IN ('NaN','Infinity'))::int AS impactos,
            SUM(r.prejuizo_potencial_evitado) FILTER(WHERE r.prejuizo_potencial_evitado>=0 AND r.prejuizo_potencial_evitado::text NOT IN ('NaN','Infinity')) AS impacto,
            min(o.criado_em) AS primeira_operacao,max(o.criado_em) AS ultima_operacao,
            max(r.gerado_em) AS ultimo_calculo
            FROM operacoes o LEFT JOIN LATERAL (
                SELECT id_recomendacao,prejuizo_potencial_evitado,gerado_em FROM recomendacoes_operacao
                WHERE tenant_id=o.tenant_id AND id_operacao=o.id_operacao ORDER BY id_recomendacao DESC LIMIT 1
            ) r ON true WHERE o.tenant_id=$1 AND ($2::timestamptz IS NULL OR o.criado_em>=$2)
            AND ($3::timestamptz IS NULL OR o.criado_em<$3)''',claims['tenant_id'],de,ate)
        consultas=await conn.fetchval('''SELECT count(*) FROM painel_consultas WHERE tenant_id=$1
            AND ($2::timestamptz IS NULL OR criado_em>=$2) AND ($3::timestamptz IS NULL OR criado_em<$3)''',claims['tenant_id'],de,ate)
        decisoes=await conn.fetchval('''SELECT count(*) FROM decisoes_gestor_operacao WHERE tenant_id=$1
            AND ($2::timestamptz IS NULL OR registrado_em>=$2) AND ($3::timestamptz IS NULL OR registrado_em<$3)''',claims['tenant_id'],de,ate)
    return {'empresa':claims['tenant_id'],'ambiente':ambiente_relatorio(),'emitido_em':datetime.now(timezone.utc),
        'periodo':{'inicio':inicio,'fim':fim,'fuso':'America/Sao_Paulo',
            'criterio':'Operações pela criação; consultas e decisões pelo registro. Última recomendação de cada operação na emissão, sem duplicar recálculos.'},
        'amostra':{**dict(r),'consultas':consultas,'decisoes':decisoes},
        'indicadores':{
            'economia_comprovada':{'valor_brl':None,'natureza':'NAO_DISPONIVEL','motivo':'Não há medição auditada de execução nem contrafactual validado neste cadastro.'},
            'custo_observado':{'valor_brl':None,'natureza':'NAO_DISPONIVEL','motivo':'O cadastro não contém comprovantes de despesas efetivamente realizadas.'},
            'custo_estimado':{'valor_brl':float(round(r['estimado'],2)) if r['custos'] else None,
                'natureza':'ESTIMATIVA_PARCIAL','operacoes_com_valor':r['custos'],'operacoes_sem_valor':r['operacoes']-r['custos'],
                'fonte':'operacoes.custo_estimado: parcelas de planejamento conhecidas da rota original, na emissão.'},
            'impacto_potencial':{'valor_brl':float(round(r['impacto'],2)) if r['impactos'] else None,
                'natureza':'POTENCIAL_NAO_COMPROVADO','operacoes_com_valor':r['impactos'],'operacoes_sem_valor':r['operacoes']-r['impactos'],
                'fonte':'prejuizo_potencial_evitado da última recomendação por operação; não representa perda efetivamente evitada.'}},
        'limitacoes':['Valores ausentes não são tratados como zero. Totais parciais indicam a cobertura.',
            'O custo estimado refere-se à rota original; não é soma de desvios nem custo observado.',
            'Tarifas, combustível e restrições têm cobertura e validade próprias; estimativas não confirmam passagem segura.',
            'Simulações e recomendações não comprovam execução, economia ou causalidade.',
            'Aprovar uma decisão não comprova que a viagem foi realizada.'],
        'fontes':['operacoes','recomendacoes_operacao (somente a última por operação)','painel_consultas','decisoes_gestor_operacao']}


@router.get('/decisoes')
async def decisoes(response:Response,id_operacao:str|None=Query(None,max_length=200),
    inicio:date|None=None,fim:date|None=None,offset:int=Query(0,ge=0),
    claims=Depends(get_current_user_claims),conn=Depends(get_connection)):
    de,ate=periodo(inicio,fim);response.headers['Cache-Control']='no-store'
    rows=await conn.fetch('''SELECT id_decisao,id_operacao,decisao,motivo_gestor,registrado_em,consulta_id,usuario_id,perfil_registro
        FROM decisoes_gestor_operacao WHERE tenant_id=$1 AND ($2::text IS NULL OR id_operacao=$2)
        AND ($3::timestamptz IS NULL OR registrado_em>=$3) AND ($4::timestamptz IS NULL OR registrado_em<$4)
        ORDER BY registrado_em DESC,id_decisao DESC OFFSET $5 LIMIT 21''',claims['tenant_id'],id_operacao,de,ate,offset)
    return {'items':[dict(r) for r in rows[:20]],'proximo_offset':offset+20 if len(rows)>20 else None}


@router.get('/decisoes/{identificador}')
async def decisao(identificador:int,response:Response,claims=Depends(get_current_user_claims),conn=Depends(get_connection)):
    response.headers['Cache-Control']='no-store'
    r=await conn.fetchrow('''SELECT d.*,c.snapshot AS consulta_snapshot FROM decisoes_gestor_operacao d
        LEFT JOIN painel_consultas c ON c.id=d.consulta_id AND c.tenant_id=d.tenant_id AND c.id_operacao=d.id_operacao
        WHERE d.id_decisao=$1 AND d.tenant_id=$2''',identificador,claims['tenant_id'])
    if not r:raise HTTPException(404,'Decisão não encontrada.')
    d=dict(r);salvo=objeto(d.pop('snapshot'));vinculado=objeto(d.pop('consulta_snapshot'))
    snapshot=salvo or vinculado or None
    return {'empresa':claims['tenant_id'],'ambiente':ambiente_relatorio(),'emitido_em':datetime.now(timezone.utc),'decisao':d,'snapshot':snapshot,
        'fonte_snapshot':'decisao.snapshot' if salvo else 'consulta.snapshot vinculada' if vinculado else None,
        'limitacoes':['Decisão registrada não comprova execução ou economia real.']+(
            [] if snapshot else ['Registro legado sem fotografia. Valores e condições da época são desconhecidos; a consulta atual não é usada como substituta.'])}


def celula(v):
    if v is None:return ''
    if isinstance(v,(dict,list)):v=json.dumps(v,ensure_ascii=False,default=str)
    if hasattr(v,'isoformat'):v=v.isoformat()
    s=str(v)
    return "'"+s if not numero(v) and s.lstrip().startswith(('=','+','-','@','\t','\r')) else s


def valores_snapshot(s):
    f=s.get('infraestrutura',{}).get('financeiro') or {};m=s.get('metricas') or {};c=s.get('contexto_consulta') or {}
    alt=alternativa(s)
    return [c.get('id_recomendacao'),c.get('calculo_gerado_em'),c.get('natureza'),c.get('fonte'),s.get('acao_recomendada'),
        s.get('confianca'),m.get('distancia_original_km'),m.get('tempo_original_min'),
        m.get('distancia_alternativa_km') if alt else None,m.get('tempo_alternativo_min') if alt else None,
        f.get('custo_original_conhecido_brl'),f.get('custo_alternativa_conhecido_brl') if alt else None,
        f.get('custo_desvio_brl') if alt else None,f.get('prejuizo_potencial_evitado_brl') if alt else None,
        f.get('tarifas_pendentes_comparacao'),f.get('premissas'),s.get('validacao_rota',{}).get('avisos_limitacao')]


COLUNAS=['recomendacao_id','calculo_gerado_em','natureza_cenario','fonte','recomendacao','confianca',
    'original_km','original_min','alternativa_km','alternativa_min','custo_original_estimado_brl',
    'custo_alternativo_estimado_brl','delta_custo_estimado_brl','impacto_potencial_brl',
    'tarifas_pendentes','premissas_json','limitacoes_json']


async def exportar_csv(conn,tenant,tipo,de,ate,op,consulta=None):
    emitido=datetime.now(timezone.utc).isoformat()
    ambiente=ambiente_relatorio()
    cab=['empresa','ambiente','emitido_em','id_consulta','operacao','registrado_em','usuario_id','perfil'] if tipo=='consultas' else [
        'empresa','ambiente','emitido_em','id_decisao','operacao','registrado_em','usuario_id','perfil','decisao','motivo','id_consulta','fonte_snapshot']
    if tipo=='consultas':
        sql='''SELECT * FROM painel_consultas WHERE tenant_id=$1 AND ($2::timestamptz IS NULL OR criado_em>=$2)
            AND ($3::timestamptz IS NULL OR criado_em<$3) AND ($4::text IS NULL OR id_operacao=$4)
            AND ($5::uuid IS NULL OR id=$5) ORDER BY criado_em,id'''
    else:
        sql='''SELECT d.*,c.snapshot AS consulta_snapshot FROM decisoes_gestor_operacao d
            LEFT JOIN painel_consultas c ON c.id=d.consulta_id AND c.tenant_id=d.tenant_id AND c.id_operacao=d.id_operacao
            WHERE d.tenant_id=$1 AND ($2::timestamptz IS NULL OR d.registrado_em>=$2)
            AND ($3::timestamptz IS NULL OR d.registrado_em<$3) AND ($4::text IS NULL OR d.id_operacao=$4)
            ORDER BY d.registrado_em,d.id_decisao'''
    class SaidaLimitada:
        def __init__(self):self.partes=[];self.tamanho=0
        def write(self,texto):
            self.tamanho+=len(texto.encode('utf-8'))
            if self.tamanho>8*1024*1024:raise HTTPException(413,'CSV excede 8 MB. Reduza o período ou escolha uma operação.')
            self.partes.append(texto)
            return len(texto)
    saida=SaidaLimitada();writer=csv.writer(saida,delimiter=';',lineterminator='\r\n');writer.writerow(cab+COLUNAS+['economia_comprovada_brl','custo_observado_brl','aviso'])
    async with conn.transaction(isolation='repeatable_read',readonly=True):
        n=0
        parametros=(tenant,de,ate,op,consulta) if tipo=='consultas' else (tenant,de,ate,op)
        async for row in conn.cursor(sql,*parametros,prefetch=100):
            n+=1
            if n>10000:raise HTTPException(413,'Mais de 10 mil registros. Reduza o período ou escolha uma operação.')
            s=objeto(row['snapshot'])
            if tipo=='consultas':
                base=[tenant,ambiente,emitido,row['id'],row['id_operacao'],row['criado_em'],s.get('contexto_consulta',{}).get('autoria_individual'),row['perfil']]
            else:
                fonte='decisao.snapshot' if s else 'consulta.snapshot vinculada' if row['consulta_snapshot'] else None
                s=s or objeto(row['consulta_snapshot'])
                base=[tenant,ambiente,emitido,row['id_decisao'],row['id_operacao'],row['registrado_em'],row['usuario_id'],row['perfil_registro'],row['decisao'],row['motivo_gestor'],row['consulta_id'],fonte]
            writer.writerow([celula(v) for v in base+valores_snapshot(s)+[None,None,
                'Planejamento não comprova execução ou economia. '+('Fotografia histórica disponível.' if s else 'Sem fotografia; valores da época desconhecidos.')]])
    return Response('\ufeff'+''.join(saida.partes),media_type='text/csv; charset=utf-8',
        headers={'Cache-Control':'no-store','Content-Disposition':f'attachment; filename="sprain-{tipo}.csv"'})


@router.get('/consultas.csv')
async def consultas_csv(inicio:date|None=None,fim:date|None=None,id_operacao:str|None=Query(None,max_length=200),id_consulta:UUID|None=None,
    claims=Depends(get_current_user_claims),conn=Depends(get_connection)):
    return await exportar_csv(conn,claims['tenant_id'],'consultas',*periodo(inicio,fim),id_operacao,id_consulta)


@router.get('/decisoes.csv')
async def decisoes_csv(inicio:date|None=None,fim:date|None=None,id_operacao:str|None=Query(None,max_length=200),
    claims=Depends(get_current_user_claims),conn=Depends(get_connection)):
    return await exportar_csv(conn,claims['tenant_id'],'decisoes',*periodo(inicio,fim),id_operacao)
