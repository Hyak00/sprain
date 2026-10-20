"""Agrega tempo de resposta por empresa sem gravar caminhos ou conteudo."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.services.planos_empresa import periodo_atual


FUSO = ZoneInfo("America/Sao_Paulo")


async def resumo_por_endpoint(conn, tenant_id: str, agora: datetime | None = None):
    inicio, fim, periodo = periodo_atual(agora)
    rows = await conn.fetch("""
        SELECT metodo,rota_template,sum(requisicoes)::bigint AS requisicoes,
            sum(erros)::bigint AS erros,
            sum(tempo_resposta_total_ms)::double precision AS tempo_total_ms,
            max(tempo_resposta_max_ms)::double precision AS tempo_max_ms
        FROM metricas_endpoint_diario
        WHERE tenant_id=$1 AND dia_local >= $2 AND dia_local < $3
        GROUP BY metodo,rota_template
        ORDER BY requisicoes DESC,metodo,rota_template LIMIT 101
    """, tenant_id, inicio.astimezone(FUSO).date(), fim.astimezone(FUSO).date())
    return {
        "empresa": tenant_id,
        "periodo": periodo,
        "fuso_periodo": "America/Sao_Paulo",
        "endpoints": [{
            "metodo": row["metodo"], "rota_template": row["rota_template"],
            "requisicoes": row["requisicoes"], "erros": row["erros"],
            "tempo_medio_ms": round(row["tempo_total_ms"] / row["requisicoes"], 2),
            "tempo_max_ms": round(row["tempo_max_ms"], 2),
        } for row in rows[:100]],
        "truncado": len(rows) > 100,
        "aviso": "Agregados de respostas autenticadas desta empresa. Tempo de resposta nao mede CPU; "
                 "gravacao em segundo plano pode perder amostras se a API parar ou a fila encher.",
    }


async def registrar_atendimento(conn, tenant_id: str, status_code: int,
                                duracao_ms: float, agora: datetime | None = None,
                                metodo: str | None = None, rota_template: str | None = None):
    dia = (agora or datetime.now(FUSO)).astimezone(FUSO).date()
    tempo = Decimal(str(round(max(0.0, min(duracao_ms, 3_600_000.0)), 3)))
    await conn.execute("""
        INSERT INTO tempo_api_empresa_diario
            (tenant_id,dia_local,requisicoes,erros,tempo_resposta_total_ms)
        VALUES($1,$2,1,$3,$4)
        ON CONFLICT(tenant_id,dia_local) DO UPDATE SET
            requisicoes=tempo_api_empresa_diario.requisicoes+1,
            erros=tempo_api_empresa_diario.erros+EXCLUDED.erros,
            tempo_resposta_total_ms=tempo_api_empresa_diario.tempo_resposta_total_ms
                +EXCLUDED.tempo_resposta_total_ms,
            atualizado_em=now()
    """, tenant_id, dia, int(status_code >= 400), tempo)
    if metodo and rota_template:
        await conn.execute("""
            INSERT INTO metricas_endpoint_diario
                (tenant_id,dia_local,metodo,rota_template,requisicoes,erros,
                 tempo_resposta_total_ms,tempo_resposta_max_ms)
            VALUES($1,$2,$3,$4,1,$5,$6,$6)
            ON CONFLICT(tenant_id,dia_local,metodo,rota_template) DO UPDATE SET
                requisicoes=metricas_endpoint_diario.requisicoes+1,
                erros=metricas_endpoint_diario.erros+EXCLUDED.erros,
                tempo_resposta_total_ms=metricas_endpoint_diario.tempo_resposta_total_ms
                    +EXCLUDED.tempo_resposta_total_ms,
                tempo_resposta_max_ms=GREATEST(metricas_endpoint_diario.tempo_resposta_max_ms,
                    EXCLUDED.tempo_resposta_max_ms),
                atualizado_em=now()
        """, tenant_id, dia, metodo[:12], rota_template[:240],
            int(status_code >= 400), tempo)
