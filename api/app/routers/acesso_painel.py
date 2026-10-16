from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, Field, ConfigDict
from app.database import get_connection
from app.seguranca import is_production, get_current_user_claims
from app.services.acesso_painel import autenticar, resumo, PREFIXO

router=APIRouter(prefix='/api/v1/acesso',tags=['Acesso individual ao painel'])


class Login(BaseModel):
    model_config=ConfigDict(extra='forbid')
    email:str=Field(min_length=3,max_length=254)
    senha:str=Field(min_length=1,max_length=256)


@router.get('/configuracao')
async def configuracao(response:Response):
    response.headers['Cache-Control']='no-store'
    return {'demonstracao_disponivel':not is_production(),'acesso_individual':True,'duracao_sessao_horas':8}


@router.post('/login')
async def login(dados:Login,request:Request,response:Response,conn=Depends(get_connection)):
    response.headers['Cache-Control']='no-store'
    email=dados.email.strip().lower()
    if not is_production():
        from app.routers.logistica import USUARIOS_CORPORATIVOS, LoginCorporativoRequest, login_corporativo
        # Contas cadastradas nunca caem no acesso demo, inclusive se desativadas.
        if email in USUARIOS_CORPORATIVOS and not await conn.fetchval('SELECT 1 FROM painel_usuarios WHERE email=$1',email):
            d=await login_corporativo(LoginCorporativoRequest(email=email,senha=dados.senha))
            return {**d,'tipo_acesso':'DEMONSTRACAO'}
    return await autenticar(conn,email,dados.senha,request.client.host if request.client else 'sem-ip')


@router.post('/logout')
async def logout(response:Response,claims=Depends(get_current_user_claims),x_api_key:str=Header(),conn=Depends(get_connection)):
    response.headers['Cache-Control']='no-store'
    if x_api_key.startswith(PREFIXO):
        await conn.execute('UPDATE painel_sessoes SET revogado_em=now() WHERE token_hash=$1',resumo(x_api_key))
    return {'encerrada':True}
