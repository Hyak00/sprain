from __future__ import annotations

import json
import math
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

STATUS_FILE_CHUVA = Path("/tmp/sprain_chuva_worker_status.json")
GRACE_SECONDS = 300


def write_chuva_status(
    phase: str,
    interval_seconds: int,
    *,
    last_result: Optional[str] = None,
    path: Path = STATUS_FILE_CHUVA,
    now: Optional[float] = None,
) -> None:
    if phase not in ("running", "sleeping") or not 60 <= interval_seconds <= 1800:
        raise ValueError("fase ou intervalo do worker de chuva invalido")
    status = {
        "phase": phase,
        "updated_at_unix": time.time() if now is None else now,
        "interval_seconds": interval_seconds,
        "last_result": last_result,
    }
    path = Path(path)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    with tmp.open("x", encoding="utf-8") as f:
        json.dump(status, f)
    os.replace(tmp, path)


def check_chuva(path: Path = STATUS_FILE_CHUVA, now: float | None = None) -> tuple[bool, str]:
    try:
        with Path(path).open(encoding="utf-8") as f:
            status = json.load(f)
    except (OSError, ValueError):
        return False, "status do worker de chuva ausente ou invalido"

    if not isinstance(status, dict):
        return False, "status invalido"

    phase = status.get("phase")
    updated_at = status.get("updated_at_unix")
    interval = status.get("interval_seconds")

    if (
        phase not in ("running", "sleeping")
        or not isinstance(updated_at, (int, float))
        or isinstance(updated_at, bool)
        or not math.isfinite(updated_at)
        or not isinstance(interval, (int, float))
        or isinstance(interval, bool)
        or not 60 <= interval <= 1800
    ):
        return False, "status do worker de chuva invalido"

    age = (time.time() if now is None else now) - updated_at
    if age < 0:
        return False, "relogio do status no futuro"
    if status.get("last_result") == "failed":
        return False, "ultima rodada de coleta falhou"
    if phase == "running" and age > 120:
        return False, "worker de chuva travado"
    if phase == "sleeping" and age > interval + GRACE_SECONDS:
        return False, "worker de chuva nao iniciou rodada no prazo"
    if phase == "sleeping" and status.get("last_result") != "ok":
        return False, "worker ainda nao concluiu uma rodada"
    return True, "worker de chuva operacional"


if __name__ == "__main__":
    healthy, message = check_chuva()
    print(message)
    sys.exit(0 if healthy else 1)
