"""Aplica manifesto revisado a referencias OSM existentes. Nao substitui cadastro humano."""
import argparse
import hashlib
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def planejar(manifesto, features, agora=None):
    agora = agora or datetime.now(timezone.utc)
    if not datetime.fromisoformat(manifesto['verificado_em']) <= agora < datetime.fromisoformat(manifesto['valido_ate']):
        raise ValueError('Manifesto vencido ou futuro: confira novamente a fonte e revise datas/valores.')
    alteracoes, ignorados = [], []
    for praca in manifesto['pracas']:
        for no in praca['nos_osm']:
            origem = f'https://www.openstreetmap.org/node/{no}'
            fonte = manifesto['fonte'] + f'#osm-node={no}'
            pontos = [f for f in features if f['properties']['fonte'] in (origem, fonte)]
            if len(pontos) != 1:
                ignorados.append({'no':no,'motivo':'Referencia ausente, alterada por responsavel ou ambigua.'})
                continue
            p = pontos[0]['properties']
            if p.get('origem_dados') != 'REFERENCIA_OSM':
                ignorados.append({'no':no,'motivo':'Cadastro ja revisado; preservado.'})
                continue
            payload = {k:p[k] for k in ('tipo','id_trecho')}
            payload.update(nome=praca['nome'],longitude=pontos[0]['geometry']['coordinates'][0],
                latitude=pontos[0]['geometry']['coordinates'][1],fonte=fonte,
                verificado_em=manifesto['verificado_em'],valido_ate=manifesto['valido_ate'],
                origem_dados='CADASTRO_MANUAL',grupo_cobranca=praca['grupo_cobranca'],
                tarifa_por_eixo=praca['tarifa_por_eixo'])
            alteracoes.append((p['id'],payload))
    return alteracoes, ignorados


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arquivo',type=Path,required=True)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--aplicar',action='store_true')
    args=parser.parse_args()
    chave=os.environ['SPRAIN_API_KEY']
    def api(caminho,corpo=None):
        req=urllib.request.Request(args.base_url.rstrip('/')+caminho,
            headers={'X-API-Key':chave,'Content-Type':'application/json'},
            data=json.dumps(corpo).encode() if corpo else None,method='PUT' if corpo else 'GET')
        with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
    manifesto=json.loads(args.arquivo.read_text(encoding='utf-8'))
    if not manifesto['fonte'].startswith('https://'):
        raise ValueError('Fonte deve usar HTTPS.')
    with urllib.request.urlopen(manifesto['fonte'],timeout=30) as r:
        documento=r.read(10_000_001)
    if len(documento)>10_000_000 or hashlib.sha256(documento).hexdigest()!=manifesto['sha256_documento']:
        raise ValueError('Documento oficial mudou: revise o manifesto antes de importar.')
    features=[]
    depois=0
    while True:
        pagina=api(f'/api/v1/infraestrutura/pontos?tipo=PEDAGIO&limite=1000&depois_id={depois}')
        features.extend(pagina['features'])
        depois=pagina['proximo_depois_id']
        if depois is None:break
    alteracoes,ignorados=planejar(manifesto,features)
    for identificador,payload in alteracoes:
        if args.aplicar:api(f'/api/v1/infraestrutura/pontos/{identificador}',payload)
    print(json.dumps({'aplicado':args.aplicar,'pontos':len(alteracoes),'ignorados':ignorados},ensure_ascii=False))


if __name__=='__main__':
    main()
