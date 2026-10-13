"""Preparar/gravar referencias OSM de pedagio, sem estimar tarifa oficial.

Usa apenas a API; chave em SPRAIN_API_KEY. Padrao: valida o lote sem gravar.
"""
import argparse
import json
import os
from pathlib import Path
from datetime import datetime,timedelta,timezone
import urllib.parse
import urllib.request


def chamada(base,key,caminho,corpo=None):
    req=urllib.request.Request(base.rstrip('/')+caminho,
        data=json.dumps(corpo).encode() if corpo is not None else None,
        headers={'X-API-Key':key,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as resposta:
        return json.load(resposta)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arquivo-overpass',type=Path,required=True)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--aplicar',action='store_true')
    args=parser.parse_args()
    key=os.getenv('SPRAIN_API_KEY','').strip()
    if not key:
        raise SystemExit('Defina SPRAIN_API_KEY com uma chave ADMIN da empresa.')
    dados=json.loads(args.arquivo_overpass.read_text(encoding='utf-8'))
    agora=datetime.now(timezone.utc)
    cadastros=[]
    sem_associacao=[]
    for no in dados['elements']:
        if no['type']!='node' or no.get('tags',{}).get('barrier')!='toll_booth':
            continue
        query=urllib.parse.urlencode(dict(longitude=no['lon'],latitude=no['lat']))
        candidatos=chamada(args.base_url,key,'/api/v1/infraestrutura/malha/trechos-proximos?'+query)['candidatos']
        if not candidatos:
            sem_associacao.append(no['id'])
            continue
        nome=no.get('tags',{}).get('name') or f"Pedagio OSM {no['id']}"
        cadastros.append(dict(tipo='PEDAGIO',nome=nome[:200],id_trecho=candidatos[0]['id_trecho'],
            longitude=no['lon'],latitude=no['lat'],fonte=f"https://www.openstreetmap.org/node/{no['id']}",
            verificado_em=agora.isoformat(),valido_ate=(agora+timedelta(days=7)).isoformat(),origem_dados='REFERENCIA_OSM'))
    resultados=[]
    for i in range(0,len(cadastros),500):
        resultados.append(chamada(args.base_url,key,'/api/v1/infraestrutura/importar-pontos',
                                  dict(pontos=cadastros[i:i+500],validar_apenas=not args.aplicar)))
    print(json.dumps(dict(referencias=len(cadastros),sem_associacao=sem_associacao,resultados=resultados),ensure_ascii=False))


if __name__=='__main__':
    main()
