import json
import urllib.request
from datetime import datetime, timezone

BASE_URL = "http://127.0.0.1:8000/api/v1"
HEADERS = {"X-API-Key": "key_admin_demo", "Content-Type": "application/json"}

def get_json(path):
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

def post_json(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    readiness = get_json("/health/readiness")
    corredor = get_json("/rotas/intermunicipal?origem=Araraquara&destino=Sao%20Paulo&tipo_veiculo=TRUCK_3_EIXOS")
    simulacao = post_json("/logistica/simular-impacto", {
        "precipitacao_mm": 75.0,
        "parametros_custo": {
            "custo_por_km": 4.50,
            "custo_hora_motorista": 35.00,
            "custo_operacional_veiculo_hora": 50.00,
            "custo_atraso_hora": 120.00,
            "prejuizo_potencial_alagamento": 2800.00
        }
    })
    sumario = get_json("/logistica/relatorios/sumario-executivo")

    relatorio = {
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "escopo_piloto": "Corredor SP-310 / SP-348 (Araraquara -> Sao Paulo) e Polo Urbano Zona Leste",
        "infraestrutura": readiness,
        "premissas_financeiras_explicitas": {
            "custo_km_brl": 4.50,
            "custo_hora_total_brl": 85.00,
            "custo_pedagio_corredor_brl": corredor["pedagios"]["custo_total_pedagio_reais"],
            "aviso_transparencia": "Valores baseados em parametros operacionais configuraveis. Nao representam garantia de economia sem validacao em campo."
        },
        "analise_corredor_rodoviario": corredor["resumo"],
        "simulacao_urbana_75mm": simulacao["resumo_operacional"],
        "kpis_atuais_tenant": sumario["kpis"]
    }

    with open("relatorio_piloto_b2b.json", "w", encoding="utf-8") as f:
        json.dump(relatorio, f, indent=2, ensure_ascii=False)

    print(json.dumps(relatorio, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
