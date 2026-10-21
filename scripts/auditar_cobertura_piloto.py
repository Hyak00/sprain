"""Auditoria somente de leitura da cobertura publica de um municipio piloto.

Execute dentro do container API, apontando para o banco de homologacao/piloto.
Os numeros medem registros disponiveis, nao risco individual nem preco atual.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import asyncpg


FUSO_PILOTO = ZoneInfo("America/Sao_Paulo")


async def auditar(municipio: str, uf: str, regiao_roubo: str | None) -> dict:
    referencia = datetime.now(FUSO_PILOTO).date()
    parametros = {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ.get("DB_PORT", "5432")),
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "database": os.environ["DB_NAME"],
    }
    conn = await asyncpg.connect(**parametros)
    try:
        async with conn.transaction(readonly=True):
            fontes = await conn.fetch(
                """SELECT nome,ultimo_sucesso_em,
                   resumo_importacao->>'data_registro_mais_recente' AS ultimo_registro
                   FROM fontes_dados_externos
                   WHERE nome LIKE 'ARTESP_%' OR nome LIKE 'ANP_%'
                     OR nome LIKE 'SSP_ROUBO_%'
                   ORDER BY nome"""
            )
            acidentes = await conn.fetchrow(
                """SELECT count(*)::integer AS com_caminhao,
                   count(*) FILTER (WHERE UPPER(classe) LIKE '%TOMB%'
                     OR UPPER(subclasse) LIKE '%TOMB%')::integer AS tombamentos_com_caminhao,
                   max(data_ocorrencia) AS ultima_ocorrencia
                   FROM tombamentos_caminhao
                   WHERE ativo AND UPPER(municipio)=UPPER($1)""",
                municipio,
            )
            rodovias = await conn.fetch(
                """SELECT rodovia,count(*)::integer AS registros,
                   max(data_ocorrencia) AS ultima_ocorrencia
                   FROM tombamentos_caminhao
                   WHERE ativo AND UPPER(municipio)=UPPER($1)
                     AND (UPPER(classe) LIKE '%TOMB%'
                       OR UPPER(subclasse) LIKE '%TOMB%')
                   GROUP BY rodovia ORDER BY registros DESC,rodovia""",
                municipio,
            )
            postos = await conn.fetchrow(
                """WITH postos_locais AS (
                     SELECT p.cnpj,p.geom IS NOT NULL AS tem_coordenada,
                       p.localizacao_verificada_em IS NOT NULL AS coordenada_verificada,
                       preco.data_coleta
                     FROM postos_combustivel p
                     LEFT JOIN LATERAL (
                       SELECT data_coleta FROM precos_combustivel
                       WHERE cnpj=p.cnpj AND produto='DIESEL S10'
                       ORDER BY data_coleta DESC LIMIT 1
                     ) preco ON true
                     WHERE p.uf=$1 AND UPPER(p.municipio)=UPPER($2)
                   )
                   SELECT count(*)::integer AS cadastrados,
                     count(*) FILTER (WHERE tem_coordenada)::integer AS com_coordenada,
                     count(*) FILTER (WHERE coordenada_verificada)::integer AS coordenada_verificada,
                     count(*) FILTER (WHERE data_coleta IS NOT NULL)::integer AS com_preco_diesel_s10,
                     count(*) FILTER (WHERE data_coleta >= $3::date)::integer AS preco_ate_7_dias,
                     count(*) FILTER (WHERE data_coleta >= $4::date)::integer AS preco_ate_14_dias,
                     max(data_coleta) AS ultima_coleta_diesel_s10
                   FROM postos_locais""",
                uf,
                municipio,
                referencia - timedelta(days=7),
                referencia - timedelta(days=14),
            )
            roubo = None
            if regiao_roubo:
                linha = await conn.fetchrow(
                    """SELECT area,periodo_inicio,periodo_fim,ocorrencias
                       FROM roubo_carga_agregados
                       WHERE nivel_geografico='REGIAO' AND area=$1
                       ORDER BY periodo_fim DESC LIMIT 1""",
                    regiao_roubo,
                )
                roubo = dict(linha) if linha else None
    finally:
        await conn.close()

    nomes_fontes = {linha["nome"] for linha in fontes}
    ausentes = []
    if not any(nome.startswith("ARTESP_") for nome in nomes_fontes):
        ausentes.append("ARTESP")
    if "ANP_CADASTRO" not in nomes_fontes:
        ausentes.append("ANP_CADASTRO")
    if not ({"ANP_DIESEL", "ANP_SEMANAL"} & nomes_fontes):
        ausentes.append("ANP_PRECOS")
    if regiao_roubo and not any(nome.startswith("SSP_ROUBO_") for nome in nomes_fontes):
        ausentes.append("SSP_ROUBO")

    return {
        "gerado_em": datetime.now(FUSO_PILOTO).isoformat(),
        "municipio": municipio,
        "uf": uf,
        "fontes": {
            "carregadas": [dict(linha) for linha in fontes],
            "ausentes": ausentes,
            "limite": "Última importação bem-sucedida não equivale à data do dado mais recente.",
        },
        "acidentes_artesp": {
            **dict(acidentes),
            "tombamentos_por_rodovia": [dict(linha) for linha in rodovias],
            "limite": "Rodovias concedidas; caminhão envolvido não prova que ele tombou. Contagens não são taxas de risco.",
        },
        "postos_anp": {
            **dict(postos),
            "limite": "Coordenadas candidatas e preços pesquisados não comprovam acesso viário ou preço atual.",
        },
        "roubo_carga_ssp": {
            "regiao_consultada": regiao_roubo,
            "trimestre_mais_recente": roubo,
            "limite": "Agregado regional; não localiza roubos em Araraquara nem em uma rodovia.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--municipio", required=True, help="Municipio exato no cadastro")
    parser.add_argument("--uf", default="SP", help="UF dos postos (padrao: SP)")
    parser.add_argument("--regiao-roubo", help="Regiao policial oficial; dado regional separado")
    args = parser.parse_args()
    municipio = args.municipio.strip()
    uf = args.uf.strip().upper()
    if not municipio or uf != "SP":
        parser.error("informe um municipio de SP; estas fontes cobrem somente esse estado")
    resultado = asyncio.run(auditar(municipio, uf, args.regiao_roubo))
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
