"""Testes de limites e API; o cenario SQL usa transacao revertida no banco local."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import asyncpg
import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.config import settings
from app.database import get_connection
from app.routers.infraestrutura import router, VeiculoDimensoes, PontoCadastro
from app.services.infraestrutura_viaria import avaliar_ponto, SCHEMA
from app.services.routing_engine import RoutingEngine
from app.routers import logistica, malha, rotas

AGORA = datetime.now(timezone.utc)
VEICULO = dict(altura_m=4.2, largura_m=2.6, comprimento_m=18, peso_total_t=40, eixos=5)


def ponte(**alteracoes):
    return dict(tipo="PONTE", verificado_em=AGORA - timedelta(days=1),
                valido_ate=AGORA + timedelta(days=1), altura_max_m=4.5, largura_max_m=3,
                comprimento_max_m=20, peso_max_t=45, **alteracoes)


@pytest.mark.parametrize("medida,limite", [
    ("altura_m", "altura_max_m"), ("largura_m", "largura_max_m"),
    ("comprimento_m", "comprimento_max_m"), ("peso_total_t", "peso_max_t"),
])
def test_limite_excedido_bloqueia_e_igual_nao_bloqueia(medida, limite):
    p = ponte()
    v = VeiculoDimensoes(**{**VEICULO, medida: p[limite]})
    assert avaliar_ponto(p, v, AGORA)["status"] == "COMPATIVEL_COM_LIMITES_CADASTRADOS"
    v = VeiculoDimensoes(**{**VEICULO, medida: p[limite] + 0.01})
    assert avaliar_ponto(p, v, AGORA)["limites_excedidos"] == [limite]


def test_limites_ausentes_e_vencidos_exigem_conferencia():
    p = ponte()
    p["altura_max_m"] = None
    assert avaliar_ponto(p, VeiculoDimensoes(**VEICULO), AGORA)["status"] == "CONFERENCIA_NECESSARIA"
    p = ponte()
    p["valido_ate"] = AGORA
    assert avaliar_ponto(p, VeiculoDimensoes(**VEICULO), AGORA)["status"] == "CONFERENCIA_NECESSARIA"
    p["altura_max_m"] = 3
    assert avaliar_ponto(p, VeiculoDimensoes(**VEICULO), AGORA)["status"] == "BLOQUEADO"


def test_tarifa_zero_e_vencida_nao_sao_confundidas():
    p = ponte()
    p.update(tipo="PEDAGIO", tarifa_por_eixo=Decimal("8.90"))
    assert avaliar_ponto(p, VeiculoDimensoes(**VEICULO), AGORA)["custo_estimado_reais"] == 44.5
    p["tarifa_por_eixo"] = Decimal("0")
    assert avaliar_ponto(p, VeiculoDimensoes(**VEICULO), AGORA)["custo_estimado_reais"] == 0
    p["valido_ate"] = AGORA
    assert avaliar_ponto(p, VeiculoDimensoes(**VEICULO), AGORA)["custo_estimado_reais"] is None


def test_referencia_osm_nao_confirma_passagem_ou_tarifa():
    p=ponte()
    p["origem_dados"]="REFERENCIA_OSM"
    assert avaliar_ponto(p,VeiculoDimensoes(**VEICULO),AGORA)["status"]=="CONFERENCIA_NECESSARIA"
    p.update(tipo="PEDAGIO",tarifa_por_eixo=Decimal("10"))
    assert avaliar_ponto(p,VeiculoDimensoes(**VEICULO),AGORA)["custo_estimado_reais"] is None
    with pytest.raises(ValidationError):
        PontoCadastro(**cadastro(tipo="PEDAGIO",origem_dados="REFERENCIA_OSM",tarifa_por_eixo=10))


def cadastro(**alteracoes):
    return {"tipo": "PONTE", "nome": "Fixture", "id_trecho": 1, "longitude": -48,
            "latitude": -21, "fonte": "Fixture de teste", "verificado_em": AGORA - timedelta(days=1),
            "valido_ate": AGORA + timedelta(days=1), **alteracoes}


@pytest.mark.parametrize("alteracoes", [
    {"verificado_em": AGORA.replace(tzinfo=None)}, {"verificado_em": AGORA + timedelta(hours=1)},
    {"valido_ate": AGORA - timedelta(days=2)}, {"altura_max_m": -1}, {"fonte": " "},
    {"tipo": "PEDAGIO", "altura_max_m": 3}, {"tarifa_por_eixo": 10},
])
def test_cadastro_invalido(alteracoes):
    with pytest.raises(ValidationError):
        PontoCadastro(**cadastro(**alteracoes))


def app_com_conexao(conn):
    app = FastAPI()
    app.include_router(router)
    app.include_router(logistica.router)
    app.include_router(malha.router)
    app.include_router(rotas.router)
    async def conexao():
        yield conn
    app.dependency_overrides[get_connection] = conexao
    return app


@pytest.mark.asyncio
async def test_autenticacao_e_permissao_de_cadastro():
    conn = AsyncMock()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_com_conexao(conn)),
                                 base_url="http://test") as client:
        assert (await client.get("/api/v1/infraestrutura/pontos")).status_code == 401
        payload = PontoCadastro(**cadastro()).model_dump(mode="json")
        for key in ("key_viewer_demo", "key_operator_demo"):
            resp = await client.post("/api/v1/infraestrutura/pontos", json=payload,
                                     headers={"X-API-Key": key})
            assert resp.status_code == 403
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_sql_rota_evitar_ponte_pedagio_filtrado_e_isolamento():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    RoutingEngine.clear_cache()
    try:
        await conn.execute(SCHEMA.read_text(encoding="utf-8"))
        # Pequena malha desconectada da malha real. Tudo e revertido ao terminar.
        await conn.execute("""
            INSERT INTO trechos_osm_vertices_pgr(id,the_geom) VALUES
            (9000000001,ST_Transform(ST_SetSRID(ST_Point(-48,-21),4326),31983)),
            (9000000002,ST_Transform(ST_SetSRID(ST_Point(-47.999,-21),4326),31983)),
            (9000000003,ST_Transform(ST_SetSRID(ST_Point(-47.9995,-20.999),4326),31983));
            INSERT INTO trechos_osm(id_trecho,name,highway,length,source,target,geom)
            SELECT edge,'Fixture','primary',length,a,b,ST_MakeLine(v1.the_geom,v2.the_geom)
            FROM (VALUES
                (9000000001::bigint,100,9000000001::bigint,9000000002::bigint),
                (9000000002,150,9000000001,9000000003),
                (9000000003,150,9000000003,9000000002)
            ) AS e(edge,length,a,b)
            JOIN trechos_osm_vertices_pgr v1 ON v1.id=a
            JOIN trechos_osm_vertices_pgr v2 ON v2.id=b;
        """)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_com_conexao(conn)),
                                     base_url="http://test", headers={"X-API-Key": "key_admin_demo"}) as client:
            payload = {"origem_lon": -48, "origem_lat": -21, "destino_lon": -47.999,
                       "destino_lat": -21, "veiculo": VEICULO, "perfil": "SHORTEST"}
            inicial = (await client.post("/api/v1/infraestrutura/rota-caminhao", json=payload)).json()
            assert inicial["rota"]["ids_trechos"] == [9000000001]
            assert inicial["status_passagem"] == "CONFERENCIA_NECESSARIA"
            assert inicial["pedagios"]["custo_total_confirmado_reais"] is None
            p = PontoCadastro(**cadastro(id_trecho=9000000001, altura_max_m=3)).model_dump(mode="json")
            resp = await client.post("/api/v1/infraestrutura/pontos", json=p)
            assert resp.status_code == 201, resp.text
            id_ponte = resp.json()["id"]
            p = PontoCadastro(**cadastro(tipo="PEDAGIO", id_trecho=9000000001,
                                         tarifa_por_eixo="8.90")).model_dump(mode="json")
            assert (await client.post("/api/v1/infraestrutura/pontos", json=p)).status_code == 201
            desviada = (await client.post("/api/v1/infraestrutura/rota-caminhao", json=payload)).json()
            assert set(desviada["rota"]["ids_trechos"]) == {9000000002, 9000000003}
            assert desviada["pedagios"]["quantidade_cadastrada_na_rota"] == 0
            outra_empresa = await client.get("/api/v1/infraestrutura/pontos",
                                             headers={"X-API-Key": "key_admin_express"})
            assert id_ponte not in [f["properties"]["id"] for f in outra_empresa.json()["features"]]
            resp = await client.put(f"/api/v1/infraestrutura/pontos/{id_ponte}", json=p,
                                     headers={"X-API-Key": "key_admin_express"})
            assert resp.status_code == 404
            p = PontoCadastro(**cadastro(id_trecho=9000000001, altura_max_m=5)).model_dump(mode="json")
            assert (await client.put(f"/api/v1/infraestrutura/pontos/{id_ponte}", json=p)).status_code == 200
            permitida = (await client.post("/api/v1/infraestrutura/rota-caminhao", json=payload)).json()
            assert permitida["rota"]["ids_trechos"] == [9000000001]
            assert permitida["pedagios"]["subtotal_conhecido_reais"] == 44.5
            # Cadastro completo: dimensoes da frota entram na viagem e na reavaliacao.
            v = {"id_veiculo":"TEST_INFRA_ROLLBACK","placa":"INF0001","modelo":"Fixture",
                 "tipo_veiculo":"CARRETA_5_EIXOS","dimensoes":VEICULO,
                 "custos_operacionais":{"custo_por_km":7,"prejuizo_potencial_alagamento":1000}}
            assert (await client.post("/api/v1/logistica/veiculos",json=v)).status_code == 200
            assert (await client.post('/api/v1/logistica/veiculos',json={**v,
                'custos_operacionais':{'custo_hora_motorista':30}})).status_code==200
            custos_frota=(await client.get('/api/v1/logistica/veiculos')).json()
            custos_frota=next(x for x in custos_frota if x['id_veiculo']==v['id_veiculo'])['custos_operacionais']
            assert custos_frota['custo_por_km']==7
            assert custos_frota['custo_hora_motorista']==30
            operacao = {"id_operacao":"TEST_INFRA_ROLLBACK","id_veiculo":v["id_veiculo"],
                "origem_nome":"Fixture A","destino_nome":"Fixture B",
                **{k:payload[k] for k in ("origem_lon","origem_lat","destino_lon","destino_lat")},
                "janela_inicio":"2026-10-12T10:00:00-03:00","janela_fim":"2026-10-12T12:00:00-03:00"}
            resp = await client.post("/api/v1/logistica/operacoes",json=operacao)
            assert resp.status_code == 200,resp.text
            assert resp.json()["infraestrutura"]["dimensoes_informadas"]
            assert (await client.post("/api/v1/logistica/operacoes",json=operacao)).status_code == 200
            lista = (await client.get("/api/v1/logistica/veiculos")).json()
            assert next(v for v in lista if v["id_veiculo"]=="TEST_INFRA_ROLLBACK")["dimensoes"]==VEICULO
            operacao["id_operacao"]="INVALIDO"
            operacao["janela_fim"]=operacao["janela_inicio"]
            assert (await client.post("/api/v1/logistica/operacoes",json=operacao)).status_code == 422
            p["altura_max_m"]=3
            assert (await client.put(f"/api/v1/infraestrutura/pontos/{id_ponte}",json=p)).status_code == 200
            reavaliada=(await client.get("/api/v1/logistica/operacoes/TEST_INFRA_ROLLBACK/rota-caminhao")).json()
            assert set(reavaliada["rota_atual_avaliada"]["ids_trechos"])=={9000000002,9000000003}
            await conn.execute("UPDATE trechos_osm SET ivi_score=0 WHERE id_trecho BETWEEN 9000000001 AND 9000000003")
            sim=await client.post('/api/v1/logistica/simular-impacto',json={
                'precipitacao_mm':0,'parametros_custo':{'prejuizo_potencial_alagamento':2800}})
            assert sim.status_code==200,sim.text
            rec=next(r for r in sim.json()['recomendacoes'] if r['id_operacao']=='TEST_INFRA_ROLLBACK')
            assert rec['acao']=='ALTERAR_ROTA'
            fin=rec['infraestrutura']['financeiro']
            assert fin['delta_pedagios_conhecidos_brl']==-44.5
            assert fin['premissas']['custo_por_km']==7
            assert fin['premissas']['prejuizo_potencial_alagamento']==1000
            assert fin['custo_desvio_brl']<0
            assert fin['prejuizo_potencial_evitado_brl']==0
            assert fin['economia_liquida_potencial_brl']==-fin['custo_desvio_brl']
            audit=await client.get('/api/v1/logistica/operacoes/TEST_INFRA_ROLLBACK/explicacao')
            assert audit.status_code==200,audit.text
            assert audit.json()['infraestrutura']['financeiro']==fin
            assert audit.json()['metricas']['distancia_alternativa_km']==0.3
            decisao='/api/v1/logistica/operacoes/TEST_INFRA_ROLLBACK/decisao'
            assert (await client.post(decisao,json={'decisao':'MANTER_ROTA_ORIGINAL'})).status_code==409
            assert (await client.post(decisao,json={'decisao':'APROVAR_DESVIO'})).status_code==200
            await conn.execute('UPDATE trechos_osm SET ivi_score=100 WHERE id_trecho=9000000001')
            RoutingEngine.clear_cache()
            sim=(await client.post('/api/v1/logistica/simular-impacto',json={'precipitacao_mm':85})).json()
            rec=next(r for r in sim['recomendacoes'] if r['id_operacao']=='TEST_INFRA_ROLLBACK')
            assert rec['impacto']['prejuizo_potencial_evitado_brl']==1000
            await conn.execute('UPDATE trechos_osm SET ivi_score=100 WHERE id_trecho=9000000002')
            RoutingEngine.clear_cache()
            sim=(await client.post('/api/v1/logistica/simular-impacto',json={'precipitacao_mm':85})).json()
            rec=next(r for r in sim['recomendacoes'] if r['id_operacao']=='TEST_INFRA_ROLLBACK')
            assert rec['impacto']['prejuizo_potencial_evitado_brl']==0
            assert rec['infraestrutura']['financeiro']['trechos_risco_residual_alternativa']>0
            await conn.execute('UPDATE trechos_osm SET ivi_score=0 WHERE id_trecho BETWEEN 9000000001 AND 9000000003')
            RoutingEngine.clear_cache()
            pequeno={**v,'id_veiculo':'TEST_INFRA_SMALL','placa':'INF0002',
                'dimensoes':{**VEICULO,'altura_m':2.5,'eixos':2},'tipo_veiculo':'VUC'}
            assert (await client.post('/api/v1/logistica/veiculos',json=pequeno)).status_code==200
            econ=await client.post('/api/v1/logistica/decisao-economica',json={
                **{k:payload[k] for k in ('origem_lon','origem_lat','destino_lon','destino_lat')},
                'id_veiculo':pequeno['id_veiculo'],'precipitacao_mm':0,
                'parametros':{'tempo_espera_min':30}})
            assert econ.status_code==200,econ.text
            assert econ.json()['infraestrutura']['original']['pedagios']['subtotal_conhecido_reais']==17.8
            assert econ.json()['decisao']['tradeoff']['rota_direta']['origem_custo_variavel']=='CUSTO_POR_KM_INFORMADO'
            assert econ.json()['decisao']['tradeoff']['rota_direta']['custo_combustivel_brl'] is None
            assert econ.json()['decisao']['tradeoff']['aguardar']['tempo_espera_informado_min']==30
            sessao=(await client.get("/api/v1/infraestrutura/sessao")).json()
            assert sessao=={"tenant_id":"demo_corp","perfil":"ADMIN"}
            mapa=(await client.post("/api/v1/infraestrutura/avaliar-mapa",json={"veiculo":VEICULO},
                headers={"X-API-Key":"key_viewer_demo"})).json()
            assert next(f for f in mapa["features"] if f["properties"].get("id")==id_ponte)["properties"]["status"]=="BLOQUEADO"
            update={"dimensoes":VEICULO,"perfil":"SHORTEST"}
            endpoint="/api/v1/logistica/operacoes/TEST_INFRA_ROLLBACK/planejamento-caminhao"
            assert (await client.put(endpoint,json=update,headers={"X-API-Key":"key_viewer_demo"})).status_code==403
            assert (await client.put(endpoint,json=update,headers={"X-API-Key":"key_admin_express"})).status_code==404
            res=await client.put(endpoint,json=update,headers={"X-API-Key":"key_operator_demo"})
            assert res.status_code==200,res.text
            assert set(res.json()["rota"]["ids_trechos"])=={9000000002,9000000003}
            assert await conn.fetchval("SELECT perfil_rota FROM operacoes WHERE id_operacao='TEST_INFRA_ROLLBACK'")=="SHORTEST"
            assert await conn.fetchval("SELECT count(*) FROM operacao_rotas_trechos WHERE id_operacao='TEST_INFRA_ROLLBACK'")==2
            await conn.execute("UPDATE operacoes SET status='DELIVERED' WHERE id_operacao='TEST_INFRA_ROLLBACK'")
            assert (await client.put(endpoint,json=update)).status_code==409
            await conn.execute("UPDATE operacoes SET status='PLANNED' WHERE id_operacao='TEST_INFRA_ROLLBACK'")
            await conn.execute("UPDATE trechos_osm SET limites_malha='{\"altura_max_m\":1}'::jsonb WHERE id_trecho IN (9000000002,9000000003)")
            RoutingEngine.clear_cache()
            assert (await client.put(endpoint,json=update)).status_code==422
            assert await conn.fetchval("SELECT count(*) FROM operacao_rotas_trechos WHERE id_operacao='TEST_INFRA_ROLLBACK'")==2
            sim=await client.post('/api/v1/logistica/simular-impacto',json={'precipitacao_mm':0})
            assert sim.status_code==200,sim.text
            rec=next(r for r in sim.json()['recomendacoes'] if r['id_operacao']=='TEST_INFRA_ROLLBACK')
            assert rec['acao']=='AGUARDAR_MELHORA'
            assert rec['impacto']['estimativa_disponivel'] is False
            assert rec['infraestrutura']['financeiro'] is None
            assert (await client.post(decisao,json={'decisao':'APROVAR_DESVIO'})).status_code==409
            await conn.execute("UPDATE trechos_osm SET limites_malha=NULL WHERE id_trecho IN (9000000002,9000000003)")
            RoutingEngine.clear_cache()
            # Validacao de lote nao grava; erro no segundo ponto reverte o primeiro.
            novo=PontoCadastro(**cadastro(nome="LOTE",id_trecho=9000000001)).model_dump(mode="json")
            lote={"pontos":[novo]}
            antes=await conn.fetchval("SELECT count(*) FROM infraestrutura_viaria")
            assert (await client.post("/api/v1/infraestrutura/importar-pontos",json=lote)).json()["status"]=="VALIDADO_SEM_GRAVAR"
            assert await conn.fetchval("SELECT count(*) FROM infraestrutura_viaria")==antes
            lote["validar_apenas"]=False
            id_lote=(await client.post("/api/v1/infraestrutura/importar-pontos",json=lote)).json()["ids"][0]
            assert (await client.post("/api/v1/infraestrutura/importar-pontos",json=lote)).json()["ids"]==[id_lote]
            antes=await conn.fetchval("SELECT count(*) FROM infraestrutura_viaria")
            erro={"pontos":[{**novo,"nome":"PRIMEIRO"},{**novo,"nome":"SEGUNDO","longitude":0}],"validar_apenas":False}
            assert (await client.post("/api/v1/infraestrutura/importar-pontos",json=erro)).status_code==422
            assert await conn.fetchval("SELECT count(*) FROM infraestrutura_viaria")==antes
            assert (await client.delete(f"/api/v1/infraestrutura/pontos/{id_lote}")).status_code==200
            hist=(await client.get(f"/api/v1/infraestrutura/pontos/{id_lote}/historico")).json()
            assert [h["acao"] for h in hist]==["DESATIVAR","SALVAR"]
            assert (await client.delete(f"/api/v1/infraestrutura/pontos/{id_lote}",headers={"X-API-Key":"key_admin_express"})).status_code==404
            # Sentido direto impede a rota inversa; o motor encontra o outro caminho.
            await conn.execute("UPDATE trechos_osm SET sentido='DIRETO' WHERE id_trecho=9000000001")
            await client.delete(f"/api/v1/infraestrutura/pontos/{id_ponte}")
            RoutingEngine.clear_cache()
            inversa = await RoutingEngine.compute_route(conn,-47.999,-21,-48,-21,profile="SHORTEST",tenant_id="demo_corp",vehicle_dimensions=VEICULO)
            assert set(inversa["ids_trechos"])=={9000000002,9000000003}
            p["longitude"] = 0
            assert (await client.post("/api/v1/infraestrutura/pontos", json=p)).status_code == 422
            payload["destino_lon"] = 0
            assert (await client.post("/api/v1/infraestrutura/rota-caminhao", json=payload)).status_code == 422
    finally:
        await tx.rollback()
        await conn.close()
        RoutingEngine.clear_cache()


@pytest.mark.asyncio
async def test_importacao_malha_transacional_direcionada_e_isolada():
    conn=await asyncpg.connect(settings.database_url)
    tx=conn.transaction()
    await tx.start()
    RoutingEngine.clear_cache()
    try:
        await conn.execute(SCHEMA.read_text(encoding="utf-8"))
        payload={"fonte":"Fixture malha","segmentos":[{"origem":"a","destino":"b",
            "coordenadas":[[-49,-22],[-48.999,-22]],"nome":"Fixture","highway":"primary","sentido":"DIRETO"}]}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_com_conexao(conn)),base_url="http://test",
                                    headers={"X-API-Key":"key_admin_demo"}) as client:
            antes=await conn.fetchval("SELECT count(*) FROM trechos_osm")
            assert (await client.post("/api/v1/infraestrutura/malha/importar",json=payload)).json()["status"]=="VALIDADO_SEM_GRAVAR"
            assert await conn.fetchval("SELECT count(*) FROM trechos_osm")==antes
            payload["validar_apenas"]=False
            res=await client.post("/api/v1/infraestrutura/malha/importar",json=payload)
            assert res.status_code==200,res.text
            id_import=res.json()["id"]
            candidatos=(await client.get("/api/v1/infraestrutura/malha/trechos-proximos?longitude=-49&latitude=-22")).json()
            assert len(candidatos["candidatos"])==1
            outro=(await client.get("/api/v1/infraestrutura/malha/trechos-proximos?longitude=-49&latitude=-22",
                headers={"X-API-Key":"key_admin_express"})).json()
            assert outro["candidatos"]==[]
            assert (await client.post("/api/v1/infraestrutura/malha/importar",json=payload)).json()["status"]=="JA_IMPORTADO"
            assert await conn.fetchval("SELECT count(*) FROM trechos_osm")==antes+1
            direta=await RoutingEngine.compute_route(conn,-49,-22,-48.999,-22,tenant_id="demo_corp",vehicle_dimensions=VEICULO)
            assert direta is not None
            await conn.execute("UPDATE trechos_osm SET limites_malha='{\"altura_max_m\":3}'::jsonb WHERE importacao_malha_id=$1",id_import)
            RoutingEngine.clear_cache()
            assert await RoutingEngine.compute_route(conn,-49,-22,-48.999,-22,tenant_id="demo_corp",vehicle_dimensions=VEICULO) is None
            pequena=await RoutingEngine.compute_route(conn,-49,-22,-48.999,-22,tenant_id="demo_corp",vehicle_dimensions={**VEICULO,"altura_m":2})
            assert pequena is not None
            assert pequena["geojson"]["features"][0]["properties"]["limites_importados"]["altura_max_m"]==3
            trecho_id=direta["ids_trechos"][0]
            correcao={"altura_max_m":5,"largura_max_m":3,"comprimento_max_m":20,"peso_max_t":45,
                "fonte":"Fixture de conferencia dos limites","verificado_em":(AGORA-timedelta(days=1)).isoformat(),
                "valido_ate":(AGORA+timedelta(days=1)).isoformat()}
            url=f"/api/v1/infraestrutura/trechos/{trecho_id}/limites"
            assert (await client.put(url,json=correcao,headers={"X-API-Key":"key_operator_demo"})).status_code==403
            assert (await client.put(url,json=correcao,headers={"X-API-Key":"key_admin_express"})).status_code==404
            assert (await client.put(url,json=correcao)).status_code==200
            conferida=await RoutingEngine.compute_route(conn,-49,-22,-48.999,-22,tenant_id="demo_corp",vehicle_dimensions=VEICULO)
            assert conferida is not None
            mapa=(await client.post('/api/v1/infraestrutura/avaliar-mapa',json={'veiculo':VEICULO})).json()
            limite=next(f for f in mapa['features'] if f['properties'].get('id_trecho')==trecho_id)
            assert limite['properties']['status']=='COMPATIVEL_COM_LIMITES_CADASTRADOS'
            assert limite['properties']['editavel'] is True
            hist=(await client.get(f'/api/v1/infraestrutura/trechos/{trecho_id}/historico')).json()
            assert hist[0]['cadastro']['antes']['altura_max_m']==3
            assert hist[0]['cadastro']['depois']['altura_max_m']==5
            inversa=await RoutingEngine.compute_route(conn,-48.999,-22,-49,-22,tenant_id="demo_corp",vehicle_dimensions=VEICULO)
            assert inversa is None
            estrangeira=await RoutingEngine.compute_route(conn,-49,-22,-48.999,-22,tenant_id="log_express",vehicle_dimensions=VEICULO)
            assert estrangeira is None
            assert (await client.delete(f"/api/v1/infraestrutura/malha/importacoes/{id_import}",headers={"X-API-Key":"key_admin_express"})).status_code==404
            assert (await client.delete(f"/api/v1/infraestrutura/malha/importacoes/{id_import}")).status_code==200
            antigo=PontoCadastro(**cadastro(id_trecho=direta["ids_trechos"][0],longitude=-49,latitude=-22)).model_dump(mode="json")
            assert (await client.post("/api/v1/infraestrutura/pontos",json=antigo)).status_code==422
            assert await RoutingEngine.compute_route(conn,-49,-22,-48.999,-22,tenant_id="demo_corp",vehicle_dimensions=VEICULO) is None
    finally:
        await tx.rollback()
        await conn.close()
        RoutingEngine.clear_cache()
