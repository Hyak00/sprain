"""Persistencia complementar da interface; calculos continuam nos servicos existentes."""
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from app.database import get_connection
from app.services.cotas_plano import verificar_cota

SCHEMA = (Path(__file__).resolve().parents[3] / 'db' / 'ci' / '10_fluxo_painel.sql').read_text(encoding='utf-8')


async def garantir_schema():
    async for conn in get_connection():
        await conn.execute(SCHEMA)
        await conn.execute((Path(__file__).resolve().parents[3]/'db/ci/12_metadados_frota.sql').read_text(encoding='utf-8'))
        await conn.execute((Path(__file__).resolve().parents[3]/'db/ci/15_onboarding_cliente.sql').read_text(encoding='utf-8'))


def objeto(v):
    return json.loads(v) if isinstance(v, str) else v


def serializar(row):
    return {k: objeto(v) if k in ('dados', 'snapshot', 'geometria') else
            v.isoformat() if hasattr(v, 'isoformat') else str(v) if k in ('id', 'corredor_id') else v
            for k, v in dict(row).items()}


async def selo(conn, tenant, id_operacao):
    row = await conn.fetchrow('''SELECT o.dimensoes,o.custos_operacionais,o.id_veiculo,o.distancia_planejada_km,
        o.tempo_planejado_min,o.status,v.dimensoes AS medidas_frota,v.custos_operacionais AS custos_frota,
        (SELECT max(id_recomendacao) FROM recomendacoes_operacao r WHERE r.id_operacao=o.id_operacao
            AND r.tenant_id=o.tenant_id) AS recomendacao
        FROM operacoes o LEFT JOIN veiculos v ON v.id_veiculo=o.id_veiculo AND v.tenant_id=o.tenant_id
        WHERE o.id_operacao=$1 AND o.tenant_id=$2''', id_operacao, tenant)
    if row is None:
        from fastapi import HTTPException
        raise HTTPException(404, 'Operacao nao encontrada.')
    return hashlib.sha256(json.dumps(dict(row), sort_keys=True, default=str).encode()).hexdigest()


async def registrar_consulta(conn, tenant, perfil, id_operacao, usuario_id=None):
    from app.routers.logistica import obter_explicacao_decisao
    explicacao = await obter_explicacao_decisao(id_operacao, tenant, conn)
    rec = await conn.fetchrow('''SELECT r.id_recomendacao,
        r.gerado_em AT TIME ZONE current_setting('TimeZone') AS gerado_em,r.confianca,c.tipo,c.precipitacao_mm
        FROM recomendacoes_operacao r LEFT JOIN cenarios_clima c ON c.id_cenario=r.id_cenario AND c.tenant_id=r.tenant_id
        WHERE r.id_operacao=$1 AND r.tenant_id=$2 ORDER BY r.id_recomendacao DESC LIMIT 1''', id_operacao, tenant)
    op = await conn.fetchrow('SELECT custos_operacionais FROM operacoes WHERE id_operacao=$1 AND tenant_id=$2', id_operacao, tenant)
    explicacao['confianca']=float(rec['confianca']) if rec and rec['confianca'] is not None else None
    if not rec:
        explicacao['confianca'] = None
        explicacao['acao_recomendada'] = 'SEM_RECOMENDACAO'
    if not explicacao['validacao_rota']['rota_alternativa_disponivel']:
        for campo in ('distancia_alternativa_km', 'tempo_alternativo_min', 'delta_km', 'delta_tempo_min', 'custo_desvio_brl', 'prejuizo_evitado_brl'):
            explicacao['metricas'][campo] = None
    explicacao['contexto_consulta'] = {
        'id_recomendacao': rec['id_recomendacao'] if rec else None,
        'calculo_gerado_em': rec['gerado_em'].isoformat() if rec and rec['gerado_em'] else None,
        'natureza': rec['tipo'] if rec else 'SEM_CENARIO',
        'precipitacao_mm': float(rec['precipitacao_mm']) if rec and rec['precipitacao_mm'] is not None else None,
        'fonte': ('Cenario registrado no SPRain; simulacao nao e observacao de chuva.'
                  if rec and rec['tipo'] == 'SIMULACAO' else
                  'Cenario registrado no SPRain; consulte a origem meteorologica nos dados da fonte.'
                  if rec else 'Cadastro da operacao e malha atual; nenhuma recomendacao calculada.'),
        'selo_premissas': await selo(conn, tenant, id_operacao),
        'premissas_editaveis': objeto(op['custos_operacionais']) or {},
        'perfil': perfil, 'autoria_individual': usuario_id,
        'aviso_autoria': 'Usuario individual autenticado.' if usuario_id else 'Credencial compartilhada por empresa/papel; identidade individual nao fornecida.'
    }
    identificador = uuid4()
    await verificar_cota(conn, tenant, 'consultas')
    criado = await conn.fetchval('''INSERT INTO painel_consultas(id,tenant_id,id_operacao,perfil,snapshot)
        VALUES($1,$2,$3,$4,$5::jsonb) RETURNING criado_em''', identificador, tenant, id_operacao, perfil,
        json.dumps(explicacao, default=str))
    return {'consulta': {'id': str(identificador), 'registrado_em': criado.isoformat()}, 'explicacao': explicacao}
