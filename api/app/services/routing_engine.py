import time
import json
import asyncpg
from typing import Dict, Any, Optional, Tuple
from types import SimpleNamespace
from app.services.infraestrutura_viaria import SELECT_PONTOS, avaliar_ponto, resumir_rota, LIMITES

class RoutingEngine:
    _cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
    _cache_ttl_seconds: float = 300.0
    _max_cache_size: int = 5000

    @classmethod
    def _make_cache_key(cls, orig_lon: float, orig_lat: float, dest_lon: float, dest_lat: float, profile: str, rain_mm: float, tipo_veiculo: str, tenant_id: str = "global") -> str:
        return f"{tenant_id}:{round(orig_lon, 5)}:{round(orig_lat, 5)}_{round(dest_lon, 5)}:{round(dest_lat, 5)}_{profile}_{round(rain_mm, 1)}_{tipo_veiculo}"

    @classmethod
    def _get_from_cache(cls, key: str) -> Optional[Dict[str, Any]]:
        agora = time.time()
        if key in cls._cache:
            timestamp, data = cls._cache[key]
            if agora - timestamp < cls._cache_ttl_seconds:
                return data
            del cls._cache[key]
        return None

    @classmethod
    def _set_cache(cls, key: str, data: Dict[str, Any]):
        if len(cls._cache) >= cls._max_cache_size:
            antigos = sorted(cls._cache.keys(), key=lambda k: cls._cache[k][0])[:500]
            for k in antigos:
                cls._cache.pop(k, None)
        cls._cache[key] = (time.time(), data)

    @classmethod
    async def compute_route(
        cls,
        conn: asyncpg.Connection,
        orig_lon: float,
        orig_lat: float,
        dest_lon: float,
        dest_lat: float,
        profile: str = "FASTEST",
        rain_mm: float = 0.0,
        tipo_veiculo: str = "VUC",
        tenant_id: str = "global",
        blocked_edge_ids: Optional[list[int]] = None,
        vehicle_dimensions: Optional[dict] = None,
        infra_context: Optional[dict] = None,
    ) -> Optional[Dict[str, Any]]:
        pontos = infra_context['pontos'] if infra_context is not None else await conn.fetch(SELECT_PONTOS, tenant_id)
        if vehicle_dimensions:
            tipo_veiculo = "CARRETA_5_EIXOS" if vehicle_dimensions["eixos"] >= 5 else ("TRUCK_3_EIXOS" if vehicle_dimensions["eixos"]>=3 else "VUC")
        veiculo = SimpleNamespace(**vehicle_dimensions) if vehicle_dimensions else None
        # Sem dimensoes, nenhuma ponte cadastrada e automaticamente considerada transponivel.
        restritos = [p["id_trecho"] for p in pontos if p["tipo"] == "PONTE" and (
            veiculo is None or avaliar_ponto(p, veiculo)["status"] == "BLOQUEADO"
        )]
        limites_malha = infra_context['limites'] if infra_context is not None else await conn.fetch("""SELECT t.id_trecho,t.limites_malha FROM trechos_osm t
            WHERE (t.tenant_malha IS NULL OR t.tenant_malha=$1) AND t.limites_malha IS NOT NULL
            AND t.limites_malha<>'{}'::jsonb AND (t.importacao_malha_id IS NULL OR EXISTS(
                SELECT 1 FROM malha_importacoes m WHERE m.id=t.importacao_malha_id AND m.ativo))""",tenant_id)
        for trecho in limites_malha:
            limites = json.loads(trecho["limites_malha"])
            if not vehicle_dimensions or any(vehicle_dimensions[medida] > limites[limite]
                for medida,limite in LIMITES.items() if limite in limites):
                restritos.append(trecho["id_trecho"])
        blocked_edge_ids = (blocked_edge_ids or []) + restritos
        cache_key = cls._make_cache_key(orig_lon, orig_lat, dest_lon, dest_lat, profile, rain_mm, tipo_veiculo, tenant_id)
        blocked_edge_ids = sorted(set(int(edge) for edge in (blocked_edge_ids or [])))
        cache_key += ":blocked=" + ",".join(str(edge) for edge in blocked_edge_ids)
        cache_key += ":dimensions=" + json.dumps(vehicle_dimensions, sort_keys=True)
        cached_result = cls._get_from_cache(cache_key)
        if cached_result is not None:
            return {**cached_result, "infraestrutura": {**cached_result['infraestrutura'],
                **resumir_rota(pontos, cached_result["ids_trechos"], vehicle_dimensions)}}

        vert_query = """
        SELECT v.id, ST_DWithin(ST_Transform(v.the_geom,4326)::geography,
            ST_SetSRID(ST_Point($1,$2),4326)::geography,150) AS coberto
        FROM trechos_osm_vertices_pgr v
        WHERE EXISTS (SELECT 1 FROM trechos_osm t WHERE (t.source=v.id OR t.target=v.id)
            AND (t.tenant_malha IS NULL OR t.tenant_malha=$3)
            AND (t.importacao_malha_id IS NULL OR EXISTS(SELECT 1 FROM malha_importacoes m
                 WHERE m.id=t.importacao_malha_id AND m.ativo)))
        ORDER BY v.the_geom <-> ST_Transform(ST_SetSRID(ST_Point($1, $2), 4326), 31983)
        LIMIT 1;
        """
        origem = await conn.fetchrow(vert_query, orig_lon, orig_lat, tenant_id)
        destino = await conn.fetchrow(vert_query, dest_lon, dest_lat, tenant_id)
        if not origem or not destino or not origem["coberto"] or not destino["coberto"]:
            return None
        orig_vert, dest_vert = origem["id"], destino["id"]

        if not orig_vert or not dest_vert or orig_vert == dest_vert:
            return None

        fator_chuva = min(1.0, rain_mm / 100.0)

        if profile == "SAFEST":
            cost_sql = f"""
            CASE 
                WHEN (COALESCE(t.ivi_score, 0.0) * (0.6 + 0.6 * {fator_chuva})) >= 80.0 THEN t.length * 80.0
                WHEN (COALESCE(t.ivi_score, 0.0) * (0.6 + 0.6 * {fator_chuva})) >= 60.0 THEN t.length * 15.0
                ELSE t.length * (1.0 + (COALESCE(t.ivi_score, 0.0) / 10.0))
            END
            """
        elif profile == "BALANCED":
            cost_sql = f"""
            t.length * (1.0 + ((COALESCE(t.ivi_score, 0.0) * (0.5 + 0.5 * {fator_chuva})) / 20.0))
            """
        elif profile == "SHORTEST":
            cost_sql = "t.length"
        else:
            cost_sql = """
            t.length / CASE 
                WHEN t.highway IN ('primary', 'trunk') THEN 40.0
                WHEN t.highway IN ('secondary', 'tertiary') THEN 30.0
                ELSE 20.0
            END
            """

        restricao = ""
        if tipo_veiculo in ["TRUCK_3_EIXOS", "CARRETA_5_EIXOS"]:
            restricao = " * CASE WHEN t.highway IN ('residential', 'living_street', 'unclassified', 'track') THEN 25.0 ELSE 1.0 END"

        filtro_bloqueios = ""
        if blocked_edge_ids:
            filtro_bloqueios = " AND t.id_trecho NOT IN (" + ",".join(str(edge) for edge in blocked_edge_ids) + ")"
        empresa_sql = "'" + tenant_id.replace("'", "''") + "'"
        arestas_sql = f"""SELECT t.id_trecho AS id, t.source::bigint, t.target::bigint,
            CASE WHEN t.sentido='INVERSO' THEN -1 ELSE (({cost_sql}){restricao})::float END AS cost,
            CASE WHEN t.sentido='DIRETO' THEN -1 ELSE (({cost_sql}){restricao})::float END AS reverse_cost
            FROM trechos_osm t WHERE t.source IS NOT NULL AND t.target IS NOT NULL
            AND (t.tenant_malha IS NULL OR t.tenant_malha={empresa_sql})
            AND (t.importacao_malha_id IS NULL OR EXISTS(SELECT 1 FROM malha_importacoes m
                WHERE m.id=t.importacao_malha_id AND m.ativo)){filtro_bloqueios}"""

        pgr_query = f"""
        SELECT 
            r.seq, 
            r.node, 
            r.edge, 
            r.cost, 
            t.id_trecho, 
            t.name, 
            t.length, 
            t.ivi_score,
            t.sentido,
            t.limites_malha, t.fonte_malha, t.limites_verificado_em,t.limites_valido_ate,
            ST_AsGeoJSON(ST_Transform(t.geom, 4326)) AS geojson
        FROM pgr_dijkstra(
            $3::text,
            $1::bigint, $2::bigint, true
        ) r
        LEFT JOIN trechos_osm t ON t.id_trecho = r.edge
        WHERE r.edge != -1
        ORDER BY r.seq;
        """

        rows = await conn.fetch(pgr_query, int(orig_vert), int(dest_vert), arestas_sql)
        if not rows:
            return None

        total_length = 0.0
        trecho_ids = []
        features = []

        for row in rows:
            l = float(row["length"] or 0.0)
            total_length += l
            trecho_ids.append(int(row["id_trecho"]))
            if row["geojson"]:
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(row["geojson"]),
                    "properties": {
                        "id_trecho": row["id_trecho"],
                        "name": row["name"],
                        "length": l,
                        "ivi_score":float(row['ivi_score'] or 0),
                        "sentido_cadastrado": row["sentido"],
                        "limites_importados": json.loads(row["limites_malha"]) if row["limites_malha"] else {},
                        "fonte_malha": row["fonte_malha"],
                        "verificado_em":row['limites_verificado_em'],
                        "valido_ate":row['limites_valido_ate'],
                        "status_limite":"CONFERENCIA_NECESSARIA"
                    }
                })

        dist_km = round(total_length / 1000.0, 2)
        tempo_min = round((dist_km / 35.0) * 60.0, 1)

        result = {
            "distancia_km": dist_km,
            "tempo_min": tempo_min,
            "ids_trechos": trecho_ids,
            "trechos_excluidos_por_limites": blocked_edge_ids,
            "infraestrutura": resumir_rota(pontos, trecho_ids, vehicle_dimensions),
            "geojson": {
                "type": "FeatureCollection",
                "features": features
            }
        }
        result['infraestrutura']['limites_mapa']={'type':'FeatureCollection',
            'features':[f for f in features if f['properties']['limites_importados']]}

        cls._set_cache(cache_key, result)
        return result

    @classmethod
    def clear_cache(cls, tenant_id: Optional[str] = None):
        if tenant_id is None:
            cls._cache.clear()
        else:
            chaves = [k for k in cls._cache if k.startswith(f"{tenant_id}:")]
            for k in chaves:
                cls._cache.pop(k, None)

    @classmethod
    def cache_stats(cls, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        if tenant_id is None:
            total = len(cls._cache)
        else:
            total = sum(1 for k in cls._cache if k.startswith(f"{tenant_id}:"))
        return {
            "total_entradas": total,
            "max_capacidade": cls._max_cache_size,
            "ttl_segundos": cls._cache_ttl_seconds
        }
