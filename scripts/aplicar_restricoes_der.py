"""Aplica limites DER revisados somente a geometrias OSM correspondentes da empresa.

Sem --aplicar apenas confere fonte e correspondencia. Nao importa vias, nao altera
topologia e nao transforma ausencia de restricao em autorizacao de passagem.
"""
import argparse
import hashlib
import json
import math
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

MANIFESTO = Path(__file__).resolve().parents[1]/'dados/referencia/restricoes-der-conferidas.json'
CAMPOS = {'altura_max_m':10, 'largura_max_m':10, 'comprimento_max_m':100, 'peso_max_t':300}


class TabelaDER(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.linhas = []
        self.secao = None
        self.linha = None
        self.celula = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.linha = []
        elif tag in ('td', 'th'):
            self.celula = []
        elif tag == 'br' and self.celula is not None:
            self.celula.append(' ')

    def handle_data(self, data):
        if self.celula is not None:
            self.celula.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.celula is not None:
            if self.linha is not None:
                self.linha.append(' '.join(''.join(self.celula).split()))
            self.celula = None
        elif tag == 'tr' and self.linha is not None:
            if self.linha and re.fullmatch(r'(?:SP|SPA|SPD|SPI)\s+\S+', self.linha[0]):
                self.secao = self.linha[0]
            elif len(self.linha) == 20 and re.fullmatch(r'\d+,\d+', self.linha[0]):
                self.linhas.append((self.secao, self.linha))
            self.linha = None


def validar_manifesto(manifesto, agora=None):
    agora = agora or datetime.now(timezone.utc)
    inicio, fim = (datetime.fromisoformat(manifesto[k]) for k in ('verificado_em', 'valido_ate'))
    if inicio.utcoffset() is None or fim.utcoffset() is None or not inicio <= agora < fim:
        raise ValueError('Manifesto futuro ou vencido: revise fonte e correspondencia antes de aplicar.')
    ids = set()
    for r in manifesto['registros']:
        if r['id'] in ids or not re.fullmatch(r'[a-z0-9-]+', r['id']):
            raise ValueError('Identificador invalido ou repetido.')
        ids.add(r['id'])
        if not r['fonte'].startswith('https://sigrr.der.sp.gov.br/RelatRestricao?'):
            raise ValueError('Fonte deve ser o relatorio publico DER/SIGRR.')
        if type(r['osm_way_id']) is not int or r['osm_way_id'] <= 0:
            raise ValueError('Referencia OSM invalida.')
        if not r['limites'] or any(k not in CAMPOS or type(v) not in (int,float)
            or not math.isfinite(v) or not 0 < v <= CAMPOS[k] for k,v in r['limites'].items()):
            raise ValueError('Limite invalido.')
        if len(r['linha_oficial']) != 20 or not r.get('evidencia_geografica'):
            raise ValueError('Registro exige linha oficial completa e justificativa geografica.')
        colunas = r['colunas_limites']
        permitidas = {'altura_max_m':(3,11),'largura_max_m':(4,12),
                     'comprimento_max_m':(5,13),'peso_max_t':(6,14)}
        if set(colunas) != set(r['limites']) or any(type(colunas[k]) is not int
            or colunas[k] not in permitidas[k]
            or float(r['linha_oficial'][colunas[k]].replace(',','.')) != v
            for k,v in r['limites'].items()):
            raise ValueError('Limite diverge da coluna oficial revisada.')
        coords = r['geometria']['coordinates']
        if r['geometria']['type'] != 'LineString' or not 2 <= len(coords) <= 1000 or any(
            len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p)
            or not -180 <= p[0] <= 180 or not -90 <= p[1] <= 90 for p in coords):
            raise ValueError('Geometria de correspondencia invalida.')


def conferir_fontes(manifesto):
    fontes = {}
    for r in manifesto['registros']:
        if r['fonte'] not in fontes:
            req = urllib.request.Request(r['fonte'], headers={'User-Agent':'SPRain-MVP/1.0'})
            with urllib.request.urlopen(req, timeout=35) as response:
                raw = response.read(8_000_001)
            if len(raw)>8_000_000:
                raise ValueError('Relatorio excede 8 MB.')
            tabela = TabelaDER()
            tabela.feed(raw.decode('utf-8-sig', errors='strict'))
            fontes[r['fonte']] = (tabela.linhas, hashlib.sha256(raw).hexdigest())
        linhas, _ = fontes[r['fonte']]
        if (r['secao'], r['linha_oficial']) not in linhas:
            raise ValueError(f"Relatorio mudou ou linha ausente: {r['id']}. Nenhum limite aplicado.")
    return {url:sha for url,(_,sha) in fontes.items()}


def aplicar(conn, tenant, manifesto, fontes, gravar=False):
    """Fonte validada antes da transacao; locks apenas durante a escrita atomica."""
    resultado = {'aplicado':gravar, 'trechos':[], 'preservados':[], 'pendentes':manifesto.get('pendentes',[])}
    with conn.cursor() as cursor:
        for r in manifesto['registros']:
            osm = f"https://www.openstreetmap.org/way/{r['osm_way_id']}"
            fonte = r['fonte']+f"#sprain={r['id']};osm-way={r['osm_way_id']}"
            cursor.execute("""WITH referencia AS (SELECT ST_Transform(
                ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),31983) AS geom)
                SELECT t.id_trecho,t.limites_malha,t.limites_verificado_em,t.fonte_malha,
                ST_CoveredBy(t.geom,ST_Buffer(r.geom,0.20)) AND t.sentido='DIRETO'
                AND ST_LineLocatePoint(r.geom,ST_StartPoint(t.geom))
                  < ST_LineLocatePoint(r.geom,ST_EndPoint(t.geom)) AS corresponde
                FROM trechos_osm t CROSS JOIN referencia r WHERE t.tenant_malha=%s AND t.fonte_malha IN (%s,%s)
                AND EXISTS(SELECT 1 FROM malha_importacoes m WHERE m.id=t.importacao_malha_id AND m.ativo)
                FOR UPDATE OF t""", (json.dumps(r['geometria']),tenant,osm,fonte))
            rows = cursor.fetchall()
            if not rows:
                resultado['preservados'].append({'registro':r['id'],'motivo':'Sem referencia ativa correspondente; nenhuma via criada.'})
            for trecho, anteriores, verificado, fonte_anterior, corresponde in rows:
                # A tabela legada nao possui unicidade em id_trecho. Arestas com
                # identificador ambiguo nao podem receber uma restricao automaticamente.
                cursor.execute('SELECT COUNT(*) FROM trechos_osm WHERE id_trecho=%s',(trecho,))
                if cursor.fetchone()[0] != 1:
                    resultado['preservados'].append({'id_trecho':trecho,'motivo':'Identificador de trecho duplicado; exige revisao.'})
                    continue
                if not corresponde or verificado is not None:
                    resultado['preservados'].append({'id_trecho':trecho,'motivo':'Geometria/sentido diferente ou cadastro ja revisado.'})
                    continue
                anteriores = anteriores or {}
                # A fonte oficial nunca eleva silenciosamente um limite mais restritivo existente.
                novos = dict(anteriores)
                for campo, valor in r['limites'].items():
                    novos[campo] = min(anteriores.get(campo,valor),valor)
                resultado['trechos'].append({'id_trecho':trecho,'registro':r['id'],'antes':anteriores,'depois':novos})
                if gravar:
                    cursor.execute("""UPDATE trechos_osm SET limites_malha=%s::jsonb,fonte_malha=%s,
                        limites_verificado_em=%s,limites_valido_ate=%s WHERE id_trecho=%s AND tenant_malha=%s""",
                        (json.dumps(novos),fonte,manifesto['verificado_em'],manifesto['valido_ate'],trecho,tenant))
                    cadastro = {'antes':anteriores,'fonte_anterior':fonte_anterior,
                        'depois':{'limites':novos,'fonte':fonte,'verificado_em':manifesto['verificado_em'],
                        'valido_ate':manifesto['valido_ate']},'manifesto':r,'sha256_relatorio':fontes[r['fonte']]}
                    cursor.execute('INSERT INTO malha_limites_revisoes(tenant_id,id_trecho,cadastro) VALUES(%s,%s,%s::jsonb)',
                        (tenant,trecho,json.dumps(cadastro)))
    return resultado


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant',required=True)
    parser.add_argument('--arquivo',type=Path,default=MANIFESTO)
    parser.add_argument('--aplicar',action='store_true')
    args = parser.parse_args()
    manifesto = json.loads(args.arquivo.read_text(encoding='utf-8'))
    validar_manifesto(manifesto)
    fontes = conferir_fontes(manifesto)
    from sincronizar_dados_publicos import conectar
    with conectar() as conn:
        resultado = aplicar(conn,args.tenant,manifesto,fontes,args.aplicar)
        if not args.aplicar:
            conn.rollback()
    print(json.dumps(resultado,ensure_ascii=False))


if __name__ == '__main__':
    main()
