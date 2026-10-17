import os
import json
import math
import urllib.request
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

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

def consultar_precipitacao(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        "&current=precipitation,rain&timezone=America%2FSao_Paulo"
    )
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "SPRain/1.2.3"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP inesperado: {resp.status}")
            resposta = json.loads(resp.read().decode("utf-8"))

        atual = resposta.get("current")
        if not isinstance(atual, dict):
            raise ValueError("Resposta sem bloco current.")

        valor = atual.get("precipitation")
        if valor is None:
            raise ValueError("Precipitacao ausente na resposta.")

        valor = float(valor)
        if not math.isfinite(valor) or valor < 0:
            raise ValueError("Valor de precipitacao invalido.")

        return valor
    except Exception as e:
        print(
            f"ERRO DE COLETA ({lat}, {lon}): {e}. "
            "O dado sera marcado como indisponivel."
        )
        return None


def calcular_impacto(precipitacao_mm_h):
    if precipitacao_mm_h >= 50.0:
        return "RISCO_CRITICO_ALAGAMENTO", 2.5
    elif precipitacao_mm_h >= 25.0:
        return "ALERTA_MODERADO", 1.5
    elif precipitacao_mm_h >= 5.0:
        return "PISTA_MOLHADA", 1.15
    return "LIBERADA", 1.0

def _executar():
    motor = create_engine(URL_BANCO)
    sucessos = 0
    falhas = 0
    print("Iniciando coleta meteorologica do corredor.")

    try:
        with motor.begin() as conn:
            for id_trecho, dados in COORDENADAS_SEGMENTOS.items():
                chuva = consultar_precipitacao(
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
                         fator_atraso, atualizado_em)
                    VALUES (:id, :status, :chuva, :fator, NOW())
                    ON CONFLICT (id_trecho) DO UPDATE
                    SET status_pista = EXCLUDED.status_pista,
                        precipitacao_mm_h = EXCLUDED.precipitacao_mm_h,
                        fator_atraso = EXCLUDED.fator_atraso,
                        atualizado_em = NOW();
                """)
                conn.execute(stmt, {
                    "id": id_trecho,
                    "status": status,
                    "chuva": chuva,
                    "fator": fator
                })
                sucessos += 1
                print(
                    f"Trecho {id_trecho} ({dados['nome']}): "
                    f"valor recebido={chuva:.1f}; "
                    f"classificacao heuristica={status}."
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
