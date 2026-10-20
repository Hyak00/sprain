"""Alteracoes manuais, transacionais e auditadas no catalogo de planos."""

import json
import re
from datetime import datetime


COLUNAS_PLANO = (
    "codigo", "nome", "funcionalidades", "limite_usuarios_ativos",
    "limite_corredores_ativos", "limite_consultas_mes", "limite_chamadas_externas_mes",
)
COLUNAS_ASSINATURA = ("tenant_id", "plano_codigo", "status", "inicio_em", "fim_em")


def _validar_ator_motivo(ator: str, motivo: str) -> None:
    if not 3 <= len(ator.strip()) <= 150 or not 5 <= len(motivo.strip()) <= 1000:
        raise ValueError("Informe ator (3-150 caracteres) e motivo (5-1000 caracteres).")


def _json(dados: dict | None) -> str | None:
    return json.dumps(dados, default=lambda valor: valor.isoformat(), ensure_ascii=False) if dados else None


async def registrar_plano(conn, dados: dict, ator: str, motivo: str, aplicar: bool = False) -> dict:
    _validar_ator_motivo(ator, motivo)
    if set(dados) != set(COLUNAS_PLANO):
        raise ValueError("A configuracao do plano deve informar todos os campos.")
    codigo = dados["codigo"]
    if not isinstance(codigo, str) or re.fullmatch(r"[A-Z0-9_]{2,64}", codigo) is None:
        raise ValueError("Codigo de plano invalido.")
    if not isinstance(dados["nome"], str) or not 2 <= len(dados["nome"].strip()) <= 120:
        raise ValueError("Nome de plano invalido.")
    funcionalidades = dados["funcionalidades"]
    if not isinstance(funcionalidades, list) or any(not isinstance(f, str) or not f.strip() for f in funcionalidades):
        raise ValueError("Funcionalidades devem ser uma lista de textos nao vazios.")
    for campo in COLUNAS_PLANO[3:]:
        valor = dados[campo]
        if valor is not None and (type(valor) is not int or valor < 0):
            raise ValueError(f"{campo} deve ser inteiro nao negativo ou nulo.")
    novo = dict(dados)
    novo["funcionalidades"] = sorted(set(funcionalidades))
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", "plano:" + codigo)
        antigo = await conn.fetchrow("""
            SELECT codigo,nome,funcionalidades,limite_usuarios_ativos,limite_corredores_ativos,
                limite_consultas_mes,limite_chamadas_externas_mes
            FROM planos_servico WHERE codigo=$1 FOR UPDATE
        """, codigo)
        anterior = dict(antigo) if antigo else None
        alterado = anterior != novo
        if aplicar and alterado:
            await conn.execute("""
                INSERT INTO planos_servico(codigo,nome,funcionalidades,limite_usuarios_ativos,
                    limite_corredores_ativos,limite_consultas_mes,limite_chamadas_externas_mes)
                VALUES($1,$2,$3,$4,$5,$6,$7)
                ON CONFLICT(codigo) DO UPDATE SET nome=EXCLUDED.nome,
                    funcionalidades=EXCLUDED.funcionalidades,
                    limite_usuarios_ativos=EXCLUDED.limite_usuarios_ativos,
                    limite_corredores_ativos=EXCLUDED.limite_corredores_ativos,
                    limite_consultas_mes=EXCLUDED.limite_consultas_mes,
                    limite_chamadas_externas_mes=EXCLUDED.limite_chamadas_externas_mes,
                    atualizado_em=now()
            """, *(novo[c] for c in COLUNAS_PLANO))
            await conn.execute("""
                INSERT INTO planos_auditoria(tipo,chave,ator,motivo,anterior,posterior)
                VALUES('PLANO',$1,$2,$3,$4::jsonb,$5::jsonb)
            """, codigo, ator.strip(), motivo.strip(), _json(anterior), _json(novo))
    return {"tipo": "PLANO", "chave": codigo, "anterior": anterior, "posterior": novo,
            "alterado": alterado, "aplicado": aplicar and alterado}


async def registrar_assinatura(conn, dados: dict, ator: str, motivo: str, aplicar: bool = False) -> dict:
    _validar_ator_motivo(ator, motivo)
    if set(dados) != set(COLUNAS_ASSINATURA):
        raise ValueError("A assinatura deve informar todos os campos.")
    tenant = dados["tenant_id"]
    if not isinstance(tenant, str) or not 1 <= len(tenant.strip()) <= 150 or tenant != tenant.strip():
        raise ValueError("Identificador de empresa invalido.")
    if dados["status"] not in ("ATIVA", "SUSPENSA", "ENCERRADA"):
        raise ValueError("Status de assinatura invalido.")
    inicio, fim = dados["inicio_em"], dados["fim_em"]
    if not isinstance(inicio, datetime) or inicio.tzinfo is None or (fim is not None and (
        not isinstance(fim, datetime) or fim.tzinfo is None or fim <= inicio
    )):
        raise ValueError("Datas devem ter fuso; fim deve ser posterior ao inicio.")
    novo = dict(dados)
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", "assinatura:" + tenant)
        plano = await conn.fetchval("SELECT 1 FROM planos_servico WHERE codigo=$1", dados["plano_codigo"])
        if not plano:
            raise ValueError("Plano inexistente; cadastre o plano antes da assinatura.")
        antigo = await conn.fetchrow("""
            SELECT tenant_id,plano_codigo,status,inicio_em,fim_em
            FROM assinaturas_empresa WHERE tenant_id=$1 FOR UPDATE
        """, tenant)
        anterior = dict(antigo) if antigo else None
        alterado = anterior != novo
        if aplicar and alterado:
            await conn.execute("""
                INSERT INTO assinaturas_empresa(tenant_id,plano_codigo,status,inicio_em,fim_em)
                VALUES($1,$2,$3,$4,$5)
                ON CONFLICT(tenant_id) DO UPDATE SET plano_codigo=EXCLUDED.plano_codigo,
                    status=EXCLUDED.status,inicio_em=EXCLUDED.inicio_em,
                    fim_em=EXCLUDED.fim_em,atualizado_em=now()
            """, *(novo[c] for c in COLUNAS_ASSINATURA))
            await conn.execute("""
                INSERT INTO planos_auditoria(tipo,chave,ator,motivo,anterior,posterior)
                VALUES('ASSINATURA',$1,$2,$3,$4::jsonb,$5::jsonb)
            """, tenant, ator.strip(), motivo.strip(), _json(anterior), _json(novo))
    return {"tipo": "ASSINATURA", "chave": tenant, "anterior": anterior, "posterior": novo,
            "alterado": alterado, "aplicado": aplicar and alterado}
