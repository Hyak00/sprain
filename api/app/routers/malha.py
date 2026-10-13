"""Importacao transacional e aditiva de segmentos GeoJSON por empresa."""
import hashlib
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.database import get_connection
from app.seguranca import require_role, resolver_tenant_autenticado
from app.services.routing_engine import RoutingEngine

router = APIRouter(prefix="/api/v1/infraestrutura/malha", tags=["Infraestrutura para caminhoes"],
                   dependencies=[Depends(require_role(["ADMIN"]))])


class SegmentoMalha(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    origem: str = Field(min_length=1,max_length=100)
    destino: str = Field(min_length=1,max_length=100)
    coordenadas: list[tuple[float, float]] = Field(min_length=2,max_length=1000)
    nome: str = Field(max_length=200)
    highway: Literal["motorway", "motorway_link", "trunk", "trunk_link", "primary", "secondary", "tertiary", "residential"]
    sentido: Literal["AMBOS", "DIRETO", "INVERSO"]
    altura_max_m: float | None = Field(None,gt=0,le=10)
    largura_max_m: float | None = Field(None,gt=0,le=10)
    comprimento_max_m: float | None = Field(None,gt=0,le=100)
    peso_max_t: float | None = Field(None,gt=0,le=300)
    referencia: str | None = Field(None,max_length=1000)

    @model_validator(mode="after")
    def validar(self):
        if self.origem == self.destino:
            raise ValueError("Segmento precisa de vertices distintos.")
        if any(not (-180 <= lon <= 180 and -90 <= lat <= 90) for lon,lat in self.coordenadas):
            raise ValueError("Coordenadas invalidas.")
        if any(not (-53 <= lon <= -44 and -26 <= lat <= -19) for lon,lat in self.coordenadas):
            raise ValueError("Importador deste piloto aceita apenas a area de Sao Paulo.")
        if self.coordenadas[0] == self.coordenadas[-1]:
            raise ValueError("Segmento nao pode ter comprimento zero.")
        return self


class ImportacaoMalha(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fonte: str = Field(min_length=1,max_length=1000)
    segmentos: list[SegmentoMalha] = Field(min_length=1,max_length=30000)
    validar_apenas: bool = True
    substituir_importacao: int | None = Field(None,gt=0)


@router.post("/importar")
async def importar(dados: ImportacaoMalha, tenant_id=Depends(resolver_tenant_autenticado),conn=Depends(get_connection)):
    vertices = {}
    for s in dados.segmentos:
        for no,coord in ((s.origem,s.coordenadas[0]),(s.destino,s.coordenadas[-1])):
            if no in vertices and vertices[no] != coord:
                raise HTTPException(422,"Um mesmo vertice possui coordenadas diferentes.")
            vertices[no] = coord
    corpo = dados.model_dump(exclude={"validar_apenas", "substituir_importacao"})
    digest = hashlib.sha256(json.dumps(corpo,sort_keys=True).encode()).hexdigest()
    if dados.substituir_importacao is not None:
        anterior = await conn.fetchval("SELECT id FROM malha_importacoes WHERE id=$1 AND tenant_id=$2",
                                      dados.substituir_importacao,tenant_id)
        if anterior is None:
            raise HTTPException(404,"Importacao anterior nao encontrada na empresa.")
    if dados.validar_apenas:
        return {"status":"VALIDADO_SEM_GRAVAR","vertices":len(vertices),"trechos":len(dados.segmentos)}
    async with conn.transaction():
        # Alocar ids sem substituir nem apagar a malha existente.
        await conn.execute("LOCK TABLE trechos_osm,trechos_osm_vertices_pgr,malha_importacoes IN EXCLUSIVE MODE")
        anterior = await conn.fetchval("SELECT id FROM malha_importacoes WHERE tenant_id=$1 AND sha256=$2",tenant_id,digest)
        if anterior:
            return {"status":"JA_IMPORTADO","id":anterior}
        if dados.substituir_importacao is not None:
            anterior = await conn.fetchval("SELECT id FROM malha_importacoes WHERE id=$1 AND tenant_id=$2 AND ativo FOR UPDATE",
                                          dados.substituir_importacao,tenant_id)
            if anterior is None:
                raise HTTPException(404,"Importacao anterior nao encontrada na empresa.")
            await conn.execute("UPDATE malha_importacoes SET ativo=false WHERE id=$1",anterior)
        id_import = await conn.fetchval("INSERT INTO malha_importacoes(tenant_id,sha256,fonte) VALUES($1,$2,$3) RETURNING id",tenant_id,digest,dados.fonte)
        base_vert = await conn.fetchval("SELECT COALESCE(MAX(id),0) FROM trechos_osm_vertices_pgr")
        base_edge = await conn.fetchval("SELECT COALESCE(MAX(id_trecho),0) FROM trechos_osm")
        mapa = {no:base_vert+i+1 for i,no in enumerate(vertices)}
        await conn.executemany("""INSERT INTO trechos_osm_vertices_pgr(id,the_geom)
            VALUES($1,ST_Transform(ST_SetSRID(ST_Point($2,$3),4326),31983))""",
            [(mapa[no],*coord) for no,coord in vertices.items()])
        await conn.executemany("""INSERT INTO trechos_osm(id_trecho,name,highway,length,geom,source,target,sentido,tenant_malha,importacao_malha_id,limites_malha,fonte_malha)
            SELECT $1,$2,$3,ST_Length(g::geography),ST_Transform(g,31983),$5,$6,$7,$8,$9,$10::jsonb,$11
            FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON($4),4326) AS g) x""",
            [(base_edge+i+1,s.nome,s.highway,json.dumps({"type":"LineString","coordinates":s.coordenadas}),
              mapa[s.origem],mapa[s.destino],s.sentido,tenant_id,id_import,
              json.dumps({k:getattr(s,k) for k in ("altura_max_m","largura_max_m","comprimento_max_m","peso_max_t") if getattr(s,k) is not None}),
              s.referencia or dados.fonte) for i,s in enumerate(dados.segmentos)])
    RoutingEngine.clear_cache(tenant_id)
    return {"status":"IMPORTADO","id":id_import,"vertices":len(vertices),"trechos":len(dados.segmentos)}


@router.get("/trechos", dependencies=[Depends(require_role(["ADMIN"]))])
async def trechos(west: float=Query(ge=-180,le=180), south: float=Query(ge=-90,le=90),
                  east: float=Query(ge=-180,le=180), north: float=Query(ge=-90,le=90),
                  depois_id: int=Query(0,ge=0), limite: int=Query(500,ge=1,le=1000),
                  tenant_id=Depends(resolver_tenant_autenticado),conn=Depends(get_connection)):
    if not west < east or not south < north or east-west > 2 or north-south > 2:
        raise HTTPException(422,"Area deve ser crescente e ter no maximo 2 graus em cada eixo.")
    rows = await conn.fetch("""SELECT id_trecho,name,sentido,ST_AsGeoJSON(ST_Transform(geom,4326)) AS geometry
        FROM trechos_osm WHERE (tenant_malha IS NULL OR tenant_malha=$1) AND id_trecho>$2
        AND (importacao_malha_id IS NULL OR EXISTS(SELECT 1 FROM malha_importacoes m WHERE m.id=importacao_malha_id AND m.ativo))
        AND ST_Intersects(geom,ST_Transform(ST_MakeEnvelope($3,$4,$5,$6,4326),31983))
        ORDER BY id_trecho LIMIT $7""",tenant_id,depois_id,west,south,east,north,limite+1)
    pagina = rows[:limite]
    return {"type":"FeatureCollection","features":[{"type":"Feature","geometry":json.loads(r["geometry"]),
        "properties":{"id_trecho":r["id_trecho"],"nome":r["name"],"sentido":r["sentido"]}} for r in pagina],
        "proximo_depois_id":pagina[-1]["id_trecho"] if len(rows)>limite else None}


@router.get("/importacoes")
async def importacoes(tenant_id=Depends(resolver_tenant_autenticado),conn=Depends(get_connection)):
    return [dict(r) for r in await conn.fetch("SELECT id,fonte,ativo,criado_em FROM malha_importacoes WHERE tenant_id=$1 ORDER BY id DESC LIMIT 100",tenant_id)]


@router.get("/trechos-proximos")
async def trechos_proximos(longitude: float=Query(ge=-180,le=180),latitude: float=Query(ge=-90,le=90),
                          somente_regional: bool=True,tenant_id=Depends(resolver_tenant_autenticado),conn=Depends(get_connection)):
    rows=await conn.fetch("""SELECT t.id_trecho,t.name,t.fonte_malha,
        ST_Distance(ST_Transform(t.geom,4326)::geography,ST_SetSRID(ST_Point($2,$3),4326)::geography) AS distancia_m
        FROM trechos_osm t WHERE (t.tenant_malha=$1 OR (NOT $4 AND t.tenant_malha IS NULL))
        AND (t.importacao_malha_id IS NULL OR EXISTS(SELECT 1 FROM malha_importacoes m WHERE m.id=t.importacao_malha_id AND m.ativo))
        AND ST_DWithin(ST_Transform(t.geom,4326)::geography,ST_SetSRID(ST_Point($2,$3),4326)::geography,50)
        ORDER BY distancia_m,t.id_trecho LIMIT 5""",tenant_id,longitude,latitude,somente_regional)
    return {"candidatos":[dict(r) for r in rows],"aviso":"Associacao por proximidade exige conferencia em vias paralelas."}


@router.delete("/importacoes/{id_importacao}")
async def desativar_importacao(id_importacao: int,tenant_id=Depends(resolver_tenant_autenticado),conn=Depends(get_connection)):
    res = await conn.fetchval("UPDATE malha_importacoes SET ativo=false WHERE id=$1 AND tenant_id=$2 AND ativo RETURNING id",id_importacao,tenant_id)
    if res is None:
        raise HTTPException(404,"Importacao nao encontrada.")
    RoutingEngine.clear_cache(tenant_id)
    return {"status":"DESATIVADO","id":res}
