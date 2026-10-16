import math
from typing import List, Dict, Any

class HydroEngine:
    def __init__(self, conn=None):
        self.conn = conn
        self.a = 200.0
        self.b = 1.6

    async def get_bacia_trecho_proportions(self, id_trecho: int) -> List[Dict[str, Any]]:
        query = """
            WITH trecho AS (
                SELECT ST_Transform(geom, 4326) AS geom_4326, geom AS geom_31983, ST_Length(geom) AS length_m 
                FROM trechos_osm WHERE id_trecho = $1
            )
            SELECT b.id_bacia, b.codigo_otto, 
                   round((ST_Length(ST_Intersection(t.geom_31983, ST_Transform(b.geom, 31983))) / NULLIF(t.length_m, 0))::numeric, 4) AS proportion
            FROM bacias_hidrograficas b
            JOIN trecho t ON ST_Intersects(t.geom_4326, b.geom)
            WHERE t.length_m > 0;
        """
        rows = await self.conn.fetch(query, id_trecho)
        return [dict(row) for row in rows]

    def convert_dbz_to_mmh(self, dbz: float) -> float:
        if dbz < 15.0:
            return 0.0
        z_linear = math.pow(10, dbz / 10.0)
        r = math.pow(z_linear / self.a, 1.0 / self.b)
        return round(r, 2)

    def calculate_effective_rainfall(self, proportions: List[Dict[str, Any]], radar_data: Dict[str, float]) -> float:
        total_rain = 0.0
        for prop in proportions:
            codigo = prop.get("codigo_otto")
            peso = float(prop.get("proportion", 0.0))
            dbz = radar_data.get(codigo, 0.0)
            rain_mmh = self.convert_dbz_to_mmh(dbz)
            total_rain += rain_mmh * peso
        return round(total_rain, 2)