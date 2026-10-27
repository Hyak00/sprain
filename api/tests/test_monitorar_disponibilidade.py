"""A sonda deve preservar alertas entre execuções separadas do timer."""

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import monitorar_disponibilidade as monitor


def opcoes(tmp_path):
    return argparse.Namespace(
        url="https://piloto.exemplo.com/api/v1/health/readiness",
        webhook_url="https://discord.com/api/webhooks/exemplo",
        state_file=tmp_path / "estado.json", failure_threshold=2,
        timeout=8.0, allow_http_local_test=False,
    )


def test_queda_e_recuperacao_geram_um_aviso_cada(tmp_path, monkeypatch):
    respostas = iter([(False, "HTTP 503")] * 3 + [(True, "READY")] * 2)
    avisos = []
    monkeypatch.setattr(monitor, "probe", lambda *_: next(respostas))
    monkeypatch.setattr(monitor, "notify", lambda _, mensagem, __: avisos.append(mensagem))
    args = opcoes(tmp_path)

    assert [monitor.check(args) for _ in range(5)] == [1, 1, 1, 0, 0]
    assert len(avisos) == 2
    assert "INDISPONÍVEL" in avisos[0]
    assert "RECUPERADO" in avisos[1]
    assert json.loads(args.state_file.read_text(encoding="utf-8"))["alerted"] is False


def test_falha_no_webhook_mantem_alerta_pendente(tmp_path, monkeypatch):
    avisos = []

    def enviar(_, mensagem, __):
        avisos.append(mensagem)
        if len(avisos) == 1:
            raise RuntimeError("destino indisponível")

    monkeypatch.setattr(monitor, "probe", lambda *_: (False, "HTTP 503"))
    monkeypatch.setattr(monitor, "notify", enviar)
    args = opcoes(tmp_path)

    assert monitor.check(args) == 1
    with pytest.raises(RuntimeError, match="destino indisponível"):
        monitor.check(args)
    assert json.loads(args.state_file.read_text(encoding="utf-8"))["alerted"] is False

    assert monitor.check(args) == 1
    assert len(avisos) == 2
    assert json.loads(args.state_file.read_text(encoding="utf-8"))["alerted"] is True


def test_http_real_queda_e_recuperacao_sem_avisos_duplicados(tmp_path):
    respostas = iter([503, 503, 503, 200, 200])
    avisos = []

    class ServidorEnsaio(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/api/v1/health/readiness"
            status = next(respostas)
            payload = (
                {"status": "READY", "postgis": "OPERACIONAL", "total_trechos_osm": 12}
                if status == 200 else {"detail": "banco indisponível"}
            )
            corpo = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_POST(self):
            assert self.path == "/webhook"
            tamanho = int(self.headers["Content-Length"])
            avisos.append(json.loads(self.rfile.read(tamanho))["content"])
            self.send_response(204)
            self.end_headers()

        def log_message(self, *_):
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), ServidorEnsaio)
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{servidor.server_port}"
        args = argparse.Namespace(
            url=f"{base}/api/v1/health/readiness",
            webhook_url=f"{base}/webhook",
            state_file=tmp_path / "estado-real.json",
            failure_threshold=2,
            timeout=2.0,
            allow_http_local_test=True,
        )
        assert [monitor.check(args) for _ in range(5)] == [1, 1, 1, 0, 0]
        assert len(avisos) == 2
        assert "INDISPONÍVEL" in avisos[0]
        assert "RECUPERADO" in avisos[1]
        assert json.loads(args.state_file.read_text(encoding="utf-8")) == {
            "url": args.url, "failures": 0, "alerted": False,
        }
    finally:
        servidor.shutdown()
        servidor.server_close()
        thread.join(timeout=3)
