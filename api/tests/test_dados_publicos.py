"""Verifica interpretacao de fontes e rejeicao de dados sem procedencia."""

import sys
import json
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.sincronizar_dados_publicos import (  # noqa: E402
    caminhoes_envolvidos,
    ler_anp,
    ler_anp_cadastro,
    ler_artesp,
    ler_coordenadas_postos,
    ler_roubo_agregado,
    ler_ssp_trimestral,
)


class FontesPublicasTest(unittest.TestCase):
    def test_artesp_separa_tombamento_com_caminhao_de_moto(self):
        csv = ("DATA,HORA,RODOVIA,KM,SENTIDO,LATITUDE,LONGITUDE,CLASSE,SUBCLASSE,"
               "VEICULOS_ENVOLVIDOS,MUNICIPIO\n"
               "2025-01-01,10:00:00,SP310,25.5,NORTE,-22.0,-48.0,TOMBAMENTO,TOMBAMENTO,"
               "CAMINHÃO=1;CARRETA=1,ARARAQUARA\n"
               "2025-01-02,10:00:00,SP310,26,NORTE,-22.0,-48.0,TOMBAMENTO,TOMBAMENTO-MOTO,"
               "MOTO=1,ARARAQUARA\n")
        registros, resumo = ler_artesp(csv.encode(), "https://dadosabertos.artesp.sp.gov.br/teste.csv")
        self.assertEqual(resumo["linhas"], 2)
        self.assertEqual(len(registros), 1)
        self.assertEqual(registros[0]["caminhoes"], 2)
        self.assertEqual(caminhoes_envolvidos("CAMINHONETE=1;CAMINHÃO=2"), 2)

    def test_anp_mantem_produto_preco_e_data_por_posto(self):
        csv = ("Estado - Sigla;Municipio;Revenda;CNPJ da Revenda;Nome da Rua;Numero Rua;"
               "Produto;Data da Coleta;Valor de Venda;Bairro;Cep\n"
               "SP;CAMPINAS;POSTO EXEMPLO;01.234.567/0001-89;RUA A;10;DIESEL S10;"
               "01/09/2026;6,29;CENTRO;13000000\n"
               "RJ;NITEROI;OUTRO POSTO;11.234.567/0001-89;RUA B;11;DIESEL;"
               "01/09/2026;6,99;CENTRO;24000000\n")
        registros, resumo = ler_anp(csv.encode(), "https://www.gov.br/anp/teste.csv")
        self.assertEqual(resumo["precos_validos"], 1)
        self.assertEqual(registros[0]["produto"], "DIESEL S10")
        self.assertEqual(str(registros[0]["preco"]), "6.29")
        self.assertEqual(registros[0]["endereco"], "RUA A, 10")

    def test_cadastro_anp_trata_coordenada_como_candidata(self):
        item = {"cnpj": "01.234.567/0001-89", "uf": "SP", "razaoSocial": "POSTO A",
                "municipio": "CAMPINAS", "endereco": "RUA A", "latitude": "-22.9",
                "longitude": "-47.1", "srid": "4674", "estimativaAcuracia": "9",
                "dataObtencao": "01/09/2026", "validacao": "Posicao nao validada"}
        registros, resumo = ler_anp_cadastro(json.dumps({"data": [item]}).encode())
        self.assertEqual(resumo["coordenadas_candidatas_nao_validadas"], 1)
        self.assertEqual(registros[0]["latitude"], -22.9)
        self.assertEqual(str(registros[0]["obtida"]), "2026-09-01")
        item["latitude"] = "-10"
        registros, resumo = ler_anp_cadastro(json.dumps({"data": [item]}).encode())
        self.assertEqual(resumo["coordenadas_rejeitadas"], 1)
        self.assertIsNone(registros[0]["latitude"])

    def test_roubo_agregado_nao_vira_ponto(self):
        csv = ("nivel_geografico,area,periodo_inicio,periodo_fim,ocorrencias\n"
               "REGIAO,CAMPINAS,2025-01-01,2025-12-31,25\n")
        registros, resumo = ler_roubo_agregado(csv.encode(), "https://www.ssp.sp.gov.br/estatistica/spcarga")
        self.assertEqual(resumo["sem_localizacao_pontual"], 1)
        self.assertNotIn("latitude", registros[0])
        with self.assertRaises(ValueError):
            ler_roubo_agregado(csv.replace(",25", ",-1").encode(), "https://www.ssp.sp.gov.br/estatistica/spcarga")

    def test_ssp_preserva_total_e_regioes_sem_sobreposicao(self):
        colunas = ["ITEM", "Natureza", "Capital", "Gde SP(1)", "Interior",
                   *[f"Deinter {n}" for n in range(1, 11)], "Estado"]
        valores = ["", "Roubo de Carga", "4", "3", "2", "2", *(["0"] * 9), "9"]
        def linha(celulas):
            return "<tr>" + "".join(f"<td>{valor}</td>" for valor in celulas) + "</tr>"
        html = (linha(colunas) + linha(valores)).encode()
        url = "https://www.ssp.sp.gov.br/assets/estatistica/trimestral/arquivos/2025-04.htm"
        registros, resumo = ler_ssp_trimestral(html, url)
        self.assertEqual(resumo["total_estado"], 9)
        self.assertEqual(sum(r["ocorrencias"] for r in registros if r["nivel"] == "REGIAO"), 9)
        self.assertEqual(len(registros), 13)
        self.assertEqual(str(registros[0]["inicio"]), "2025-10-01")
        with self.assertRaises(ValueError):
            ler_ssp_trimestral(html.replace(b">9<", b">10<"), url)

    def test_coordenadas_de_posto_exigem_fonte(self):
        csv = ("cnpj,latitude,longitude,fonte,verificado_em\n"
               "01234567000189,-22.9,-47.1,https://www.openstreetmap.org/node/1,2025-01-01T10:00:00+00:00\n")
        registros, _ = ler_coordenadas_postos(csv.encode())
        self.assertEqual(registros[0]["cnpj"], "01234567000189")
        with self.assertRaises(ValueError):
            ler_coordenadas_postos(csv.replace("https://", "http://").encode())


if __name__ == "__main__":
    unittest.main()
