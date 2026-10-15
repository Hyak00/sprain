"""Premissa explicita de combustivel; nunca soma diesel a um custo total por km."""
from datetime import date

FONTE_CONSUMO = 'https://www.gov.br/transportes/pt-br/assuntos/sustentabilidade/mudanca-do-clima/0_ineavar_2025.pdf'


async def referencia_diesel(conn):
    linha = await conn.fetchrow("""WITH ultima AS (
        SELECT MAX(data_coleta) AS data FROM precos_combustivel
        WHERE produto='DIESEL S10' AND data_coleta<=CURRENT_DATE
    ), amostra AS (
        SELECT DISTINCT ON (p.cnpj) p.preco_litro,p.data_coleta,p.url_fonte
        FROM precos_combustivel p JOIN postos_combustivel r USING(cnpj),ultima u
        WHERE p.produto='DIESEL S10' AND r.uf='SP'
          AND p.data_coleta BETWEEN u.data-6 AND u.data
        ORDER BY p.cnpj,p.data_coleta DESC
    ) SELECT AVG(preco_litro)::float8 AS preco,MAX(data_coleta) AS data,
        COUNT(*)::int AS amostra,MIN(url_fonte) AS fonte FROM amostra""")
    return dict(linha)


def completar_custos(custos, dimensoes, referencia):
    """Media amostral estadual e consumo estatistico; nunca consumo real inferido."""
    custos = dict(custos)
    estimado = custos.get('consumo_estimado', custos.get('consumo_km_l') is None)
    completo = all(custos.get(k) is not None for k in (
        'consumo_km_l', 'preco_combustivel_litro', 'custo_por_km_sem_combustivel'))
    if custos.get('custo_por_km') is not None:
        custos['custo_total_por_km_informado'] = True
        return custos
    if completo and not custos.get('combustivel_estimado'):
        return custos
    dims = dimensoes or {}
    pesado = dims.get('eixos', 3) >= 3 or dims.get('peso_total_t', 40) > 16
    if estimado:
        custos['consumo_km_l'] = 3.45 if pesado else 5.56
    custos.setdefault('custo_por_km_sem_combustivel', 0.0)
    if (custos.get('preco_combustivel_litro') is None or custos.get('combustivel_estimado')) and referencia.get('preco'):
        custos['preco_combustivel_litro'] = referencia['preco']
        custos['combustivel_data_coleta'] = str(referencia['data'])
        custos['combustivel_fonte'] = referencia['fonte']
        custos['combustivel_amostra_postos'] = referencia['amostra']
        custos['combustivel_estimado'] = True
    custos['consumo_estimado'] = estimado
    if estimado:
        custos['consumo_fonte'] = FONTE_CONSUMO
    return custos


async def resolver_custos(conn, custos, dimensoes):
    referencia = await referencia_diesel(conn)
    return completar_custos(custos, dimensoes, referencia)


def custo_quilometrico(premissas):
    campos = ('consumo_km_l', 'preco_combustivel_litro', 'custo_por_km_sem_combustivel')
    coleta = premissas.get('combustivel_data_coleta')
    if isinstance(coleta, str):
        coleta = date.fromisoformat(coleta)
    idade = (date.today() - coleta).days if coleta else None
    completo = all(premissas.get(k) is not None for k in campos)
    vigente = idade is None or 0 <= idade <= 14
    if completo and vigente and not premissas.get('custo_total_por_km_informado'):
        por_km = premissas['preco_combustivel_litro'] / premissas['consumo_km_l']
        return {'custo_por_km_aplicado': premissas['custo_por_km_sem_combustivel'] + por_km,
                'combustivel_por_km': por_km,
                'modo': 'REFERENCIA_AUTOMATICA' if premissas.get('consumo_estimado') else 'CONSUMO_INFORMADO',
                'consumo_km_l': premissas['consumo_km_l'],
                'consumo_estimado': premissas.get('consumo_estimado', False),
                'fonte_consumo': premissas.get('consumo_fonte'),
                'fonte_preco': premissas.get('combustivel_fonte'),
                'preco_litro': premissas['preco_combustivel_litro'],
                'data_coleta': coleta, 'idade_preco_dias': idade,
                'aviso': 'Preco e consumo sao premissas de planejamento. Nao garante abastecimento, acesso ao posto ou preco na chegada.'}
    manual = premissas.get('custo_total_por_km_informado')
    aviso = ('Custo por km informado; combustivel nao foi somado novamente.' if manual else
             'Sem referencia recente suficiente de combustivel: usada a premissa geral de custo por km.'
             if not completo else 'Preco coletado ha mais de 14 dias ou futuro: usada premissa geral de custo por km; atualize a referencia.')
    return {'custo_por_km_aplicado': premissas.get('custo_por_km', 4.5),
            'combustivel_por_km': None, 'modo': 'CUSTO_TOTAL_POR_KM',
            'data_coleta': coleta, 'idade_preco_dias': idade,
            'aviso': aviso}
