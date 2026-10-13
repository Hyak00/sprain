"""Baixa dados OSM; prepara arquivo para validar/importar pela API, sem acessar o banco.

OSM nao fornece automaticamente uma homologacao para caminhoes.
"""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
import urllib.parse
import urllib.request
import re


def converter(dados):
    nos = {e["id"]: (e["lon"],e["lat"]) for e in dados["elements"] if e["type"]=="node"}
    segmentos = []
    for via in dados["elements"]:
        if via["type"] != "way":
            continue
        tags = via.get("tags",{})
        if tags.get("access") in ("no","private") or tags.get("hgv") in ("no","private"):
            continue
        # Nao transformar acesso condicional ou limite nao interpretado em passagem permitida.
        if any(k in tags for k in ("oneway:conditional","access:conditional","hgv:conditional","maxaxleload")):
            continue
        limites = {}
        invalido = False
        for tag,campo,unidade in (("maxheight","altura_max_m","m"),("maxwidth","largura_max_m","m"),
                                   ("maxlength","comprimento_max_m","m"),("maxweight","peso_max_t","t")):
            if tag not in tags:
                continue
            match=re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*"+unidade+r"?\s*",tags[tag])
            if not match or float(match[1].replace(",",".")) <= 0:
                invalido = True
                break
            limites[campo]=float(match[1].replace(",","."))
        if invalido or any(k in tags for k in ("maxheight:conditional","maxwidth:conditional","maxlength:conditional","maxweight:conditional")):
            continue
        highway = tags.get("highway")
        if highway not in ("motorway","motorway_link","trunk","trunk_link","primary","secondary","tertiary","residential"):
            continue
        one = tags.get("oneway")
        if one in ("yes","1","true"):
            sentido="DIRETO"
        elif one == "-1":
            sentido="INVERSO"
        elif one in ("no","0","false"):
            sentido="AMBOS"
        elif one not in (None, ""):
            continue
        elif highway == "motorway" or tags.get("junction")=="roundabout":
            sentido="DIRETO"
        else:
            sentido="AMBOS"
        for a,b in zip(via["nodes"],via["nodes"][1:]):
            if a==b or a not in nos or b not in nos:
                continue
            segmentos.append({"origem":str(a),"destino":str(b),"coordenadas":[nos[a],nos[b]],
                              "nome":tags.get("name",tags.get("ref","Via OSM")),"highway":highway,"sentido":sentido,
                              "referencia":f"https://www.openstreetmap.org/way/{via['id']}",**limites})
    return {"fonte":"OpenStreetMap / Overpass; consulta " + datetime.now(timezone.utc).date().isoformat(),
            "validar_apenas":True,"segmentos":segmentos}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arquivo-osm",type=Path,help="JSON Overpass existente (dispensa rede)")
    parser.add_argument("--saida",type=Path,required=True)
    parser.add_argument("--endpoint",default="https://overpass-api.de/api/interpreter")
    parser.add_argument("--arquivo-base",type=Path,help="Malha convertida existente para acrescentar alcas baixadas")
    parser.add_argument("--somente-principais",action="store_true",help="Consulta menor, sem buscar alcas")
    args=parser.parse_args()
    if args.arquivo_osm:
        dados=json.loads(args.arquivo_osm.read_text(encoding="utf-8"))
    else:
        query='[out:json][timeout:60];(way["ref"~"SP[- ]?(310|330|348)"]["highway"~"motorway|trunk|primary"](-23.8,-48.4,-21.5,-46.3);way["highway"~"^(motorway_link|trunk_link)$"](-22.7,-47.65,-22.3,-47.25););(._;>;);out body;'
        if args.arquivo_base:
            query='[out:json][timeout:25];way["highway"~"^(motorway_link|trunk_link)$"](-22.7,-47.65,-22.3,-47.25);(._;>;);out body;'
        if args.somente_principais:
            query='[out:json][timeout:60];way["ref"~"SP[- ]?(310|330|348)"]["highway"~"motorway|trunk|primary"](-23.8,-48.4,-21.5,-46.3);(._;>;);out body;'
        req=urllib.request.Request(args.endpoint,
            data=urllib.parse.urlencode({"data":query}).encode(),headers={"User-Agent":"SPRain-MVP/1.0"})
        with urllib.request.urlopen(req,timeout=75) as response:
            dados=json.load(response)
        args.saida.with_suffix(".overpass.json").write_text(json.dumps(dados),encoding="utf-8")
    convertido=converter(dados)
    if args.arquivo_base:
        base=json.loads(args.arquivo_base.read_text(encoding="utf-8"))
        chaves={(s["origem"],s["destino"],tuple(map(tuple,s["coordenadas"]))):s for s in base["segmentos"]}
        chaves.update({(s["origem"],s["destino"],tuple(map(tuple,s["coordenadas"]))):s for s in convertido["segmentos"]})
        base["segmentos"]=list(chaves.values())
        convertido=base
    if not convertido["segmentos"]:
        raise SystemExit("Nenhum segmento encontrado; nada foi gravado.")
    if len(convertido["segmentos"])>30000:
        raise SystemExit("Mais de 30000 segmentos: dividir a area antes da importacao.")
    args.saida.write_text(json.dumps(convertido,ensure_ascii=False),encoding="utf-8")
    print(f"Arquivo preparado: {len(convertido['segmentos'])} segmentos. Validacao e importacao pela API.")


if __name__=="__main__":
    main()
