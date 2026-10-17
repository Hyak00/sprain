"""Consultas de dados historicos; nenhuma estimativa e apresentada como dado ao vivo."""

import math
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.database import get_connection
from app.seguranca import require_role


router = APIRouter(
    prefix="/api/v1/dados-publicos",
    tags=["Dados publicos de risco e combustiveis"],
    dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))],
)


def limites_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if bbox is None:
        return None
    try:
        valores = tuple(float(parte.strip()) for parte in bbox.split(","))
    except ValueError as exc:
        raise HTTPException(422, "bbox deve ser min_lon,min_lat,max_lon,max_lat") from exc
    if (len(valores) != 4 or not all(math.isfinite(valor) for valor in valores)
            or not (-180 <= valores[0] < valores[2] <= 180)
            or not (-90 <= valores[1] < valores[3] <= 90)):
        raise HTTPException(422, "bbox fora dos limites geograficos ou invertida")
    return valores


@router.get("/fontes")
async def listar_fontes(conn=Depends(get_connection)):
    linhas = await conn.fetch("""SELECT nome,url,hash_sha256,registros_importados,ultimo_sucesso_em
        FROM fontes_dados_externos ORDER BY nome""")
    return {"fontes": [dict(linha) for linha in linhas],
            "aviso": "Ausencia de fonte ou importacao antiga nao equivale a ausencia de risco."}


@router.get("/tombamentos")
async def listar_tombamentos(
    bbox: str | None = None,
    desde: date | None = None,
    limite: int = Query(200, ge=1, le=500),
    conn=Depends(get_connection),
):
    limites = limites_bbox(bbox)
    desde = desde or date.today() - timedelta(days=3 * 365)
    sql = """SELECT id_fonte,data_ocorrencia,rodovia,km,sentido,municipio,classe,subclasse,
        caminhoes_envolvidos,veiculos_envolvidos,url_fonte,
        ST_X(geom) AS longitude,ST_Y(geom) AS latitude
        FROM tombamentos_caminhao WHERE ativo AND (UPPER(classe) LIKE '%TOMB%' OR UPPER(subclasse) LIKE '%TOMB%') AND data_ocorrencia >= $1
        AND ($2::boolean = false OR ST_Intersects(geom,ST_MakeEnvelope($3,$4,$5,$6,4326)))
        ORDER BY data_ocorrencia DESC,id_fonte LIMIT $7"""
    west, south, east, north = limites or (-180.0, -90.0, 180.0, 90.0)
    linhas = await conn.fetch(sql, desde, limites is not None, west, south, east, north, limite + 1)
    features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                 "properties": {k: r[k] for k in ("id_fonte", "data_ocorrencia", "rodovia", "km", "sentido",
                                                   "municipio", "classe", "subclasse", "caminhoes_envolvidos",
                                                   "veiculos_envolvidos", "url_fonte")}} for r in linhas[:limite]]
    return {"type": "FeatureCollection", "features": features, "truncado": len(linhas) > limite,
            "desde": desde, "interpretacao": "Tombamentos com caminh\u00e3o, carreta ou bitrem envolvido; o registro n\u00e3o identifica necessariamente qual ve\u00edculo tombou."}


@router.get("/tombamentos/por-rodovia")
async def resumir_tombamentos(
    desde: date | None = None,
    limite: int = Query(100, ge=1, le=500),
    conn=Depends(get_connection),
):
    desde = desde or date.today() - timedelta(days=3 * 365)
    linhas = await conn.fetch("""SELECT rodovia,COUNT(*)::integer AS ocorrencias,
        MIN(data_ocorrencia) AS primeira_ocorrencia,MAX(data_ocorrencia) AS ultima_ocorrencia
        FROM tombamentos_caminhao WHERE ativo AND (UPPER(classe) LIKE '%TOMB%' OR UPPER(subclasse) LIKE '%TOMB%') AND data_ocorrencia >= $1
        GROUP BY rodovia ORDER BY ocorrencias DESC,rodovia LIMIT $2""", desde, limite)
    return {"desde": desde, "rodovias": [dict(linha) for linha in linhas],
            "interpretacao": "Contagem historica observada; sem volume de trafego nao representa probabilidade de tombamento."}


@router.get("/postos")
async def listar_postos(
    produto: str = Query("DIESEL S10", min_length=2, max_length=50),
    municipio: str | None = Query(None, min_length=2, max_length=100),
    bbox: str | None = None,
    limite: int = Query(200, ge=1, le=500),
    conn=Depends(get_connection),
):
    limites = limites_bbox(bbox)
    west, south, east, north = limites or (-180.0, -90.0, 180.0, 90.0)
    linhas = await conn.fetch("""SELECT p.cnpj,p.nome,p.uf,p.municipio,p.endereco,p.bairro,p.cep,
        p.localizacao_fonte,p.localizacao_verificada_em,p.localizacao_obtida_em,
        p.localizacao_acuracia_m,p.localizacao_validacao,
        ST_X(p.geom) AS longitude,ST_Y(p.geom) AS latitude,
        preco.produto,preco.data_coleta,preco.preco_litro,preco.url_fonte
        FROM postos_combustivel p
        LEFT JOIN LATERAL (SELECT produto,data_coleta,preco_litro,url_fonte FROM precos_combustivel
          WHERE cnpj=p.cnpj AND produto=$1 ORDER BY data_coleta DESC LIMIT 1) preco ON true
        WHERE ($2::text IS NULL OR p.municipio ILIKE $2)
          AND ($3::boolean = false OR (p.geom IS NOT NULL AND
            ST_Intersects(p.geom,ST_MakeEnvelope($4,$5,$6,$7,4326))))
        ORDER BY preco.data_coleta DESC NULLS LAST,p.cnpj LIMIT $8""",
        produto.strip().upper(), municipio.strip() if municipio else None,
        limites is not None, west, south, east, north, limite + 1)
    postos = []
    for linha in linhas[:limite]:
        posto = dict(linha)
        posto["preco_litro"] = float(posto["preco_litro"]) if posto["preco_litro"] is not None else None
        posto["localizacao_confirmada"] = posto["localizacao_verificada_em"] is not None
        postos.append(posto)
    return {"postos": postos, "truncado": len(linhas) > limite,
            "interpretacao": "Preco pesquisado na data_coleta, quando disponivel. Coordenadas ANP nao validadas sao candidatas aproximadas; confirme antes de usar para navegacao."}


@router.get("/qualidade-precos")
async def consultar_qualidade_precos(conn=Depends(get_connection)):
    from app.services.qualidade_precos import analisar_qualidade_precos

    linhas = await conn.fetch("""
        SELECT p.uf, p.municipio, c.produto,
               c.data_coleta AS data, c.preco_litro AS preco, c.url_fonte
        FROM precos_combustivel c
        JOIN postos_combustivel p USING (cnpj)
        WHERE c.data_coleta <= CURRENT_DATE
        ORDER BY c.data_coleta DESC
    """)

    registros = [dict(linha) for linha in linhas]
    alertas = analisar_qualidade_precos(registros)

    contagens = {
        "PRECO_ATIPICO": 0,
        "DADO_DESATUALIZADO": 0,
    }
    amostras = {
        "PRECO_ATIPICO": [],
        "DADO_DESATUALIZADO": [],
    }

    for alerta in alertas:
        tipo = alerta["tipo"]
        if tipo not in contagens:
            continue

        contagens[tipo] += 1

        if len(amostras[tipo]) >= 10:
            continue

        registro = registros[alerta["indice"]]
        amostras[tipo].append({
            "tipo": tipo,
            "motivo": alerta["motivo"],
            "preco_original": str(alerta["preco_original"]),
            "data_coleta": registro["data"],
            "produto": registro["produto"],
            "municipio": registro["municipio"],
            "uf": registro["uf"],
            "url_fonte": alerta["url_fonte"],
        })

    return {
        "total_registros_analisados": len(registros),
        "alertas": {
            "preco_atipico": contagens["PRECO_ATIPICO"],
            "dado_desatualizado": contagens["DADO_DESATUALIZADO"],
        },
        "amostras": {
            "precos_atipicos": amostras["PRECO_ATIPICO"],
            "dados_desatualizados": amostras["DADO_DESATUALIZADO"],
        },
        "interpretacao": (
            "Alertas indicam itens para revisao. Os valores originais "
            "nao sao alterados nem automaticamente invalidados."
        ),
    }

@router.get("/roubo-carga")
async def listar_roubo_carga(
    nivel: str | None = Query(None, pattern="^(ESTADO|REGIAO|MUNICIPIO)$"),
    area: str | None = Query(None, min_length=2, max_length=120),
    limite: int = Query(200, ge=1, le=500),
    conn=Depends(get_connection),
):
    linhas = await conn.fetch("""SELECT nivel_geografico,area,periodo_inicio,periodo_fim,ocorrencias,url_fonte
        FROM roubo_carga_agregados WHERE ($1::text IS NULL OR nivel_geografico=$1)
        AND ($2::text IS NULL OR area ILIKE $2)
        ORDER BY periodo_fim DESC,area LIMIT $3""", nivel, area, limite + 1)
    return {"agregados": [dict(linha) for linha in linhas[:limite]], "truncado": len(linhas) > limite,
            "interpretacao": "Agregados por area; nao identificam uma rua, posto ou ponto de roubo."}


@router.get("/roubo-carga/por-regiao")
async def ranquear_roubo_carga(periodo_fim: date | None = None, conn=Depends(get_connection)):
    linhas = await conn.fetch("""WITH periodo AS (
        SELECT COALESCE($1::date, MAX(periodo_fim)) AS fim
        FROM roubo_carga_agregados
        WHERE nivel_geografico='REGIAO'
          AND url_fonte LIKE 'https://www.ssp.sp.gov.br/assets/estatistica/trimestral/arquivos/%'
    )
    SELECT r.area,r.periodo_inicio,r.periodo_fim,r.ocorrencias,r.url_fonte
    FROM roubo_carga_agregados r,periodo p
    WHERE r.nivel_geografico='REGIAO' AND r.periodo_fim=p.fim
      AND r.url_fonte LIKE 'https://www.ssp.sp.gov.br/assets/estatistica/trimestral/arquivos/%'
    ORDER BY r.ocorrencias DESC,r.area""", periodo_fim)
    return {"regioes": [dict(linha) for linha in linhas],
            "interpretacao": "Contagens trimestrais de 12 regioes policiais sem sobreposicao; sem volume de cargas transportadas, nao sao taxas de risco e nao localizam o roubo em uma via."}


class ConsultaRota(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    rota: dict[str, Any]
    raio_tombamento_m: int = Field(500, ge=50, le=5000)
    raio_posto_m: int = Field(3000, ge=100, le=10000)
    produto: str = Field("DIESEL S10", min_length=2, max_length=50)
    incluir_postos_nao_verificados: bool = False

    @model_validator(mode="after")
    def validar_rota(self):
        tipo = self.rota.get('type')
        coordenadas = self.rota.get('coordinates')
        if set(self.rota) != {'type', 'coordinates'} or tipo not in ('LineString', 'MultiLineString'):
            raise ValueError('Informe LineString ou MultiLineString GeoJSON.')
        if not isinstance(coordenadas, list):
            raise ValueError('Coordenadas devem ser listas.')
        linhas = [coordenadas] if tipo == 'LineString' else coordenadas
        if not linhas or sum(len(linha) for linha in linhas if isinstance(linha, list)) > 100000:
            raise ValueError('Rota vazia ou com mais de 100000 pontos.')
        for linha in linhas:
            if not isinstance(linha, list) or len(linha) < 2:
                raise ValueError('Cada segmento precisa de ao menos dois pontos.')
            for ponto in linha:
                if (not isinstance(ponto, list) or len(ponto) != 2
                        or not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                   and math.isfinite(v) for v in ponto)
                        or not -180 <= ponto[0] <= 180 or not -90 <= ponto[1] <= 90):
                    raise ValueError('Coordenadas GeoJSON invalidas.')
        return self


@router.post("/consultar-rota")
async def consultar_rota(dados: ConsultaRota, conn=Depends(get_connection)):
    from app.services.contexto_rota import consultar_geometria
    return await consultar_geometria(conn, dados.rota, dados.raio_tombamento_m, dados.raio_posto_m,
                                    dados.produto, dados.incluir_postos_nao_verificados)
