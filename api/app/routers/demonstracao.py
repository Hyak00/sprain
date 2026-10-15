import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_connection
from app.seguranca import require_role, is_production
from app.services.routing_engine import RoutingEngine

router = APIRouter(prefix="/api/v1/demonstracao", tags=["Dados de Demonstracao"], dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])

@router.post("/cenario-historico-sp310", dependencies=[Depends(require_role(["ADMIN"]))])
async def gerar_cenario_historico_sp310(conn: asyncpg.Connection = Depends(get_connection)):
    if is_production():
        raise HTTPException(503, "Cenario de demonstracao indisponivel em producao.")
    orig_lon, orig_lat = -48.18, -21.79
    dest_lon, dest_lat = -47.89, -22.01
    
    await conn.execute("""
        INSERT INTO alertas_operacionais 
        (id_evento, categoria, fonte, primeira_deteccao, ultima_atualizacao, expiracao_em, confianca, status_evento, trechos_afetados)
        VALUES ('DEMO_SP310_BLOQUEIO', 'OCORRENCIA_CONFIRMADA', 'DEMONSTRACAO', now(), now(), now() + interval '1 hour', 0.99, 'CONFIRMADO', ARRAY[101, 102])
        ON CONFLICT (id_evento) DO UPDATE SET fonte = EXCLUDED.fonte, expiracao_em = EXCLUDED.expiracao_em, ultima_atualizacao = now()
    """)
    
    rota_original = await RoutingEngine.compute_route(conn, orig_lon, orig_lat, dest_lon, dest_lat, "FASTEST", 0.0, "CARRETA_5_EIXOS", "demo_corp")
    rota_segura = await RoutingEngine.compute_route(conn, orig_lon, orig_lat, dest_lon, dest_lat, "SAFEST", 85.0, "CARRETA_5_EIXOS", "demo_corp")
    
    return {
        "modo": "DATASET_DEMONSTRACAO_B2B",
        "evento_historico": "Bloqueio por alagamento severo na SP-310 (Regiao de Araraquara)",
        "data_referencia": "2026-03-15",
        "comparativo_rotas": {
            "rota_original_km": rota_original["distancia_km"] if rota_original else None,
            "rota_alternativa_km": rota_segura["distancia_km"] if rota_segura else None,
            "tempo_original_min": rota_original["tempo_min"] if rota_original else None,
            "tempo_alternativo_min": rota_segura["tempo_min"] if rota_segura else None
        },
        "aviso": "Demonstracao voltada ao apoio a decisao logistica; nao afirma prevencao automatica de prejuizo."
    }
