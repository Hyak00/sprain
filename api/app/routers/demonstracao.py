from typing import Literal
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict
from app.database import get_connection
from app.seguranca import require_role, get_current_user_claims, is_production
from app.services import demonstracao as demo

router=APIRouter(prefix='/api/v1/demonstracao',tags=['Dados de Demonstracao'])

class Etapa(BaseModel):
    model_config=ConfigDict(extra='forbid')
    etapa:Literal['SEM_BLOQUEIO','BLOQUEIO','LIBERACAO']

@router.get('/estado')
async def estado(response:Response,conn=Depends(get_connection)):
    response.headers['Cache-Control']='no-store'
    if not demo.habilitada() or is_production():
        return {'modo':'OPERACIONAL' if is_production() else 'DESENVOLVIMENTO','demo_isolada':False,
            'aviso':'Simulações devem ser identificadas e não comprovam dados observados.'}
    await demo.exigir_ambiente(conn)
    return {'modo':'DEMONSTRACAO_ISOLADA','demo_isolada':True,
        'aviso':'AMBIENTE DE DEMONSTRAÇÃO — exemplos sintéticos e referência histórica; não usar para operação real.'}

@router.get('/referencia',dependencies=[Depends(require_role(['ADMIN','OPERATOR','VIEWER']))])
async def referencia(response:Response,conn=Depends(get_connection)):
    await demo.exigir_ambiente(conn);response.headers['Cache-Control']='no-store'
    return demo.referencia()

@router.post('/preparar',dependencies=[Depends(require_role(['ADMIN']))])
async def preparar(response:Response,claims=Depends(get_current_user_claims),conn=Depends(get_connection)):
    response.headers['Cache-Control']='no-store'
    return await demo.preparar(conn,claims['tenant_id'])

@router.post('/reproduzir',dependencies=[Depends(require_role(['ADMIN','OPERATOR','VIEWER']))])
async def reproduzir(dados:Etapa,response:Response,claims=Depends(get_current_user_claims),conn=Depends(get_connection)):
    response.headers['Cache-Control']='no-store'
    return await demo.reproduzir(conn,claims['tenant_id'],dados.etapa)

@router.post('/cenario-historico-sp310',dependencies=[Depends(require_role(['ADMIN']))])
async def gerar_cenario_historico_sp310(conn=Depends(get_connection),claims=Depends(get_current_user_claims)):
    # Contrato anterior preservado; só prepara/reproduz no banco reservado.
    await demo.exigir_ambiente(conn)
    await demo.preparar(conn,claims['tenant_id'])
    return await demo.reproduzir(conn,claims['tenant_id'],'BLOQUEIO')
