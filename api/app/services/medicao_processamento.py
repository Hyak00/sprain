"""Agrega tempo de resposta por empresa sem gravar caminhos ou conteudo."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo


FUSO = ZoneInfo("America/Sao_Paulo")


async def registrar_atendimento(conn, tenant_id: str, status_code: int,
                                duracao_ms: float, agora: datetime | None = None):
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
