"""Administracao de usuarios da propria empresa."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from app.database import get_connection
from app.seguranca import get_current_user_claims
from app.services import gestao_usuarios


router = APIRouter(prefix='/api/v1/acesso/usuarios', tags=['Gestão de usuários'])


def exigir_admin_individual(claims=Depends(get_current_user_claims)):
    if claims['role'] != 'ADMIN' or not claims.get('usuario_id'):
        raise HTTPException(403, 'Somente ADMIN com acesso individual pode gerir usuários.')
    return claims


class NovoUsuario(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=3, max_length=254)
    senha: str = Field(min_length=15, max_length=256)
    papel: Literal['ADMIN', 'OPERATOR', 'VIEWER']


class MudancaPapel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    papel: Literal['ADMIN', 'OPERATOR', 'VIEWER']


@router.get('')
async def listar_usuarios(
    response: Response,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    claims=Depends(exigir_admin_individual),
    conn=Depends(get_connection),
):
    response.headers['Cache-Control'] = 'no-store'
    return await gestao_usuarios.listar(conn, claims, limit, offset)


@router.post('', status_code=201)
async def criar_usuario(
    dados: NovoUsuario, response: Response,
    claims=Depends(exigir_admin_individual), conn=Depends(get_connection),
):
    response.headers['Cache-Control'] = 'no-store'
    return await gestao_usuarios.criar(conn, claims, dados.email, dados.senha, dados.papel)


@router.get('/auditoria')
async def listar_auditoria(
    response: Response,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    claims=Depends(exigir_admin_individual), conn=Depends(get_connection),
):
    response.headers['Cache-Control'] = 'no-store'
    return await gestao_usuarios.listar_auditoria(conn, claims, limit, offset)


@router.patch('/{usuario_id}/papel')
async def alterar_papel(
    usuario_id: UUID, dados: MudancaPapel, response: Response,
    claims=Depends(exigir_admin_individual), conn=Depends(get_connection),
):
    response.headers['Cache-Control'] = 'no-store'
    return await gestao_usuarios.alterar_papel(conn, claims, usuario_id, dados.papel)


@router.post('/{usuario_id}/desativar')
async def desativar_usuario(
    usuario_id: UUID, response: Response,
    claims=Depends(exigir_admin_individual), conn=Depends(get_connection),
):
    response.headers['Cache-Control'] = 'no-store'
    return await gestao_usuarios.desativar(conn, claims, usuario_id)
