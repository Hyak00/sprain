import re
import urllib.request
import os
from sqlalchemy import create_engine, text

URL_BANCO = os.getenv("URL_BANCO", "postgresql+psycopg2://enchentes:enchentes@localhost:5432/enchentes")
URL_ESTACAO_ITAQUERA = "https://www.cgesp.org/v3/estacao.jsp?POSTO=1000864"

def coletar_chuva_cge() -> dict:
    req = urllib.request.Request(
        URL_ESTACAO_ITAQUERA,
        headers={"User-Agent": "sprain-telemetria/1.0 (pesquisa e monitoramento)"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    texto_limpo = re.sub(r'<[^>]+>', ' ', html)
    texto_limpo = re.sub(r'\s+', ' ', texto_limpo)

    m_atual = re.search(r'Per[íi\.]*\s*Atual[:\s]+([\d\.,]+)\s*mm', texto_limpo, re.I)
    m_anterior = re.search(r'Per[íi\.]*\s*Anterior[:\s]+([\d\.,]+)\s*mm', texto_limpo, re.I)

    if not m_atual or not m_anterior:
        raise ValueError(
            "Resposta do CGE incompleta: coleta invalidada para evitar "
            "confundir falha de leitura com ausencia de chuva."
        )

    chuva_atual = float(m_atual.group(1).replace(",", "."))
    chuva_anterior = float(m_anterior.group(1).replace(",", "."))
    if chuva_atual < 0 or chuva_anterior < 0:
        raise ValueError("O CGE retornou precipitacao negativa.")

    return {
        "posto": "1000864",
        "nome": "Itaquera - CGE SP",
        "chuva_periodo_atual_mm": chuva_atual,
        "chuva_periodo_anterior_mm": chuva_anterior,
        "chuva_acumulada_recente_mm": round(chuva_atual + chuva_anterior, 1)
    }

def atualizar_risco_por_chuva(dados_chuva: dict):
    raise RuntimeError(
        "Escrita CGE desativada: falta delimitar geograficamente "
        "os trechos compativeis com a estacao de Itaquera."
    )

def main():
    print("1. Conectando à estação meteorológica do CGE em Itaquera...")
    dados = coletar_chuva_cge()
    print(f"   -> Posto: {dados['nome']}")
    print(f"   -> Chuva Período Atual: {dados['chuva_periodo_atual_mm']} mm")
    print(f"   -> Chuva Período Anterior: {dados['chuva_periodo_anterior_mm']} mm")
    print(f"   -> Acumulado Recente: {dados['chuva_acumulada_recente_mm']} mm")

    print("\n2. Processando impacto na malha viária...")
    res = atualizar_risco_por_chuva(dados)
    if res["limiar_ivi_ativado"]:
        print(f"   -> Limiar IVI ativado: >= {res['limiar_ivi_ativado']}")
        print(f"   -> Trechos viários sensibilizados: {res['trechos_em_alerta_ou_bloqueio']}")
    else:
        print(f"   -> {res['status']}")

if __name__ == "__main__":
    main()
