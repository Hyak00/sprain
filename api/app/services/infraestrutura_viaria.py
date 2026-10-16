"""Informacoes cadastradas nao representam homologacao de uma rota inteira."""
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace

from app import database

SCHEMA = Path(__file__).resolve().parents[3] / "db/ci/03_infraestrutura_viaria.sql"
LIMITES = {
    "altura_m": "altura_max_m",
    "largura_m": "largura_max_m",
    "comprimento_m": "comprimento_max_m",
    "peso_total_t": "peso_max_t",
}


async def garantir_schema():
    async with database.db_pool.acquire() as conn:
        await conn.execute(SCHEMA.read_text(encoding="utf-8"))


def avaliar_ponto(ponto, veiculo, agora=None):
    agora = agora or datetime.now(timezone.utc)
    vigente = ponto["verificado_em"] <= agora < ponto["valido_ate"]
    referencia_osm = ponto.get("origem_dados") == "REFERENCIA_OSM"
    excedidos = []
    ausentes = []
    if ponto["tipo"] == "PONTE":
        for medida, limite in LIMITES.items():
            if ponto[limite] is None or veiculo is None:
                ausentes.append(limite)
            elif getattr(veiculo, medida) > float(ponto[limite]):
                excedidos.append(limite)
        # Um limite excedido continua exigindo bloqueio mesmo com cadastro vencido.
        status = "BLOQUEADO" if excedidos else (
            "COMPATIVEL_COM_LIMITES_CADASTRADOS" if vigente and not ausentes and not referencia_osm else "CONFERENCIA_NECESSARIA"
        )
        return {"status": status, "limites_excedidos": excedidos,
                "limites_ausentes": ausentes, "dados_vigentes": vigente}
    tarifa = ponto["tarifa_por_eixo"]
    custo = round(tarifa * veiculo.eixos, 2) if vigente and tarifa is not None and veiculo is not None and not referencia_osm else None
    return {"status": "TARIFA_DISPONIVEL" if custo is not None else "TARIFA_A_CONFIRMAR",
            "custo_estimado_reais": float(custo) if custo is not None else None,
            "dados_vigentes": vigente}


def feature(ponto, avaliacao=None):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [ponto["longitude"], ponto["latitude"]]},
        "properties": {
            **{campo: ponto[campo] for campo in (
                "id", "tipo", "nome", "id_trecho", "fonte", "verificado_em", "valido_ate",
                "altura_max_m", "largura_max_m", "comprimento_max_m", "peso_max_t"
            )},
            "tarifa_por_eixo": float(ponto["tarifa_por_eixo"]) if ponto["tarifa_por_eixo"] is not None else None,
            "origem_dados": ponto.get("origem_dados", "CADASTRO_MANUAL"),
            **(avaliacao or {}),
        },
    }


SELECT_PONTOS = """
    SELECT *, ST_X(geom) AS longitude, ST_Y(geom) AS latitude
    FROM infraestrutura_viaria WHERE tenant_id = $1 AND ativo
"""


async def dimensoes_veiculo(conn, tenant_id, id_veiculo):
    import json
    from fastapi import HTTPException
    if not id_veiculo:
        return None
    row = await conn.fetchrow("SELECT dimensoes FROM veiculos WHERE id_veiculo=$1 AND tenant_id=$2",
                              id_veiculo, tenant_id)
    if row is None:
        raise HTTPException(404, "Veiculo nao encontrado na empresa autenticada.")
    return json.loads(row["dimensoes"]) if row["dimensoes"] else None


def resumir_rota(pontos, ids_trechos, dimensoes):
    veiculo = SimpleNamespace(**dimensoes) if dimensoes else None
    ids = set(ids_trechos)
    ordem = {edge:seq for seq,edge in enumerate(ids_trechos)}
    caminho = sorted((p for p in pontos if p["id_trecho"] in ids),key=lambda p:ordem[p["id_trecho"]])
    avaliacoes = {p["id"]: avaliar_ponto(p, veiculo) for p in caminho}
    pedagios = [avaliacoes[p["id"]] for p in caminho if p["tipo"] == "PEDAGIO"]
    conhecidos = [Decimal(str(p["custo_estimado_reais"])) for p in pedagios
                  if p["custo_estimado_reais"] is not None]
    return {
        "pontos_mapa": {"type": "FeatureCollection", "features": [feature(p, avaliacoes[p["id"]]) for p in caminho]},
        "pedagios": {"quantidade_cadastrada_na_rota": len(pedagios),
                     "subtotal_conhecido_reais": float(sum(conhecidos, Decimal("0"))),
                     "tarifas_pendentes": len(pedagios)-len(conhecidos), "custo_total_confirmado_reais": None},
        "status_passagem": "CONFERENCIA_NECESSARIA",
        "dimensoes_informadas": dimensoes is not None,
        "avisos": ["Cobertura parcial: ausencia de limites nao libera a passagem.",
                   "Tarifas estimadas por eixo; confirmar categoria, sentido de cobranca e descontos.",
                   "Conferir sinalizacao e restricoes locais antes da viagem."],
    }
