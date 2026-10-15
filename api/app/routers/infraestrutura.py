from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.database import get_connection
from app.seguranca import require_role, resolver_tenant_autenticado, get_current_user_claims
from app.services.infraestrutura_viaria import SELECT_PONTOS, avaliar_ponto, feature
from app.services.routing_engine import RoutingEngine
from app.schemas_infraestrutura import VeiculoDimensoes
from app.schemas import CustosCaminhao
from app.services.viagem_caminhao import comparar_custos
from app.services.custo_combustivel import resolver_custos
import json

router = APIRouter(prefix="/api/v1/infraestrutura", tags=["Infraestrutura para caminhoes"],
                   dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])


@router.get("/sessao")
async def sessao(claims=Depends(get_current_user_claims)):
    return {"tenant_id":claims["tenant_id"],"perfil":claims["role"]}


@router.get('/pendencias')
async def pendencias(tenant_id=Depends(resolver_tenant_autenticado), conn=Depends(get_connection)):
    pontos = await conn.fetchrow("""SELECT
        COUNT(*) FILTER (WHERE tipo='PONTE')::int AS pontes_cadastradas,
        COUNT(*) FILTER (WHERE tipo='PEDAGIO' AND (tarifa_por_eixo IS NULL
            OR origem_dados='REFERENCIA_OSM' OR valido_ate<=now() OR verificado_em>now()))::int AS pedagios_sem_tarifa_vigente,
        COUNT(*) FILTER (WHERE tipo='PONTE' AND (altura_max_m IS NULL OR largura_max_m IS NULL
            OR comprimento_max_m IS NULL OR peso_max_t IS NULL OR origem_dados='REFERENCIA_OSM'
            OR valido_ate<=now() OR verificado_em>now()))::int AS pontes_sem_limites_completos_vigentes
        FROM infraestrutura_viaria WHERE tenant_id=$1 AND ativo""", tenant_id)
    caminhoes = await conn.fetchval('SELECT COUNT(*) FROM veiculos WHERE tenant_id=$1 AND dimensoes IS NULL', tenant_id)
    return {**dict(pontos), 'caminhoes_sem_medidas': caminhoes,
            'cobertura_completa': False,
            'aviso': 'Contagem do cadastro existente; nao mede cobertura de todas as pontes e pedagios da malha.'}


class PontoCadastro(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)
    tipo: Literal["PEDAGIO", "PONTE"]
    nome: str = Field(min_length=1, max_length=200)
    id_trecho: int = Field(gt=0)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    fonte: str = Field(min_length=1, max_length=1000, description="Referencia consultada pelo responsavel pelo cadastro")
    verificado_em: datetime
    valido_ate: datetime
    altura_max_m: float | None = Field(None, gt=0, le=10)
    largura_max_m: float | None = Field(None, gt=0, le=10)
    comprimento_max_m: float | None = Field(None, gt=0, le=100)
    peso_max_t: float | None = Field(None, gt=0, le=300)
    tarifa_por_eixo: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    origem_dados: Literal["CADASTRO_MANUAL", "REFERENCIA_OSM"] = "CADASTRO_MANUAL"
    grupo_cobranca: str | None = Field(None, min_length=1, max_length=120,
        description='Identificador conferido da mesma praca; evita duplicar pontos de cabines na mesma viagem.')

    @model_validator(mode="after")
    def validar_cadastro(self):
        if self.verificado_em.utcoffset() is None or self.valido_ate.utcoffset() is None:
            raise ValueError("Datas devem informar o fuso horario.")
        if self.verificado_em > datetime.now(timezone.utc) or self.valido_ate <= self.verificado_em:
            raise ValueError("Verificacao nao pode ser futura; validade deve ser posterior a verificacao.")
        if self.tipo == "PONTE" and self.tarifa_por_eixo is not None:
            raise ValueError("Tarifa deve ser cadastrada em um ponto PEDAGIO.")
        if self.origem_dados == "REFERENCIA_OSM" and self.tarifa_por_eixo is not None:
            raise ValueError("Tarifa deve ser conferida em fonte tarifaria e cadastrada como CADASTRO_MANUAL.")
        if self.tipo == "PEDAGIO" and any(getattr(self, campo) is not None for campo in (
            "altura_max_m", "largura_max_m", "comprimento_max_m", "peso_max_t"
        )):
            raise ValueError("Limites devem ser cadastrados em um ponto PONTE.")
        return self


class RotaCaminhaoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    origem_lon: float = Field(ge=-180, le=180)
    origem_lat: float = Field(ge=-90, le=90)
    destino_lon: float = Field(ge=-180, le=180)
    destino_lat: float = Field(ge=-90, le=90)
    veiculo: VeiculoDimensoes
    custos_operacionais: CustosCaminhao | None = None
    perfil: Literal["FASTEST", "SHORTEST", "SAFEST", "BALANCED"] = "FASTEST"
    chuva_mm: float = Field(0, ge=0, le=1000)


class AvaliarMapaRequest(BaseModel):
    veiculo: VeiculoDimensoes


@router.post("/avaliar-mapa")
async def avaliar_mapa(dados: AvaliarMapaRequest,tenant_id=Depends(resolver_tenant_autenticado),conn=Depends(get_connection)):
    pontos=await conn.fetch(SELECT_PONTOS+" ORDER BY id LIMIT 5001",tenant_id)
    features=[feature(p,avaliar_ponto(p,dados.veiculo)) for p in pontos[:5000]]
    linhas=await conn.fetch("""SELECT t.id_trecho,t.name,t.limites_malha,t.fonte_malha,t.tenant_malha,
        t.limites_verificado_em,t.limites_valido_ate,
        ST_AsGeoJSON(ST_Transform(t.geom,4326)) AS geometry FROM trechos_osm t
        WHERE (t.tenant_malha IS NULL OR t.tenant_malha=$1) AND t.limites_malha IS NOT NULL
        AND (t.limites_malha<>'{}'::jsonb OR t.limites_verificado_em IS NOT NULL) AND (t.importacao_malha_id IS NULL OR EXISTS(
            SELECT 1 FROM malha_importacoes m WHERE m.id=t.importacao_malha_id AND m.ativo))
        ORDER BY t.id_trecho LIMIT 2001""",tenant_id)
    for linha in linhas[:2000]:
        limites=json.loads(linha["limites_malha"])
        origem='CADASTRO_MANUAL' if linha['limites_verificado_em'] else 'REFERENCIA_OSM'
        ponto={"tipo":"PONTE","verificado_em":linha['limites_verificado_em'] or datetime.now(timezone.utc),
               "valido_ate":linha['limites_valido_ate'] or datetime.max.replace(tzinfo=timezone.utc),"origem_dados":origem,
               **{k:limites.get(k) for k in ("altura_max_m","largura_max_m","comprimento_max_m","peso_max_t")}}
        features.append({"type":"Feature","geometry":json.loads(linha["geometry"]),"properties":{
            "tipo":"LIMITE_MALHA","id_trecho":linha["id_trecho"],"nome":linha["name"],
            "fonte":linha["fonte_malha"],"origem_dados":origem,"editavel":linha['tenant_malha']==tenant_id,
            "verificado_em":linha['limites_verificado_em'],"valido_ate":linha['limites_valido_ate'],**limites,
            **avaliar_ponto(ponto,dados.veiculo)}})
    return {"type":"FeatureCollection","features":features,"truncado":len(pontos)>5000 or len(linhas)>2000}


class LimitesTrechoUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False,str_strip_whitespace=True)
    altura_max_m: float | None=Field(None,gt=0,le=10)
    largura_max_m: float | None=Field(None,gt=0,le=10)
    comprimento_max_m: float | None=Field(None,gt=0,le=100)
    peso_max_t: float | None=Field(None,gt=0,le=300)
    fonte: str=Field(min_length=1,max_length=1000)
    verificado_em: datetime
    valido_ate: datetime

    @model_validator(mode='after')
    def datas(self):
        if self.verificado_em.utcoffset() is None or self.valido_ate.utcoffset() is None:
            raise ValueError('Datas devem conter fuso horario.')
        if self.verificado_em>datetime.now(timezone.utc) or self.valido_ate<=self.verificado_em:
            raise ValueError('Confira as datas de verificacao e validade.')
        return self


@router.put('/trechos/{id_trecho}/limites',dependencies=[Depends(require_role(['ADMIN']))])
async def atualizar_limites_trecho(id_trecho: int,dados: LimitesTrechoUpdate,tenant_id=Depends(resolver_tenant_autenticado),conn=Depends(get_connection)):
    async with conn.transaction():
        row=await conn.fetchrow("""SELECT t.limites_malha FROM trechos_osm t
            WHERE t.id_trecho=$1 AND t.tenant_malha=$2 AND EXISTS(
                SELECT 1 FROM malha_importacoes m WHERE m.id=t.importacao_malha_id AND m.ativo) FOR UPDATE""",id_trecho,tenant_id)
        if row is None:
            raise HTTPException(404,'Trecho ativo nao encontrado na malha da empresa.')
        limites={k:getattr(dados,k) for k in ('altura_max_m','largura_max_m','comprimento_max_m','peso_max_t') if getattr(dados,k) is not None}
        await conn.execute("""UPDATE trechos_osm SET limites_malha=$3::jsonb,fonte_malha=$4,
            limites_verificado_em=$5,limites_valido_ate=$6 WHERE id_trecho=$1 AND tenant_malha=$2""",
            id_trecho,tenant_id,json.dumps(limites),dados.fonte,dados.verificado_em,dados.valido_ate)
        await conn.execute("""INSERT INTO malha_limites_revisoes(tenant_id,id_trecho,cadastro)
            VALUES($1,$2,$3::jsonb)""",tenant_id,id_trecho,json.dumps({'antes':json.loads(row['limites_malha']) if row['limites_malha'] else {},'depois':dados.model_dump(mode='json')}))
    RoutingEngine.clear_cache(tenant_id)
    return {'status':'ATUALIZADO','id_trecho':id_trecho}


@router.get('/trechos/{id_trecho}/historico')
async def historico_limites_trecho(id_trecho: int,tenant_id=Depends(resolver_tenant_autenticado),conn=Depends(get_connection)):
    rows=await conn.fetch('SELECT cadastro,registrado_em FROM malha_limites_revisoes WHERE tenant_id=$1 AND id_trecho=$2 ORDER BY id DESC LIMIT 100',tenant_id,id_trecho)
    return [{'cadastro':json.loads(r['cadastro']),'registrado_em':r['registrado_em']} for r in rows]


async def salvar_ponto(conn, dados, tenant_id, id_ponto=None):
    async with conn.transaction():
        if id_ponto is not None:
            existe = await conn.fetchval("SELECT id FROM infraestrutura_viaria WHERE id=$1 AND tenant_id=$2 FOR UPDATE",
                                         id_ponto, tenant_id)
            if existe is None:
                raise HTTPException(404, "Ponto nao encontrado.")
        proximo = await conn.fetchval("""
            SELECT ST_DWithin(ST_Transform(geom, 4326)::geography,
                ST_SetSRID(ST_Point($2,$3),4326)::geography, 50)
            FROM trechos_osm t WHERE id_trecho=$1 AND (tenant_malha IS NULL OR tenant_malha=$4)
                AND (t.importacao_malha_id IS NULL OR EXISTS(SELECT 1 FROM malha_importacoes m
                    WHERE m.id=t.importacao_malha_id AND m.ativo))
        """, dados.id_trecho, dados.longitude, dados.latitude, tenant_id)
        if not proximo:
            raise HTTPException(422, "Trecho inexistente ou ponto a mais de 50 metros do trecho informado.")
        valores = (tenant_id, dados.tipo, dados.nome, dados.id_trecho, dados.longitude, dados.latitude,
                   dados.fonte, dados.verificado_em, dados.valido_ate, dados.altura_max_m,
                   dados.largura_max_m, dados.comprimento_max_m, dados.peso_max_t, dados.tarifa_por_eixo, dados.origem_dados)
        if id_ponto is None:
            id_ponto = await conn.fetchval("""
                INSERT INTO infraestrutura_viaria (tenant_id,tipo,nome,id_trecho,geom,fonte,verificado_em,
                    valido_ate,altura_max_m,largura_max_m,comprimento_max_m,peso_max_t,tarifa_por_eixo,origem_dados)
                VALUES ($1,$2,$3,$4,ST_SetSRID(ST_Point($5,$6),4326),$7,$8,$9,$10,$11,$12,$13,$14,$15)
                RETURNING id
            """, *valores)
        else:
            await conn.execute("""
                UPDATE infraestrutura_viaria SET tipo=$2,nome=$3,id_trecho=$4,
                    geom=ST_SetSRID(ST_Point($5,$6),4326),fonte=$7,verificado_em=$8,valido_ate=$9,
                    altura_max_m=$10,largura_max_m=$11,comprimento_max_m=$12,peso_max_t=$13,
                    tarifa_por_eixo=$14,origem_dados=$15,atualizado_em=now(),ativo=true WHERE tenant_id=$1 AND id=$16
            """, *valores, id_ponto)
        await conn.execute('UPDATE infraestrutura_viaria SET grupo_cobranca=$3 WHERE id=$1 AND tenant_id=$2',
                           id_ponto, tenant_id, dados.grupo_cobranca)
        await conn.execute("""INSERT INTO infraestrutura_revisoes(ponto_id,tenant_id,acao,cadastro)
            VALUES($1,$2,'SALVAR',$3::jsonb)""", id_ponto, tenant_id, dados.model_dump_json())
    RoutingEngine.clear_cache(tenant_id)
    return {"id": id_ponto, "status": "CADASTRADO"}


@router.post("/pontos", status_code=201, dependencies=[Depends(require_role(["ADMIN"]))])
async def cadastrar_ponto(dados: PontoCadastro, tenant_id=Depends(resolver_tenant_autenticado),
                         conn=Depends(get_connection)):
    return await salvar_ponto(conn, dados, tenant_id)


@router.put("/pontos/{id_ponto}", dependencies=[Depends(require_role(["ADMIN"]))])
async def atualizar_ponto(id_ponto: int, dados: PontoCadastro, tenant_id=Depends(resolver_tenant_autenticado),
                         conn=Depends(get_connection)):
    return await salvar_ponto(conn, dados, tenant_id, id_ponto)


@router.get("/pontos")
async def listar_pontos(tipo: Literal["PEDAGIO", "PONTE"] | None = None,
                        limite: int = Query(500, ge=1, le=1000),
                        depois_id: int = Query(0, ge=0),
                        tenant_id=Depends(resolver_tenant_autenticado), conn=Depends(get_connection)):
    pontos = await conn.fetch(SELECT_PONTOS + " AND ($2::text IS NULL OR tipo=$2) AND id>$3 ORDER BY id LIMIT $4",
                             tenant_id, tipo, depois_id, limite + 1)
    pagina = pontos[:limite]
    return {"type": "FeatureCollection", "features": [feature(p) for p in pagina],
            "proximo_depois_id": pagina[-1]["id"] if len(pontos) > limite else None}


class ImportacaoPontos(BaseModel):
    pontos: list[PontoCadastro] = Field(min_length=1, max_length=500)
    validar_apenas: bool = True


@router.post("/importar-pontos", dependencies=[Depends(require_role(["ADMIN"]))])
async def importar_pontos(dados: ImportacaoPontos, tenant_id=Depends(resolver_tenant_autenticado),
                          conn=Depends(get_connection)):
    ids = []
    try:
        async with conn.transaction():
            for p in dados.pontos:
                # Reenvio idempotente; atualizacao ocorre por PUT explicito.
                existente = await conn.fetchval("""SELECT id FROM infraestrutura_viaria
                    WHERE tenant_id=$1 AND tipo=$2 AND nome=$3 AND id_trecho=$4 AND fonte=$5 AND ativo""",
                    tenant_id, p.tipo, p.nome, p.id_trecho, p.fonte)
                if existente is not None:
                    ids.append(existente)
                else:
                    ids.append((await salvar_ponto(conn, p, tenant_id))["id"])
            if dados.validar_apenas:
                raise _ValidacaoLote(ids)
    except _ValidacaoLote:
        return {"status": "VALIDADO_SEM_GRAVAR", "quantidade": len(ids)}
    return {"status": "IMPORTADO", "ids": ids}


class _ValidacaoLote(Exception):
    def __init__(self, ids):
        self.ids = ids


@router.delete("/pontos/{id_ponto}", dependencies=[Depends(require_role(["ADMIN"]))])
async def desativar_ponto(id_ponto: int, tenant_id=Depends(resolver_tenant_autenticado), conn=Depends(get_connection)):
    async with conn.transaction():
        row = await conn.fetchrow("""UPDATE infraestrutura_viaria SET ativo=false,atualizado_em=now()
            WHERE id=$1 AND tenant_id=$2 AND ativo RETURNING id""", id_ponto, tenant_id)
        if row is None:
            raise HTTPException(404, "Ponto nao encontrado.")
        await conn.execute("""INSERT INTO infraestrutura_revisoes(ponto_id,tenant_id,acao,cadastro)
            VALUES($1,$2,'DESATIVAR','{}'::jsonb)""", id_ponto, tenant_id)
    RoutingEngine.clear_cache(tenant_id)
    return {"status": "DESATIVADO", "id": id_ponto}


@router.get("/pontos/{id_ponto}/historico")
async def historico_ponto(id_ponto: int, tenant_id=Depends(resolver_tenant_autenticado), conn=Depends(get_connection)):
    rows = await conn.fetch("""SELECT acao,cadastro,registrado_em FROM infraestrutura_revisoes
        WHERE ponto_id=$1 AND tenant_id=$2 ORDER BY id DESC LIMIT 100""", id_ponto, tenant_id)
    return [{"acao": r["acao"], "cadastro": json.loads(r["cadastro"]), "registrado_em": r["registrado_em"]} for r in rows]


@router.post("/rota-caminhao")
async def calcular_rota_caminhao(dados: RotaCaminhaoRequest,
                                tenant_id=Depends(resolver_tenant_autenticado),
                                conn: asyncpg.Connection = Depends(get_connection)):
    for lon, lat in ((dados.origem_lon, dados.origem_lat), (dados.destino_lon, dados.destino_lat)):
        na_malha = await conn.fetchval("""
            SELECT EXISTS (SELECT 1 FROM trechos_osm_vertices_pgr v
                WHERE ST_DWithin(ST_Transform(v.the_geom,4326)::geography,
                    ST_SetSRID(ST_Point($1,$2),4326)::geography,150)
                AND EXISTS(SELECT 1 FROM trechos_osm t WHERE (t.source=v.id OR t.target=v.id)
                    AND (t.tenant_malha IS NULL OR t.tenant_malha=$3)
                    AND (t.importacao_malha_id IS NULL OR EXISTS(SELECT 1 FROM malha_importacoes m
                        WHERE m.id=t.importacao_malha_id AND m.ativo))))
        """, lon, lat, tenant_id)
        if not na_malha:
            raise HTTPException(422, "Origem ou destino fora da cobertura: informe um ponto a ate 150m de um vertice da malha.")
    pontos = await conn.fetch(SELECT_PONTOS, tenant_id)
    avaliacoes = {p["id"]: avaliar_ponto(p, dados.veiculo) for p in pontos}
    bloqueados = sorted({p["id_trecho"] for p in pontos if avaliacoes[p["id"]]["status"] == "BLOQUEADO"})
    rota = await RoutingEngine.compute_route(
        conn, dados.origem_lon, dados.origem_lat, dados.destino_lon, dados.destino_lat,
        profile=dados.perfil, rain_mm=dados.chuva_mm,
        tipo_veiculo="CARRETA_5_EIXOS" if dados.veiculo.eixos >= 5 else "TRUCK_3_EIXOS",
        tenant_id=tenant_id, blocked_edge_ids=bloqueados, vehicle_dimensions=dados.veiculo.model_dump(),
    )
    if rota is None:
        raise HTTPException(404, "Sem caminho entre os pontos na malha disponivel, considerando os bloqueios cadastrados.")
    ids = set(rota["ids_trechos"])
    ordem = {edge:seq for seq,edge in enumerate(rota["ids_trechos"])}
    no_caminho = sorted((p for p in pontos if p["id_trecho"] in ids),key=lambda p:ordem[p["id_trecho"]])
    custos=await resolver_custos(conn,dados.custos_operacionais.model_dump(mode="json",exclude_none=True) if dados.custos_operacionais else {},dados.veiculo.model_dump())
    return {
        "rota": rota,
        "custos":comparar_custos(rota,rota,custos,False),
        "pontos_mapa": {"type": "FeatureCollection",
                        "features": [feature(p, avaliacoes[p["id"]]) for p in no_caminho]},
        "trechos_excluidos_por_limites": bloqueados,
        "pedagios": rota['infraestrutura']['pedagios'],
        "status_passagem": "CONFERENCIA_NECESSARIA",
        "avisos": ["Cadastro parcial: ausencia de pontos ou limites nao significa passagem liberada.",
                   "Rota limitada a malha disponivel. Conferir sinalizacao, sentido da via e restricoes locais.",
                   "Tarifa por eixo e estimativa; descontos, categoria e sentido de cobranca exigem conferencia."],
    }
