from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import asyncpg
from app.database import get_connection
from app.seguranca import require_role, resolver_tenant_autenticado

router = APIRouter(prefix="/api/v1/simulacao", tags=["Simulação de Chuva"])

class SimulacaoRequest(BaseModel):
    milimetros_chuva: float = Field(..., ge=5.0, le=200.0, description="Volume acumulado em mm")

@router.post("/disparar", dependencies=[Depends(require_role(["ADMIN", "OPERATOR"]))])
async def disparar_simulacao(dados: SimulacaoRequest, conn: asyncpg.Connection = Depends(get_connection), tenant_id: str = Depends(resolver_tenant_autenticado)):
    limiar_calculado = float(max(35.0, 85.0 - (dados.milimetros_chuva * 0.6)))
    relato = f"Simulacao hidrologica: precipitacao projetada de {dados.milimetros_chuva} mm"

    query = """
    SELECT id_trecho
    FROM trechos_osm
    WHERE CAST(COALESCE(ivi_score, 0) AS float8) >= $1::float8;
    """

    rows = await conn.fetch(query, limiar_calculado)

    return {
        "sucesso": True,
        "cenario_mm": dados.milimetros_chuva,
        "limiar_ivi_aplicado": round(limiar_calculado, 2),
        "total_vias_comprometidas": len(rows)
    }
