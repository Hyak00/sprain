from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from app.url_segura import post_seguro
from app.services.open_meteo_endpoint import fonte_disponivel, url_previsao

if __package__:
    from .worker_chuva_status import write_chuva_status, STATUS_FILE_CHUVA
else:
    from worker_chuva_status import write_chuva_status, STATUS_FILE_CHUVA

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

INTERVALO_SEGUNDOS = int(os.getenv("CHUVA_INTERVALO_SEGUNDOS", "600"))
WEBHOOK_ALERTA = os.getenv("WEBHOOK_ALERTA_DADOS", "")
TETO_MM = 1000.0
STATUS_FILE_CHUVA = Path("/tmp/sprain_chuva_worker_status.json")


def _banco_url():
    from sqlalchemy.engine import URL
    raw = os.getenv("URL_BANCO")
    if raw:
        return raw
    return URL.create(
        "postgresql+psycopg2",
        username=os.getenv("DB_USER", "enchentes"),
        password=os.getenv("DB_PASSWORD", "enchentes"),
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "enchentes"),
    )


def _disparar_alerta(fonte: str, erro: str) -> None:
    if not WEBHOOK_ALERTA:
        return
    payload = {
        "evento": "FALHA_COLETA_CHUVA",
        "fonte": fonte,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "erro": erro[-1000:],
    }
    try:
        status = post_seguro(
            WEBHOOK_ALERTA,
            {"Content-Type": "application/json"},
            json.dumps(payload).encode("utf-8"),
            timeout=10,
        )
        if not 200 <= status < 300:
            raise RuntimeError(f"webhook respondeu HTTP {status}")
    except Exception as e:
        logger.warning("Falha ao enviar alerta: %s", e)


def _valor_valido(bruto) -> Optional[float]:
    if bruto is None or isinstance(bruto, bool):
        return None
    try:
        v = float(bruto)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(v) or v < 0 or v > TETO_MM:
        return None
    return v


def coletar_open_meteo(id_estacao: str, lat: float, lon: float) -> Optional[float]:
    try:
        url = url_previsao({
            "latitude": lat, "longitude": lon,
            "current": "precipitation", "timezone": "America/Sao_Paulo",
        })
        req = urllib.request.Request(url, headers={"User-Agent": "SPRain-chuva/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        atual = dados.get("current")
        if not isinstance(atual, dict):
            raise ValueError("resposta sem bloco current")
        return _valor_valido(atual.get("precipitation"))
    except Exception as e:
        logger.warning("Open-Meteo %s (%s,%s): %s", id_estacao, lat, lon, type(e).__name__)
        return None


def gravar_leitura(conn, id_estacao: str, precipitacao_mm: float) -> None:
    from sqlalchemy import text
    agora = datetime.now(timezone.utc)
    validade = datetime.fromtimestamp(agora.timestamp() + 3600, tz=timezone.utc)
    conn.execute(
        text(
            "INSERT INTO leituras_meteorologicas "
            "(id_estacao, data_referencia, coletado_em, validade_ate, precipitacao_mm) "
            "VALUES (:est, :ref, :col, :val, :mm) "
            "ON CONFLICT (id_estacao, data_referencia) DO NOTHING"
        ),
        {
            "est": id_estacao,
            "ref": agora,
            "col": agora,
            "val": validade,
            "mm": precipitacao_mm,
        },
    )


def executar_rodada() -> bool:
    from sqlalchemy import create_engine, text

    motor = create_engine(_banco_url())
    sucesso_geral = True
    try:
        with motor.begin() as conn:
            estacoes = conn.execute(
                text(
                    "SELECT e.id_estacao, f.id_fonte, "
                    "ST_Y(e.geom) AS lat, ST_X(e.geom) AS lon "
                    "FROM estacoes_meteorologicas e "
                    "JOIN fontes_meteorologicas f ON e.id_fonte = f.id_fonte "
                    "WHERE e.ativa = true AND f.id_fonte = 'OPEN_METEO'"
                )
            ).fetchall()

            for row in estacoes:
                id_estacao = row[0]
                lat, lon = float(row[2]), float(row[3])
                valor = coletar_open_meteo(id_estacao, lat, lon)
                if valor is None:
                    logger.warning("Sem dado para %s", id_estacao)
                    sucesso_geral = False
                    _disparar_alerta(id_estacao, "Open-Meteo sem dado valido")
                    continue
                gravar_leitura(conn, id_estacao, valor)
                logger.info("Gravado %s: %.1f mm", id_estacao, valor)
    except Exception as e:
        logger.exception("Erro na rodada de coleta: %s", e)
        _disparar_alerta("worker_chuva", str(e))
        sucesso_geral = False
    finally:
        motor.dispose()

    return sucesso_geral


def main():
    if not 60 <= INTERVALO_SEGUNDOS <= 1800:
        sys.exit("CHUVA_INTERVALO_SEGUNDOS deve estar entre 60 e 1800")
    if not fonte_disponivel():
        sys.exit("Coletor de chuva em produção exige OPEN_METEO_API_KEY comercial")

    logger.info("Worker de coleta de chuva iniciado. Intervalo: %ds", INTERVALO_SEGUNDOS)
    last_result = None

    while True:
        write_chuva_status("running", INTERVALO_SEGUNDOS, last_result=last_result)
        sucesso = executar_rodada()
        last_result = "ok" if sucesso else "failed"
        write_chuva_status("sleeping", INTERVALO_SEGUNDOS, last_result=last_result)
        logger.info("Rodada concluida. Proximo em %ds", INTERVALO_SEGUNDOS)
        time.sleep(INTERVALO_SEGUNDOS)


if __name__ == "__main__":
    main()
