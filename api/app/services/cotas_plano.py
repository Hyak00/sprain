"""Cotas transacionais por empresa; sem preco ou suspensao de acesso."""

from fastapi import HTTPException

from app.services.planos_empresa import periodo_atual


LIMITES = {
    "usuarios": ("limite_usuarios_ativos", "usuarios ativos"),
    "corredores": ("limite_corredores_ativos", "corredores ativos"),
    "consultas": ("limite_consultas_mes", "consultas no mes"),
}


async def verificar_cota(conn, tenant: str, recurso: str) -> dict:
    """Reservar a vez antes da escrita, na mesma transacao READ COMMITTED.

    O bloqueio compartilhado pelo PostgreSQL impede que duas replicas contem o
    mesmo saldo simultaneamente. O chamador deve inserir/ativar antes do commit.
    """
    if not conn.is_in_transaction():
        raise RuntimeError("Verificacao de cota exige transacao junto com a escrita.")
    if recurso not in LIMITES:
        raise ValueError("Recurso de cota desconhecido.")
    coluna, nome = LIMITES[recurso]
    limite = await conn.fetchval(f"""
        SELECT p.{coluna} FROM assinaturas_empresa a
        JOIN planos_servico p ON p.codigo=a.plano_codigo
        WHERE a.tenant_id=$1
    """, tenant)
    if limite is None:
        return {"recurso": recurso, "limite": None}
    await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", "cota:" + tenant + ":" + recurso)
    # O plano pode ter sido alterado enquanto aguardavamos o bloqueio.
    limite = await conn.fetchval(f"""
        SELECT p.{coluna} FROM assinaturas_empresa a
        JOIN planos_servico p ON p.codigo=a.plano_codigo
        WHERE a.tenant_id=$1
    """, tenant)
    if limite is None:
        return {"recurso": recurso, "limite": None}
    if recurso == "usuarios":
        atual = await conn.fetchval("SELECT count(*) FROM painel_usuarios WHERE tenant_id=$1 AND ativo", tenant)
    elif recurso == "corredores":
        atual = await conn.fetchval("SELECT count(*) FROM painel_corredores WHERE tenant_id=$1 AND dados->>'ativo'='true'", tenant)
    else:
        # Usa o mesmo relogio da coluna criado_em (DEFAULT now()) da transacao.
        inicio, fim, _ = periodo_atual(await conn.fetchval("SELECT now()"))
        atual = await conn.fetchval("""
            SELECT count(*) FROM painel_consultas
            WHERE tenant_id=$1 AND criado_em >= $2 AND criado_em < $3
        """, tenant, inicio, fim)
    if atual >= limite:
        raise HTTPException(429, f"Limite do plano para {nome} atingido.")
    return {"recurso": recurso, "limite": limite, "uso_antes": atual}
