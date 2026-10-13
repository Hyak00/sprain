"""Consulta espacial em PostGIS com fixture revertida ao final."""

import secrets
import unittest
from datetime import date

import asyncpg

from app.config import settings
from app.routers.dados_publicos import ConsultaRota, consultar_rota, limites_bbox, listar_postos
from app.services.dados_publicos import SCHEMA


class DadosPublicosBancoTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.conn = await asyncpg.connect(settings.database_url)
        self.transacao = self.conn.transaction()
        await self.transacao.start()
        await self.conn.execute(SCHEMA.read_text(encoding="utf-8"))

    async def asyncTearDown(self):
        await self.transacao.rollback()
        await self.conn.close()

    async def test_consulta_rota_encontra_somente_pontos_verificados(self):
        identificador = f"fixture-{secrets.token_hex(8)}"
        cnpj = f"{secrets.randbelow(10**14):014d}"
        await self.conn.execute("""INSERT INTO tombamentos_caminhao
            (id_fonte,data_ocorrencia,rodovia,classe,caminhoes_envolvidos,veiculos_envolvidos,geom,url_fonte)
            VALUES ($1,$2,'SP310','TOMBAMENTO',1,'CAMINHAO=1',
            ST_SetSRID(ST_MakePoint(-47.1,-22.9),4326),'https://dadosabertos.artesp.sp.gov.br/')""",
            identificador, date.today())
        await self.conn.execute("""INSERT INTO postos_combustivel
            (cnpj,nome,uf,municipio,endereco,geom,localizacao_fonte,localizacao_verificada_em)
            VALUES ($1,'POSTO TESTE','SP','CAMPINAS','RUA TESTE',
            ST_SetSRID(ST_MakePoint(-47.101,-22.9),4326),
            'https://www.openstreetmap.org/node/1',now())""", cnpj)
        await self.conn.execute("""INSERT INTO precos_combustivel
            (cnpj,produto,data_coleta,preco_litro,url_fonte)
            VALUES ($1,'DIESEL S10',$2,6.25,'https://www.gov.br/anp/')""", cnpj, date.today())
        cnpj_candidato = f"{secrets.randbelow(10**14):014d}"
        await self.conn.execute("""INSERT INTO postos_combustivel
            (cnpj,nome,uf,municipio,endereco,geom,localizacao_fonte,localizacao_validacao)
            VALUES ($1,'POSTO CANDIDATO','SP','CAMPINAS','RUA TESTE',
            ST_SetSRID(ST_MakePoint(-47.102,-22.9),4326),
            'https://revendedoresapi.anp.gov.br/v1/combustivel','NAO_VALIDADA_PELA_ANP')""", cnpj_candidato)
        await self.conn.execute("""INSERT INTO precos_combustivel
            (cnpj,produto,data_coleta,preco_litro,url_fonte)
            VALUES ($1,'DIESEL S10',$2,6.30,'https://www.gov.br/anp/')""",
            cnpj_candidato, date.today())
        resultado = await consultar_rota(ConsultaRota(rota={"type": "LineString",
            "coordinates": [[-47.11, -22.9], [-47.09, -22.9]]}), conn=self.conn)
        self.assertIn(identificador, {r["id_fonte"] for r in resultado["tombamentos"]})
        self.assertIn(cnpj, {r["cnpj"] for r in resultado["postos"]})
        self.assertNotIn(cnpj_candidato, {r["cnpj"] for r in resultado["postos"]})
        mapa = await listar_postos(produto="DIESEL S10", municipio="CAMPINAS",
                                  bbox="-47.2,-23,-47,-22.8", limite=500, conn=self.conn)
        self.assertFalse(next(p["localizacao_confirmada"] for p in mapa["postos"]
                              if p["cnpj"] == cnpj_candidato))
        self.assertIn("agregados", resultado["roubo_carga"])

    def test_bbox_invertida_e_rejeitada(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            limites_bbox("-46,-23,-48,-22")


if __name__ == "__main__":
    unittest.main()
