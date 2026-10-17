"""Demonstração reprodutível somente em banco reservado, sem alertas globais."""
import json
import os
from pathlib import Path

from fastapi import HTTPException
from app.config import settings
from app.seguranca import is_production

RAIZ=Path(__file__).resolve().parents[3]
TENANT='demo_corp'
VEICULO='DEMO_34_CAMINHAO'
OPERACAO='DEMO_34_VIAGEM'
FONTE_MALHA='SPRain DEMO 3.4 v1 - MALHA SINTETICA DIDATICA, SEM ASSOCIACAO GEOGRAFICA AO EVENTO'


def habilitada():
    return os.getenv('SPRAIN_DEMO_ENABLED','').strip()=='1'


def banco_reservado(nome):
    return nome=='sprain_demo' or nome.startswith('sprain_demo_')


def validar_configuracao():
    if habilitada() and (is_production() or not banco_reservado(settings.DB_NAME)):
        raise RuntimeError('Demonstração exige ambiente não produtivo e banco reservado sprain_demo.')


async def exigir_ambiente(conn):
    if is_production() or not habilitada():
        raise HTTPException(503,'Demonstração bloqueada neste ambiente. Use compose.demo.yml.')
    if not banco_reservado(settings.DB_NAME):
        raise HTTPException(503,'Banco configurado não é reservado para demonstração.')
    real=await conn.fetchval('SELECT current_database()')
    if real!=settings.DB_NAME or not banco_reservado(real):
        raise HTTPException(503,'O banco conectado não corresponde ao ambiente de demonstração.')


def referencia():
    return json.loads((RAIZ/'dados/demonstracao/evento-historico.json').read_text(encoding='utf-8'))


def malha():
    # Nós locais independentes, com dois caminhos. Não são os trechos do km 205.
    pontos={'A':(-47.84,-22.25),'B':(-47.83,-22.25),'C':(-47.82,-22.25),'D':(-47.83,-22.24)}
    return {'fonte':FONTE_MALHA,'validar_apenas':False,'segmentos':[
        {'origem':'DEMO34_'+a,'destino':'DEMO34_'+b,'coordenadas':[pontos[a],pontos[b]],
         'nome':'DEMONSTRAÇÃO - ligação sintética '+a+'-'+b,'highway':'primary','sentido':'AMBOS'}
        for a,b in [('A','B'),('B','C'),('A','D'),('D','C')]]}


async def preparar(conn,tenant):
    await exigir_ambiente(conn)
    if tenant!=TENANT:raise HTTPException(403,'O exercício usa somente a empresa de demonstração.')
    from app.routers.malha import importar, ImportacaoMalha
    from app.routers.logistica import criar_operacao
    from app.schemas import OperacaoCreate
    from datetime import datetime,timedelta,timezone
    async with conn.transaction():
        await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))','sprain:demo34')
        imp=await importar(ImportacaoMalha(**malha()),tenant_id=tenant,conn=conn)
        ativo=await conn.fetchval('SELECT ativo FROM malha_importacoes WHERE id=$1 AND tenant_id=$2',imp['id'],tenant)
        if not ativo:raise HTTPException(409,'A malha do exercício está desativada. Nenhum cadastro foi reativado.')
        existente=await conn.fetchrow('SELECT tenant_id,modelo FROM veiculos WHERE id_veiculo=$1',VEICULO)
        if existente and (existente['tenant_id']!=tenant or existente['modelo']!='DEMONSTRAÇÃO - caminhão sintético'):
            raise HTTPException(409,'Identificador de demonstração ocupado; nenhum veículo foi sobrescrito.')
        await conn.execute('''INSERT INTO veiculos(id_veiculo,placa,modelo,tipo_veiculo,tenant_id,dimensoes,custos_operacionais)
            VALUES($1,'DEMO034','DEMONSTRAÇÃO - caminhão sintético','VUC',$2,
            '{"altura_m":3,"largura_m":2.4,"comprimento_m":8,"peso_total_t":10,"eixos":2}',
            '{"custo_por_km":4.5,"custo_hora_motorista":35,"custo_operacional_veiculo_hora":50}')
            ON CONFLICT(id_veiculo) DO NOTHING''',VEICULO,tenant)
        op=await conn.fetchrow('SELECT tenant_id,id_veiculo FROM operacoes WHERE id_operacao=$1',OPERACAO)
        if op and (op['tenant_id']!=tenant or op['id_veiculo']!=VEICULO):
            raise HTTPException(409,'Identificador do exercício ocupado; nenhuma viagem foi sobrescrita.')
        if not op:
            inicio=datetime.now(timezone.utc)+timedelta(hours=1)
            await criar_operacao(OperacaoCreate(id_operacao=OPERACAO,id_veiculo=VEICULO,
                origem_nome='DEMO - origem sintética A',origem_lat=-22.25,origem_lon=-47.84,
                destino_nome='DEMO - destino sintético C',destino_lat=-22.25,destino_lon=-47.82,
                janela_inicio=inicio.isoformat(),janela_fim=(inicio+timedelta(hours=4)).isoformat(),
                custos_operacionais={'custo_por_km':4.5,'custo_hora_motorista':35,'custo_operacional_veiculo_hora':50}),conn=conn,tenant_id=tenant)
    return {'preparado':True,'id_operacao':OPERACAO,'id_veiculo':VEICULO,'importacao_id':imp['id'],
        'referencia_historica':referencia(),'dados_do_exercicio':'SINTETICOS',
        'aviso':'Somente no banco de demonstração. Não é reconstrução geográfica nem evidência de economia real.'}


async def reproduzir(conn,tenant,etapa):
    await exigir_ambiente(conn)
    if tenant!=TENANT:raise HTTPException(403,'Exercício reservado à empresa de demonstração.')
    from app.services.routing_engine import RoutingEngine
    from app.services.viagem_caminhao import comparar_custos,objeto
    op=await conn.fetchrow('SELECT * FROM operacoes WHERE id_operacao=$1 AND tenant_id=$2',OPERACAO,tenant)
    if not op:raise HTTPException(409,'Prepare os dados de demonstração antes de reproduzir.')
    segmentos=await conn.fetch('''SELECT t.id_trecho,t.name FROM trechos_osm t JOIN malha_importacoes m ON m.id=t.importacao_malha_id
        WHERE m.tenant_id=$1 AND m.fonte=$2 AND m.ativo ORDER BY t.id_trecho''',tenant,FONTE_MALHA)
    bloqueados=[r['id_trecho'] for r in segmentos if r['name']=='DEMONSTRAÇÃO - ligação sintética B-C'] if etapa=='BLOQUEIO' else []
    if len(segmentos)!=4 or etapa=='BLOQUEIO' and not bloqueados:
        raise HTTPException(409,'Malha do exercício alterada ou desativada. Nenhum trecho externo será bloqueado.')
    dims=objeto(op['dimensoes']) or None
    args=(conn,op['origem_lon'],op['origem_lat'],op['destino_lon'],op['destino_lat'])
    original=await RoutingEngine.compute_route(*args,profile='FASTEST',rain_mm=0,tenant_id=tenant,vehicle_dimensions=dims)
    alternativa=await RoutingEngine.compute_route(*args,profile='FASTEST',rain_mm=0,tenant_id=tenant,
        vehicle_dimensions=dims,blocked_edge_ids=bloqueados)
    return {'modo':'DATASET_DEMONSTRACAO_B2B','etapa':etapa,'referencia_historica':referencia(),
        'natureza':'REPRODUCAO_DIDATICA_EM_MALHA_SINTETICA','id_operacao':OPERACAO,
        'bloqueios_somente_nesta_consulta':bloqueados,'rota_original':original,'rota_alternativa':alternativa,
        'comparativo_rotas':{'rota_original_km':original['distancia_km'] if original else None,
            'rota_alternativa_km':alternativa['distancia_km'] if alternativa else None,
            'tempo_original_min':original['tempo_min'] if original else None,
            'tempo_alternativo_min':alternativa['tempo_min'] if alternativa else None},
        'financeiro':comparar_custos(original,alternativa,objeto(op['custos_operacionais']),False) if original and alternativa else None,
        'parametros_sinteticos':{'chuva_mm_h':0,'explicacao':'Parâmetro neutro para isolar o bloqueio; não é chuva observada no evento.','dimensoes':dims},
        'aviso':'Histórico encerrado. As geometrias, veículo, custos e bloqueio são ilustrativos. Nenhum alerta atual foi criado ou alterado; sem rota, valores permanecem desconhecidos.'}
