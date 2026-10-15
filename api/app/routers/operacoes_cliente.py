import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.database import get_connection
from app.seguranca import require_role, resolver_tenant_autenticado

router = APIRouter(prefix="/api/v1/cliente/operacoes", tags=["Dados de Operacao do Cliente"], dependencies=[Depends(require_role(["ADMIN", "OPERATOR"]))])

class ViagemClienteCreate(BaseModel):
    id_viagem: str = Field(min_length=1, max_length=100)
    origem: str = Field(min_length=1, max_length=200)
    destino: str = Field(min_length=1, max_length=200)
    status_viagem: str = Field(default="EM_ANDAMENTO")
    atraso_minutos: float = Field(default=0.0, ge=0.0)

@router.post("")
@router.post("/")
async def registrar_viagem_cliente(dados: ViagemClienteCreate, tenant_id=Depends(resolver_tenant_autenticado), conn: asyncpg.Connection = Depends(get_connection)):
    async with conn.transaction():
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS operacoes_cliente_frota (
                id_reg SERIAL PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                id_viagem TEXT NOT NULL,
                origem TEXT NOT NULL,
                destino TEXT NOT NULL,
                status_viagem TEXT NOT NULL,
                atraso_minutos NUMERIC(8,2) NOT NULL,
                registrado_em TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (tenant_id, id_viagem)
            )
        """)
        
        await conn.execute("""
            INSERT INTO operacoes_cliente_frota (tenant_id, id_viagem, origem, destino, status_viagem, atraso_minutos)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (tenant_id, id_viagem) DO UPDATE
            SET status_viagem = EXCLUDED.status_viagem,
                atraso_minutos = EXCLUDED.atraso_minutos,
                registrado_em = NOW()
        """, tenant_id, dados.id_viagem, dados.origem, dados.destino, dados.status_viagem, dados.atraso_minutos)
        
    return {"sucesso": True, "tenant_id": tenant_id, "id_viagem": dados.id_viagem, "status": "GRAVADO_COM_ISOLAMENTO"}

@router.get("")
@router.get("/")
async def listar_viagens_cliente(tenant_id=Depends(resolver_tenant_autenticado), conn: asyncpg.Connection = Depends(get_connection)):
    rows = await conn.fetch("""
        SELECT id_viagem, origem, destino, status_viagem, atraso_minutos, registrado_em
        FROM operacoes_cliente_frota
        WHERE tenant_id = $1
        ORDER BY registrado_em DESC
        LIMIT 100
    """, tenant_id)
    return [{
        "id_viagem": r["id_viagem"], "origem": r["origem"], "destino": r["destino"],
        "status_viagem": r["status_viagem"], "atraso_minutos": float(r["atraso_minutos"]),
        "registros_em": r["registrado_em"].isoformat()
    } for r in rows]