"""Carga idempotente do exercício 3.4, exclusivamente na API local de demonstração."""
import argparse
import json
import os
import urllib.request
from demo_guard import verificar_api_demo,SemRedirect


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url',default='http://127.0.0.1:18000')
    p.add_argument('--apenas-verificar',action='store_true')
    a=p.parse_args()
    estado=verificar_api_demo(a.base_url)
    if a.apenas_verificar:print(json.dumps(estado,ensure_ascii=False));return
    req=urllib.request.Request(a.base_url.rstrip('/')+'/api/v1/demonstracao/preparar',data=b'{}',
        headers={'X-API-Key':os.environ.get('SPRAIN_API_KEY','key_admin_demo'),'Content-Type':'application/json'})
    with urllib.request.build_opener(SemRedirect).open(req,timeout=90) as r:d=json.load(r)
    print(json.dumps({'preparado':d['preparado'],'id_operacao':d['id_operacao'],'id_veiculo':d['id_veiculo'],
        'importacao_id':d['importacao_id'],'referencia':d['referencia_historica']['fonte_url'],'aviso':d['aviso']},ensure_ascii=False))
    print('Abra '+a.base_url.rstrip('/')+'/static/b2b.html > Central de trabalho > Demonstracao.')


if __name__=='__main__':main()
