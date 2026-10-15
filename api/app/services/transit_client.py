import time
import urllib.request
import json
from typing import Dict, Any, Optional

class TransitClient:
    _cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
    _cache_ttl: float = 300.0
    _total_consultas: int = 0

    @classmethod
    def consultar_transito(cls, origem_lat: float, origem_lon: float, destino_lat: float, dest_lon: float) -> Dict[str, Any]:
        chave = f"{round(origem_lat, 4)},{round(origem_lon, 4)}:{round(destino_lat, 4)},{round(dest_lon, 4)}"
        agora = time.time()
        
        if chave in cls._cache:
            ts, dados = cls._cache[chave]
            if agora - ts < cls._cache_ttl:
                return {**dados, "origem_cache": True}
            del cls._cache[chave]

        cls._total_consultas += 1
        
        url = f"https://router.project-osrm.org/route/v1/driving/{origem_lon},{origem_lat};{dest_lon},{destino_lat}?overview=false"
        req = urllib.request.Request(url, headers={"User-Agent": "SPRain-TransitClient/1.0"})
        
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                resultado = json.loads(resp.read().decode("utf-8"))
                if resultado.get("code") == "Ok" and resultado.get("routes"):
                    rota = resultado["routes"][0]
                    payload = {
                        "status": "DISPONIVEL",
                        "distancia_metros": float(rota.get("distance", 0.0)),
                        "tempo_observado_min": round(float(rota.get("duration", 0.0)) / 60.0, 1),
                        "custo_consulta_usd": 0.001,
                        "origem_cache": False
                    }
                    cls._cache[chave] = (agora, payload)
                    return payload
        except Exception:
            pass

        return {
            "status": "INDISPONIVEL",
            "motivo": "Provedor de transito externo indisponivel. Limitacao explicita aplicada.",
            "tempo_observado_min": None,
            "custo_consulta_usd": 0.0
        }

    @classmethod
    def metricas(cls) -> Dict[str, Any]:
        return {
            "total_consultas_realizadas": cls._total_consultas,
            "entradas_no_cache": len(cls._cache)
        }