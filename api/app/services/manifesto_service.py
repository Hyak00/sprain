from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import asyncpg
from app.services.manifesto_parser import parse_manifesto_csv, FUSO_SP

logger = logging.getLogger("manifesto_service")

COORDENADAS_CIDADES_SP: Dict[str, Tuple[float, float]] = {
    "araraquara": (-21.7944, -48.1766),
    "sao carlos": (-22.0175, -47.8908),
    "ribeirao preto": (-21.1775, -47.8103),
    "campinas": (-22.9099, -47.0626),
    "rio claro": (-22.4149, -47.5651),
    "limeira": (-22.5647, -47.4017),
    "jundiai": (-23.1857, -46.8978),
    "sao paulo": (-23.5505, -46.6333),
    "sertaozinho": (-21.1375, -47.9892),
    "santos": (-23.9608, -46.3336),
    "franca": (-20.5386, -47.4008),
    "sorocaba": (-23.5015, -47.4581),
    "bauru": (-22.3147, -49.0606),
    "piracicaba": (-22.7338, -47.6476),
    "marilia": (-22.2139, -49.9458),
    "barretos": (-20.5572, -48.5678),
    "taquaritinga": (-21.4061, -48.5053),
    "matao": (-21.6033, -48.3644),
    "jaboticabal": (-21.2553, -48.3242),
    "ibate": (-21.9547, -47.9944)
}

DEFAULT_ORIGEM = (-21.7944, -48.1766)
DEFAULT_DESTINO = (-23.5505, -46.6333)


def _normalizar_chave(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-zA-Z0-9]+", " ", sem_acento.strip().lower()).strip()


def resolver_coordenadas(localidade: str, eh_destino: bool = False) -> Tuple[float, float]:
    chave = _normalizar_chave(localidade)
    if chave in COORDENADAS_CIDADES_SP:
        return COORDENADAS_CIDADES_SP[chave]
    for cid, coords in COORDENADAS_CIDADES_SP.items():
        if cid in chave or chave in cid:
            return coords
    return DEFAULT_DESTINO if eh_destino else DEFAULT_ORIGEM


async def consultar_viagens_existentes(
    conn: asyncpg.Connection,
    tenant_id: str
) -> Set[Tuple[str, str, str]]:
    query = """
    SELECT v.placa, o.janela_inicio
    FROM operacoes o
    JOIN veiculos v ON o.id_veiculo = v.id_veiculo
    WHERE o.tenant_id = $1;
    """
    rows = await conn.fetch(query, tenant_id)
    existentes: Set[Tuple[str, str, str]] = set()
    for r in rows:
        placa = (r["placa"] or "").upper()
        dt = r["janela_inicio"]
        if dt:
            data_str = dt.strftime("%Y-%m-%d")
            hora_str = dt.strftime("%H:%M")
            existentes.add((placa, data_str, hora_str))
    return existentes


async def processar_manifesto(
    conteudo_bytes: bytes,
    tenant_id: str,
    dry_run: bool,
    conn: asyncpg.Connection,
    referencia_agora: Optional[datetime] = None
) -> Dict[str, Any]:
    viagens_existentes = await consultar_viagens_existentes(conn, tenant_id)
    relatorio = parse_manifesto_csv(
        conteudo_bytes,
        tenant_id=tenant_id,
        viagens_existentes=viagens_existentes,
        referencia_agora=referencia_agora
    )

    if dry_run or not relatorio["linhas_validas"]:
        return {
            "resumo": relatorio["resumo"],
            "colunas_ignoradas": relatorio["colunas_ignoradas"],
            "erros": relatorio["erros"],
            "avisos": relatorio["avisos"],
            "importadas": 0
        }

    importadas = 0
    linhas_a_gravar = [
        l for l in relatorio["linhas_validas"]
        if (l["placa"], l["data_saida"], l["hora_saida"]) not in viagens_existentes
    ]

    if not linhas_a_gravar:
        return {
            "resumo": relatorio["resumo"],
            "colunas_ignoradas": relatorio["colunas_ignoradas"],
            "erros": relatorio["erros"],
            "avisos": relatorio["avisos"],
            "importadas": 0
        }

    try:
        async with conn.transaction():
            for l in linhas_a_gravar:
                placa = l["placa"]
                id_veiculo = await conn.fetchval(
                    "SELECT id_veiculo FROM veiculos WHERE placa = $1 AND tenant_id = $2 LIMIT 1",
                    placa, tenant_id
                )
                if not id_veiculo:
                    id_veiculo = f"{tenant_id}_{placa}"[:50]
                    await conn.execute(
                        """
                        INSERT INTO veiculos (id_veiculo, placa, modelo, tipo_veiculo, status, tenant_id)
                        VALUES ($1, $2, $3, 'VUC', 'DISPONIVEL', $4)
                        ON CONFLICT (id_veiculo) DO NOTHING
                        """,
                        id_veiculo, placa, f"Veiculo {placa}", tenant_id
                    )

                orig_lat, orig_lon = resolver_coordenadas(l["origem"], eh_destino=False)
                dest_lat, dest_lon = resolver_coordenadas(l["destino"], eh_destino=True)

                id_operacao = f"OP_{tenant_id}_{placa}_{l['data_saida'].replace('-', '')}_{l['hora_saida'].replace(':', '')}"[:50]
                dt_iso = datetime.fromisoformat(l["data_hora_saida"])
                dt_naive = dt_iso.replace(tzinfo=None)
                janela_fim = dt_naive + timedelta(hours=6)

                metadados = {
                    "motorista": l["motorista"],
                    "telefone_motorista": l["telefone_motorista"],
                    "observacao": l["observacao"]
                }
                custos_json = json.dumps(metadados)

                await conn.execute(
                    """
                    INSERT INTO operacoes (
                        id_operacao, id_veiculo, origem_nome, origem_lat, origem_lon,
                        destino_nome, destino_lat, destino_lon, janela_inicio, janela_fim,
                        status, tenant_id, custos_operacionais
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'PLANNED', $11, $12::jsonb)
                    ON CONFLICT (id_operacao) DO UPDATE SET
                        id_veiculo = EXCLUDED.id_veiculo,
                        origem_nome = EXCLUDED.origem_nome,
                        origem_lat = EXCLUDED.origem_lat,
                        origem_lon = EXCLUDED.origem_lon,
                        destino_nome = EXCLUDED.destino_nome,
                        destino_lat = EXCLUDED.destino_lat,
                        destino_lon = EXCLUDED.destino_lon,
                        janela_inicio = EXCLUDED.janela_inicio,
                        janela_fim = EXCLUDED.janela_fim,
                        custos_operacionais = EXCLUDED.custos_operacionais
                    WHERE operacoes.tenant_id = EXCLUDED.tenant_id
                    """,
                    id_operacao, id_veiculo, l["origem"], orig_lat, orig_lon,
                    l["destino"], dest_lat, dest_lon, dt_naive, janela_fim,
                    tenant_id, custos_json
                )
                importadas += 1

    except Exception as exc:
        logger.error("Falha ao gravar lote de manifesto para o tenant %s: %s", tenant_id, type(exc).__name__)
        raise

    return {
        "resumo": relatorio["resumo"],
        "colunas_ignoradas": relatorio["colunas_ignoradas"],
        "erros": relatorio["erros"],
        "avisos": relatorio["avisos"],
        "importadas": importadas
    }
