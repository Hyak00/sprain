"""O resumo do piloto nao deve converter cenarios em economia comprovada."""

import uuid

import asyncpg
import pytest

from app.config import settings
from app.routers.logistica import exportar_auditoria_csv, obter_sumario_executivo


@pytest.mark.asyncio
async def test_sumario_usa_ultima_recomendacao_e_separa_planejado_de_observado():
    conn = await asyncpg.connect(settings.database_url)
    transacao = conn.transaction()
    await transacao.start()
    try:
        identificador = uuid.uuid4().hex[:12]
        tenant = f"piloto_{identificador}"
        operacoes = [f"PIL_{identificador}_{sufixo}" for sufixo in "ABC"]
        for id_operacao in operacoes:
            await conn.execute("""
                INSERT INTO operacoes (id_operacao, origem_lat, origem_lon, destino_lat, destino_lon,
                                      janela_inicio, janela_fim, tenant_id)
                VALUES ($1, -23.5, -46.5, -23.6, -46.6, now(), now() + interval '2 hours', $2)
            """, id_operacao, tenant)

        async def recomendar(id_operacao, acao, risco, impacto, minutos, custo):
            await conn.execute("""
                INSERT INTO recomendacoes_operacao (id_operacao, tipo_acao, nivel_risco, motivo,
                    prejuizo_potencial_evitado, minutos_adicionais, custo_desvio, tenant_id)
                VALUES ($1, $2, $3, 'Cenario de teste', $4, $5, $6, $7)
            """, id_operacao, acao, risco, impacto, minutos, custo, tenant)

        await recomendar(operacoes[0], "MANTER_ROTA_ORIGINAL", "RISCO", 9999, 999, 999)
        await recomendar(operacoes[0], "ALTERAR_ROTA", "CRITICO", 1000, 20, 50)
        await recomendar(operacoes[1], "AGUARDAR_MELHORA", "RISCO", 500, 0, 0)
        await recomendar(operacoes[2], "ALTERAR_ROTA", "NORMAL", 0, 10, 20)
        await conn.execute("""
            INSERT INTO decisoes_gestor_operacao (id_operacao, tenant_id, decisao, motivo_gestor, consulta_id)
            VALUES ($1, $3, 'APROVAR_DESVIO', 'Teste', $4),
                   ($2, $3, 'AGUARDAR_MELHORA', 'Teste', NULL)
        """, operacoes[0], operacoes[1], tenant, uuid.uuid4())

        resposta = await obter_sumario_executivo(tenant_id=tenant, conn=conn)
        kpis = resposta["kpis"]
        assert "sem filtro de datas" in resposta["periodo"]
        assert kpis["total_operacoes"] == 3
        assert kpis["rotas_em_risco_alagamento"] == 2
        assert kpis["rotas_com_alternativa_sugerida"] == 2
        assert kpis["taxa_alternativa_sugerida_em_risco_pct"] == 50
        assert kpis["impacto_potencial_cenario_brl"] == 1500
        assert kpis["tempo_adicional_planejado_min"] == 30
        assert kpis["custo_desvio_planejado_brl"] == 70
        assert kpis["decisoes_registradas"] == 2
        assert kpis["decisoes_por_tipo"]["aprovar_desvio"] == 1
        assert kpis["decisoes_vinculadas_consulta"] == 1
        assert kpis["economia_comprovada_brl"] is None
        assert kpis["custo_observado_brl"] is None
        assert kpis["desvios_realizados"] is None
        assert kpis["status_sla"] == "NAO_MEDIDO"

        exportacao = await exportar_auditoria_csv(tenant_id=tenant, conn=conn)
        texto_csv = "".join([trecho async for trecho in exportacao.body_iterator])
        assert "impacto_potencial_cenario_reais" in texto_csv.splitlines()[0]
        assert "custo_evitado_reais" not in texto_csv

        vazio = (await obter_sumario_executivo(tenant_id=f"outro_{identificador}", conn=conn))["kpis"]
        assert vazio["total_operacoes"] == 0
        assert vazio["taxa_alternativa_sugerida_em_risco_pct"] is None
        assert vazio["impacto_potencial_cenario_brl"] is None
        assert vazio["economia_comprovada_brl"] is None
    finally:
        await transacao.rollback()
        await conn.close()
