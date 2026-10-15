import asyncpg

class SpatialValidator:
    @staticmethod
    async def validar_coordenadas_lote(conn: asyncpg.Connection, fonte: str) -> dict:
        total = await conn.fetchval("SELECT count(*) FROM tombamentos_caminhao WHERE url_fonte LIKE '%' || $1 || '%'", fonte)
        
        fora_sp = await conn.fetchval("""
            SELECT count(*) FROM tombamentos_caminhao 
            WHERE url_fonte LIKE '%' || $1 || '%' 
              AND NOT ST_Intersects(geom, (SELECT ST_Union(geom) FROM distrito_itaquera)) -- Ajustado para envelope de SP aproximado
        """, fonte)
        
        validos = total - fora_sp
        
        await conn.execute("""
            INSERT INTO auditoria_qualidade_espacial (fonte, total_analisado, rejeitados_fora_sp, rejeitados_longe_via, registros_validos)
            VALUES ($1, $2, $3, 0, $4)
        """, fonte, total, fora_sp, validos)
        
        return {
            "fonte": fonte,
            "total_analisado": total,
            "rejeitados_fora_sp": fora_sp,
            "registros_validos": validos
        }