import pytest
from app.services.routing_engine import RoutingEngine

def calcular_tempo_trechos(rows, rain_mm=0.0):
    velocidades_base_kmh = {
        "motorway": 90.0,
        "motorway_link": 50.0,
        "trunk": 80.0,
        "trunk_link": 45.0,
        "primary": 60.0,
        "primary_link": 40.0,
        "secondary": 50.0,
        "secondary_link": 35.0,
        "tertiary": 40.0,
        "tertiary_link": 30.0,
        "residential": 30.0,
        "living_street": 20.0,
        "unclassified": 30.0
    }
    fatores_declividade = {
        1.0: 1.00,
        2.0: 0.90,
        3.0: 0.75,
        4.0: 0.60
    }
    tempo_total_min = 0.0
    total_length = 0.0
    for row in rows:
        l = float(row["length"] or 0.0)
        total_length += l
        extensao_km = l / 1000.0
        tipo_via = str(row["highway"] or "residential").lower()
        v_base = velocidades_base_kmh.get(tipo_via, 30.0)
        dec = float(row["classe_declividade"]) if row.get("classe_declividade") is not None else 1.0
        f_dec = fatores_declividade.get(dec, 1.00)
        if rain_mm > 0.0:
            f_chuva = max(0.70, 1.0 - (min(rain_mm, 100.0) / 100.0) * 0.25)
        else:
            f_chuva = 1.0
        v_real = max(10.0, v_base * f_dec * f_chuva)
        tempo_total_min += (extensao_km / v_real) * 60.0
    return round(total_length / 1000.0, 2), round(tempo_total_min, 1)

def test_velocidade_diferenciada_por_tipo_de_via():
    trecho_motorway = [{"length": 90000.0, "highway": "motorway", "classe_declividade": 1.0}]
    trecho_residencial = [{"length": 30000.0, "highway": "residential", "classe_declividade": 1.0}]
    km_m, tempo_m = calcular_tempo_trechos(trecho_motorway, rain_mm=0.0)
    km_r, tempo_r = calcular_tempo_trechos(trecho_residencial, rain_mm=0.0)
    assert km_m == 90.0
    assert tempo_m == 60.0
    assert km_r == 30.0
    assert tempo_r == 60.0

def test_impacto_declividade_em_caminhao():
    trecho_plano = [{"length": 60000.0, "highway": "primary", "classe_declividade": 1.0}]
    trecho_ingreme = [{"length": 60000.0, "highway": "primary", "classe_declividade": 4.0}]
    _, tempo_plano = calcular_tempo_trechos(trecho_plano, rain_mm=0.0)
    _, tempo_ingreme = calcular_tempo_trechos(trecho_ingreme, rain_mm=0.0)
    assert tempo_plano == 60.0
    assert tempo_ingreme == 100.0

def test_impacto_chuva_na_velocidade():
    trecho_seco = [{"length": 80000.0, "highway": "trunk", "classe_declividade": 1.0}]
    trecho_chuva = [{"length": 80000.0, "highway": "trunk", "classe_declividade": 1.0}]
    _, tempo_seco = calcular_tempo_trechos(trecho_seco, rain_mm=0.0)
    _, tempo_chuva = calcular_tempo_trechos(trecho_chuva, rain_mm=100.0)
    assert tempo_seco == 60.0
    assert tempo_chuva == 80.0