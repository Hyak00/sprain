"""Carregar a demonstracao pela API local, sem apagar a base existente."""
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def api(path,body=None):
    req=urllib.request.Request('http://127.0.0.1:8000'+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'X-API-Key':os.environ.get('SPRAIN_API_KEY','key_admin_demo'),'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as response:
        return json.load(response)


def main():
    if os.environ.get('ENVIRONMENT','development').strip().lower()=='production':
        raise SystemExit('A demonstracao nao deve ser carregada em producao.')
    previous=api('/api/v1/infraestrutura/malha/importacoes')
    if previous:
        print('Importacoes existentes preservadas. Nenhuma malha nem referencia foi adicionada, substituida ou reativada.')
        print('Abrir http://localhost:8000/static/b2b.html; para completar a base usar os importadores explicitamente.')
        return
    with gzip.open(ROOT/'dados/referencia/corredor-demo.json.gz','rt',encoding='utf-8') as source:
        payload=json.load(source)
    payload['validar_apenas']=False
    response=api('/api/v1/infraestrutura/malha/importar',payload)
    imports=api('/api/v1/infraestrutura/malha/importacoes')
    if not any(i['id']==response['id'] and i['ativo'] for i in imports):
        raise SystemExit('Esse snapshot foi desativado. Cadastros e importacoes existentes foram preservados.')
    print(f"Malha de referencia: {response['status']} (importacao {response['id']}).")
    points=api('/api/v1/infraestrutura/pontos?tipo=PEDAGIO&limite=1')
    if points['features'] or response['status']=='JA_IMPORTADO':
        print('Cadastros existentes preservados. Nenhum pedagio foi sobrescrito ou reativado.')
        print('Para completar dados ausentes, usar importar_pedagios_osm.py explicitamente.')
    else:
        env=os.environ.copy();env.setdefault('SPRAIN_API_KEY','key_admin_demo')
        subprocess.run([sys.executable,str(ROOT/'scripts/importar_pedagios_osm.py'),
            '--arquivo-overpass',str(ROOT/'dados/referencia/pedagios-demo-overpass.json'),'--aplicar'],env=env,check=True)
    print('Abrir http://localhost:8000/static/b2b.html — Login / Minha Frota / Corredor.')


if __name__=='__main__':
    main()
