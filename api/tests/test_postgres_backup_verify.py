"""Verificação offline dos arquivos de backup, sem acessar Docker ou banco."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.postgres_backup import verify_latest


def create_backup(folder: Path, created_at: datetime, *, content: bytes = b"backup") -> Path:
    stamp = created_at.strftime("%Y%m%dT%H%M%SZ")
    archive = folder / f"sprain-enchentes-{stamp}-test.dump"
    archive.write_bytes(content)
    manifest = {
        "format": "pg_dump-custom",
        "created_at_utc": created_at.isoformat(),
        "source_database": "enchentes",
        "archive_file": archive.name,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    archive.with_name(f"{archive.name}.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return archive


def options(folder: Path, max_age_hours: float = 36) -> argparse.Namespace:
    return argparse.Namespace(output_dir=folder, database="enchentes", max_age_hours=max_age_hours)


def test_verify_latest_aceita_backup_recente_e_rejeita_antigo(tmp_path, capsys):
    recent = create_backup(tmp_path, datetime.now(timezone.utc) - timedelta(hours=2))
    verify_latest(options(tmp_path))
    assert recent.name in capsys.readouterr().out

    with pytest.raises(RuntimeError, match="está antigo"):
        verify_latest(options(tmp_path, max_age_hours=1))


def test_verify_latest_nao_ignora_backup_mais_recente_corrompido(tmp_path):
    now = datetime.now(timezone.utc)
    create_backup(tmp_path, now - timedelta(days=1))
    latest = create_backup(tmp_path, now - timedelta(hours=1))
    latest.write_bytes(b"corrompido")

    with pytest.raises(RuntimeError, match="SHA-256"):
        verify_latest(options(tmp_path))


def test_verify_latest_rejeita_manifesto_de_outro_banco(tmp_path):
    archive = create_backup(tmp_path, datetime.now(timezone.utc))
    manifest_path = archive.with_name(f"{archive.name}.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_database"] = "outro_banco"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="não corresponde"):
        verify_latest(options(tmp_path))


def test_verify_latest_rejeita_pasta_sem_backup(tmp_path):
    with pytest.raises(RuntimeError, match="nenhum backup completo"):
        verify_latest(options(tmp_path))
