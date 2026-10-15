from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.services.transit_client import TransitClient
from app.seguranca import require_role

router = APIRouter(prefix="/api/v1/transito", tags=["Transito e Roteamento"], dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])

class TransitoRequest(BaseModel):
    origem_lat: float = Field(..., ge=-90, le=90)
    origem_lon: float = Field(..., ge=-180, le=180)
    destino_lat: float = Field(..., ge=-90, le=90)
    destino_lon: float = Field(..., ge=-180, le=180)

@router.post("/comparar")
async def comparar_tempo_transito(dados: TransitoRequest):
    info = TransitClient.consultar_transito(dados.origem_lat, dados.origem_lon, dados.destino_lat, dados.destino_lon)
    if info["status"] == "INDISPONIVEL":
        raise HTTPException(status_code=502, detail=info["motivo"])
    return {
        "status": "OPERACIONAL",
        "transito": info,
        "aviso": "Comparacao de tempo real obtida com isolamento de provedor e cache ativo."
    }

@router.get("/metricas")
async def metricas_transito():
    return TransitClient.metricas()