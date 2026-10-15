"""Anota estruturas em vias OSM ja importadas, sem alterar geometria ou cadastro humano."""
import argparse
import gzip
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parents[1]/'dados/referencia/estruturas-corredor-osm.json.gz'


def limites_tags(tags):
    limites = {}
    for tag,campo,unidade,maximo in (
        ('maxheight','altura_max_m','m',10),('maxwidth','largura_max_m','m',10),
        ('maxlength','comprimento_max_m','m',100),('maxweight','peso_max_t','t',300)):
        valor = str(tags.get(tag,''))
        match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*'+unidade+r'?\s*',valor)
        if match and 0 < float(match[1].replace(',','.')) <= maximo:
            limites[campo] = float(match[1].replace(',','.'))
    return limites


def registros_osm(dados):
    registros = []
    for via in dados.get('elements',[]):
        if via['type'] != 'way':
            continue
        tags = via.get('tags',{})
        ponte = tags.get('bridge') not in (None,'no')
        tunel = tags.get('tunnel') not in (None,'no')
        limites = limites_tags(tags)
        estrutura = None
        fonte = f"https://www.openstreetmap.org/way/{via['id']}"
        if ponte or tunel:
            estrutura = {'osm_way_id':via['id'],'tipo':'TUNEL' if tunel else 'VIADUTO' if tags.get('bridge')=='viaduct' else 'PONTE',
                         'nome':tags.get('bridge:name',tags.get('name','Estrutura OSM')),'fonte':fonte}
        if estrutura or limites:
            registros.append({'fonte':fonte,'estrutura':estrutura,'limites':limites})
    return registros


def aplicar(conn,tenant,registros,observado_em):
    total = 0
    with conn.cursor() as cursor:
        for r in registros:
            cursor.execute("""SELECT t.id_trecho,t.limites_malha FROM trechos_osm t
                WHERE t.tenant_malha=%s AND t.fonte_malha=%s AND t.limites_verificado_em IS NULL
                  AND EXISTS(SELECT 1 FROM malha_importacoes m WHERE m.id=t.importacao_malha_id AND m.ativo)
                FOR UPDATE""",(tenant,r['fonte']))
            for identificador,limites in cursor.fetchall():
                limites = limites or {}
                # Novas referencias podem restringir, mas nunca liberar um limite conhecido automaticamente.
                for campo,valor in r['limites'].items():
                    limites[campo] = min(limites.get(campo,valor),valor)
                estrutura = {**r['estrutura'],'observado_em':observado_em} if r['estrutura'] else None
                cursor.execute("""UPDATE trechos_osm SET limites_malha=%s::jsonb,
                    estrutura_malha=COALESCE(%s::jsonb,estrutura_malha) WHERE id_trecho=%s AND tenant_malha=%s""",
                    (json.dumps(limites),json.dumps(estrutura) if estrutura else None,identificador,tenant))
                total += 1
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant',required=True)
    parser.add_argument('--snapshot',action='store_true',help='Usar inventario OSM versionado para instalacao inicial')
    parser.add_argument('--aplicar',action='store_true')
    args = parser.parse_args()
    from sincronizar_dados_publicos import conectar
    with conectar() as conn:
        if args.snapshot:
            with gzip.open(SNAPSHOT,'rt',encoding='utf-8') as f:dados=json.load(f)
            observado_em = dados['observado_em']
            registros = [{'fonte':e['fonte'],'estrutura':e,'limites':{}} for e in dados['estruturas']]
        else:
            with conn.cursor() as c:
                c.execute("""SELECT DISTINCT t.fonte_malha FROM trechos_osm t WHERE t.tenant_malha=%s
                    AND t.limites_verificado_em IS NULL AND EXISTS(SELECT 1 FROM malha_importacoes m
                        WHERE m.id=t.importacao_malha_id AND m.ativo)""",(args.tenant,))
                ids = sorted({int(m[1]) for (fonte,) in c.fetchall() if (m:=re.fullmatch(r'https://www\.openstreetmap\.org/way/(\d+)',fonte or ''))})
            conn.commit()  # Nao segurar transacao/locks enquanto aguarda o provedor externo.
            if not ids:
                print(json.dumps({'trechos_atualizados':0,'aviso':'Sem vias OSM ativas da empresa.'}));return
            if len(ids)>10000:raise ValueError('Divida a malha em lotes menores antes de sincronizar.')
            query='[out:json][timeout:45];way(id:'+','.join(map(str,ids))+');out tags;'
            req=urllib.request.Request('https://overpass-api.de/api/interpreter',
                data=urllib.parse.urlencode({'data':query}).encode(),headers={'User-Agent':'SPRain-MVP/1.0'})
            with urllib.request.urlopen(req,timeout=60) as response:payload=response.read(10_000_001)
            if len(payload)>10_000_000:raise ValueError('Resposta OSM excede 10 MB.')
            dados = json.loads(payload)
            if dados.get('remark') or not dados.get('elements'):raise ValueError('Consulta OSM incompleta; cadastro anterior mantido.')
            registros = registros_osm(dados)
            observado_em = datetime.now(timezone.utc).isoformat()
        total=aplicar(conn,args.tenant,registros,observado_em) if args.aplicar else 0
        print(json.dumps({'referencias':len(registros),'trechos_atualizados':total,'aplicado':args.aplicar,'observado_em':observado_em}))


if __name__=='__main__':
    main()
