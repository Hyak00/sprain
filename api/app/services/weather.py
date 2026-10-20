import json
import math
import re
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

TETO_CHUVA_MM = 1000.0
FOLGA_RELOGIO_MIN = 5


class WeatherService:
    def __init__(self, conn):
        self.conn = conn

    async def obter_clima_trecho(self, id_trecho: int) -> Dict[str, Any]:
        query = """
            WITH trecho AS (
                SELECT ST_Transform(geom, 4326) AS geom FROM trechos_osm WHERE id_trecho = $1
            ),
            estacao_proxima AS (
                SELECT e.id_estacao, e.id_fonte, e.nome, e.distancia_maxima_cobertura_m,
                       f.tipo, f.frequencia_minutos,
                       ST_Distance(e.geom::geography, t.geom::geography) AS distancia_m
                FROM estacoes_meteorologicas e
                JOIN fontes_meteorologicas f ON e.id_fonte = f.id_fonte
                CROSS JOIN trecho t
                WHERE e.ativa = true
                ORDER BY e.geom <-> t.geom LIMIT 1
            ),
            leitura AS (
                SELECT l.precipitacao_mm, l.data_referencia,
                       EXTRACT(EPOCH FROM (now() - l.data_referencia))/60 AS idade_minutos,
                       (l.validade_ate IS NOT NULL AND l.validade_ate < now()) AS expirada
                FROM leituras_meteorologicas l
                JOIN estacao_proxima ep ON l.id_estacao = ep.id_estacao
                ORDER BY l.data_referencia DESC LIMIT 1
            )
            SELECT ep.nome AS estacao, ep.id_fonte AS fonte, ep.tipo, ep.frequencia_minutos,
                   ep.distancia_m, ep.distancia_maxima_cobertura_m AS cobertura_m,
                   l.precipitacao_mm, l.data_referencia, l.idade_minutos, l.expirada
            FROM estacao_proxima ep
            LEFT JOIN leitura l ON true;
        """
        row = await self.conn.fetchrow(query, id_trecho)
        if not row:
            return {"status": "DESCONHECIDO", "motivo_indisponivel": "Sem estacao proxima na regiao.", "precipitacao_mm": None}

        base = {
            "estacao": row["estacao"],
            "fonte": row["fonte"],
            "tipo": row["tipo"],
            "distancia_m": round(row["distancia_m"], 1),
        }

        if row["distancia_m"] > row["cobertura_m"]:
            return {
                **base,
                "status": "FORA_DE_COBERTURA",
                "motivo_indisponivel": f"Estacao a {int(row['distancia_m'])} m, alem da cobertura de {row['cobertura_m']} m.",
                "precipitacao_mm": None,
            }

        if row["precipitacao_mm"] is None:
            return {
                **base,
                "status": "INDISPONIVEL",
                "motivo_indisponivel": "Estacao ativa, mas sem leituras disponiveis.",
                "precipitacao_mm": None,
            }

        try:
            valor = float(row["precipitacao_mm"])
        except (TypeError, ValueError):
            valor = math.nan
        if not math.isfinite(valor) or valor < 0 or valor > TETO_CHUVA_MM:
            return {
                **base,
                "status": "INDISPONIVEL",
                "motivo_indisponivel": "Leitura de precipitacao invalida.",
                "precipitacao_mm": None,
            }

        idade = float(row["idade_minutos"])
        if idade < -FOLGA_RELOGIO_MIN:
            return {
                **base,
                "status": "INDISPONIVEL",
                "motivo_indisponivel": "Data de referencia da leitura esta no futuro.",
                "precipitacao_mm": None,
            }

        tolerancia = row["frequencia_minutos"] * 2
        if row["expirada"]:
            motivo = "Leitura passou da validade informada pela fonte."
        elif idade > tolerancia:
            motivo = f"Dado antigo ({int(idade)} min). Tolerancia de seguranca: {tolerancia} min."
        else:
            motivo = None

        if motivo:
            return {
                **base,
                "status": "DESATUALIZADO",
                "motivo_indisponivel": motivo,
                "idade_minutos": int(idade),
                "precipitacao_mm": None,
                "aviso": "Limitacao explicita: dado atual ausente. Nao havera estimativa insegura.",
            }

        return {
            **base,
            "status": "VALIDO",
            "tipo_dado": "OBSERVADO" if row["tipo"] == "OBSERVACAO" else "ESTIMADO",
            "idade_minutos": max(0, int(idade)),
            "precipitacao_mm": valor,
            "data_referencia": row["data_referencia"].isoformat(),
        }

    async def registrar_avaliacao_risco(self, id_trecho: int, precipitacao_mm: Optional[float], risco: str, fonte: str, idade_min: int, versao: str = "v1.0"):
        await self.conn.execute("""
            INSERT INTO historico_avaliacoes_risco
            (id_trecho, regra_versao, precipitacao_aplicada_mm, risco_estimado, id_fonte, idade_dado_minutos)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, id_trecho, versao, precipitacao_mm, risco, fonte, idade_min)

class WeatherProvider(ABC):
    @abstractmethod
    def get_current_rainfall(self, station_id: str) -> Optional[float]:
        pass

    @abstractmethod
    def get_forecast_rainfall(self, lat: float, lon: float, days: int = 1) -> Optional[float]:
        pass

class CGEWeatherProvider(WeatherProvider):
    URL_BASE = "https://www.cgesp.org/v3/estacao.jsp?POSTO="
    def get_current_rainfall(self, station_id: str = "1000864") -> Optional[float]:
        try:
            url = f"{self.URL_BASE}{station_id}"
            req = urllib.request.Request(url, headers={"User-Agent": "SPRain-B2B/2.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            texto = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))
            m_atual = re.search(r'Per[íi\.]*\s*Atual[:\s]+([\d\.,]+)\s*mm', texto, re.I)
            m_ant = re.search(r'Per[íi\.]*\s*Anterior[:\s]+([\d\.,]+)\s*mm', texto, re.I)
            if not m_atual or not m_ant:
                return None
            v1 = float(m_atual.group(1).replace(",", "."))
            v2 = float(m_ant.group(1).replace(",", "."))
            if (
                not math.isfinite(v1)
                or not math.isfinite(v2)
                or v1 < 0
                or v2 < 0
            ):
                return None
            return round(v1 + v2, 1)
        except (ValueError, TypeError, OverflowError):
            return None
        except Exception:
            return None
    def get_forecast_rainfall(self, lat: float, lon: float, days: int = 1) -> Optional[float]: return None

class SimulatedWeatherProvider(WeatherProvider):
    def __init__(self, fixed_mm: float = 0.0):
        self.fixed_mm = fixed_mm
    def get_current_rainfall(self, station_id: str) -> Optional[float]: return self.fixed_mm
    def get_forecast_rainfall(self, lat: float, lon: float, days: int = 1) -> Optional[float]: return self.fixed_mm

class OpenMeteoProvider(WeatherProvider):
    def get_current_rainfall(self, station_id: str) -> Optional[float]:
        return None

    def get_forecast_rainfall(self, lat: float, lon: float, days: int = 1) -> Optional[float]:
        try:
            lat, lon = float(lat), float(lon)
            if not math.isfinite(lat) or not -90 <= lat <= 90:
                return None
            if not math.isfinite(lon) or not -180 <= lon <= 180:
                return None
            if isinstance(days, bool) or not isinstance(days, int) or not 0 <= days <= 15:
                return None

            url = (
                "https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}"
                "&daily=precipitation_sum&timezone=America%2FSao_Paulo"
                f"&forecast_days={days + 1}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "SPRain-B2B/3.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            daily = data.get("daily")
            values = daily.get("precipitation_sum") if isinstance(daily, dict) else None
            if not isinstance(values, list) or len(values) <= days:
                return None

            value = values[days]
            if value is None or isinstance(value, bool):
                return None
            value = float(value)
            return value if math.isfinite(value) and value >= 0 else None
        except Exception:
            return None
