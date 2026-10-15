"""Categorias tarifarias e inventario nao podem fabricar liberacao de passagem."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from types import SimpleNamespace
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

from app.services.infraestrutura_viaria import avaliar_ponto
from app.services.estruturas_viarias import complementar_estruturas
from app.routers.infraestrutura import PontoCadastro

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.sincronizar_estruturas_corredor import limites_tags,registros_osm


def ponto():
    agora=datetime.now(timezone.utc)
    return {'tipo':'PEDAGIO','verificado_em':agora-timedelta(days=1),'valido_ate':agora+timedelta(days=1),
            'tarifa_por_eixo':None,'tarifas_por_eixos':{'2':'23.30','5':'58.30'}}


def test_categoria_exata_nao_usa_tarifa_de_carro_multiplicada():
    p=ponto()
    assert avaliar_ponto(p,SimpleNamespace(eixos=5))['custo_estimado_reais']==58.30
    assert avaliar_ponto(p,SimpleNamespace(eixos=2))['custo_estimado_reais']==23.30
    assert avaliar_ponto(p,SimpleNamespace(eixos=10))['custo_estimado_reais'] is None
    p['valido_ate']=datetime.now(timezone.utc)-timedelta(hours=1)
    assert avaliar_ponto(p,SimpleNamespace(eixos=5))['custo_estimado_reais'] is None


@pytest.mark.parametrize('tabela',[{}, {'1':'1.00'}, {'16':'1.00'}, {'5':'-1.00'}, {'5':'NaN'}, {'5':'58.301'}])
def test_tabela_invalida_nao_entra_no_cadastro(tabela):
    p=ponto()
    with pytest.raises(ValidationError):PontoCadastro(**{**p,'nome':'Teste','id_trecho':1,'latitude':-22,'longitude':-47,
        'fonte':'https://eixosp.com.br/tarifas/','tarifas_por_eixos':tabela})


def test_inventario_sem_limites_nao_vira_peso_altura_ou_largura_permitidos():
    props={'estrutura_viaria':{'osm_way_id':123,'tipo':'PONTE','nome':'Ponte','fonte':'https://www.openstreetmap.org/way/123'},'limites_importados':{}}
    feature={'geometry':{'type':'LineString','coordinates':[[-47,-22],[-47.001,-22]]},'properties':props}
    info={'pontos_mapa':{'type':'FeatureCollection','features':[]}}
    complementar_estruturas(info,[feature,feature])
    assert len(info['estruturas_referencia'])==1
    assert info['estruturas_sem_limites_completos']==1
    assert len(info['pontos_mapa']['features'])==1
    p=info['pontos_mapa']['features'][0]['properties']
    assert p['status']=='CONFERENCIA_NECESSARIA'
    assert p['peso_max_t'] is None and p['altura_max_m'] is None


def test_importador_ignora_dimensoes_da_obra_e_limites_nao_interpretaveis():
    tags={'bridge':'yes','length':'100','width':'9','maxheight':'4.3 m','maxweight':'default','maxwidth':'2,6','maxlength:conditional':'18 @ (Mo-Fr)'}
    assert limites_tags(tags)=={'altura_max_m':4.3,'largura_max_m':2.6}
    registros=registros_osm({'elements':[{'type':'way','id':123,'tags':tags}]})
    assert registros[0]['estrutura']['tipo']=='PONTE'
    assert 'comprimento_max_m' not in registros[0]['limites']
    assert 'peso_max_t' not in registros[0]['limites']
