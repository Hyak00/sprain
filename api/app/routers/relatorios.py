from app.seguranca import require_role
import csv
import io
from datetime import datetime

import asyncpg
from fastapi import APIRouter, Depends, Response, Query
from fastapi.responses import HTMLResponse

from app.database import get_connection

router = APIRouter(prefix="/api/v1/relatorios", tags=["Relatorios"], dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])

SQL_OCORRENCIAS = r"""
    SELECT e.id_estado,
           t.name AS logradouro,
           e.status,
           e.severidade,
           e.registrado_em
    FROM estado_operacional_trechos e
    JOIN trechos_osm t ON t.id_trecho = e.id_trecho
    WHERE e.status != 'TRANSITAVEL'
    ORDER BY e.registrado_em DESC;
"""


@router.get("/boletim-defesa-civil/json")
async def gerar_boletim_json(conn: asyncpg.Connection = Depends(get_connection)):
    linhas = await conn.fetch(SQL_OCORRENCIAS)

    stats = await conn.fetchrow("""
        SELECT
            (SELECT COUNT(*) FROM estado_operacional_trechos
             WHERE status IN ('INTRANSITAVEL', 'INTRANSITAVEL_LEVES')) AS total_bloqueadas,
            ROUND(AVG(COALESCE(ivi_score, 0))::numeric, 2) AS media_ivi,
            COUNT(*) FILTER (WHERE COALESCE(ivi_score, 0) >= 70) AS total_criticas
        FROM trechos_osm;
    """)

    return {
        "orgao_emissor": "Defesa Civil / SPRAIN Sala de Situacao",
        "jurisdicao": "Distrito de Itaquera - Sao Paulo / SP",
        "data_emissao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sumario_executivo": {
            "vias_interditadas_momento": stats["total_bloqueadas"],
            "vias_risco_critico_ivi": stats["total_criticas"],
            "indice_vulnerabilidade_medio": float(stats["media_ivi"] or 0)
        },
        "detalhamento_vias": [
            {
                "id": r["id_estado"],
                "logradouro": r["logradouro"] or "Sem denominacao",
                "status": r["status"],
                "severidade": r["severidade"],
                "origem": "NAO_INFORMADA",
                "horario": r["registrado_em"].strftime("%H:%M:%S") if r["registrado_em"] else "",
                "observacao": None
            }
            for r in linhas
        ]
    }


@router.get("/boletim-defesa-civil/csv")
async def gerar_boletim_csv(conn: asyncpg.Connection = Depends(get_connection)):
    linhas = await conn.fetch(SQL_OCORRENCIAS)

    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=';')
    escritor.writerow(["LOGRADOURO", "STATUS", "SEVERIDADE", "CORPORACAO_ORIGEM", "HORARIO_REGISTRO", "OBSERVACOES"])

    for r in linhas:
        escritor.writerow([
            r["logradouro"] or "Sem denominacao",
            r["status"],
            r["severidade"],
            "NAO_INFORMADA",
            r["registrado_em"].strftime("%Y-%m-%d %H:%M:%S") if r["registrado_em"] else "",
            ""
        ])

    nome_arquivo = f"boletim_defesa_civil_itaquera_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        content="\ufeff" + saida.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"}
    )
@router.get("/auditoria-intermunicipal", dependencies=[Depends(require_role(["ADMIN", "OPERATOR", "VIEWER"]))])
async def exportar_auditoria_intermunicipal(
    origem: str = "Araraquara",
    destino: str = "Sao Paulo",
    formato: str = "json",
    conn: asyncpg.Connection = Depends(get_connection)
):
    query_dados = """
        SELECT 
            r.id_trecho,
            r.name,
            ROUND((r.length / 1000.0)::numeric, 1) AS distancia_km,
            CASE
                WHEN c.id_trecho IS NULL OR c.atualizado_em IS NULL
                    THEN 'DADOS_INDISPONIVEIS'
                WHEN c.atualizado_em < NOW() - INTERVAL '60 minutes'
                    THEN 'DADOS_DESATUALIZADOS'
                ELSE COALESCE(c.status_pista, 'DADOS_INDISPONIVEIS')
            END AS status_pista,
            c.precipitacao_mm_h,
            c.fator_atraso,
            c.atualizado_em
        FROM corredor_sp_araraquara r
        LEFT JOIN condicoes_corredor c ON c.id_trecho = r.id_trecho
        ORDER BY r.id_trecho;
    """
    rows = await conn.fetch(query_dados)
    
    total_km = sum(float(r["distancia_km"]) for r in rows)
    
    trechos_bloqueados = [
        r for r in rows
        if r["status_pista"] == "RISCO_CRITICO_ALAGAMENTO"
    ]
    houve_alerta = len(trechos_bloqueados) > 0
    indisponiveis = any(
        r["status_pista"] in (
            "DADOS_INDISPONIVEIS", "DADOS_DESATUALIZADOS"
        )
        for r in rows
    )

    if houve_alerta:
        status_operacional = "ALERTA_METEOROLOGICO_ESTIMADO"
    elif indisponiveis or not rows:
        status_operacional = "DADOS_INDISPONIVEIS"
    else:
        status_operacional = "SEM_ALERTA_METEOROLOGICO"
    
    dados_sumario = {
        "rota": f"{origem} -> {destino}",
        "distancia_nominal_km": round(total_km, 1),
        "tempo_nominal_min": None,
        "tempo_estimado_sem_desvio_min": None,
        "tempo_com_desvio_min": None,
        "economia_tempo_min": None,
        "custo_diesel_extra_brl": None,
        "economia_hora_parada_brl": None,
        "beneficio_liquido_brl": None,
        "status_operacional": status_operacional,
        "qualidade_dados": {
            "total_trechos": len(rows),
            "trechos_indisponiveis_ou_desatualizados": sum(
                1 for r in rows
                if r["status_pista"] in (
                    "DADOS_INDISPONIVEIS", "DADOS_DESATUALIZADOS"
                )
            ),
            "limite_antiguidade_minutos": 60,
            "observacao": (
                "Ausencia de alerta nao comprova seguranca da rodovia."
            )
        },
        "motivo_indisponivel": "Tempo e custos dependem de velocidade calibrada por classe de via e consumo real por categoria; valores ficticios foram removidos."
    }
    
    if formato.lower() == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=dados_sumario.keys())
        writer.writeheader()
        writer.writerow(dados_sumario)
        return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=sumario_auditoria_intermunicipal.csv"})
        
    return dados_sumario



@router.get("/backtest-comercial")
async def obter_backtest_comercial(
    formato: str = Query("json", description="Formato de exportacao: json ou csv"),
    conn: asyncpg.Connection = Depends(get_connection)
):
    periodo = await conn.fetchrow("""
        SELECT MIN(data_ocorrencia) AS inicio, MAX(data_ocorrencia) AS fim
        FROM tombamentos_caminhao
        WHERE rodovia IN ('SP-310', 'SP-330', 'SP-348');
    """)

    geral = await conn.fetchrow("""
        SELECT
            count(*) AS total_corredor,
            count(*) FILTER (WHERE condicao_meteorologica IN ('CHUVA', 'GAROA', 'CHUVA COM VENTANIA')) AS chuva_corredor,
            count(*) FILTER (WHERE condicao_meteorologica IN ('CHUVA', 'GAROA', 'CHUVA COM VENTANIA') AND subclasse ILIKE '%tombamento%') AS tombamentos_chuva
        FROM tombamentos_caminhao
        WHERE rodovia IN ('SP-310', 'SP-330', 'SP-348');
    """)

    rodovias_rows = await conn.fetch("""
        SELECT rodovia,
               count(*) AS total,
               count(*) FILTER (WHERE condicao_meteorologica IN ('CHUVA', 'GAROA', 'CHUVA COM VENTANIA')) AS chuva
        FROM tombamentos_caminhao
        WHERE rodovia IN ('SP-310', 'SP-330', 'SP-348')
        GROUP BY rodovia
        ORDER BY rodovia;
    """)

    municipios_rows = await conn.fetch("""
        SELECT municipio, rodovia, count(*) AS acidentes_chuva
        FROM tombamentos_caminhao
        WHERE rodovia IN ('SP-310', 'SP-330', 'SP-348')
          AND condicao_meteorologica IN ('CHUVA', 'GAROA', 'CHUVA COM VENTANIA')
        GROUP BY municipio, rodovia
        ORDER BY acidentes_chuva DESC
        LIMIT 5;
    """)

    total = int(geral["total_corredor"] or 0)
    chuva = int(geral["chuva_corredor"] or 0)
    tombamentos = int(geral["tombamentos_chuva"] or 0)
    pct_chuva = round((chuva / total * 100.0), 2) if total > 0 else None

    distribuicao = [
        {
            "rodovia": r["rodovia"],
            "total_sinistros": int(r["total"]),
            "sinistros_sob_chuva": int(r["chuva"]),
            "percentual_sob_chuva": round((float(r["chuva"]) / float(r["total"]) * 100.0), 2) if r["total"] > 0 else 0.0
        }
        for r in rodovias_rows
    ]

    top_pontos = [
        {
            "municipio": m["municipio"],
            "rodovia": m["rodovia"],
            "acidentes_sob_chuva": int(m["acidentes_chuva"])
        }
        for m in municipios_rows
    ]

    resultado = {
        "titulo": "Dossie Comercial B2B - Resiliencia e Reducao de Sinistros no Corredor Araraquara - Sao Paulo",
        "fonte_dados": "ARTESP / Base Oficial de Acidentes Rodoviarios do Estado de SP",
        "periodo": {
            "inicio": str(periodo["inicio"]) if periodo and periodo["inicio"] else None,
            "fim": str(periodo["fim"]) if periodo and periodo["fim"] else None
        },
        "corredor": "SP-310 (Washington Luis), SP-330 (Anhanguera), SP-348 (Bandeirantes)",
        "estatisticas_gerais": {
            "total_sinistros_caminhao": total,
            "sinistros_sob_chuva_ou_pista_molhada": chuva,
            "tombamentos_caminhao_sob_chuva": tombamentos,
            "percentual_sinistros_sob_chuva": pct_chuva
        },
        "qualidade_dados": {
            "status": "SEM_REGISTROS_NO_BANCO" if total == 0 else "COBERTURA_NAO_VERIFICADA",
            "aviso": "Contagens do banco local para as tres rodovias; nao comprovam cobertura integral da base oficial nem causalidade da chuva."
        },
        "distribuicao_rodovias": distribuicao,
        "principais_pontos_criticos_chuva": top_pontos,
        "proposta_valor_b2b": {
            "reducao_esperada_sinistros_pct": None,
            "argumento_comercial": "A reducao de sinistros ainda nao foi medida. Exige piloto com grupo de comparacao e cobertura historica validada."
        }
    }

    if formato.lower() == "csv":
        saida = io.StringIO()
        escritor = csv.writer(saida, delimiter=';')
        escritor.writerow(["METRICA", "VALOR", "DETALHE"])
        escritor.writerow(["TOTAL_SINISTROS_CAMINHAO", total, "Corredor Araraquara - SP"])
        escritor.writerow(["SINISTROS_SOB_CHUVA", chuva,
                          f"{pct_chuva}% do total" if pct_chuva is not None else "Percentual indisponivel: sem registros"])
        escritor.writerow(["TOMBAMENTOS_SOB_CHUVA", tombamentos, "Tombamentos diretos"])
        for d in distribuicao:
            escritor.writerow([f"RODOVIA_{d['rodovia']}", d["sinistros_sob_chuva"], f"{d['percentual_sob_chuva']}% sob chuva"])
        for p in top_pontos:
            escritor.writerow(["PONTO_CRITICO", p["acidentes_sob_chuva"], f"{p['municipio']} ({p['rodovia']})"])
        nome_arquivo = "dossie_backtest_comercial_b2b.csv"
        return Response(
            content="\ufeff" + saida.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"}
        )
    elif formato.lower() == "html":
        linhas_rodovias = "".join(
            f"<tr><td><strong>{d['rodovia']}</strong></td><td>{d['total_sinistros']}</td><td>{d['sinistros_sob_chuva']}</td><td>{d['percentual_sob_chuva']}%</td></tr>"
            for d in distribuicao
        )
        linhas_municipios = "".join(
            f"<tr><td>{m['municipio']}</td><td>{m['rodovia']}</td><td><strong>{m['acidentes_sob_chuva']}</strong></td></tr>"
            for m in top_pontos
        )
        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>{resultado['titulo']}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 30px; color: rgb(30, 41, 59); background: rgb(248, 250, 252); }}
.container {{ max-width: 900px; margin: 0 auto; background: white; padding: 32px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
.topo {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid rgb(226, 232, 240); padding-bottom: 16px; margin-bottom: 24px; }}
.marca {{ font-size: 24px; font-weight: bold; color: rgb(30, 58, 138); }}
.meta {{ font-size: 13px; color: rgb(100, 116, 139); }}
.grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
.card {{ background: rgb(241, 245, 249); border-radius: 6px; padding: 16px; text-align: center; border-left: 4px solid rgb(37, 99, 235); }}
.card.destaque {{ border-left-color: rgb(220, 38, 38); }}
.numero {{ font-size: 28px; font-weight: bold; color: rgb(15, 23, 42); margin: 6px 0; }}
.rotulo {{ font-size: 12px; color: rgb(71, 85, 105); text-transform: uppercase; }}
h2 {{ font-size: 16px; color: rgb(15, 23, 42); margin-top: 24px; margin-bottom: 12px; border-left: 4px solid rgb(30, 58, 138); padding-left: 8px; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 14px; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid rgb(226, 232, 240); }}
th {{ background: rgb(248, 250, 252); color: rgb(71, 85, 105); font-weight: 600; }}
.argumento {{ background: rgb(238, 242, 255); border: 1px solid rgb(199, 210, 254); border-radius: 6px; padding: 16px; color: rgb(30, 27, 75); font-size: 14px; margin-top: 24px; }}
.btn-print {{ background: rgb(37, 99, 235); color: white; border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; }}
@media print {{
    body {{ background: white; margin: 0; }}
    .container {{ box-shadow: none; padding: 0; }}
    .btn-print {{ display: none; }}
}}
</style>
</head>
<body>
<div class="container">
    <div class="topo">
        <div>
            <div class="marca">SPRain Intelligence</div>
            <div class="meta">{resultado['corredor']} | Fonte: {resultado['fonte_dados']}</div>
        </div>
        <button class="btn-print" onclick="window.print()">Imprimir / Salvar PDF</button>
    </div>

    <div class="grid">
        <div class="card">
            <div class="rotulo">Total Sinistros Caminhao</div>
            <div class="numero">{total}</div>
            <div class="rotulo">Corredor Monitorado</div>
        </div>
        <div class="card destaque">
            <div class="rotulo">Sinistros Sob Chuva</div>
            <div class="numero">{chuva}</div>
            <div class="rotulo">{pct_chuva}% das ocorrencias</div>
        </div>
        <div class="card destaque">
            <div class="rotulo">Tombamentos sob Chuva</div>
            <div class="numero">{tombamentos}</div>
            <div class="rotulo">Sinistros Gravissimos</div>
        </div>
        <div class="card">
            <div class="rotulo">Reducao de Sinistros</div>
            <div class="numero">Ainda nao medida</div>
            <div class="rotulo">Piloto necessario</div>
        </div>
    </div>

    <h2>Distribuicao de Sinistros por Rodovia</h2>
    <table>
        <thead>
            <tr><th>Rodovia</th><th>Total Sinistros</th><th>Sob Chuva / Garoa</th><th>% Sob Chuva</th></tr>
        </thead>
        <tbody>
            {linhas_rodovias}
        </tbody>
    </table>

    <h2>Top 5 Trechos com Maior Incidencia sob Chuva</h2>
    <table>
        <thead>
            <tr><th>Municipio</th><th>Rodovia</th><th>Acidentes Sob Chuva</th></tr>
        </thead>
        <tbody>
            {linhas_municipios}
        </tbody>
    </table>

    <div class="argumento">
        <strong>Recomendacao Operacional B2B:</strong> {resultado['proposta_valor_b2b']['argumento_comercial']}
    </div>
</div>
</body>
</html>"""
        return HTMLResponse(content=html)

    return resultado
