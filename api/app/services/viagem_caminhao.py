"""Complemento dos fluxos existentes: restricoes, pedagios e custo comparavel.

Carrega o cadastro uma vez por lote; nao consulta provedores externos ao rotear.
"""
import json
from types import SimpleNamespace
from app.schemas import ParametrosFinanceiros
from app.services.infraestrutura_viaria import SELECT_PONTOS, LIMITES, avaliar_ponto, resumir_rota
from app.services.routing_engine import RoutingEngine
from app.services.hydro_engine import HydroEngine
from app.services.estruturas_viarias import complementar_estruturas
from app.services.custo_combustivel import custo_quilometrico, referencia_diesel, completar_custos


def objeto(valor):
    return json.loads(valor) if isinstance(valor, str) else (valor or {})


def dados_viagem(op):
    # As medidas e premissas do despacho sao preservadas; cadastros legados usam a frota.
    dimensoes = objeto(op.get('dimensoes')) or objeto(op.get('dimensoes_frota')) or None
    custos = objeto(op.get('custos_operacionais')) or objeto(op.get('custos_frota'))
    return dimensoes, custos


def comparar_custos(original, alternativa, premissas, risco_climatico, janela_min=None):
    """Diferencas com sinal: um desvio pode custar menos. Sem tarifa inventada."""
    p = ParametrosFinanceiros().model_dump() | premissas
    combustivel = custo_quilometrico(p)
    hora = p['custo_hora_motorista'] + p['custo_operacional_veiculo_hora']
    def custo(rota):
        atraso=max(0.0,rota['tempo_min']-janela_min)/60*p['custo_atraso_hora'] if janela_min is not None else 0.0
        return round(rota['distancia_km'] * combustivel['custo_por_km_aplicado'] + rota['tempo_min'] / 60 * hora
                     + rota['infraestrutura']['pedagios']['subtotal_conhecido_reais'] + atraso, 2)
    direto, desvio = custo(original), custo(alternativa)
    delta = round(desvio - direto, 2)
    potencial = p['prejuizo_potencial_alagamento'] if risco_climatico else 0.0
    pendentes = (original['infraestrutura']['pedagios']['tarifas_pendentes']
                 + alternativa['infraestrutura']['pedagios']['tarifas_pendentes'])
    return {
        'custo_original_conhecido_brl': direto, 'custo_alternativa_conhecido_brl': desvio,
        'custo_medio_original_conhecido_por_km_brl': round(direto/original['distancia_km'],2) if original['distancia_km'] else None,
        'custo_medio_alternativa_conhecido_por_km_brl': round(desvio/alternativa['distancia_km'],2) if alternativa['distancia_km'] else None,
        'combustivel_original_estimado_litros': (round(original['distancia_km']/p['consumo_km_l'],2)
            if combustivel['combustivel_por_km'] is not None else None),
        'delta_pedagios_conhecidos_brl': round(alternativa['infraestrutura']['pedagios']['subtotal_conhecido_reais']
                                              - original['infraestrutura']['pedagios']['subtotal_conhecido_reais'], 2),
        'custo_desvio_brl': delta,
        'economia_operacional_conhecida_brl': max(0.0, -delta),
        'prejuizo_potencial_evitado_brl': potencial,
        'economia_liquida_potencial_brl': round(potencial - delta, 2),
        'tarifas_pendentes_comparacao': pendentes,
        'comparacao_completa': False,
        'janela_disponivel_min': janela_min,
        'combustivel': combustivel,
        'delta_combustivel_estimado_brl': (round((alternativa['distancia_km'] - original['distancia_km'])
            * combustivel['combustivel_por_km'], 2) if combustivel['combustivel_por_km'] is not None else None),
        'premissas': p,
        'aviso': 'Estimativa com custos conhecidos e perda potencial informada; nao e dinheiro efetivamente salvo. '
                 'Cobertura de restricoes parcial; tarifas pendentes podem alterar a comparacao.'
    }


class ContextoViagens:
    def __init__(self, conn, tenant, ops, pontos, trechos, limites):
        self.conn, self.tenant, self.ops, self.pontos = conn, tenant, ops, pontos
        self.infra_context={'pontos':pontos,'limites':limites}
        self.trechos = {}
        for t in trechos:
            self.trechos.setdefault(t['id_operacao'], []).append(dict(t))

    @classmethod
    async def carregar(cls, conn, tenant, id_operacao=None):
        ops = await conn.fetch('''SELECT o.*,v.tipo_veiculo,v.placa,v.modelo,
            v.dimensoes AS dimensoes_frota,v.custos_operacionais AS custos_frota
            FROM operacoes o LEFT JOIN veiculos v ON v.id_veiculo=o.id_veiculo AND v.tenant_id=o.tenant_id
            WHERE o.tenant_id=$1 AND ($2::text IS NULL OR o.id_operacao=$2) ORDER BY o.id_operacao''',tenant,id_operacao)
        pontos = [dict(p) for p in await conn.fetch(SELECT_PONTOS, tenant)]
        trechos = await conn.fetch('''SELECT ort.id_operacao,t.id_trecho,t.length,t.ivi_score,
            t.NULL AS estrutura_malha,t.limites_malha,t.fonte_malha,t.limites_verificado_em,t.limites_valido_ate,
            ST_AsGeoJSON(ST_Transform(t.geom,4326)) AS geojson,
            (t.tenant_malha IS NULL OR t.tenant_malha=$1) AND
            (t.importacao_malha_id IS NULL OR EXISTS(SELECT 1 FROM malha_importacoes m
                WHERE m.id=t.importacao_malha_id AND m.ativo)) AS disponivel
            FROM operacao_rotas_trechos ort JOIN operacoes o ON o.id_operacao=ort.id_operacao
            JOIN trechos_osm t ON t.id_trecho=ort.id_trecho
            WHERE o.tenant_id=$1 AND ($2::text IS NULL OR o.id_operacao=$2) ORDER BY ort.id_operacao,ort.seq''',tenant,id_operacao)
        limites=await conn.fetch('''SELECT t.id_trecho,t.limites_malha FROM trechos_osm t
            WHERE (t.tenant_malha IS NULL OR t.tenant_malha=$1) AND t.limites_malha IS NOT NULL
            AND t.limites_malha<>'{}'::jsonb AND (t.importacao_malha_id IS NULL OR EXISTS(
                SELECT 1 FROM malha_importacoes m WHERE m.id=t.importacao_malha_id AND m.ativo))''',tenant)
        referencia=await referencia_diesel(conn)
        operacoes=[dict(o) for o in ops]
        for op in operacoes:
            dims,custos=dados_viagem(op)
            op['custos_operacionais']=completar_custos(custos,dims,referencia)
        return cls(conn,tenant,operacoes,pontos,trechos,limites)

    def original(self, op):
        dims, _ = dados_viagem(op)
        ts = self.trechos.get(op['id_operacao'], [])
        ids = [t['id_trecho'] for t in ts]
        info = resumir_rota(self.pontos,ids,dims)
        bloqueios = set()
        veiculo = SimpleNamespace(**dims) if dims else None
        for p in self.pontos:
            if p['id_trecho'] in ids and p['tipo']=='PONTE' and (
                dims is None or avaliar_ponto(p,veiculo)['status']=='BLOQUEADO'):
                bloqueios.add(p['id_trecho'])
        limites = []
        limites_mapa=[]
        for t in ts:
            lim = objeto(t['limites_malha'])
            excedidos = [k for medida,k in LIMITES.items() if k in lim and dims and dims[medida]>lim[k]]
            if not t['disponivel'] or (lim and (dims is None or excedidos)):
                bloqueios.add(t['id_trecho'])
            if lim:
                limites.append({'id_trecho':t['id_trecho'],'limites':lim,'fonte':t['fonte_malha'],
                                'excedidos':excedidos,'dimensoes_ausentes':dims is None})
                if t['geojson']:
                    limites_mapa.append({'type':'Feature','geometry':json.loads(t['geojson']),
                        'properties':{'id_trecho':t['id_trecho'],'limites_importados':lim,
                            'fonte_malha':t['fonte_malha'],'verificado_em':t['limites_verificado_em'],
                            'valido_ate':t['limites_valido_ate'],
                            'status_limite':'BLOQUEADO' if t['id_trecho'] in bloqueios else 'CONFERENCIA_NECESSARIA'}})
        complementar_estruturas(info,[{'geometry':json.loads(t['geojson']),'properties':{'estrutura_viaria':t['estrutura_malha'],'limites_importados':objeto(t['limites_malha'])}} for t in ts if t['geojson']])
        info['limites_trechos'] = limites
        info['trechos_incompativeis'] = sorted(bloqueios)
        info['limites_mapa']={'type':'FeatureCollection','features':limites_mapa}
        return {'distancia_km':float(op['distancia_planejada_km'] or 0),
                'tempo_min':float(op['tempo_planejado_min'] or 0), 'ids_trechos':ids,'infraestrutura':info}

    async def analisar(self, op, chuva, premissas=None, forcar=False):
        original = self.original(op)
        ts = self.trechos.get(op['id_operacao'], [])
        if float(chuva or 0) <= 0.0:
            engine = HydroEngine(self.conn)
            chuva_trechos = []
            for t in ts:
                id_t = t.get('id_trecho')
                if id_t:
                    props = await engine.get_bacia_trecho_proportions(id_t)
                    if props:
                        chuva_trechos.append(engine.calculate_effective_rainfall(props, {}))
            if chuva_trechos:
                chuva = max(chuva_trechos)
        fator = min(1.0,chuva/100)
        criticos = sum(float(t['ivi_score'] or 0)*(0.6+0.6*fator)>=80 for t in ts)
        risco = sum(60<=float(t['ivi_score'] or 0)*(0.6+0.6*fator)<80 for t in ts)
        fisico = bool(original['infraestrutura']['trechos_incompativeis'])
        nivel = 'CRITICO' if criticos or fisico else ('RISCO' if risco else 'NORMAL')
        dims, custos = dados_viagem(op)
        base = {'original':original,'dimensoes':dims,'nivel_risco':nivel,
                'trechos_criticos':criticos,'trechos_risco':risco,'restricao_fisica':fisico,
                'alternativa':None,'financeiro':None,'necessita_desvio':bool(criticos or risco or fisico)}
        if not base['necessita_desvio'] and not forcar:
            return base
        alternativa = await RoutingEngine.compute_route(self.conn,op['origem_lon'],op['origem_lat'],
            op['destino_lon'],op['destino_lat'],profile='SAFEST',rain_mm=chuva,
            tipo_veiculo=op.get('tipo_veiculo') or 'VUC',tenant_id=self.tenant,
            vehicle_dimensions=dims,infra_context=self.infra_context)
        base['alternativa']=alternativa
        if alternativa:
            risco_residual=sum(float(f['properties'].get('ivi_score',0))*(0.6+0.6*fator)>=60
                               for f in alternativa['geojson']['features'])
            base['trechos_risco_residual_alternativa']=risco_residual
            janela=(op['janela_fim']-op['janela_inicio']).total_seconds()/60 if op.get('janela_inicio') and op.get('janela_fim') else None
            parametros=(premissas or {}) | custos
            base['financeiro']=comparar_custos(original,alternativa,parametros,bool(criticos or risco) and risco_residual==0,janela)
            base['financeiro']['trechos_risco_residual_alternativa']=risco_residual
            base['financeiro']['perda_potencial_informada_brl']=parametros.get('prejuizo_potencial_alagamento',0)
            base['delta_km']=round(alternativa['distancia_km']-original['distancia_km'],2)
            base['delta_tempo_min']=round(alternativa['tempo_min']-original['tempo_min'],1)
        return base


async def gravar_recomendacao(conn, op, tenant, cenario, analise):
    alternativa=analise['alternativa']
    financeiro=analise['financeiro'] or {}
    acao='ALTERAR_ROTA' if alternativa else 'AGUARDAR_MELHORA'
    motivo=(f"Detectados {analise['trechos_criticos']} trechos criticos e {analise['trechos_risco']} em risco de inundacao. "
            f"{len(analise['original']['infraestrutura']['trechos_incompativeis'])} trecho(s) incompativel(is) ou sem medidas do caminhao.")
    if not alternativa:
        motivo+=' Nenhuma alternativa disponivel na malha para este caminhao; nao ha economia confirmada.'
    snapshot={**analise,'alternativa':{k:v for k,v in alternativa.items() if k not in ('geojson','ids_trechos')} if alternativa else None}
    await conn.execute('''INSERT INTO recomendacoes_operacao(id_operacao,id_cenario,tipo_acao,nivel_risco,
        motivo,confianca,km_adicionais,minutos_adicionais,custo_desvio,prejuizo_potencial_evitado,
        rota_alternativa_geojson,tenant_id,analise_infraestrutura)
        VALUES($1,$2,$3,$4,$5,0.88,$6,$7,$8,$9,$10,$11,$12::jsonb)''',
        op['id_operacao'],cenario,acao,analise['nivel_risco'],motivo,
        analise.get('delta_km',0),analise.get('delta_tempo_min',0),financeiro.get('custo_desvio_brl',0),
        financeiro.get('prejuizo_potencial_evitado_brl',0),
        json.dumps(alternativa['geojson']) if alternativa else None,tenant,
        json.dumps(snapshot,default=str))
    return {'id_operacao':op['id_operacao'],'id_veiculo':op['id_veiculo'],
            'nivel_risco':analise['nivel_risco'],'acao':acao,'motivo':motivo,
            'impacto':{'km_adicionais':analise.get('delta_km',0),
                'minutos_adicionais':analise.get('delta_tempo_min',0),
                'custo_desvio_brl':financeiro.get('custo_desvio_brl',0),
                'prejuizo_potencial_evitado_brl':financeiro.get('prejuizo_potencial_evitado_brl',0),
                'economia_liquida_potencial_brl':financeiro.get('economia_liquida_potencial_brl'),
                'tarifas_pendentes_comparacao':financeiro.get('tarifas_pendentes_comparacao'),
                'estimativa_disponivel':bool(alternativa)},'infraestrutura':snapshot}
