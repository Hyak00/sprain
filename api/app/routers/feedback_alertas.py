import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.database import get_connection
from app.seguranca import require_role, resolver_tenant_autenticado

router = APIRouter(prefix="/api/v1/alertas", tags=["Sistema de Confianca dos Alertas"], dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])

class FeedbackRequest(BaseModel):
    id_evento: str
    falso_alerta: bool = False
    evento_nao_detectado: bool = False
    motivo_reporte: str = Field(min_length=1, max_length=500)

@router.post("/feedback", dependencies=[Depends(require_role(["ADMIN", "OPERATOR"]))])
async def registrar_feedback_alerta(dados: FeedbackRequest, tenant_id=Depends(resolver_tenant_autenticado), conn: asyncpg.Connection = Depends(get_connection)):
    async with conn.transaction():
        existe = await conn.fetchval("SELECT id_evento FROM alertas_operacionais WHERE id_evento = $1", dados.id_evento)
        if not existe:
            raise HTTPException(404, "Evento de alerta nao encontrado.")
            
        await conn.execute("""
            INSERT INTO feedback_alertas_operacionais (id_evento, tenant_id, falso_alerta, evento_nao_detectado, motivo_reporte)
            VALUES ($1, $2, $3, $4, $5)
        """, dados.id_evento, tenant_id, dados.falso_alerta, dados.evento_nao_detectado, dados.motivo_reporte)
        
    return {"sucesso": True, "id_evento": dados.id_evento, "status": "FEEDBACK_REGISTRADO"}

@router.get("/precisao")
async def calcular_precisao_alertas(tenant_id=Depends(resolver_tenant_autenticado), conn: asyncpg.Connection = Depends(get_connection)):
    row = await conn.fetchrow("""
        WITH ultimo_feedback AS (
            SELECT DISTINCT ON (id_evento)
                id_evento, falso_alerta, evento_nao_detectado
            FROM feedback_alertas_operacionais
            WHERE tenant_id = $1
            ORDER BY id_evento, reportado_em DESC, id_feedback DESC
        )
        SELECT 
            COUNT(*) AS total_avaliados,
            COUNT(*) FILTER (WHERE a.status_evento = 'CONFIRMADO' AND NOT f.falso_alerta) AS confirmados_validos,
            COUNT(*) FILTER (WHERE f.falso_alerta) AS falsos_positivos,
            COUNT(*) FILTER (WHERE f.evento_nao_detectado) AS falsos_negativos
        FROM ultimo_feedback f
        JOIN alertas_operacionais a ON a.id_evento = f.id_evento
    """, tenant_id)
    
    total = int(row["total_avaliados"] or 0)
    vp = int(row["confirmados_validos"] or 0)
    fp = int(row["falsos_positivos"] or 0)
    fn = int(row["falsos_negativos"] or 0)
    
    precisao = round((vp / max(1, vp + fp)) * 100.0, 1)
    sensibilidade = round((vp / max(1, vp + fn)) * 100.0, 1)
    
    return {
        "tenant_id": tenant_id,
        "total_eventos_analisados": total,
        "metricas_precisao": {
            "precisao_alertas_pct": precisao,
            "sensibilidade_pct": sensibilidade,
            "falsos_positivos": fp,
            "falsos_negativos": fn
        },
        "status_calibracao": "AMOSTRA_INSUFICIENTE" if total == 0 else ("MOTOR_ESTAVEL" if precisao >= 80.0 else "NECESSITA_CALIBRAGEM")
    }
