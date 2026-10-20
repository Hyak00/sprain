"""Leitura por empresa de assinatura e consumo persistido, sem cobranca automatica."""

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.database import get_connection


SCHEMA = (Path(__file__).resolve().parents[3] / "db" / "ci" / "16_planos_empresa.sql").read_text(encoding="utf-8")
SCHEMA_AUDITORIA = (Path(__file__).resolve().parents[3] / "db" / "ci" / "17_auditoria_planos.sql").read_text(encoding="utf-8")
FUSO_CONSUMO = ZoneInfo("America/Sao_Paulo")


async def garantir_schema():
    async for conn in get_connection():
        await conn.execute(SCHEMA)
        await conn.execute(SCHEMA_AUDITORIA)


def periodo_atual(agora: datetime | None = None) -> tuple[datetime, datetime, str]:
    local = (agora or datetime.now(timezone.utc)).astimezone(FUSO_CONSUMO)
    inicio = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    proximo = inicio.replace(year=inicio.year + 1, month=1) if inicio.month == 12 else inicio.replace(month=inicio.month + 1)
    return inicio.astimezone(timezone.utc), proximo.astimezone(timezone.utc), inicio.strftime("%Y-%m")


async def resumo(conn, tenant_id: str, agora: datetime | None = None) -> dict:
    inicio, fim, periodo = periodo_atual(agora)
    plano = await conn.fetchrow("""
        SELECT a.tenant_id,a.status,a.inicio_em,a.fim_em,a.atualizado_em,
               p.codigo,p.nome,p.funcionalidades,p.limite_usuarios_ativos,
               p.limite_corredores_ativos,p.limite_consultas_mes,p.limite_chamadas_externas_mes
        FROM assinaturas_empresa a JOIN planos_servico p ON p.codigo=a.plano_codigo
        WHERE a.tenant_id=$1
    """, tenant_id)
    uso = await conn.fetchrow("""
        SELECT
            (SELECT count(*)::integer FROM painel_usuarios WHERE tenant_id=$1 AND ativo) AS usuarios_ativos,
            (SELECT count(*)::integer FROM painel_corredores WHERE tenant_id=$1 AND dados->>'ativo'='true') AS corredores_ativos,
            (SELECT count(*)::integer FROM painel_consultas WHERE tenant_id=$1
                AND criado_em >= $2 AND criado_em < $3) AS consultas_mes
    """, tenant_id, inicio, fim)
    assinatura = None
    if plano:
        assinatura = {
            "codigo": plano["codigo"], "nome": plano["nome"], "status_registrado": plano["status"],
            "inicio_em": plano["inicio_em"], "fim_em": plano["fim_em"],
            "atualizado_em": plano["atualizado_em"], "funcionalidades": plano["funcionalidades"],
            "limites": {campo: plano["limite_" + campo] for campo in (
                "usuarios_ativos", "corredores_ativos", "consultas_mes", "chamadas_externas_mes")},
        }
    return {
        "empresa": tenant_id,
        "periodo": periodo,
        "fuso_periodo": "America/Sao_Paulo",
        "assinatura": assinatura,
        "situacao": "REGISTRADA" if assinatura else "SEM_ASSINATURA_CONFIGURADA",
        "uso": {**dict(uso), "chamadas_externas_mes": None, "custo_servir_brl": None},
        "aviso": "Contagens de usuarios, corredores e consultas persistidas nesta empresa. "
                 "Limites e status sao informativos nesta etapa: ainda nao bloqueiam operacoes. "
                 "Chamadas externas e custo de servir ainda nao sao medidos; nulo nao significa zero.",
    }
