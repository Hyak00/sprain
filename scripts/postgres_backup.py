"""Backup e restauração segura de PostgreSQL/PostGIS em contêiner Docker.

Requer Python 3.9+; backup e restore também requerem o cliente Docker.
Não recebe nem imprime senhas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
CONTAINER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")


def database_identifier(value: str) -> str:
    if len(value) > 63 or not IDENTIFIER.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "use um identificador PostgreSQL de até 63 caracteres: letras, números e _"
        )
    return value


def container_name(value: str) -> str:
    if not CONTAINER_NAME.fullmatch(value):
        raise argparse.ArgumentTypeError("nome de contêiner Docker inválido")
    return value


def run_docker(args: list[str], *, stdin=None, stdout=subprocess.PIPE) -> subprocess.CompletedProcess:
    command = ["docker", *args]
    try:
        result = subprocess.run(
            command, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE, check=False
        )
    except OSError as exc:
        raise RuntimeError(f"não foi possível executar Docker: {exc}") from exc
    if result.returncode:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"comando Docker falhou ({result.returncode}): {error}")
    return result


def sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def positive_hours(value: str) -> float:
    try:
        hours = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("informe um número positivo de horas") from exc
    if not math.isfinite(hours) or hours <= 0:
        raise argparse.ArgumentTypeError("informe um número positivo de horas")
    return hours


def verify_archive(archive: Path) -> dict:
    manifest_path = archive.with_name(f"{archive.name}.json")
    with manifest_path.open(encoding="utf-8") as stream:
        metadata = json.load(stream)
    if not isinstance(metadata, dict):
        raise RuntimeError("manifesto inválido")
    if metadata.get("format") != "pg_dump-custom" or metadata.get("archive_file") != archive.name:
        raise RuntimeError("manifesto não corresponde a este backup customizado")
    digest, size = sha256_and_size(archive)
    if digest != metadata.get("sha256") or size != metadata.get("bytes"):
        raise RuntimeError("SHA-256 ou tamanho do backup não corresponde ao manifesto")
    return metadata


def backup(args: argparse.Namespace) -> None:
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"sprain-{args.database}-{timestamp}-{uuid.uuid4().hex[:12]}.dump"
    archive = output_dir / name
    partial = output_dir / f"{name}.partial"
    manifest = output_dir / f"{name}.json"

    # 'xb' garante que nem um arquivo parcial preexistente será sobrescrito.
    with partial.open("xb") as stream:
        run_docker(
            [
                "exec", args.container, "pg_dump", "-U", args.user, "-d", args.database,
                "--format=custom", "--no-owner", "--no-privileges",
            ],
            stdout=stream,
        )

    with partial.open("rb") as stream:
        run_docker(
            ["exec", "-i", args.container, "pg_restore", "--list"],
            stdin=stream,
            stdout=subprocess.DEVNULL,
        )

    digest, size = sha256_and_size(partial)
    if size == 0:
        raise RuntimeError("o arquivo de backup está vazio")

    # No Windows, rename falha caso o destino exista. O nome também contém UUID.
    partial.rename(archive)
    metadata = {
        "format": "pg_dump-custom",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_container": args.container,
        "source_database": args.database,
        "source_user": args.user,
        "archive_file": archive.name,
        "bytes": size,
        "sha256": digest,
    }
    with manifest.open("x", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(f"Backup verificado: {archive}")
    print(f"Manifesto SHA-256: {manifest}")


def restore(args: argparse.Namespace) -> None:
    archive = args.backup.expanduser().resolve(strict=True)
    verify_archive(archive)

    with archive.open("rb") as stream:
        run_docker(
            ["exec", "-i", args.container, "pg_restore", "--list"],
            stdin=stream,
            stdout=subprocess.DEVNULL,
        )

    query = f"SELECT 1 FROM pg_database WHERE datname = '{args.new_database}'"
    existing = run_docker(
        ["exec", args.container, "psql", "-U", args.user, "-d", "postgres", "-tA", "-c", query]
    ).stdout.decode("utf-8", errors="replace").strip()
    if existing:
        raise RuntimeError(f"o banco {args.new_database!r} já existe; nada foi alterado")

    run_docker(
        ["exec", args.container, "createdb", "-U", args.user, "-T", "template0", args.new_database]
    )
    try:
        with archive.open("rb") as stream:
            run_docker(
                [
                    "exec", "-i", args.container, "pg_restore", "-U", args.user,
                    "-d", args.new_database, "--no-owner", "--no-privileges", "--exit-on-error",
                ],
                stdin=stream,
            )
    except RuntimeError as exc:
        raise RuntimeError(
            f"restauração falhou; o banco novo {args.new_database!r} foi preservado para diagnóstico: {exc}"
        ) from exc
    print(f"Restauração concluída no banco novo {args.new_database!r} do contêiner {args.container!r}")


def verify_latest(args: argparse.Namespace) -> None:
    output_dir = args.output_dir.expanduser().resolve(strict=True)
    if not output_dir.is_dir():
        raise RuntimeError("pasta de backups inválida")
    manifests = sorted(output_dir.glob(f"sprain-{args.database}-*.dump.json"), reverse=True)
    if not manifests:
        raise RuntimeError(f"nenhum backup completo de {args.database!r} encontrado")

    # O nome contém o instante UTC; um backup mais recente inválido não pode ser
    # escondido pela existência de uma cópia antiga íntegra.
    archive = manifests[0].with_suffix("")
    metadata = verify_archive(archive)
    if metadata.get("source_database") != args.database:
        raise RuntimeError("o banco do manifesto não corresponde ao solicitado")
    try:
        created_at = datetime.fromisoformat(metadata["created_at_utc"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("data UTC do manifesto inválida") from exc
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise RuntimeError("data do manifesto não tem fuso horário")
    age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
    if age_hours < -5 / 60:
        raise RuntimeError("data do backup está no futuro")
    if age_hours > args.max_age_hours:
        raise RuntimeError(
            f"backup mais recente está antigo: {age_hours:.1f} h (limite {args.max_age_hours:g} h)"
        )
    print(f"Backup recente com SHA-256 válido: {archive} ({max(age_hours, 0):.1f} h)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="operation", required=True)
    backup_parser = subcommands.add_parser("backup", help="criar e verificar backup sem alterar o banco")
    backup_parser.add_argument("--container", type=container_name, required=True)
    backup_parser.add_argument("--database", type=database_identifier, required=True)
    backup_parser.add_argument("--user", type=database_identifier, required=True)
    backup_parser.add_argument("--output-dir", type=Path, required=True)
    backup_parser.set_defaults(action=backup)

    restore_parser = subcommands.add_parser("restore", help="restaurar apenas em um banco novo")
    restore_parser.add_argument("--container", type=container_name, required=True)
    restore_parser.add_argument("--new-database", type=database_identifier, required=True)
    restore_parser.add_argument("--user", type=database_identifier, required=True)
    restore_parser.add_argument("--backup", type=Path, required=True)
    restore_parser.set_defaults(action=restore)

    verify_parser = subcommands.add_parser(
        "verify-latest", help="conferir hash e idade do backup completo mais recente"
    )
    verify_parser.add_argument("--database", type=database_identifier, required=True)
    verify_parser.add_argument("--output-dir", type=Path, required=True)
    verify_parser.add_argument("--max-age-hours", type=positive_hours, required=True)
    verify_parser.set_defaults(action=verify_latest)

    args = parser.parse_args()
    try:
        args.action(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
