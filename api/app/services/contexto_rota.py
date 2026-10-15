"""Consulta local sob demanda. Preserva segmentos desconectados sem criar atalhos."""
import json
from datetime import date


async def consultar_geometria(conn, geometria, raio_tombamento_m=500, raio_posto_m=3000,
                            produto='DIESEL S10', incluir_postos_nao_verificados=False):
    geojson = json.dumps(geometria, separators=(",", ":"))
    acidentes = await conn.fetch("""WITH rota AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON($1::text),4326) AS geom)
        SELECT a.id_fonte,a.data_ocorrencia,a.rodovia,a.km,a.municipio,a.caminhoes_envolvidos,
        a.url_fonte,ROUND(ST_Distance(a.geom::geography,rota.geom::geography))::integer AS distancia_rota_m,
        ST_X(a.geom) AS longitude,ST_Y(a.geom) AS latitude
        FROM tombamentos_caminhao a,rota
        WHERE a.ativo AND a.data_ocorrencia >= CURRENT_DATE - INTERVAL '3 years'
        AND ST_DWithin(a.geom::geography,rota.geom::geography,$2)
        ORDER BY distancia_rota_m,a.data_ocorrencia DESC LIMIT 201""", geojson, raio_tombamento_m)
    postos = await conn.fetch("""WITH rota AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON($1::text),4326) AS geom)
        SELECT p.cnpj,p.nome,p.municipio,p.endereco,p.localizacao_fonte,
        ST_X(p.geom) AS longitude,ST_Y(p.geom) AS latitude,
        ROUND(ST_Distance(p.geom::geography,rota.geom::geography))::integer AS distancia_rota_m,
        preco.data_coleta,preco.preco_litro,preco.url_fonte,p.localizacao_verificada_em
        FROM postos_combustivel p CROSS JOIN rota
        JOIN LATERAL (SELECT data_coleta,preco_litro,url_fonte FROM precos_combustivel
            WHERE cnpj=p.cnpj AND produto=$3 ORDER BY data_coleta DESC LIMIT 1) preco ON true
        WHERE p.geom IS NOT NULL AND ($4::boolean OR p.localizacao_verificada_em IS NOT NULL)
          AND ST_DWithin(p.geom::geography,rota.geom::geography,$2)
        ORDER BY distancia_rota_m,p.cnpj LIMIT 201""", geojson, raio_posto_m, produto.upper(), incluir_postos_nao_verificados)
    lista_postos = []
    for linha in postos[:200]:
        item = dict(linha)
        item["preco_litro"] = float(item["preco_litro"])
        lista_postos.append(item)
    for posto in lista_postos:
        posto['localizacao_confirmada'] = posto['localizacao_verificada_em'] is not None
        posto['idade_preco_dias'] = (date.today() - posto['data_coleta']).days
        posto['preco_recente'] = 0 <= posto['idade_preco_dias'] <= 14
        posto['acesso_viario_confirmado'] = False
    return {"tombamentos": [dict(linha) for linha in acidentes[:200]],
            "postos": lista_postos, "truncado": len(acidentes) > 200 or len(postos) > 200,
            "roubo_carga": "Consultar agregados por area; sem pontos confiaveis para cruzamento com a rota.",
            "interpretacao": "Proximidade e historico nao representam risco individual nem disponibilidade/preco atual de combustivel."}
