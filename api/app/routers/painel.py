"""Fluxo persistente do painel sem substituir os endpoints e motores existentes."""
import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.database import get_connection
from app.schemas import CustosCaminhao, OperacaoCreate
from app.schemas_infraestrutura import VeiculoDimensoes
from app.seguranca import get_current_user_claims, require_role
from app.services.painel import objeto, registrar_consulta, selo, serializar
from app.services.cotas_plano import verificar_cota
from app.services.routing_engine import RoutingEngine

router = APIRouter(prefix='/api/v1/painel', tags=['Fluxo persistente do painel'],
                   dependencies=[Depends(require_role(['ADMIN', 'OPERATOR', 'VIEWER']))])
escrita = Depends(require_role(['ADMIN', 'OPERATOR']))


class PrimeiroResultado(BaseModel):
    model_config = ConfigDict(extra='forbid')
    consulta_id: UUID


class Acompanhamento(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operacoes: list[str] = Field(min_length=1,max_length=500)


@router.post('/acompanhamento')
async def acompanhar_operacoes(dados: Acompanhamento, claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    """Leitura para todos os perfis: existência de decisão no histórico das viagens exibidas.

    Não confirma que uma decisão passada continue válida para o cenário atual.
    Registros de outra empresa não são retornados.
    """
    if any(not op or len(op)>200 for op in dados.operacoes):
        raise HTTPException(422,'Identificador de operacao invalido.')
    rows=await conn.fetch('''SELECT o.id_operacao,
        EXISTS(SELECT 1 FROM decisoes_gestor_operacao d WHERE d.tenant_id=o.tenant_id
            AND d.id_operacao=o.id_operacao) AS possui_decisao
        FROM operacoes o WHERE o.tenant_id=$1 AND o.id_operacao=ANY($2::text[])''',
        claims['tenant_id'],list(set(dados.operacoes)))
    return {'items':[dict(r) for r in rows],'criterio':'Existência de decisão no histórico; não valida uma decisão passada no cenário atual.'}


async def estado_onboarding(conn, tenant):
    row = await conn.fetchrow('SELECT * FROM painel_onboarding WHERE tenant_id=$1', tenant)
    totais = await conn.fetchrow('''SELECT
        (SELECT count(*) FROM veiculos WHERE tenant_id=$1) AS caminhoes,
        (SELECT count(*) FROM painel_corredores WHERE tenant_id=$1 AND dados->>'ativo'='true') AS corredores,
        (SELECT count(*) FROM operacoes WHERE tenant_id=$1) AS viagens,
        EXISTS(SELECT 1 FROM painel_financeiro WHERE tenant_id=$1) AS financeiro''', tenant)
    estado = serializar(row) if row else None
    if estado:
        estado['consulta_id'] = str(row['consulta_id']) if row['consulta_id'] else None
        estado['usuario_id'] = str(row['usuario_id']) if row['usuario_id'] else None
        estado['tempo_ate_primeiro_resultado_segundos'] = (
            (row['primeiro_resultado_em']-row['iniciado_em']).total_seconds()
            if row['primeiro_resultado_em'] else None)
    return {'empresa':tenant,'onboarding':estado,'cadastros':dict(totais),
        'criterio':'Tempo do início explícito até confirmar uma comparação consultada após esse início. '
                   'Não comprova viagem realizada, economia, qualidade das medidas ou cobertura das fontes.'}


@router.get('/onboarding')
async def consultar_onboarding(claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    """Progresso observado nos cadastros e medição persistente, restritos à empresa."""
    return await estado_onboarding(conn, claims['tenant_id'])


@router.post('/onboarding/iniciar', dependencies=[escrita])
async def iniciar_onboarding(claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    """Inicia a medição pelo relógio do servidor; repetição não reinicia o prazo."""
    await conn.execute('INSERT INTO painel_onboarding(tenant_id) VALUES($1) ON CONFLICT DO NOTHING', claims['tenant_id'])
    return await estado_onboarding(conn, claims['tenant_id'])


@router.post('/onboarding/primeiro-resultado', dependencies=[escrita])
async def confirmar_primeiro_resultado(dados: PrimeiroResultado, claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    """Confirma uma fotografia da própria empresa com rota original calculada.

    Sem onboarding iniciado: 409. Consulta de outra empresa: 404. Consulta antiga
    ou sem geometria/distância: 422. A primeira confirmação é preservada.
    """
    tenant = claims['tenant_id']
    async with conn.transaction():
        estado = await conn.fetchrow('SELECT * FROM painel_onboarding WHERE tenant_id=$1 FOR UPDATE', tenant)
        if not estado:
            raise HTTPException(409, 'Inicie a configuração do cliente em Primeiros passos antes de confirmar.')
        consulta = await conn.fetchrow('SELECT * FROM painel_consultas WHERE id=$1 AND tenant_id=$2', dados.consulta_id, tenant)
        if not consulta:
            raise HTTPException(404, 'Consulta nao encontrada nesta empresa.')
        snapshot = objeto(consulta['snapshot'])
        distancia = snapshot.get('metricas',{}).get('distancia_original_km')
        geometrias = snapshot.get('geometrias',{}).get('rota_original_geojson') or {}
        rota = any((f.get('geometry') or {}).get('type') in ('LineString','MultiLineString')
                   and (f.get('geometry') or {}).get('coordinates') for f in (geometrias.get('features') or []) if isinstance(f,dict))
        if (consulta['criado_em'] < estado['iniciado_em'] or isinstance(distancia,bool)
                or not isinstance(distancia,(int,float)) or distancia <= 0 or not rota):
            raise HTTPException(422, 'Abra uma viagem após iniciar a configuração e confira uma rota calculada antes de confirmar.')
        if not estado['primeiro_resultado_em']:
            await conn.execute('''UPDATE painel_onboarding SET primeiro_resultado_em=now(),
                consulta_id=$2,usuario_id=$3 WHERE tenant_id=$1''',tenant,dados.consulta_id,claims.get('usuario_id'))
        return await estado_onboarding(conn, tenant)


class Corredor(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, str_strip_whitespace=True)
    nome: str = Field(min_length=1, max_length=150)
    origem_nome: str = Field(min_length=1, max_length=200)
    origem_lat: float = Field(ge=-90, le=90)
    origem_lon: float = Field(ge=-180, le=180)
    destino_nome: str = Field(min_length=1, max_length=200)
    destino_lat: float = Field(ge=-90, le=90)
    destino_lon: float = Field(ge=-180, le=180)
    ativo: bool = True
    dimensoes_referencia: VeiculoDimensoes | None = None
    versao: int | None = Field(default=None, ge=1)


class Recorrencia(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    nome: str = Field(min_length=1, max_length=150)
    dias_semana: list[int] = Field(min_length=1, max_length=7, description='Segunda=0, domingo=6; sem duplicatas')
    horario_local: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    janela_minutos: int = Field(ge=1, le=2880)
    id_veiculo: str | None = Field(default=None, max_length=100)
    dimensoes: VeiculoDimensoes | None = None
    custos_operacionais: CustosCaminhao = Field(default_factory=CustosCaminhao)
    ativo: bool = True
    versao: int | None = Field(default=None, ge=1)

    @model_validator(mode='after')
    def dias_validos(self):
        if len(set(self.dias_semana)) != len(self.dias_semana) or any(d < 0 or d > 6 for d in self.dias_semana):
            raise ValueError('Dias devem ser distintos entre 0 e 6.')
        return self


class Despacho(BaseModel):
    model_config = ConfigDict(extra='forbid')
    data_local: date
    chave_idempotencia: UUID


class Consulta(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id_operacao: str = Field(min_length=1, max_length=200)


class Premissas(BaseModel):
    model_config = ConfigDict(extra='forbid')
    selo_esperado: str = Field(min_length=64, max_length=64)
    custos_operacionais: CustosCaminhao
    precipitacao_mm: float = Field(ge=0, le=250, allow_inf_nan=False, description='Chuva explicitamente escolhida para este recalculo simulado')


class Relato(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, str_strip_whitespace=True)
    categoria: Literal['ALAGAMENTO', 'TRANSITO', 'PONTE', 'OUTRO']
    descricao: str = Field(min_length=5, max_length=1000)
    ocorrido_em: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    chave_idempotencia: UUID | None = None

    @model_validator(mode='after')
    def horario(self):
        if self.ocorrido_em.tzinfo is None or self.ocorrido_em > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError('Informe horario com fuso, sem data futura.')
        return self


async def corredor(conn, tenant, identificador):
    row = await conn.fetchrow('SELECT * FROM painel_corredores WHERE id=$1 AND tenant_id=$2', identificador, tenant)
    if not row:
        raise HTTPException(404, 'Corredor nao encontrado.')
    return row


async def validar_rota(conn, tenant, dados, recorrencia=None):
    dims = recorrencia.dimensoes.model_dump() if recorrencia and recorrencia.dimensoes else None
    tipo = 'VUC'
    if recorrencia and recorrencia.id_veiculo:
        veiculo = await conn.fetchrow('SELECT tipo_veiculo,dimensoes FROM veiculos WHERE id_veiculo=$1 AND tenant_id=$2', recorrencia.id_veiculo, tenant)
        if not veiculo:
            raise HTTPException(422, 'Veiculo nao cadastrado nesta empresa.')
        tipo = veiculo['tipo_veiculo']
        dims = dims or objeto(veiculo['dimensoes'])
    elif not dims:
        dims = dados.get('dimensoes_referencia')
    rota = await RoutingEngine.compute_route(conn, dados['origem_lon'], dados['origem_lat'], dados['destino_lon'], dados['destino_lat'],
        profile='FASTEST', rain_mm=0.0, tipo_veiculo=tipo, tenant_id=tenant, vehicle_dimensions=dims)
    if not rota:
        raise HTTPException(422, 'Sem rota na malha disponivel para este cadastro. Confira coordenadas e medidas.')
    return rota


@router.get('/corredores')
async def listar_corredores(offset: int = Query(0, ge=0), limite: int = Query(20, ge=1, le=100),
    claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    rows = await conn.fetch('SELECT * FROM painel_corredores WHERE tenant_id=$1 ORDER BY atualizado_em DESC,id OFFSET $2 LIMIT $3', claims['tenant_id'], offset, limite+1)
    items = [serializar(r) for r in rows[:limite]]
    rs = await conn.fetch('SELECT * FROM painel_recorrencias WHERE corredor_id=ANY($1::uuid[]) AND tenant_id=$2 ORDER BY criado_em,id',
                          [UUID(i['id']) for i in items], claims['tenant_id']) if items else []
    for item in items:
        item['recorrencias'] = [serializar(r) for r in rs if str(r['corredor_id'])==item['id']]
    return {'items': items, 'proximo_offset': offset+limite if len(rows)>limite else None, 'fuso': 'America/Sao_Paulo'}


@router.post('/corredores', dependencies=[escrita])
async def criar_corredor(dados: Corredor, claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    config = dados.model_dump(exclude={'versao'})
    rota = await validar_rota(conn, claims['tenant_id'], config)
    async with conn.transaction():
        if dados.ativo:
            await verificar_cota(conn, claims['tenant_id'], 'corredores')
        row = await conn.fetchrow('''INSERT INTO painel_corredores(id,tenant_id,dados,geometria)
            VALUES($1,$2,$3::jsonb,$4::jsonb) RETURNING *''', uuid4(), claims['tenant_id'], json.dumps(config), json.dumps(rota['geojson']))
    return serializar(row)


@router.put('/corredores/{identificador}', dependencies=[escrita])
async def editar_corredor(identificador: UUID, dados: Corredor, claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    await corredor(conn, claims['tenant_id'], identificador)
    config = dados.model_dump(exclude={'versao'})
    rota = await validar_rota(conn, claims['tenant_id'], config)
    async with conn.transaction():
        # Serializa ativacoes e criacoes pelo mesmo recurso do tenant.
        if dados.ativo:
            await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))',
                               'cota:' + claims['tenant_id'] + ':corredores')
        atual = await conn.fetchrow('SELECT dados FROM painel_corredores WHERE id=$1 AND tenant_id=$2 FOR UPDATE',
                                   identificador, claims['tenant_id'])
        if not atual:
            raise HTTPException(404, 'Corredor nao encontrado.')
        if dados.ativo and not objeto(atual['dados']).get('ativo'):
            await verificar_cota(conn, claims['tenant_id'], 'corredores')
        row = await conn.fetchrow('''UPDATE painel_corredores SET dados=$3::jsonb,geometria=$4::jsonb,
            versao=versao+1,atualizado_em=now() WHERE id=$1 AND tenant_id=$2 AND versao=$5 RETURNING *''',
            identificador, claims['tenant_id'], json.dumps(config), json.dumps(rota['geojson']), dados.versao)
    if not row:
        raise HTTPException(409, 'Cadastro mudou. Atualize antes de salvar.')
    return serializar(row)


@router.post('/corredores/{identificador}/recorrencias', dependencies=[escrita])
async def criar_recorrencia(identificador: UUID, dados: Recorrencia, claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    c = await corredor(conn, claims['tenant_id'], identificador)
    await validar_rota(conn, claims['tenant_id'], objeto(c['dados']), dados)
    row = await conn.fetchrow('''INSERT INTO painel_recorrencias(id,corredor_id,tenant_id,dados)
        VALUES($1,$2,$3,$4::jsonb) RETURNING *''', uuid4(), identificador, claims['tenant_id'], dados.model_dump_json(exclude={'versao'}, exclude_none=True))
    return serializar(row)


@router.put('/recorrencias/{identificador}', dependencies=[escrita])
async def editar_recorrencia(identificador: UUID, dados: Recorrencia, claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    r = await conn.fetchrow('SELECT * FROM painel_recorrencias WHERE id=$1 AND tenant_id=$2', identificador, claims['tenant_id'])
    if not r:
        raise HTTPException(404, 'Recorrencia nao encontrada.')
    c = await corredor(conn, claims['tenant_id'], r['corredor_id'])
    await validar_rota(conn, claims['tenant_id'], objeto(c['dados']), dados)
    row = await conn.fetchrow('''UPDATE painel_recorrencias SET dados=$3::jsonb,versao=versao+1,atualizado_em=now()
        WHERE id=$1 AND tenant_id=$2 AND versao=$4 RETURNING *''', identificador, claims['tenant_id'],
        dados.model_dump_json(exclude={'versao'}, exclude_none=True), dados.versao)
    if not row:
        raise HTTPException(409, 'Recorrencia mudou. Atualize antes de salvar.')
    return serializar(row)


@router.post('/recorrencias/{identificador}/despachar', dependencies=[escrita])
async def despachar(identificador: UUID, dados: Despacho, claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    from app.routers.logistica import criar_operacao
    tenant = claims['tenant_id']
    async with conn.transaction():
        await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))', tenant+str(dados.chave_idempotencia))
        anterior = await conn.fetchrow('SELECT * FROM painel_despachos WHERE tenant_id=$1 AND chave=$2', tenant, dados.chave_idempotencia)
        if anterior:
            if anterior['recorrencia_id'] != identificador or anterior['data_local'] != dados.data_local:
                raise HTTPException(409, 'Chave de envio ja usada para outro despacho.')
            return {'id_operacao': anterior['id_operacao'], 'reutilizado': True}
        r = await conn.fetchrow('SELECT * FROM painel_recorrencias WHERE id=$1 AND tenant_id=$2 FOR UPDATE', identificador, tenant)
        if not r:
            raise HTTPException(404, 'Recorrencia nao encontrada.')
        existente = await conn.fetchval('SELECT id_operacao FROM painel_despachos WHERE tenant_id=$1 AND recorrencia_id=$2 AND data_local=$3', tenant, identificador, dados.data_local)
        if existente:
            return {'id_operacao':existente,'reutilizado':True}
        c = await corredor(conn, tenant, r['corredor_id'])
        config, rec = objeto(c['dados']), objeto(r['dados'])
        if not config['ativo'] or not rec['ativo']:
            raise HTTPException(409, 'Corredor ou recorrencia inativo.')
        if dados.data_local < datetime.now(ZoneInfo('America/Sao_Paulo')).date() or dados.data_local.weekday() not in rec['dias_semana']:
            raise HTTPException(422, 'Data fora dos dias cadastrados ou no passado.')
        inicio = datetime.combine(dados.data_local, time.fromisoformat(rec['horario_local']), ZoneInfo('America/Sao_Paulo'))
        if inicio < datetime.now(timezone.utc):
            raise HTTPException(422, 'Horario de partida ja passou. Selecione outra data.')
        op_id = 'REC_' + uuid5(NAMESPACE_URL, tenant+str(identificador)+str(dados.chave_idempotencia)).hex
        op = OperacaoCreate(**{k:v for k,v in config.items() if k not in ('nome','ativo','dimensoes_referencia')}, id_operacao=op_id,
            id_veiculo=rec.get('id_veiculo'), dimensoes=rec.get('dimensoes') or (config.get('dimensoes_referencia') if not rec.get('id_veiculo') else None), custos_operacionais=rec.get('custos_operacionais'),
            janela_inicio=inicio.isoformat(), janela_fim=(inicio+timedelta(minutes=rec['janela_minutos'])).isoformat())
        await criar_operacao(op, conn, tenant)
        await conn.execute('INSERT INTO painel_despachos(tenant_id,chave,recorrencia_id,data_local,id_operacao) VALUES($1,$2,$3,$4,$5)',
            tenant, dados.chave_idempotencia, identificador, dados.data_local, op_id)
    return {'id_operacao': op_id, 'reutilizado': False}


@router.post('/consultas')
async def consultar(dados: Consulta, claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    async with conn.transaction():
        return await registrar_consulta(conn, claims['tenant_id'], claims['role'], dados.id_operacao,claims.get('usuario_id'))


@router.get('/consultas')
async def consultas(id_operacao: str | None = None, offset: int = Query(0, ge=0), limite: int = Query(20, ge=1, le=100),
    claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    rows = await conn.fetch('''SELECT id,id_operacao,perfil,criado_em,snapshot#>>'{contexto_consulta,autoria_individual}' AS usuario_id FROM painel_consultas
        WHERE tenant_id=$1 AND ($2::text IS NULL OR id_operacao=$2) ORDER BY criado_em DESC,id OFFSET $3 LIMIT $4''', claims['tenant_id'], id_operacao, offset, limite+1)
    return {'items':[serializar(r) for r in rows[:limite]], 'proximo_offset':offset+limite if len(rows)>limite else None}


@router.get('/consultas/{identificador}')
async def consulta(identificador: UUID, claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    row = await conn.fetchrow('SELECT * FROM painel_consultas WHERE id=$1 AND tenant_id=$2', identificador, claims['tenant_id'])
    if not row:
        raise HTTPException(404, 'Consulta nao encontrada.')
    return serializar(row)


@router.put('/operacoes/{identificador}/premissas', dependencies=[escrita])
async def premissas(identificador: str, dados: Premissas, claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    from app.services.viagem_caminhao import ContextoViagens, comparar_custos, gravar_recomendacao
    tenant = claims['tenant_id']
    async with conn.transaction():
        op = await conn.fetchrow('SELECT * FROM operacoes WHERE id_operacao=$1 AND tenant_id=$2 FOR UPDATE', identificador, tenant)
        if not op:
            raise HTTPException(404, 'Operacao nao encontrada.')
        if op['status'] != 'PLANNED':
            raise HTTPException(409, 'Somente viagens planejadas podem ser recalculadas.')
        if dados.selo_esperado != await selo(conn, tenant, identificador):
            raise HTTPException(409, 'Premissas ou recomendacao mudaram. Atualize antes de salvar.')
        await conn.execute('UPDATE operacoes SET custos_operacionais=$3::jsonb WHERE id_operacao=$1 AND tenant_id=$2', identificador, tenant, dados.custos_operacionais.model_dump_json(exclude_none=True))
        contexto = await ContextoViagens.carregar(conn, tenant, identificador)
        viagem = contexto.ops[0]
        cenario_id = 'SIM_PAINEL_' + uuid4().hex
        await conn.execute('''INSERT INTO cenarios_clima(id_cenario,nome,precipitacao_mm,tipo,tenant_id)
            VALUES($1,'Recalculo manual do painel',$2,'SIMULACAO',$3)''', cenario_id, dados.precipitacao_mm, tenant)
        analise = await contexto.analisar(viagem, dados.precipitacao_mm, forcar=True)
        base = contexto.original(viagem)
        janela = (viagem['janela_fim']-viagem['janela_inicio']).total_seconds()/60 if viagem.get('janela_fim') and viagem.get('janela_inicio') else None
        custos = objeto(viagem.get('custos_operacionais')) or {}
        custo = comparar_custos(base, base, custos, False, janela)['custo_original_conhecido_brl']
        await conn.execute('UPDATE operacoes SET custo_estimado=$3 WHERE id_operacao=$1 AND tenant_id=$2', identificador, tenant, custo)
        await gravar_recomendacao(conn, viagem, tenant, cenario_id, analise)
        return {'sucesso':True,'id_operacao':identificador,'aviso':'Premissas salvas e comparacao recalculada no motor existente. Atualize a consulta antes de decidir.'}


@router.post('/relatos', dependencies=[escrita])
async def relatar(dados: Relato, claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    payload=dados.model_dump_json(exclude_none=True)
    identificador=uuid5(NAMESPACE_URL,'relato:'+claims['tenant_id']+':'+str(dados.chave_idempotencia)) if dados.chave_idempotencia else uuid4()
    row = await conn.fetchrow('''INSERT INTO painel_relatos(id,tenant_id,dados,perfil)
        VALUES($1,$2,$3::jsonb,$4) ON CONFLICT(id) DO NOTHING RETURNING *''', identificador, claims['tenant_id'], payload, claims['role'])
    reutilizado=row is None
    if reutilizado:
        row=await conn.fetchrow('SELECT * FROM painel_relatos WHERE id=$1 AND tenant_id=$2',identificador,claims['tenant_id'])
        if not row or objeto(row['dados'])!=json.loads(payload):
            raise HTTPException(409,'Identificador de relato ja utilizado; confira os dados do envio.')
    return {**serializar(row), 'reutilizado':reutilizado,'status':'PENDENTE_VALIDACAO', 'aviso':'Relato privado registrado. Nao confirma interdicao nem altera automaticamente o roteamento.'}


@router.get('/eventos')
async def eventos(claims=Depends(get_current_user_claims), conn=Depends(get_connection)):
    from app.routers.ocorrencias import listar_ocorrencias_ativas
    publicos = await listar_ocorrencias_ativas(conn, claims['tenant_id'])
    items, features = [], []
    for e in publicos:
        categoria = str(e['categoria']).upper()
        natureza = ('HISTORICO' if 'HISTOR' in categoria else 'PREVISAO' if 'PREVIS' in categoria else
                    'SIMULACAO' if 'SIMUL' in categoria else 'OCORRENCIA_CONFIRMADA' if e['status_evento']=='CONFIRMADO' else
                    'TRANSITO_OBSERVADO' if 'TRANSITO_OBSERVADO' in categoria else 'INCERTO')
        trechos = await conn.fetch('''SELECT id_trecho,name,ST_AsGeoJSON(ST_Transform(geom,4326)) AS geo
            FROM trechos_osm WHERE id_trecho=ANY($1::integer[]) AND (tenant_malha IS NULL OR tenant_malha=$2)
            AND (importacao_malha_id IS NULL OR EXISTS(SELECT 1 FROM malha_importacoes m WHERE m.id=importacao_malha_id AND m.ativo))''', e['trechos_afetados'] or [], claims['tenant_id'])
        e.update(natureza=natureza, escopo='PUBLICO', local=', '.join(t['name'] or str(t['id_trecho']) for t in trechos) or 'Trecho nao localizado na malha disponivel',
            consequencia_possivel='Pode provocar atraso ou impedir passagem; a extensao e a consequencia precisam de conferencia na fonte.',
            criterio_consequencia='Possibilidade generica, nao consequencia confirmada para esta viagem.')
        items.append(e)
        for t in trechos:
            if t['geo']:
                features.append({'type':'Feature','geometry':json.loads(t['geo']),'properties':{'id_evento':e['id_evento'],'natureza':natureza,'fonte':e['fonte'],'atualizacao':e['ultima_atualizacao'],'expiracao':e['expiracao_em']}})
    relatos = await conn.fetch('SELECT * FROM painel_relatos WHERE tenant_id=$1 ORDER BY criado_em DESC LIMIT 51', claims['tenant_id'])
    for r in relatos[:50]:
        d = objeto(r['dados'])
        e = {'id_evento':str(r['id']), 'categoria':d['categoria'], 'natureza':'RELATO_NAO_VALIDADO','escopo':'PRIVADO',
            'status_evento':'PENDENTE_VALIDACAO','fonte':'Relato do usuario da empresa','confianca':None,
            'ultima_atualizacao':r['criado_em'].isoformat(), 'primeira_deteccao':d['ocorrido_em'],'expiracao_em':None,
            'trechos_afetados':[], 'local':f"{d['latitude']}, {d['longitude']}", 'descricao':d['descricao'],
            'consequencia_possivel':'Impacto relatado ainda nao validado; nao autoriza bloqueio automatico.',
            'o_que_nao_sabemos':'Confirmacao, duracao, extensao e restricoes reais da ocorrencia.'}
        items.append(e)
        features.append({'type':'Feature','geometry':{'type':'Point','coordinates':[d['longitude'],d['latitude']]},
            'properties':{'id_evento':e['id_evento'],'natureza':e['natureza'],'fonte':e['fonte'],'atualizacao':e['ultima_atualizacao'],'expiracao':None}})
    return {'items':items,'mapa':{'type':'FeatureCollection','features':features},'limites':{'publicos':50,'relatos':50,'relatos_truncados':len(relatos)>50},
        'aviso':'Geometria por trechos associados ou coordenada do relato; nao representa extensao confirmada de interdicao.'}
