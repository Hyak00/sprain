import json
import sys

import asyncpg
import httpx

from app.config import settings

BASE = "http://127.0.0.1:8000/api/v1/logistica"
VIEWER = {"X-API-Key": "key_viewer_demo"}
OPERADOR = {"X-API-Key": "key_operator_demo"}
EXPRESS = {"X-API-Key": "key_admin_express"}


def titulo(texto):
    print()
    print("=" * 60)
    print(texto)
    print("=" * 60)


def curto(obj, limite=700):
    texto = json.dumps(obj, ensure_ascii=True)
    return texto if len(texto) <= limite else texto[:limite] + "..."


async def buscar_coordenadas():
    import asyncio
    conn = await asyncpg.connect(settings.database_url)
    try:
        linhas = await conn.fetch(
            "SELECT * FROM operacoes WHERE tenant_id = 'demo_corp' ORDER BY id_operacao LIMIT 5"
        )
    finally:
        await conn.close()
    campos = ["origem_lat", "origem_lon", "destino_lat", "destino_lon"]
    if not linhas or any(c not in linhas[0].keys() for c in campos):
        colunas = list(linhas[0].keys()) if linhas else []
        print("nao achei as colunas de coordenada. colunas da tabela:", colunas)
        sys.exit(1)
    return [{c: float(l[c]) for c in campos} for l in linhas]


def decidir(cliente, coords, chuva):
    corpo = dict(coords)
    corpo["precipitacao_mm"] = chuva
    return cliente.post(BASE + "/decisao-economica", json=corpo, headers=VIEWER)


def principal():
    import asyncio
    lista = asyncio.run(buscar_coordenadas())

    with httpx.Client(timeout=60) as c:
        titulo("1. Sem chave de acesso a API recusa")
        r = c.get(BASE + "/veiculos")
        print("status:", r.status_code)

        titulo("2. Sumario executivo (perfil somente leitura)")
        r = c.get(BASE + "/relatorios/sumario-executivo", headers=VIEWER)
        print("status:", r.status_code)
        print(curto(r.json().get("kpis", r.json())))

        titulo("3. Painel da central de frota")
        r = c.get(BASE + "/central-frota", headers=VIEWER)
        print("status:", r.status_code)
        print(curto(r.json(), 500))

        titulo("4. Decisao economica: rota direta x rota segura")
        escolhida = None
        for coords in lista:
            r = decidir(c, coords, 100.0)
            if r.status_code == 200:
                escolhida = coords
                break
        if escolhida is None:
            print("nenhuma das operacoes testadas gerou rota")
        else:
            for chuva in (0.0, 100.0):
                r = decidir(c, escolhida, chuva)
                print("chuva", chuva, "mm -> status", r.status_code)
                print(curto(r.json().get("decisao", r.json())))
                print()

        titulo("5. Simulacao de impacto com 75 mm (grava no banco)")
        r = c.post(BASE + "/simular-impacto", json={"precipitacao_mm": 75.0}, headers=OPERADOR)
        print("status:", r.status_code)
        print(curto(r.json(), 900))

        titulo("6. Isolamento entre clientes")
        demo = c.get(BASE + "/veiculos", headers=VIEWER).json()
        express = c.get(BASE + "/veiculos", headers=EXPRESS).json()
        print("veiculos vistos por demo_corp:", len(demo))
        print("veiculos vistos por log_express:", len(express))


principal()