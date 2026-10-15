"""Contratos de custo, geometria e fontes; sem alterar cadastros da demonstracao."""
import importlib.util
import io
import sys
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.routers.dados_publicos import ConsultaRota
from app.schemas import CustosCaminhao
from app.services.custo_combustivel import completar_custos, custo_quilometrico
from app.services.infraestrutura_viaria import resumir_rota
from app.services.viagem_caminhao import comparar_custos

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts import worker_dados_publicos as worker
from scripts.anp_semanal import para_csv, descobrir_url
from scripts.sincronizar_dados_publicos import ler_anp, ler_artesp
from scripts.aplicar_tarifas_conferidas import planejar


def referencia(preco=7):
    return {'preco':preco,'data':date.today(),'fonte':'https://www.gov.br/anp/exemplo','amostra':100}


def test_automatico_varia_com_caminhao_e_respeita_custo_total_informado():
    leve=completar_custos({}, {'peso_total_t':8,'eixos':2}, referencia())
    pesado=completar_custos({}, {'peso_total_t':40,'eixos':5}, referencia())
    assert custo_quilometrico(pesado)['custo_por_km_aplicado'] > custo_quilometrico(leve)['custo_por_km_aplicado']
    assert pesado['consumo_estimado'] is True
    manual=completar_custos({'custo_por_km':5,'consumo_km_l':2,'preco_combustivel_litro':7,'custo_por_km_sem_combustivel':1}, {}, referencia())
    assert custo_quilometrico(manual)['custo_por_km_aplicado']==5
    assert custo_quilometrico(manual)['combustivel_por_km'] is None


def test_consumo_real_tem_prioridade_e_preco_automatico_atualiza_no_recalculo():
    custos=completar_custos({'consumo_km_l':2}, {}, referencia(6))
    assert custos['consumo_estimado'] is False
    assert custo_quilometrico(custos)['custo_por_km_aplicado']==3
    custos=completar_custos(custos, {}, referencia(8))
    assert custo_quilometrico(custos)['custo_por_km_aplicado']==4
    assert custos['consumo_km_l']==2


def test_preco_vencido_nao_substitui_custo_total_nem_se_torna_atual():
    custos=completar_custos({}, {}, referencia())
    custos['combustivel_data_coleta']=str(date.today()-timedelta(days=15))
    c=custo_quilometrico(custos)
    assert c['modo']=='CUSTO_TOTAL_POR_KM'
    assert c['custo_por_km_aplicado']==4.5
    assert c['idade_preco_dias']==15


def test_combustivel_nao_e_somado_duas_vezes_na_economia():
    custos={'consumo_km_l':2,'preco_combustivel_litro':6,'custo_por_km_sem_combustivel':1,
            'custo_por_km':99,'custo_hora_motorista':0,'custo_operacional_veiculo_hora':0}
    def rota(km):return {'distancia_km':km,'tempo_min':0,'infraestrutura':{'pedagios':{'subtotal_conhecido_reais':0,'tarifas_pendentes':0}}}
    resultado=comparar_custos(rota(100),rota(80),custos,False)
    assert resultado['custo_original_conhecido_brl']==400
    assert resultado['economia_operacional_conhecida_brl']==80
    assert resultado['delta_combustivel_estimado_brl']==-60


@pytest.mark.parametrize('valor',[0,-1,float('inf'),float('nan')])
def test_consumo_invalido_e_rejeitado(valor):
    with pytest.raises(ValidationError):CustosCaminhao(consumo_km_l=valor)


def test_multilinha_grande_preserva_descontinuidades_e_rejeita_valores_invalidos():
    linhas=[[[-47,-22],[-46.99,-22]]]*3000
    assert len(ConsultaRota(rota={'type':'MultiLineString','coordinates':linhas}).rota['coordinates'])==3000
    for coords in ([],[[[True,-22],[-47,-22]]],[[[-47,-22]]],[[[-47,-22],[float('inf'),-22]]]):
        with pytest.raises(ValidationError):ConsultaRota(rota={'type':'MultiLineString','coordinates':coords})


def test_worker_continua_apos_timeout_de_uma_fonte():
    import subprocess
    with patch.object(worker.subprocess,'run',side_effect=[subprocess.TimeoutExpired('fonte',600),*[SimpleNamespace(returncode=0)]*(len(worker.FONTES)-1)]) as executar:
        assert worker.executar_rodada() is False
        assert executar.call_count==len(worker.FONTES)


def test_importador_artesp_deduplica_antes_do_upsert():
    cabecalho='DATA,HORA,RODOVIA,KM,SENTIDO,LATITUDE,LONGITUDE,CLASSE,SUBCLASSE,VEICULOS_ENVOLVIDOS,MUNICIPIO\n'
    linha='2025-01-01,10:00,SP310,10,NORTE,-22,-47,TOMBAMENTO,TOMBAMENTO,CAMINHÃO=1,TESTE\n'
    registros,resumo=ler_artesp((cabecalho+linha+linha).encode(),'https://dadosabertos.artesp.sp.gov.br/exemplo')
    assert len(registros)==1
    assert resumo['duplicados']==1


def test_leitor_semanal_sem_dependencia_extra_valida_cabecalho_e_data():
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    def linha(numero,celulas):
        return '<row>'+''.join(f'<c r="{k}{numero}" t="inlineStr"><is><t>{v}</t></is></c>' for k,v in celulas.items())+'</row>'
    xml=f'<worksheet xmlns="{ns}"><sheetData>'+linha(1,{'A':'CNPJ','J':'ESTADO','L':'PRODUTO','O':'DATA DA COLETA'})+linha(2,{'A':'12345678000190','B':'POSTO TESTE','J':'SAO PAULO','L':'DIESEL S10','N':'7.25','O':'01/10/2026'})+'</sheetData></worksheet>'
    arq=io.BytesIO()
    with zipfile.ZipFile(arq,'w') as z:z.writestr('xl/worksheets/sheet1.xml',xml)
    registros,_=ler_anp(para_csv(arq.getvalue()),'https://www.gov.br/anp/exemplo.xlsx')
    assert str(registros[0]['preco'])=='7.25'
    assert registros[0]['data']==date(2026,10,1)
    with pytest.raises(ValueError):descobrir_url('sem planilha')


def test_github_actions_nao_sobrescreve_configuracao(monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS','true')
    monkeypatch.setenv('DB_PASSWORD','senha_sintetica_teste')
    monkeypatch.setenv('API_KEYS','chave_sintetica_teste')
    caminho=Path(__file__).resolve().parents[1]/'app/config.py'
    spec=importlib.util.spec_from_file_location('config_regressao',caminho)
    modulo=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=modulo
    try:
        spec.loader.exec_module(modulo)
        assert modulo.settings.DB_PASSWORD=='senha_sintetica_teste'
        assert modulo.settings.API_KEYS=='chave_sintetica_teste'
    finally:sys.modules.pop(spec.name,None)


def test_manifesto_vencido_nunca_renova_tarifa_sozinho():
    with pytest.raises(ValueError):planejar({'verificado_em':'2025-01-01T00:00:00+00:00','valido_ate':'2025-02-01T00:00:00+00:00'},[])


def test_cabines_da_mesma_praca_nao_duplicam_tarifa():
    agora=datetime.now(timezone.utc)
    def ponto(i,tarifa):return {'id':i,'id_trecho':i,'tipo':'PEDAGIO','grupo_cobranca':'PRACA-A',
        'nome':'Praca','longitude':-47,'latitude':-22,'fonte':'https://exemplo.gov.br',
        'verificado_em':agora-timedelta(days=1),'valido_ate':agora+timedelta(days=1),
        'altura_max_m':None,'largura_max_m':None,'comprimento_max_m':None,'peso_max_t':None,
        'tarifa_por_eixo':tarifa}
    dims={'eixos':5}
    resultado=resumir_rota([ponto(1,10),ponto(2,10)],[1,2],dims)['pedagios']
    assert resultado['quantidade_cadastrada_na_rota']==1
    assert resultado['subtotal_conhecido_reais']==50
    resultado=resumir_rota([ponto(1,10),ponto(2,11)],[1,2],dims)['pedagios']
    assert resultado['tarifas_pendentes']==1
    assert resultado['subtotal_conhecido_reais']==0


@pytest.mark.asyncio
async def test_despacho_guarda_custo_automatico_sem_exigir_custo_por_km():
    import asyncpg
    import httpx
    import json
    import secrets
    from fastapi import FastAPI
    from app.config import settings
    from app.database import get_connection
    from app.routers.logistica import router
    from app.services.routing_engine import RoutingEngine
    conn=await asyncpg.connect(settings.database_url)
    tx=conn.transaction()
    await tx.start()
    identificador='TEST_AUTO_'+secrets.token_hex(5)
    try:
        # Preco sintetico isolado pela transacao; nao depende da disponibilidade da ANP.
        cnpj=f'{secrets.randbelow(10**14):014d}'
        await conn.execute("""INSERT INTO postos_combustivel(cnpj,nome,uf,municipio,endereco)
            VALUES($1,'TESTE','SP','TESTE','TESTE')""",cnpj)
        await conn.execute("""INSERT INTO precos_combustivel(cnpj,produto,data_coleta,preco_litro,url_fonte)
            VALUES($1,'DIESEL S10',CURRENT_DATE,7,'https://www.gov.br/anp/teste')""",cnpj)
        app=FastAPI();app.include_router(router)
        async def conexao():yield conn
        app.dependency_overrides[get_connection]=conexao
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'X-API-Key':'key_admin_demo'}) as cliente:
            veiculo={'id_veiculo':identificador,'placa':'TST4321','modelo':'Referencia de teste',
                'dimensoes':{'altura_m':4.2,'largura_m':2.6,'comprimento_m':18,'peso_total_t':40,'eixos':5}}
            assert (await cliente.post('/api/v1/logistica/veiculos',json=veiculo)).status_code==200
            # Usa dois vertices adjacentes da malha ja instalada, inclusive em CI sem malha regional.
            pontos=await conn.fetchrow("""SELECT ST_X(ST_Transform(a.the_geom,4326)) AS olon,
                ST_Y(ST_Transform(a.the_geom,4326)) AS olat,ST_X(ST_Transform(b.the_geom,4326)) AS dlon,
                ST_Y(ST_Transform(b.the_geom,4326)) AS dlat FROM trechos_osm t
                JOIN trechos_osm_vertices_pgr a ON a.id=t.source
                JOIN trechos_osm_vertices_pgr b ON b.id=t.target
                WHERE t.source<>t.target AND t.tenant_malha IS NULL LIMIT 1""")
            operacao={'id_operacao':identificador,'id_veiculo':identificador,'origem_nome':'','destino_nome':'',
                'origem_lon':pontos['olon'],'origem_lat':pontos['olat'],'destino_lon':pontos['dlon'],
                'destino_lat':pontos['dlat'],'janela_inicio':datetime.now(timezone.utc).isoformat(),
                'janela_fim':(datetime.now(timezone.utc)+timedelta(hours=6)).isoformat()}
            resultado=await cliente.post('/api/v1/logistica/operacoes',json=operacao)
            assert resultado.status_code==200,resultado.text
            linha=await conn.fetchrow('SELECT custos_operacionais,custo_estimado FROM operacoes WHERE id_operacao=$1',identificador)
            custos=json.loads(linha['custos_operacionais'])
            assert custos['consumo_estimado'] is True
            assert custos['combustivel_data_coleta']==str(date.today())
            assert linha['custo_estimado']>0
    finally:
        await tx.rollback()
        await conn.close()
        RoutingEngine.clear_cache()
