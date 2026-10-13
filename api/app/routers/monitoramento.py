import sys
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.database import get_connection

sys.path.append("/app")

try:
    from scripts.monitorar_chuva_cge import coletar_chuva_cge
except ImportError:
    coletar_chuva_cge = None

router = APIRouter(prefix="/api/v1/monitoramento", tags=["Monitoramento"])
POSTO_ITAQUERA_ID = "1000864"

async def aplicar_impacto_chuva(conn, acumulado_mm: float) -> int:
    query = """
        WITH calc AS (
            SELECT 
                t.id_trecho,
                CASE 
                    WHEN $1 >= 90.0 AND t.distancia_agua_m <= 45.0 AND t.ivi_score >= 78.0 THEN 'INTRANSITAVEL'
                    WHEN $1 >= 60.0 AND t.distancia_agua_m <= 30.0 AND t.ivi_score >= 80.0 THEN 'INTRANSITAVEL'
                    WHEN $1 >= 60.0 AND t.distancia_agua_m <= 110.0 AND t.ivi_score >= 68.0 THEN 'INTRANSITAVEL_LEVES'
                    WHEN $1 >= 35.0 AND t.distancia_agua_m <= 60.0 AND t.ivi_score >= 70.0 THEN 'INTRANSITAVEL_LEVES'
                    ELSE 'TRANSITAVEL'
                END AS novo_status,
                CASE 
                    WHEN $1 >= 90.0 AND t.distancia_agua_m <= 45.0 AND t.ivi_score >= 78.0 THEN 'VERMELHO'
                    WHEN $1 >= 60.0 AND t.distancia_agua_m <= 30.0 AND t.ivi_score >= 80.0 THEN 'VERMELHO'
                    WHEN $1 >= 60.0 AND t.distancia_agua_m <= 110.0 AND t.ivi_score >= 68.0 THEN 'LARANJA'
                    WHEN $1 >= 35.0 AND t.distancia_agua_m <= 60.0 AND t.ivi_score >= 70.0 THEN 'LARANJA'
                    WHEN $1 >= 30.0 AND t.distancia_agua_m <= 220.0 AND t.ivi_score >= 50.0 THEN 'AMARELO'
                    ELSE 'VERDE'
                END AS nova_severidade
            FROM trechos_osm t
        )
        UPDATE estado_operacional_trechos e
        SET status = calc.novo_status,
            severidade = calc.nova_severidade,
            relato_origem = format('Telemetria CGE: precipitacao acumulada de %s mm', $1::text),
            registrado_em = NOW()
        FROM calc
        WHERE e.id_trecho = calc.id_trecho;
    """
    res = await conn.execute(query, acumulado_mm)
    try:
        return int(res.split(" ")[-1])
    except Exception:
        return 0

@router.post("/sincronizar-cge")
async def sincronizar_cge(conn=Depends(get_connection)):
    if not coletar_chuva_cge:
        from app.services.weather import CGEWeatherProvider
        provider = CGEWeatherProvider()
        acumulado = provider.get_current_rainfall(POSTO_ITAQUERA_ID)
        if acumulado is None:
            raise HTTPException(
                status_code=502,
                detail="Fonte CGE indisponivel no momento. Estado operacional preservado para seguranca viaria."
            )
        dados = {"posto": POSTO_ITAQUERA_ID, "nome": "Itaquera", "chuva_acumulada_recente_mm": acumulado}
    else:
        try:
            dados = coletar_chuva_cge()
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Falha de comunicacao com a estacao meteorologica: {str(e)}"
            )

    if not dados or "chuva_acumulada_recente_mm" not in dados:
        raise HTTPException(
            status_code=502,
            detail="Dados meteorologicos ausentes. Malha viaria mantida em estado seguro anterior."
        )

    acumulado = float(dados["chuva_acumulada_recente_mm"])
    linhas = await aplicar_impacto_chuva(conn, acumulado)
    return {
        "status": "sucesso",
        "telemetria": {
            "posto_id": dados.get("posto", POSTO_ITAQUERA_ID),
            "posto_nome": dados.get("nome", "Itaquera"),
            "acumulado_mm": acumulado,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confiabilidade": "VALIDADO_SENSOR"
        },
        "trechos_atualizados": linhas
    }

@router.post("/simular-chuva")
async def simular_chuva_manual(acumulado_mm: float, conn=Depends(get_connection)):
    if acumulado_mm < 0:
        raise HTTPException(status_code=400, detail="Volume de chuva nao pode ser negativo.")
    linhas = await aplicar_impacto_chuva(conn, acumulado_mm)
    return {
        "status": "sucesso",
        "acumulado_mm": acumulado_mm,
        "trechos_atualizados": linhas,
        "modo": "SIMULACAO_MANUAL"
    }
