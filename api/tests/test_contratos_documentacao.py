"""Contratos de leitura do painel e OpenAPI; executar somente no ambiente de testes."""
import re
from copy import deepcopy
from pathlib import Path
import httpx
import pytest
from app.main import app
from app.documentacao import EXEMPLOS

LEITURAS=[
 ('/api/v1/logistica/operacoes',200),('/api/v1/logistica/veiculos',200),
 ('/api/v1/logistica/alertas/ativos',200),('/api/v1/logistica/relatorios/sumario-executivo',200),
 ('/api/v1/logistica/exportar-contingencia/csv',200),('/api/v1/logistica/observabilidade/metricas',200),
 ('/api/v1/rotas/intermunicipal',200),('/api/v1/dados-publicos/fontes',200),
 ('/api/v1/dados-publicos/qualidade-precos',200),('/api/v1/indicadores/qualidade',200),
 ('/api/v1/alertas/precisao',200),('/api/v1/infraestrutura/malha/importacoes',200),
 ('/api/v1/painel/corredores',200),('/api/v1/painel/consultas',200),('/api/v1/painel/eventos',200),
 ('/api/v1/painel/relatorios/piloto',200),('/api/v1/painel/relatorios/decisoes',200),
 ('/api/v1/painel/relatorios/consultas.csv',200),('/api/v1/painel/relatorios/decisoes.csv',200),
 ('/api/v1/administracao/financeiro',200),('/api/v1/acesso/usuarios',403),
 ('/api/v1/administracao/recuperacao',403),('/api/v1/administracao/exportacao',403),
 ('/api/v1/operacional/fontes',200),('/api/v1/operacional/importacoes',200),
 ('/api/v1/health/liveness',200),('/api/v1/health/readiness',200),
 ('/api/v1/acesso/configuracao',200),('/api/v1/demonstracao/estado',200),
]


@pytest.mark.asyncio
@pytest.mark.parametrize('url,status',LEITURAS)
async def test_endpoints_de_leitura_do_painel_existem_e_respeitam_acesso(url,status):
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8000',timeout=30) as c:
        r=await c.get(url,headers={'X-API-Key':'key_admin_demo'})
        assert r.status_code==status,(url,r.status_code)
        if (url.endswith('.csv') or url.endswith('/csv')) and status==200:assert 'text/csv' in r.headers['content-type']
        else:assert isinstance(r.json(),(dict,list))


def test_swagger_descreve_operacoes_e_autenticacao_sem_mudar_handlers():
    schema=app.openapi()
    assert schema['components']['securitySchemes']['SessaoOuChave']['name']=='X-API-Key'
    for path,methods in schema['paths'].items():
        if not path.startswith('/api/v1/'):continue
        for method,op in methods.items():
            if method in ('get','post','put','patch','delete'):assert len(op['description'])>60,(method,path)
    assert schema['paths']['/api/v1/acesso/login']['post']['security']==[]
    assert schema['paths']['/api/v1/operacional/importacoes']['get']['security']==[{'SessaoOuChave':[]}]
    assert 'nao at' in schema['paths']['/api/v1/logistica/operacoes/importar-lote']['post']['description'].lower().replace('ã','a').replace('ô','o')


def test_exemplos_swagger_validam_nos_modelos_reais():
    from app.routers import acesso_painel,painel,administracao_painel,gestao_usuarios,demonstracao,logistica
    from app import schemas
    modulos=[acesso_painel,painel,administracao_painel,gestao_usuarios,demonstracao,logistica,schemas]
    for nome,exemplo in EXEMPLOS.items():
        modelo=next((getattr(m,nome) for m in modulos if hasattr(m,nome)),None)
        assert modelo is not None,nome
        modelo.model_validate(deepcopy(exemplo))


def test_prefixos_de_api_escritos_na_interface_correspondem_a_rotas_reais():
    paths=list(app.openapi()['paths'])
    pasta=Path(__file__).resolve().parents[1]/'static'
    literais=set()
    for arquivo in [pasta/'b2b.html',*pasta.glob('*.js')]:
        literais.update(re.findall(r'''["'](/api/v1/[^"'\s]+)["']''',arquivo.read_text(encoding='utf-8')))
    assert len(literais)>30
    for literal in literais:
        caminho=literal.split('?')[0]
        assert any(p.startswith(caminho.rstrip('/')) or re.fullmatch(re.sub(r'\{[^}]+\}',r'[^/]+',p),caminho) for p in paths),literal
