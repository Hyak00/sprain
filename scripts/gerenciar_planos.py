"""Previa ou aplica configuracoes manuais de plano e assinatura com auditoria.

Exemplo: python /app/scripts/gerenciar_planos.py plano --arquivo plano.json
Depois de conferir: repetir com --aplicar. Nao aceita precos nem credenciais.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from app.database import close_db_pool, get_connection, init_db_pool
from app.services.gestao_planos import registrar_assinatura, registrar_plano


def ler_configuracao(tipo: str, arquivo: Path) -> dict:
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        raise ValueError("O arquivo deve conter um objeto JSON.")
    if tipo == "assinatura":
        for campo in ("inicio_em", "fim_em"):
            if dados.get(campo) is not None:
                dados[campo] = datetime.fromisoformat(dados[campo].replace("Z", "+00:00"))
    return dados


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tipo", choices=("plano", "assinatura"))
    parser.add_argument("--arquivo", type=Path, required=True, help="JSON completo da configuracao")
    parser.add_argument("--ator", required=True, help="Identidade do operador responsavel")
    parser.add_argument("--motivo", required=True, help="Justificativa da alteracao")
    parser.add_argument("--aplicar", action="store_true", help="Gravar a mudanca apos conferir a previa")
    args = parser.parse_args()
    try:
        dados = ler_configuracao(args.tipo, args.arquivo)
    except (OSError, ValueError, TypeError) as erro:
        parser.error(f"Configuracao invalida: {erro}")
    await init_db_pool()
    try:
        async for conn in get_connection():
            if not await conn.fetchval("SELECT to_regclass('public.planos_auditoria') IS NOT NULL"):
                parser.error("Migração de planos pendente; inicie a API atualizada antes de usar este comando.")
            funcao = registrar_plano if args.tipo == "plano" else registrar_assinatura
            try:
                resultado = await funcao(conn, dados, args.ator, args.motivo, args.aplicar)
            except ValueError as erro:
                parser.error(str(erro))
        print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
        if not args.aplicar:
            print("PREVIA: nenhuma alteracao foi gravada. Repita com --aplicar apos conferir.")
    finally:
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(main())
