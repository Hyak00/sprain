import math
import unittest

from app.services.validacao_clima import (
    validar_precipitacao_cenario,
    precipitacao_para_csv,
)


class TestValidacaoClimaIsolada(unittest.TestCase):
    def test_chuva_valida_inteira_e_decimal(self):
        self.assertEqual(validar_precipitacao_cenario(0), 0.0)
        self.assertEqual(validar_precipitacao_cenario(85), 85.0)
        self.assertEqual(validar_precipitacao_cenario("12.5"), 12.5)

    def test_chuva_ausente_e_rejeitada(self):
        with self.assertRaisesRegex(ValueError, "indisponivel"):
            validar_precipitacao_cenario(None)

    def test_chuva_negativa_e_rejeitada(self):
        with self.assertRaises(ValueError):
            validar_precipitacao_cenario(-1)

    def test_valores_nao_finitos_sao_rejeitados(self):
        for valor in (math.nan, math.inf, -math.inf):
            with self.subTest(valor=valor):
                with self.assertRaises(ValueError):
                    validar_precipitacao_cenario(valor)

    def test_texto_invalido_e_rejeitado(self):
        with self.assertRaises(ValueError):
            validar_precipitacao_cenario("chuva desconhecida")

    def test_csv_preserva_ausencia_sem_fingir_zero(self):
        self.assertEqual(precipitacao_para_csv(None), "")
        self.assertEqual(precipitacao_para_csv(0.0), 0.0)
        self.assertEqual(precipitacao_para_csv(12.5), 12.5)


if __name__ == "__main__":
    unittest.main()
