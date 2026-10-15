"""Inventario de estruturas na propria via; geometria nao informa capacidade portante."""
import json

LIMITES = ('altura_max_m','largura_max_m','comprimento_max_m','peso_max_t')


def complementar_estruturas(infraestrutura, features):
    estruturas = {}
    for feature in features:
        props = feature['properties']
        estrutura = props.get('estrutura_viaria')
        if isinstance(estrutura,str):
            estrutura = json.loads(estrutura)
        if not estrutura:
            continue
        chave = str(estrutura['osm_way_id'])
        if chave in estruturas:
            continue
        limites = props.get('limites_importados') or {}
        ausentes = [k for k in LIMITES if limites.get(k) is None]
        estruturas[chave] = {**estrutura, 'limites_cadastrados':limites,
            'limites_ausentes':ausentes,'status':'CONFERENCIA_NECESSARIA'}
        coords = feature['geometry']['coordinates']
        infraestrutura['pontos_mapa']['features'].append({'type':'Feature',
            'geometry':{'type':'Point','coordinates':coords[len(coords)//2]},
            'properties':{'id':'estrutura-osm-'+chave,'tipo':'PONTE',
                'nome':estrutura['tipo']+' · '+estrutura['nome'],
                'fonte':estrutura['fonte'],'origem_dados':'REFERENCIA_OSM',
                'verificado_em':None,'valido_ate':None,'status':'CONFERENCIA_NECESSARIA',
                **{k:limites.get(k) for k in LIMITES},'limites_ausentes':ausentes}})
    infraestrutura['estruturas_referencia'] = list(estruturas.values())
    infraestrutura['estruturas_sem_limites_completos'] = sum(bool(e['limites_ausentes']) for e in estruturas.values())
    return infraestrutura
