import asyncpg
from fastapi import APIRouter, Depends
from app.database import get_connection
from app.seguranca import require_role
from app.services.routing_engine import RoutingEngine

router = APIRouter(prefix="/api/v1/demonstracao", tags=["Dados de Demonstracao"], dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])

@router.post("/cenario-historico-sp310")
async def gerar_cenario_historico_sp310(conn: asyncpg.Connection = Depends(get_connection)):
    orig_lon, orig_lat = -48.18, -21.79
    dest_lon, dest_lat = -47.89, -22.01
    
    await conn.execute("""
        INSERT INTO alertas_operacionais 
        (id_evento, categoria, fonte, primeira_deteccao, ultima_atualizacao, expiracao_em, confianca, status_evento, trechos_afetados)
        VALUES ('DEMO_SP310_BLOQUEIO', 'OCORRENCIA_CONFIRMADA', 'DEFESA_CIVIL', now(), now(), now() + interval '7 days', 0.99, 'CONFIRMADO', ARRAY[101, 102])
        ON CONFLICT (id_evento) DO NOTHING
    """)
    
    rota_original = await RoutingEngine.compute_route(conn, orig_lon, orig_lat, dest_lon, dest_lat, "FASTEST", 0.0, "CARRETA_5_EIXOS", "demo_corp")
    rota_segura = await RoutingEngine.compute_route(conn, orig_lon, orig_lat, dest_lon, dest_lat, "SAFEST", 85.0, "CARRETA_5_EIXOS", "demo_corp")
    
    return {
        "modo": "DATASET_DEMONSTRACAO_B2B",
        "evento_historico": "Bloqueio por alagamento severo na SP-310 (Regiao de Araraquara)",
        "data_referencia": "2026-03-15",
        "comparativo_rotas": {
            "rota_original_km": rota_original["distancia_km"] if rota_original else 45.2,
            "rota_alternativa_km": rota_segura["distancia_km"] if rota_segura else 52.8,
            "tempo_original_min": rota_original["tempo_min"] if rota_original else 40.0,
            "tempo_alternativo_min": rota_segura["tempo_min"] if rota_segura else 55.0
        },
        "aviso": "Demonstracao voltada ao apoio a decisao logistica; nao afirma prevencao automatica de prejuizo."
    }