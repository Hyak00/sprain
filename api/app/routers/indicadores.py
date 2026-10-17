import asyncpg
import math
from fastapi import APIRouter, Depends
from app.database import get_connection
from app.seguranca import require_role

router = APIRouter(prefix="/api/v1/indicadores", tags=["Indicadores de Dados"], dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])

@router.get("/qualidade")
async def obter_indicadores_qualidade(conn: asyncpg.Connection = Depends(get_connection)):
    fontes = await conn.fetch("""
        SELECT nome, registros_importados, ultimo_sucesso_em,
               EXTRACT(EPOCH FROM (now() - ultimo_sucesso_em))/3600 AS horas_desde_ultima_atualizacao
        FROM fontes_dados_externos
    """)
    
    total_tombamentos = await conn.fetchval("SELECT count(*) FROM tombamentos_caminhao WHERE ativo = true")
    total_postos = await conn.fetchval("SELECT count(*) FROM postos_combustivel")
    total_trechos = await conn.fetchval("SELECT count(*) FROM trechos_osm")
    
    lista_fontes = []
    fontes_no_prazo = 0
    for f in fontes:
        valor=f['horas_desde_ultima_atualizacao']
        horas=float(valor) if valor is not None else None
        valida=horas is not None and math.isfinite(horas) and horas>=0
        atualizada = valida and horas <= 48.0
        if atualizada:
            fontes_no_prazo += 1
        lista_fontes.append({
            "fonte": f["nome"],
            "registros_importados": f["registros_importados"],
            "ultimo_sucesso_em": f["ultimo_sucesso_em"].isoformat() if f['ultimo_sucesso_em'] else None,
            "horas_desde_ultima_atualizacao": round(horas, 1) if valida else None,
            "status_prazo": "SEM_DATA_VALIDA" if not valida else "ATUALIZADA" if atualizada else "ATRASADA"
        })

    pct_atualizadas = round((fontes_no_prazo / max(1, len(lista_fontes))) * 100.0, 1)

    return {
        "status_geral": "OPERACIONAL" if pct_atualizadas >= 50.0 else "ATENCAO_FONTES",
        "percentual_fontes_atualizadas_prazo": pct_atualizadas,
        "total_registros_base": {
            "tombamentos_rodoviarios": total_tombamentos,
            "postos_combustivel": total_postos,
            "trechos_osm": total_trechos
        },
        "detalhamento_fontes": lista_fontes,
        "aviso": "Indicadores consolidados para auditoria operacional interna e consumo do painel."
    }
