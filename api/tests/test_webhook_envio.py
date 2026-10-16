import json
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from app.services.webhook_dispatcher import WebhookDispatcher
from app import url_segura
from app.routers import logistica
from app.schemas import WebhookAlertaRequest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts import worker_dados_publicos as worker


class Registro:
    def __init__(self):
        self.chamadas = []


def subir_servidor(codigo, destino=None):
    registro = Registro()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            tamanho = int(self.headers.get("Content-Length", 0))
            corpo = self.rfile.read(tamanho)
            registro.chamadas.append({
                "corpo": corpo,
                "caminho": self.path,
                "assinatura": self.headers.get("X-SPRain-Signature"),
            })
            self.send_response(codigo)
            if destino:
                self.send_header("Location", destino)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    servidor = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, registro


def derrubar(servidor):
    servidor.shutdown()
    servidor.server_close()


def permitir_servidor_local_de_teste(monkeypatch):
    def resolver(url):
        partes = urlsplit(url)
        porta = partes.port
        return partes, partes.hostname, porta, [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", porta))
        ]

    monkeypatch.setattr(url_segura, "_resolver_url", resolver)


def test_envio_entrega_corpo_assinado(monkeypatch):
    permitir_servidor_local_de_teste(monkeypatch)
    servidor, registro = subir_servidor(200)
    try:
        url = f"http://127.0.0.1:{servidor.server_port}/hook"
        corpo = json.dumps({"evento": "ALERTA_ALAGAMENTO"}, sort_keys=True).encode("utf-8")
        assinatura = WebhookDispatcher.gerar_assinatura("segredo_de_teste", corpo)
        headers = {"Content-Type": "application/json", "X-SPRain-Signature": assinatura}
        resultado = WebhookDispatcher._enviar_http(url, headers, corpo)
    finally:
        derrubar(servidor)
    assert resultado == {"enviado": True, "codigo_http": 200, "entregue": True}
    assert len(registro.chamadas) == 1
    assert registro.chamadas[0]["corpo"] == corpo
    assert registro.chamadas[0]["assinatura"] == assinatura


def test_envio_nao_segue_redirect(monkeypatch):
    permitir_servidor_local_de_teste(monkeypatch)
    servidor, registro = subir_servidor(302, destino="/outro")
    try:
        url = f"http://127.0.0.1:{servidor.server_port}/hook"
        resultado = WebhookDispatcher._enviar_http(url, {}, b"{}")
    finally:
        derrubar(servidor)
    assert resultado == {"enviado": True, "codigo_http": 302, "entregue": False}
    assert len(registro.chamadas) == 1
    assert registro.chamadas[0]["caminho"] == "/hook"


def test_envio_recusa_url_interna():
    servidor, registro = subir_servidor(200)
    try:
        url = f"http://127.0.0.1:{servidor.server_port}/hook"
        resultado = WebhookDispatcher._enviar_http(url, {}, b"{}")
    finally:
        derrubar(servidor)
    assert resultado == {"enviado": False, "motivo": "URL_BLOQUEADA"}
    assert registro.chamadas == []


def test_envio_falha_de_conexao(monkeypatch):
    permitir_servidor_local_de_teste(monkeypatch)
    servidor, _ = subir_servidor(200)
    porta = servidor.server_port
    derrubar(servidor)
    resultado = WebhookDispatcher._enviar_http(f"http://127.0.0.1:{porta}/hook", {}, b"{}")
    assert resultado["enviado"] is False
    assert resultado["motivo"] == "FALHA_ENVIO"


@pytest.mark.asyncio
async def test_enviar_resultado_manda_o_payload_assinado(monkeypatch):
    permitir_servidor_local_de_teste(monkeypatch)
    servidor, registro = subir_servidor(202)
    try:
        payload = {"evento": "ROTA_RECALCULADA", "tenant_id": "demo_corp", "payload": {"id_trecho": 7}}
        corpo = json.dumps(payload, sort_keys=True).encode("utf-8")
        assinatura = WebhookDispatcher.gerar_assinatura("segredo_de_teste", corpo)
        resultado = {
            "url_destino": f"http://127.0.0.1:{servidor.server_port}/hook",
            "headers": {"Content-Type": "application/json", "X-SPRain-Signature": assinatura},
            "payload_enviado": payload,
        }
        envio = await WebhookDispatcher.enviar_resultado(resultado)
    finally:
        derrubar(servidor)
    assert envio == {"enviado": True, "codigo_http": 202, "entregue": True}
    assert registro.chamadas[0]["corpo"] == corpo
    assert registro.chamadas[0]["assinatura"] == assinatura


def test_envio_usa_ip_validado_sem_nova_resolucao_dns(monkeypatch):
    consultas_dns = []
    conexoes = []

    def resolver_dns(host, porta, **kwargs):
        consultas_dns.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", porta))]

    class SocketFalso:
        def settimeout(self, timeout):
            pass

        def connect(self, destino):
            conexoes.append(destino)

        def close(self):
            pass

    class HTTPFalso:
        def __init__(self, host, porta, timeout):
            self.sock = None

        def request(self, metodo, caminho, body, headers):
            assert metodo == "POST"
            assert caminho == "/hook?x=1"
            assert headers["Host"] == "webhook.example"

        def getresponse(self):
            return SimpleNamespace(status=200)

        def close(self):
            self.sock.close()

    monkeypatch.setattr(url_segura.socket, "getaddrinfo", resolver_dns)
    monkeypatch.setattr(url_segura.socket, "socket", lambda *args: SocketFalso())
    monkeypatch.setattr(url_segura.http.client, "HTTPConnection", HTTPFalso)

    resultado = WebhookDispatcher._enviar_http("http://webhook.example/hook?x=1", {}, b"{}")
    assert resultado["entregue"] is True
    assert consultas_dns == ["webhook.example"]
    assert conexoes == [("8.8.8.8", 80)]


def test_envio_recusa_resposta_dns_com_ip_publico_e_privado(monkeypatch):
    def resolver_dns(host, porta, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", porta)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", porta)),
        ]

    monkeypatch.setattr(url_segura.socket, "getaddrinfo", resolver_dns)
    monkeypatch.setattr(
        url_segura.socket, "socket",
        lambda *args: pytest.fail("não deveria abrir conexão para DNS misto"),
    )
    assert WebhookDispatcher._enviar_http("http://webhook.example/hook", {}, b"{}") == {
        "enviado": False, "motivo": "URL_BLOQUEADA"
    }


def test_https_verifica_nome_original_no_tls(monkeypatch):
    servidores_tls = []
    destinos = []

    def resolver_dns(host, porta, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", porta))]

    class SocketFalso:
        def settimeout(self, timeout):
            pass

        def connect(self, destino):
            destinos.append(destino)

        def close(self):
            pass

    class ContextoTLSFalso:
        def set_alpn_protocols(self, protocolos):
            assert protocolos == ["http/1.1"]

        def wrap_socket(self, sock, server_hostname):
            servidores_tls.append(server_hostname)
            return sock

    class HTTPFalso:
        def __init__(self, host, porta, timeout):
            self.sock = None

        def request(self, metodo, caminho, body, headers):
            assert headers["Host"] == "webhook.example"

        def getresponse(self):
            return SimpleNamespace(status=204)

        def close(self):
            self.sock.close()

    monkeypatch.setattr(url_segura.socket, "getaddrinfo", resolver_dns)
    monkeypatch.setattr(url_segura.socket, "socket", lambda *args: SocketFalso())
    monkeypatch.setattr(url_segura.ssl, "create_default_context", ContextoTLSFalso)
    monkeypatch.setattr(url_segura.http.client, "HTTPConnection", HTTPFalso)

    resultado = WebhookDispatcher._enviar_http("https://webhook.example/hook", {}, b"{}")
    assert resultado["entregue"] is True
    assert destinos == [("8.8.8.8", 443)]
    assert servidores_tls == ["webhook.example"]


@pytest.mark.asyncio
async def test_alerta_operacional_tambem_usa_envio_seguro(monkeypatch):
    enviados = []

    class ConexaoFalsa:
        async def fetchrow(self, query, *args):
            if "FROM operacoes" in query:
                return {"criado_em": "agora", "id_operacao": "OP-1", "status": "PLANNED", "id_veiculo": "V-1"}
            return None

    def enviar(url, headers, corpo, timeout):
        enviados.append((url, timeout))
        return 202

    monkeypatch.setattr(logistica, "is_safe_url", lambda url: True)
    monkeypatch.setattr(logistica, "post_seguro", enviar)
    dados = WebhookAlertaRequest(
        webhook_url="https://webhook.example/hook", id_operacao="OP-1", tenant_id="demo_corp"
    )
    resposta = await logistica.disparar_alerta_webhook(
        dados, conn=ConexaoFalsa(), tenant_autenticado="demo_corp"
    )
    assert resposta["sucesso"] is True
    assert enviados == [("https://webhook.example/hook", 4.0)]


@pytest.mark.asyncio
async def test_alerta_operacional_bloqueia_dns_que_muda_para_rede_interna(monkeypatch):
    consultas = []

    def resolver_dns(host, porta, **kwargs):
        consultas.append(host)
        ip = "8.8.8.8" if len(consultas) == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, porta))]

    class ConexaoFalsa:
        async def fetchrow(self, query, *args):
            if "FROM operacoes" in query:
                return {"criado_em": "agora", "id_operacao": "OP-1", "status": "PLANNED", "id_veiculo": "V-1"}
            return None

    monkeypatch.setattr(url_segura.socket, "getaddrinfo", resolver_dns)
    monkeypatch.setattr(
        url_segura.socket, "socket",
        lambda *args: pytest.fail("não deveria conectar ao endereço privado"),
    )
    dados = WebhookAlertaRequest(
        webhook_url="http://webhook.example/hook", id_operacao="OP-1", tenant_id="demo_corp"
    )
    resposta = await logistica.disparar_alerta_webhook(
        dados, conn=ConexaoFalsa(), tenant_autenticado="demo_corp"
    )
    assert resposta["sucesso"] is False
    assert resposta["status_envio"] == "FALHA_ENVIO"
    assert consultas == ["webhook.example", "webhook.example"]


def test_worker_envia_alerta_pelo_cliente_seguro(monkeypatch):
    enviados = []

    def enviar(url, headers, corpo, timeout):
        enviados.append((url, headers, json.loads(corpo), timeout))
        return 202

    monkeypatch.setenv("WEBHOOK_ALERTA_DADOS", "https://webhook.example/dados")
    monkeypatch.setattr(worker, "post_seguro", enviar)
    worker.disparar_alerta("anp", "falha de teste")
    assert len(enviados) == 1
    url, headers, corpo, timeout = enviados[0]
    assert url == "https://webhook.example/dados"
    assert headers == {"Content-Type": "application/json"}
    assert corpo["fonte"] == "anp"
    assert corpo["erro"] == "falha de teste"
    assert timeout == 10


def test_worker_recusa_webhook_interno(monkeypatch, capsys):
    monkeypatch.setenv("WEBHOOK_ALERTA_DADOS", "http://127.0.0.1:8000/interno")
    monkeypatch.setattr(
        url_segura.socket, "socket",
        lambda *args: pytest.fail("não deveria abrir conexão interna"),
    )
    worker.disparar_alerta("anp", "falha de teste")
    assert "Falha ao enviar alerta para webhook" in capsys.readouterr().err
