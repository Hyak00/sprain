import importlib.util
from datetime import time
from pathlib import Path

import pytest

caminho_script = Path(__file__).resolve().parents[2] / "scripts" / "coletar_chuva_cge.py"
especificacao = importlib.util.spec_from_file_location("coletar_chuva_cge", caminho_script)
coleta = importlib.util.module_from_spec(especificacao)
especificacao.loader.exec_module(coleta)

PAGINA_REAL = (
    "Chuva (Por Per&iacute;odo*) Temperatura Umidade Press&atilde;o "
    "Per. Atual: 0.0 mm Per. Anterior: 0.0 mm Zeramento: 10:00:00 "
    "Atual: 14.3 &deg;C M&aacute;xima: 20.3 &deg;C M&iacute;nima: 13.9 &deg;C"
)


def test_pagina_real_do_cge():
    leitura = coleta.extrair_periodos(PAGINA_REAL)
    assert leitura == {
        "periodo_atual_mm": 0.0,
        "periodo_anterior_mm": 0.0,
        "horario_zeramento": time(10, 0),
    }


def test_virgula_decimal_e_rotulo_acentuado():
    leitura = coleta.extrair_periodos(
        "Per&iacute;odo Atual: 12,4 mm Per&iacute;odo Anterior: 3.5 mm"
    )
    assert leitura["periodo_atual_mm"] == 12.4
    assert leitura["periodo_anterior_mm"] == 3.5
    assert leitura["horario_zeramento"] is None


def test_zeramento_invalido_nao_derruba_a_leitura():
    leitura = coleta.extrair_periodos(
        "Per. Atual: 1.0 mm Per. Anterior: 2.0 mm Zeramento: 25:99:00"
    )
    assert leitura["horario_zeramento"] is None


@pytest.mark.parametrize("pagina", [
    "",
    "Atual: 14.3 C Maxima: 20.3 C",
    "Per. Atual: 5.0 mm",
    "Per. Anterior: 5.0 mm",
    "Per. Atual: -1.0 mm Per. Anterior: 0.0 mm",
    "Per. Atual: nan mm Per. Anterior: 0.0 mm",
    "Per. Atual: 1500.0 mm Per. Anterior: 0.0 mm",
    "Per. Atual: . mm Per. Anterior: 0.0 mm",
])
def test_pagina_invalida_nunca_vira_leitura(pagina):
    with pytest.raises(ValueError):
        coleta.extrair_periodos(pagina)