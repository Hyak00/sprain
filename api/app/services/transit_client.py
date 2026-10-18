import json
import math
import time
import urllib.request
from typing import Any, Dict

from app.config import settings


class TransitClient:
    _cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
    _cache_ttl: float = 300.0
    _total_consultas: int = 0

    @staticmethod
    def _indisponivel(motivo: str) -> Dict[str, Any]:
        return {
            "status": "INDISPONIVEL",
            "motivo": motivo,
            "tempo_estimado_min": None,
            "tempo_observado_min": None,
            "custo_consulta_usd": None,
            "origem_cache": False,
        }

    @classmethod
    def consultar_transito(
        cls, origem_lat: float, origem_lon: float, destino_lat: float, destino_lon: float
    ) -> Dict[str, Any]:
        # O OSRM publico e apenas uma demonstracao. Nem o cache deve ser usado em producao.
        if settings.ambiente_atual == "production":
            return cls._indisponivel(
                "OSRM demo desativado em producao; nao ha provedor de transito observado configurado."
            )

        chave = f"{round(origem_lat, 4)},{round(origem_lon, 4)}:{round(destino_lat, 4)},{round(destino_lon, 4)}"
        agora = time.time()

        if chave in cls._cache:
            ts, dados = cls._cache[chave]
            if agora - ts < cls._cache_ttl:
                return {**dados, "origem_cache": True}
            del cls._cache[chave]

        cls._total_consultas += 1
        url = (
            "https://router.project-osrm.org/route/v1/driving/"
            f"{origem_lon},{origem_lat};{destino_lon},{destino_lat}?overview=false"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "SPRain-TransitClient/1.0"})

        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                resultado = json.loads(resp.read().decode("utf-8"))
            if isinstance(resultado, dict) and resultado.get("code") == "Ok" and resultado.get("routes"):
                rota = resultado["routes"][0]
                distancia = float(rota["distance"])
                duracao = float(rota["duration"])
                if not all(math.isfinite(valor) and valor >= 0 for valor in (distancia, duracao)):
                    raise ValueError("Rota OSRM com distancia ou duracao invalida")
                payload = {
                    "status": "ESTIMATIVA_DISPONIVEL",
                    "fonte": "OSRM_DEMO",
                    "tipo_dado": "ESTIMATIVA_ROTA_SEM_TRANSITO_AO_VIVO",
                    "distancia_metros": distancia,
                    "tempo_estimado_min": round(duracao / 60.0, 1),
                    "tempo_observado_min": None,
                    "custo_consulta_usd": None,
                    "origem_cache": False,
                }
                cls._cache[chave] = (agora, payload)
                return payload
        except (KeyError, TypeError, ValueError, OSError, TimeoutError):
            pass

        return cls._indisponivel(
            "Provedor de estimativa de rota indisponivel. Limitacao explicita aplicada."
        )

    @classmethod
    def metricas(cls) -> Dict[str, Any]:
        return {
            "total_consultas_realizadas": cls._total_consultas,
            "entradas_no_cache": len(cls._cache),
            "escopo": "processo_atual; tentativas ao OSRM demo, nao consultas faturadas",
        }
