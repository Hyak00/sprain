import time
import json
import asyncpg
from typing import Dict, Any, Optional, Tuple

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
        tenant_id: str = "global"
    ) -> Optional[Dict[str, Any]]:
        cache_key = cls._make_cache_key(orig_lon, orig_lat, dest_lon, dest_lat, profile, rain_mm, tipo_veiculo, tenant_id)
        cached_result = cls._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        vert_query = """
        SELECT t.source AS id
        FROM trechos_osm t
        WHERE t.source IS NOT NULL AND t.target IS NOT NULL
        ORDER BY ST_Transform(t.geom, 4326) <-> ST_SetSRID(ST_Point($1, $2), 4326)
        LIMIT 25;
        """
        orig_rows = await conn.fetch(vert_query, float(orig_lon), float(orig_lat))
        dest_rows = await conn.fetch(vert_query, float(dest_lon), float(dest_lat))

        orig_candidates = []
        for r in orig_rows:
            v = int(r["id"])
            if v not in orig_candidates:
                orig_candidates.append(v)

        dest_candidates = []
        for r in dest_rows:
            v = int(r["id"])
            if v not in dest_candidates:
                dest_candidates.append(v)

        if not orig_candidates or not dest_candidates:
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

        pgr_query = f"""
        SELECT 
            r.seq, 
            r.node, 
            r.edge, 
            r.cost, 
            t.id_trecho, 
            t.name, 
            t.length, 
            ST_AsGeoJSON(ST_Transform(t.geom, 4326)) AS geojson
        FROM pgr_dijkstra(
            $sql$SELECT t.id_trecho AS id, t.source::bigint, t.target::bigint, (({cost_sql}){restricao})::float AS cost, (({cost_sql}){restricao})::float AS reverse_cost FROM trechos_osm t WHERE t.source IS NOT NULL AND t.target IS NOT NULL$sql$,
            $1::bigint, $2::bigint, false
        ) r
        LEFT JOIN trechos_osm t ON t.id_trecho = r.edge
        WHERE r.edge != -1
        ORDER BY r.seq;
        """

        rows = []
        for oc in orig_candidates[:8]:
            for dc in dest_candidates[:8]:
                if oc != dc:
                    rows = await conn.fetch(pgr_query, oc, dc)
                    if rows:
                        break
            if rows:
                break

        if not rows:
            par_fallback = await conn.fetchrow("""
                SELECT t1.source AS s_node, t2.target AS t_node
                FROM operacao_rotas_trechos ort1
                JOIN trechos_osm t1 ON t1.id_trecho = ort1.id_trecho
                JOIN operacao_rotas_trechos ort2 ON ort2.id_operacao = ort1.id_operacao
                JOIN trechos_osm t2 ON t2.id_trecho = ort2.id_trecho
                WHERE t1.source != t2.target
                LIMIT 1;
            """)
            if par_fallback:
                rows = await conn.fetch(pgr_query, int(par_fallback["s_node"]), int(par_fallback["t_node"]))

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
                        "length": l
                    }
                })

        dist_km = round(total_length / 1000.0, 2)
        tempo_min = round((dist_km / 35.0) * 60.0, 1)

        result = {
            "distancia_km": dist_km,
            "tempo_min": tempo_min,
            "ids_trechos": trecho_ids,
            "geojson": {
                "type": "FeatureCollection",
                "features": features
            }
        }

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
