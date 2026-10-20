import os
import json
import math
import sys
import urllib.request
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from app.services.limiares_chuva import impacto_corredor as calcular_impacto

URL_BANCO = os.getenv("URL_BANCO") or URL.create(
    "postgresql+psycopg2",
    username=os.getenv("DB_USER", "enchentes"),
    password=os.getenv("DB_PASSWORD", "enchentes"),
    host=os.getenv("DB_HOST", "db"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME", "enchentes"),
)

COORDENADAS_SEGMENTOS = {
    1: {"nome": "Araraquara/Sao Carlos", "lat": -21.90, "lon": -48.03},
    2: {"nome": "Sao Carlos/Rio Claro", "lat": -22.21, "lon": -47.72},
    3: {"nome": "Rio Claro/Limeira", "lat": -22.48, "lon": -47.48},
    4: {"nome": "Limeira/Campinas", "lat": -22.73, "lon": -47.23},
    5: {"nome": "Campinas/Jundiai", "lat": -23.04, "lon": -46.97},
    6: {"nome": "Jundiai/Sao Paulo", "lat": -23.35, "lon": -46.80}
}


def _validar_precipitacao(bruto):
    if bruto is None or isinstance(bruto, bool):
        return None
    try:
        valor = float(bruto)
        if math.isfinite(valor) and 0.0 <= valor <= 1000.0:
            return valor
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def _consultar_open_meteo_primario(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        "&current=precipitation,rain&timezone=America%2FSao_Paulo"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "SPRain/2.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        if resp.status == 200:
            resposta = json.loads(resp.read().decode("utf-8"))
            atual = resposta.get("current")
            if isinstance(atual, dict):
                return _validar_precipitacao(atual.get("precipitation"))
    return None


def _consultar_open_meteo_gfs(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        "&hourly=precipitation&forecast_days=1&models=gfs_seamless"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "SPRain/2.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        if resp.status == 200:
            resposta = json.loads(resp.read().decode("utf-8"))
            hourly = resposta.get("hourly")
            if isinstance(hourly, dict):
                vals = hourly.get("precipitation")
                if isinstance(vals, list) and vals:
                    return _validar_precipitacao(vals[0])
    return None


def _consultar_wttr_in(lat, lon):
    url = f"https://wttr.in/{lat},{lon}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": "SPRain/2.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        if resp.status == 200:
            resposta = json.loads(resp.read().decode("utf-8"))
            cond = resposta.get("current_condition")
            if isinstance(cond, list) and cond:
                return _validar_precipitacao(cond[0].get("precipMM"))
    return None


def consultar_precipitacao_resiliente(lat, lon):
    try:
        v = _consultar_open_meteo_primario(lat, lon)
        if v is not None:
            return v, "OPEN_METEO_PRIMARIO"
    except Exception as e:
        print(f"Aviso de falha na fonte primaria ({lat}, {lon}): {e}")

    try:
        v = _consultar_open_meteo_gfs(lat, lon)
        if v is not None:
            return v, "OPEN_METEO_GFS_REDUNDANCIA"
    except Exception as e:
        print(f"Aviso de falha na fonte redundante GFS ({lat}, {lon}): {e}")

    try:
        v = _consultar_wttr_in(lat, lon)
        if v is not None:
            return v, "WTTR_IN_REDUNDANCIA"
    except Exception as e:
        print(f"Aviso de falha na fonte redundante WTTR ({lat}, {lon}): {e}")

    return None, "INDISPONIVEL"


def consultar_precipitacao(lat, lon):
    valor, _ = consultar_precipitacao_resiliente(lat, lon)
    return valor


def _executar():
    motor = create_engine(URL_BANCO)
    sucessos = 0
    falhas = 0
    print("Iniciando coleta meteorologica do corredor com redundancia.")

    try:
        with motor.begin() as conn:
            for id_trecho, dados in COORDENADAS_SEGMENTOS.items():
                chuva, fonte = consultar_precipitacao_resiliente(
                    dados["lat"], dados["lon"]
                )

                if chuva is None:
                    falhas += 1
                    print(
                        f"SEM ATUALIZACAO: trecho {id_trecho} "
                        f"({dados['nome']}); registro anterior preservado."
                    )
                    continue

                status, fator = calcular_impacto(chuva)
                stmt = text("""
                    INSERT INTO condicoes_corredor
                        (id_trecho, status_pista, precipitacao_mm_h,
                         fator_atraso, fonte_coleta, atualizado_em)
                    VALUES (:id, :status, :chuva, :fator, :fonte, NOW())
                    ON CONFLICT (id_trecho) DO UPDATE
                    SET status_pista = EXCLUDED.status_pista,
                        precipitacao_mm_h = EXCLUDED.precipitacao_mm_h,
                        fator_atraso = EXCLUDED.fator_atraso,
                        fonte_coleta = EXCLUDED.fonte_coleta,
                        atualizado_em = NOW();
                """)
                conn.execute(stmt, {
                    "id": id_trecho,
                    "status": status,
                    "chuva": chuva,
                    "fator": fator,
                    "fonte": fonte
                })
                sucessos += 1
                print(
                    f"Trecho {id_trecho} ({dados['nome']}): "
                    f"valor={chuva:.1f} mm; "
                    f"fonte={fonte}; status={status}."
                )
    finally:
        motor.dispose()

    print(
        f"Coleta concluida: {sucessos} atualizados; "
        f"{falhas} indisponiveis. Falha de coleta nao significa "
        "pista liberada."
    )

    return {"registros": sucessos, "falhas": falhas}


def main():
    try:
        from scripts.auditoria_importacoes import executar_auditado
    except ModuleNotFoundError:
        from auditoria_importacoes import executar_auditado
    motor_auditoria = create_engine(URL_BANCO)
    try:
        return executar_auditado(_executar, motor_auditoria.raw_connection, "OPEN_METEO_CORREDOR")
    finally:
        motor_auditoria.dispose()


if __name__ == "__main__":
    main()
