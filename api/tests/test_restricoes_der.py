"""Restrições oficiais exigem fonte e correspondencia; nunca liberam dados ausentes."""
import copy
import io
import json
import secrets
import sys
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.aplicar_restricoes_der import MANIFESTO, TabelaDER, aplicar, conferir_fontes, validar_manifesto
from scripts.sincronizar_dados_publicos import conectar


def manifesto():
    m = json.loads(MANIFESTO.read_text(encoding='utf-8'))
    agora = datetime.now(timezone.utc)
    m.update(verificado_em=(agora-timedelta(minutes=1)).isoformat(),valido_ate=(agora+timedelta(days=1)).isoformat())
    return m


def html_registro(r, secao=None):
    return '<table><tr><th>'+escape(secao or r['secao'])+'</th></tr><tr>'+''.join(
        '<td>'+escape(v)+'</td>' for v in r['linha_oficial'])+'</tr></table>'


def test_der_rejeita_linha_alterada_e_nao_confunde_acesso_com_eixo(monkeypatch):
    m = manifesto()
    r = m['registros'][0]
    p = TabelaDER(); p.feed(html_registro(r,'SPA 015/330'))
    assert p.linhas == [('SPA 015/330',r['linha_oficial'])]
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:io.BytesIO(html_registro(r,'SPA 015/330').encode()))
    with pytest.raises(ValueError,match='Relatorio mudou'):
        conferir_fontes(m)


@pytest.mark.parametrize('campo,valor', [('largura_max_m',float('nan')),('peso_max_t',-1),('altura_max_m',float('inf'))])
def test_der_rejeita_limites_invalidos(campo,valor):
    m = manifesto(); m['registros'][0]['limites']={campo:valor}
    with pytest.raises(ValueError,match='Limite invalido'):validar_manifesto(m)


def test_der_manifesto_expirado_nao_renova_verificacao_automaticamente():
    m = manifesto();m['valido_ate']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError,match='vencido'):validar_manifesto(m)


def test_der_valor_importado_deve_corresponder_a_coluna_publicada():
    m=manifesto();validar_manifesto(m)
    m['registros'][0]['limites']['largura_max_m']=5
    with pytest.raises(ValueError,match='coluna oficial'):validar_manifesto(m)


def test_der_importa_so_mesma_empresa_geometria_sentido_e_preserva_revisao_humana():
    m = manifesto();m['registros']=m['registros'][:1]
    r = m['registros'][0]
    tenant = 'TEST_DER_'+secrets.token_hex(5)
    base = 9_000_000_000+secrets.randbelow(1_000_000_000)
    origem = f"https://www.openstreetmap.org/way/{r['osm_way_id']}"
    conn = conectar()
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO malha_importacoes(tenant_id,sha256,fonte) VALUES(%s,%s,'TESTE') RETURNING id",(tenant,secrets.token_hex(32)))
            imp = c.fetchone()[0]
            for i,empresa,reverso,deslocamento,verificado in (
                (0,tenant,False,0,False),(1,tenant,False,0,True),(2,tenant+'OUTRA',False,0,False),
                (3,tenant,True,0,False),(4,tenant,False,10,False)):
                coords=copy.deepcopy(r['geometria'])
                if reverso:coords['coordinates'].reverse()
                c.execute("""INSERT INTO trechos_osm(id_trecho,tenant_malha,fonte_malha,sentido,geom,
                    importacao_malha_id,limites_malha,limites_verificado_em)
                    VALUES(%s,%s,%s,'DIRETO',ST_Translate(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),31983),%s,0),
                    %s,%s::jsonb,%s)""",(base+i,empresa,origem,json.dumps(coords),deslocamento,imp,
                        json.dumps({'altura_max_m':4.2,'largura_max_m':4.3}) if i==0 else '{}',
                        datetime.now(timezone.utc) if verificado else None))
        fontes={r['fonte']:'SHA_TESTE'}
        ensaio=aplicar(conn,tenant,m,fontes,False)
        assert len(ensaio['trechos'])==1
        with conn.cursor() as c:
            c.execute('SELECT limites_malha FROM trechos_osm WHERE id_trecho=%s',(base,))
            assert c.fetchone()[0]=={'altura_max_m':4.2,'largura_max_m':4.3}
        resultado=aplicar(conn,tenant,m,fontes,True)
        assert resultado['trechos'][0]['depois']=={'altura_max_m':4.2,'largura_max_m':4.3}
        repeticao=aplicar(conn,tenant,m,fontes,True)
        assert repeticao['trechos']==[]
        with conn.cursor() as c:
            c.execute('SELECT COUNT(*) FROM malha_limites_revisoes WHERE tenant_id=%s',(tenant,))
            assert c.fetchone()[0]==1
            c.execute('SELECT COUNT(*) FROM trechos_osm WHERE id_trecho BETWEEN %s AND %s AND limites_verificado_em IS NOT NULL',(base,base+4))
            assert c.fetchone()[0]==2  # Apenas o novo registro e o cadastro humano preexistente.
    finally:
        conn.rollback();conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('perfil,chuva',[('FASTEST',0),('SAFEST',85)])
async def test_limite_recalcula_rota_cache_e_diferenca_financeira(perfil,chuva):
    import asyncpg
    from app.config import settings
    from app.services.routing_engine import RoutingEngine
    from app.services.viagem_caminhao import comparar_custos
    conn=await asyncpg.connect(settings.database_url)
    tx=conn.transaction();await tx.start()
    tenant='TEST_DER_ROTA_'+secrets.token_hex(5)
    base=20_000_000_000+secrets.randbelow(1_000_000_000)
    coords=[[-50,-25],[-49.9996,-25],[-49.9992,-25],[-49.9996,-24.9996]]
    try:
        for i,(lon,lat) in enumerate(coords):
            await conn.execute('INSERT INTO trechos_osm_vertices_pgr(id,the_geom) VALUES($1,ST_Transform(ST_SetSRID(ST_Point($2,$3),4326),31983))',base+i,lon,lat)
        for i,(a,b) in enumerate([(0,1),(1,2),(0,3),(3,2)]):
            geom=json.dumps({'type':'LineString','coordinates':[coords[a],coords[b]]})
            await conn.execute("""INSERT INTO trechos_osm(id_trecho,source,target,geom,length,name,highway,sentido,
                tenant_malha,limites_malha,ivi_score) SELECT $1,$2,$3,g,ST_Length(g),'TESTE','primary','DIRETO',$4,'{}',0
                FROM (SELECT ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON($5),4326),31983) g) s""",base+i,base+a,base+b,tenant,geom)
        dims={'altura_m':4.2,'largura_m':4.5,'comprimento_m':18,'peso_total_t':40,'eixos':5}
        args=dict(orig_lon=coords[0][0],orig_lat=coords[0][1],dest_lon=coords[2][0],dest_lat=coords[2][1],
            tenant_id=tenant,vehicle_dimensions=dims,profile=perfil,rain_mm=chuva)
        original=await RoutingEngine.compute_route(conn,**args)
        assert original['ids_trechos']==[base,base+1]
        # Simula a gravacao do limite oficial usando a mesma coluna do importador,
        # depois de a rota original ja estar em cache.
        await conn.execute("UPDATE trechos_osm SET limites_malha=$2::jsonb WHERE id_trecho=$1",base,json.dumps({'largura_max_m':4.4}))
        alternativa=await RoutingEngine.compute_route(conn,**args)
        assert alternativa['ids_trechos']==[base+2,base+3]
        assert base in alternativa['trechos_excluidos_por_limites']
        financeiro=comparar_custos(original,alternativa,{},False)
        assert financeiro['custo_desvio_brl']>0
        assert financeiro['prejuizo_potencial_evitado_brl']==0  # Nao inventar perda por colisao com ponte.
        assert financeiro['economia_liquida_potencial_brl']==-financeiro['custo_desvio_brl']
        permitido=await RoutingEngine.compute_route(conn,**{**args,'vehicle_dimensions':{**dims,'largura_m':4.4}})
        assert permitido['ids_trechos']==original['ids_trechos']
    finally:
        await tx.rollback();await conn.close();RoutingEngine.clear_cache(tenant)
