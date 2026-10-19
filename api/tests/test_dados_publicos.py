import sys
import json
import hashlib
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.sincronizar_dados_publicos import (
    caminhoes_envolvidos,
    ler_anp,
    ler_anp_cadastro,
    ler_artesp,
    ler_coordenadas_postos,
    ler_roubo_agregado,
    ler_ssp_trimestral,
)

class FontesPublicasTest(unittest.TestCase):
    def test_artesp_le_layout_atual_e_filtra_caminhao(self):
        cabecalho = ("DATA,HORA,CONCESSIONARIA,RODOVIA,KM,SENTIDO,LATITUDE,LONGITUDE,CLASSE,SUBCLASSE,"
                     "CAUSA_PROVAVEL,VEICULOS_ENVOLVIDOS,VISIBILIDADE,CONDICAO_METERIOLOGICA,MUNICIPIO\n")
        linhas = [
            "2026-08-27,06:55:52,L30,SP304,280.0,LESTE,-22.5,-48.5,COLISAO,COLISAO-TRANSVERSAL,NAO INFORMADO,CAMINHAO=1|AUTOMOVEL=1,BOA,CHUVA,MINEIROS\n",
            "2026-08-27,07:10:00,L30,SP304,281.0,LESTE,-22.5,-48.5,COLISAO,COLISAO-TRASEIRA,NAO INFORMADO,AUTOMOVEL=2,BOA,BOA,MINEIROS\n",
            "2026-08-27,08:00:00,L30,SP304,282.0,LESTE,,,CHOQUE,CHOQUE-POSTE,NAO INFORMADO,CARRETA=1,BOA,BOA,MINEIROS\n",
            "2026-08-28,09:00:00,L29,SPA074/255,10.0,NORTE,-22.5,-48.5,TOMBAMENTO,TOMBAMENTO,NAO INFORMADO,CAMINHONETE=1|CARRETA=1,BOA,BOA,ARARAQUARA\n",
        ]
        csv = cabecalho + "".join(linhas)
        registros, resumo = ler_artesp(csv.encode(), "https://dadosabertos.artesp.sp.gov.br/teste.csv")
        self.assertEqual(resumo["linhas"], 4)
        self.assertEqual(resumo["sem_caminhao"], 1)
        self.assertEqual(resumo["sem_coordenadas"], 1)
        self.assertEqual(resumo["data_registro_mais_recente"], "2026-08-28")
        self.assertEqual(len(registros), 2)
        self.assertEqual(registros[0]["rodovia"], "SP-304")
        self.assertEqual(registros[0]["km"], 280.0)
        self.assertEqual(registros[0]["latitude"], -22.5)
        self.assertEqual(registros[0]["condicao"], "CHUVA")
        self.assertEqual(registros[1]["rodovia"], "SPA074/255")
        self.assertEqual(registros[1]["caminhoes"], 1)

    def test_artesp_rejeita_layout_sem_coordenadas(self):
        layout_antigo = ("DATA,HORA,N OC MITs,CONCESSIONARIA,RODOVIA,LOCAL (KM),SENTIDO,REG ADM,MUNICIPIO,CAUSA,CLASSE DO ACIDENTE,SUBCLASSE\n"
                         "2026-08-27 00:00:00,1899-12-30 06:55:52,6947,L30,SP304,280.0,LESTE,BAURU,MINEIROS,NEBLINA,COLISAO,COLISAO TRANSVERSAL\n")
        with self.assertRaises(ValueError):
            ler_artesp(layout_antigo.encode(), "https://dadosabertos.artesp.sp.gov.br/teste.csv")

    def test_artesp_padroniza_caixa_e_prefixos_numericos(self):
        cabecalho = ("DATA,HORA,CONCESSIONARIA,RODOVIA,KM,SENTIDO,LATITUDE,LONGITUDE,CLASSE,SUBCLASSE,"
                     "CAUSA_PROVAVEL,VEICULOS_ENVOLVIDOS,VISIBILIDADE,CONDICAO_METERIOLOGICA,MUNICIPIO\n")
        linha = "2026-02-03,10:00:00,L30,SP310,217.0,Norte,-22.5,-47.9,Tombamento,Tombamento,NAO INFORMADO,Caminhao=1,1 Bom,2 Chuva,Itirapina\n"
        registros, _ = ler_artesp((cabecalho + linha).encode(), "https://dadosabertos.artesp.sp.gov.br/teste.csv")
        self.assertEqual(registros[0]["classe"], "TOMBAMENTO")
        self.assertEqual(registros[0]["sentido"], "NORTE")
        self.assertEqual(registros[0]["municipio"], "ITIRAPINA")
        self.assertEqual(registros[0]["condicao"], "CHUVA")
        self.assertEqual(registros[0]["visibilidade"], "BOA")

    def test_anp_mantem_produto_preco_e_data_por_posto(self):
        csv = ("Estado - Sigla;Municipio;Revenda;CNPJ da Revenda;Nome da Rua;Numero Rua;"
               "Produto;Data da Coleta;Valor de Venda;Bairro;Cep\n"
               "SP;CAMPINAS;POSTO EXEMPLO;01.234.567/0001-89;RUA A;10;DIESEL S10;"
               "01/09/2026;6,29;CENTRO;13000000\n"
               "RJ;NITEROI;OUTRO POSTO;11.234.567/0001-89;RUA B;11;DIESEL;"
               "01/09/2026;6,99;CENTRO;24000000\n")
        registros, resumo = ler_anp(csv.encode(), "https://www.gov.br/anp/teste.csv")
        self.assertEqual(resumo["precos_validos"], 1)
        self.assertEqual(resumo["data_registro_mais_recente"], "2026-09-01")
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
        self.assertEqual(resumo["data_registro_mais_recente"], "2025-12-31")
        self.assertNotIn("latitude", registros[0])
        with self.assertRaises(ValueError):
            ler_roubo_agregado(csv.replace(",25", ",-1").encode(), "https://www.ssp.sp.gov.br/estatistica/spcarga")

    def test_ssp_preserva_total_e_regioes_sem_sobreposicao(self):
        colunas = ["ITEM", "Natureza", "Capital", "Gde SP(1)", "Interior",
                   *["Deinter " + str(n) for n in range(1, 11)], "Estado"]
        valores = ["", "Roubo de Carga", "4", "3", "2", "2", *(["0"] * 9), "9"]
        def linha(celulas):
            return "<tr>" + "".join("<td>" + str(valor) + "</td>" for valor in celulas) + "</tr>"
        html = (linha(colunas) + linha(valores)).encode()
        url = "https://www.ssp.sp.gov.br/assets/estatistica/trimestral/arquivos/2025-04.htm"
        registros, resumo = ler_ssp_trimestral(html, url)
        self.assertEqual(resumo["total_estado"], 9)
        self.assertEqual(resumo["data_registro_mais_recente"], "2025-12-31")
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

    def test_coordenadas_rejeitam_cnpj_duplicado(self):
        cabecalho = "cnpj,latitude,longitude,fonte,verificado_em\n"
        linha = "01234567000189,-22.9,-47.1,https://www.openstreetmap.org/node/1,2025-01-01T10:00:00+00:00\n"
        with self.assertRaisesRegex(ValueError, "CNPJ duplicado"):
            ler_coordenadas_postos((cabecalho + linha + linha).encode())

    def test_coordenadas_rejeitam_pontos_fora_da_area_de_sp(self):
        csv = ("cnpj,latitude,longitude,fonte,verificado_em\n"
               "01234567000189,-10.0,-47.1,https://www.openstreetmap.org/node/1,2025-01-01T10:00:00+00:00\n")
        with self.assertRaisesRegex(ValueError, "Coordenada de posto invalida"):
            ler_coordenadas_postos(csv.encode())


    def test_aplicar_rejeita_cnpj_ausente_sem_gravar(self):
        registro = {
            "cnpj": "01234567000189",
            "latitude": -22.9,
            "longitude": -47.1,
            "fonte": "https://www.openstreetmap.org/node/1",
            "verificado_em": __import__("datetime").datetime.fromisoformat(
                "2025-01-01T10:00:00+00:00"
            ),
        }

        conn = MagicMock()
        cursor = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchall.return_value = []

        with patch(
            "scripts.sincronizar_dados_publicos.conectar",
            return_value=conn,
        ):
            with self.assertRaisesRegex(ValueError, "CNPJ.*ausente"):
                from scripts.sincronizar_dados_publicos import aplicar
                aplicar(
                    "COORDENADAS_POSTOS",
                    "https://exemplo.invalid/coordenadas.csv",
                    b"conteudo-de-teste",
                    [registro],
                    {},
                )

        consultas = [
            chamada.args[0]
            for chamada in cursor.execute.call_args_list
        ]
        self.assertTrue(any("SELECT cnpj FROM postos_combustivel" in q
                            for q in consultas))
        self.assertFalse(any("UPDATE postos_combustivel SET" in q
                             for q in consultas))


    def test_aplicar_aceita_coordenada_ignorada_por_verificacao_recente(self):
        from datetime import datetime
        registro = {
            "cnpj": "01234567000189",
            "latitude": -22.9,
            "longitude": -47.1,
            "fonte": "https://www.openstreetmap.org/node/1",
            "verificado_em": datetime.fromisoformat("2025-01-01T10:00:00+00:00"),
        }

        conn = MagicMock()
        cursor = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchall.return_value = [("01234567000189",)]
        cursor.fetchone.return_value = None
        cursor.rowcount = 0

        with patch("scripts.sincronizar_dados_publicos.conectar", return_value=conn):
            from scripts.sincronizar_dados_publicos import aplicar
            resultado = aplicar(
                "COORDENADAS_POSTOS",
                "https://exemplo.invalid/coordenadas.csv",
                b"conteudo-de-teste-2",
                [registro],
                {},
            )

        self.assertFalse(resultado["sem_alteracoes"])
        comandos = [c.args[0] for c in cursor.execute.call_args_list]
        atualizacoes = [q for q in comandos if "UPDATE postos_combustivel SET" in q]
        self.assertEqual(len(atualizacoes), 1)
        self.assertIn("localizacao_verificada_em IS NULL OR localizacao_verificada_em <= %s",
                      atualizacoes[0])

    def test_fonte_inalterada_atualiza_resumo_sem_regravar_precos(self):
        from scripts.sincronizar_dados_publicos import aplicar
        conn, cursor = MagicMock(), MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor
        dados = b"mesma-fonte"
        resumo = {"data_registro_mais_recente": "2026-10-09"}
        cursor.fetchone.return_value = (hashlib.sha256(dados).hexdigest(), 1)
        with patch("scripts.sincronizar_dados_publicos.conectar", return_value=conn):
            resultado = aplicar("ANP_SEMANAL", "https://www.gov.br/anp/teste", dados, [{}], resumo)
        self.assertTrue(resultado["sem_alteracoes"])
        comandos = cursor.execute.call_args_list
        atualizacao = next(c for c in comandos if "SET ultimo_sucesso_em=now()" in c.args[0])
        self.assertEqual(json.loads(atualizacao.args[1][0]), resumo)
        self.assertFalse(any("INSERT INTO precos_combustivel" in c.args[0] for c in comandos))

if __name__ == "__main__":
    unittest.main()
