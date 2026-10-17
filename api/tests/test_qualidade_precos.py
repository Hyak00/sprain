import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.qualidade_precos import analisar_qualidade_precos


class TestQualidadePrecos(unittest.TestCase):
    def criar_registro(self, preco, data=None):
        return {
            "uf": "SP",
            "municipio": "ARARAQUARA",
            "produto": "DIESEL S10",
            "data": data or date(2026, 9, 29),
            "preco": Decimal(str(preco)),
            "url_fonte": "https://exemplo.gov.br/anp.csv",
        }

    def test_precos_normais_nao_geram_alerta_atipico(self):
        registros = [
            self.criar_registro("6.00"),
            self.criar_registro("6.10"),
            self.criar_registro("6.20"),
            self.criar_registro("6.15"),
            self.criar_registro("6.05"),
        ]

        alertas = analisar_qualidade_precos(
            registros, data_referencia=date(2026, 9, 30)
        )

        self.assertFalse(
            any(a["tipo"] == "PRECO_ATIPICO" for a in alertas)
        )

    def test_preco_atipico_gera_alerta_sem_alterar_valor(self):
        registros = [
            self.criar_registro("6.00"),
            self.criar_registro("6.10"),
            self.criar_registro("6.20"),
            self.criar_registro("6.15"),
            self.criar_registro("9.99"),
        ]

        alertas = analisar_qualidade_precos(
            registros, data_referencia=date(2026, 9, 30)
        )

        atipicos = [a for a in alertas if a["tipo"] == "PRECO_ATIPICO"]

        self.assertEqual(len(atipicos), 1)
        self.assertEqual(atipicos[0]["indice"], 4)
        self.assertEqual(atipicos[0]["preco_original"], Decimal("9.99"))
        self.assertEqual(
            atipicos[0]["url_fonte"], "https://exemplo.gov.br/anp.csv"
        )
        self.assertEqual(registros[4]["preco"], Decimal("9.99"))

    def test_amostra_insuficiente_nao_gera_alerta_atipico(self):
        registros = [
            self.criar_registro("6.00"),
            self.criar_registro("6.10"),
            self.criar_registro("6.20"),
            self.criar_registro("9.99"),
        ]

        alertas = analisar_qualidade_precos(
            registros, data_referencia=date(2026, 9, 30)
        )

        self.assertFalse(
            any(a["tipo"] == "PRECO_ATIPICO" for a in alertas)
        )

    def test_dado_antigo_gera_alerta_de_desatualizacao(self):
        registros = [self.criar_registro("6.29", date(2026, 9, 1))]

        alertas = analisar_qualidade_precos(
            registros, data_referencia=date(2026, 9, 30)
        )

        antigos = [
            a for a in alertas if a["tipo"] == "DADO_DESATUALIZADO"
        ]

        self.assertEqual(len(antigos), 1)
        self.assertEqual(antigos[0]["preco_original"], Decimal("6.29"))
        self.assertEqual(registros[0]["preco"], Decimal("6.29"))


if __name__ == "__main__":
    unittest.main()
