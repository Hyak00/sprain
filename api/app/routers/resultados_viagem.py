"""Resultados declarados apos a viagem, separados das previsoes e decisoes."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, model_validator

from app.database import get_connection
from app.seguranca import get_current_user_claims, require_role


router = APIRouter(prefix="/api/v1/logistica", tags=["Resultados de viagem"])


class ResultadoViagemRequest(BaseModel):
    finalizada_em: datetime
    rota_executada: Literal["ORIGINAL", "DESVIO", "OUTRA", "NAO_INFORMADA"]
    duracao_real_min: Decimal | None = Field(default=None, ge=0, le=1000000, max_digits=12, decimal_places=2)
    distancia_real_km: Decimal | None = Field(default=None, ge=0, le=1000000, max_digits=12, decimal_places=2)
    custo_real_brl: Decimal | None = Field(default=None, ge=0, le=1000000000, max_digits=12, decimal_places=2)
    fonte: Literal["RELATO_OPERADOR", "TELEMETRIA", "DOCUMENTO"]
    referencia_evidencia: str | None = Field(default=None, max_length=200)
    observacoes: str | None = Field(default=None, max_length=1000)
    id_decisao: int | None = Field(default=None, gt=0)
    substitui_id: UUID | None = None

    @model_validator(mode="after")
    def validar_registro(self):
        if self.finalizada_em.tzinfo is None or self.finalizada_em.utcoffset() is None:
            raise ValueError("finalizada_em precisa incluir fuso horario.")
        if self.finalizada_em > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("A viagem nao pode terminar no futuro.")
        if all(valor is None for valor in (self.duracao_real_min, self.distancia_real_km, self.custo_real_brl)):
            raise ValueError("Informe ao menos uma medida real: duracao, distancia ou custo.")
        if self.fonte == "DOCUMENTO" and not (self.referencia_evidencia or "").strip():
            raise ValueError("DOCUMENTO requer uma referencia de evidencia.")
        return self


def serializar(row):
    dados = dict(row)
    for campo in ("id", "substitui_id", "usuario_id"):
        if dados.get(campo) is not None:
            dados[campo] = str(dados[campo])
    for campo in ("finalizada_em", "registrada_em"):
        dados[campo] = dados[campo].isoformat()
    for campo in ("duracao_real_min", "distancia_real_km", "custo_real_brl"):
        if dados[campo] is not None:
            dados[campo] = float(dados[campo])
    dados["verificacao"] = "NAO_VERIFICADO"
    return dados


@router.post(
    "/operacoes/{id_operacao}/resultados-viagem",
    status_code=201,
    dependencies=[Depends(require_role(["ADMIN", "OPERATOR"]))],
)
async def registrar_resultado(
    id_operacao: str,
    payload: ResultadoViagemRequest,
    claims: dict = Depends(get_current_user_claims),
    conn: asyncpg.Connection = Depends(get_connection),
):
    tenant = claims["tenant_id"]
    async with conn.transaction():
        operacao = await conn.fetchval(
            "SELECT id_operacao FROM operacoes WHERE id_operacao=$1 AND tenant_id=$2 FOR UPDATE",
            id_operacao, tenant,
        )
        if operacao is None:
            raise HTTPException(404, "Operacao nao encontrada.")
        anterior = await conn.fetchval("""
            SELECT atual.id FROM resultados_viagem atual
            WHERE atual.id_operacao=$1 AND atual.tenant_id=$2
              AND NOT EXISTS (SELECT 1 FROM resultados_viagem proximo WHERE proximo.substitui_id=atual.id)
        """, id_operacao, tenant)
        if anterior != payload.substitui_id:
            raise HTTPException(409, "Resultado alterado. Consulte o registro mais recente antes de corrigir.")
        if payload.id_decisao is not None:
            decisao = await conn.fetchval("""
                SELECT id_decisao FROM decisoes_gestor_operacao
                WHERE id_decisao=$1 AND id_operacao=$2 AND tenant_id=$3
            """, payload.id_decisao, id_operacao, tenant)
            if decisao is None:
                raise HTTPException(422, "Decisao nao pertence a esta operacao.")
        row = await conn.fetchrow("""
            INSERT INTO resultados_viagem (
                id,tenant_id,id_operacao,id_decisao,substitui_id,finalizada_em,usuario_id,
                rota_executada,duracao_real_min,distancia_real_km,custo_real_brl,fonte,
                referencia_evidencia,observacoes
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            RETURNING *
        """, uuid4(), tenant, id_operacao, payload.id_decisao, anterior,
            payload.finalizada_em, UUID(claims["usuario_id"]) if claims.get("usuario_id") else None,
            payload.rota_executada, payload.duracao_real_min, payload.distancia_real_km,
            payload.custo_real_brl, payload.fonte, payload.referencia_evidencia, payload.observacoes)
    return serializar(row)


@router.get(
    "/operacoes/{id_operacao}/resultados-viagem",
    dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))],
)
async def listar_resultados(
    id_operacao: str,
    response: Response,
    offset: int = Query(0, ge=0),
    claims: dict = Depends(get_current_user_claims),
    conn: asyncpg.Connection = Depends(get_connection),
):
    tenant = claims["tenant_id"]
    existe = await conn.fetchval(
        "SELECT id_operacao FROM operacoes WHERE id_operacao=$1 AND tenant_id=$2",
        id_operacao, tenant,
    )
    if existe is None:
        raise HTTPException(404, "Operacao nao encontrada.")
    rows = await conn.fetch("""
        SELECT * FROM resultados_viagem
        WHERE id_operacao=$1 AND tenant_id=$2
        ORDER BY registrada_em DESC, id DESC OFFSET $3 LIMIT 21
    """, id_operacao, tenant, offset)
    response.headers["Cache-Control"] = "no-store"
    return {
        "items": [serializar(row) for row in rows[:20]],
        "proximo_offset": offset + 20 if len(rows) > 20 else None,
        "aviso": "Medidas informadas; documentos e execucao ainda nao foram verificados. Nao representam economia comprovada.",
    }
