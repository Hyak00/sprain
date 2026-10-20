import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.database import get_connection
from app.config import settings
from app.services.medicao_api_externa import reservar_osrm, concluir
from app.services.transit_client import TransitClient
from app.seguranca import require_role, resolver_tenant_autenticado

router = APIRouter(prefix="/api/v1/transito", tags=["Transito e Roteamento"], dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])

class TransitoRequest(BaseModel):
    origem_lat: float = Field(..., ge=-90, le=90)
    origem_lon: float = Field(..., ge=-180, le=180)
    destino_lat: float = Field(..., ge=-90, le=90)
    destino_lon: float = Field(..., ge=-180, le=180)

@router.post("/comparar")
async def comparar_tempo_transito(dados: TransitoRequest,
                                 tenant_id=Depends(resolver_tenant_autenticado),
                                 conn=Depends(get_connection)):
    coordenadas = (dados.origem_lat, dados.origem_lon, dados.destino_lat, dados.destino_lon)
    if settings.ambiente_atual == "production":
        info = TransitClient.consultar_transito(*coordenadas)
    else:
        info = TransitClient.consultar_cache(*coordenadas)
        if info is None:
            identificador = await reservar_osrm(conn, tenant_id)
            try:
                info = await asyncio.to_thread(TransitClient.consultar_transito,
                                               *coordenadas, usar_cache=False)
            except Exception:
                await concluir(conn, tenant_id, identificador, False)
                raise
            await concluir(conn, tenant_id, identificador,
                           info["status"] != "INDISPONIVEL")
    if info["status"] == "INDISPONIVEL":
        raise HTTPException(status_code=502, detail=info["motivo"])
    return {
        "status": "ESTIMATIVA",
        "transito": info,
        "aviso": "Tempo estimado pelo OSRM, sem transito observado em tempo real. Nao comprova congestionamento ou atraso."
    }

@router.get("/metricas")
async def metricas_transito():
    return TransitClient.metricas()
