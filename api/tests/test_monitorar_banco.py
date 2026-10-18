"""A consulta operacional lê estatísticas reais sem alterar o banco da suíte."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.monitorar_banco import coletar


def test_monitoramento_banco_consulta_estatisticas_reais():
    dados = coletar()
    assert dados["tamanho_banco_bytes"] > 0
    assert 1 <= dados["conexoes_banco"] <= dados["limite_global_conexoes"]
    assert 1 <= dados["conexoes_servidor"] <= dados["limite_global_conexoes"]
    assert 0 <= dados["uso_global_conexoes_pct"] <= 100
    assert "T" in dados["consultado_em"]
    assert set(dados) == {
        "consultado_em", "tamanho_banco_bytes", "conexoes_banco",
        "conexoes_servidor", "limite_global_conexoes", "uso_global_conexoes_pct",
    }
