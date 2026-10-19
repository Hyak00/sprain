"""A saúde do trabalhador depende de progresso real, sem consultar banco ou rede."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts import worker_dados_publicos as worker
from scripts.worker_status import check_status, write_status


def test_worker_agenda_pesquisa_semanal_anp():
    with patch.object(
        worker.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="")
    ) as executar:
        assert worker.executar_rodada() is True

    fontes_executadas = [chamada.args[0][3] for chamada in executar.call_args_list]
    assert fontes_executadas == list(worker.FONTES)
    assert fontes_executadas.count("anp-semanal") == 1
    assert fontes_executadas.index("anp") < fontes_executadas.index("anp-semanal")


def test_healthcheck_detecta_progresso_e_atraso(tmp_path):
    status_file = tmp_path / "worker.json"

    write_status("running", 24, source="anp", path=status_file, now=1000)
    assert check_status(status_file, now=1000 + 14 * 60)[0]
    assert not check_status(status_file, now=1000 + 16 * 60)[0]

    write_status("sleeping", 24, last_result="ok", path=status_file, now=1000)
    assert check_status(status_file, now=1000 + 24 * 3600 + 14 * 60)[0]
    assert not check_status(status_file, now=1000 + 24 * 3600 + 16 * 60)[0]


def test_healthcheck_detecta_falha_e_estado_ausente(tmp_path):
    status_file = tmp_path / "worker.json"
    assert not check_status(status_file)[0]

    status_file.write_text("{quebrado", encoding="utf-8")
    assert not check_status(status_file)[0]

    write_status("sleeping", 24, last_result="failed", path=status_file, now=1000)
    assert not check_status(status_file, now=1001)[0]


def test_worker_registra_cada_fonte_e_resultado_da_rodada(monkeypatch):
    estados = []
    monkeypatch.setattr(worker, "write_status", lambda *args, **kwargs: estados.append((args, kwargs)))
    monkeypatch.setattr(worker.sys, "argv", ["worker_dados_publicos.py", "--once"])
    monkeypatch.setenv("DADOS_PUBLICOS_INTERVALO_HORAS", "24")

    def rodada(heartbeat):
        for fonte in worker.FONTES:
            heartbeat(fonte)
        return True

    with patch.object(worker, "executar_rodada", side_effect=rodada):
        with pytest.raises(SystemExit) as terminou:
            worker.main()

    assert terminou.value.code == 0
    assert estados[0][0] == ("running", 24)
    assert [estado[1]["source"] for estado in estados[1:-1]] == list(worker.FONTES)
    assert estados[-1][0] == ("sleeping", 24)
    assert estados[-1][1]["last_result"] == "ok"
