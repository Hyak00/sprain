"""Validação e envio de webhooks sem uma segunda resolução de DNS."""

import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit


class URLBloqueada(ValueError):
    pass


def _resolver_url(url: str):
    try:
        partes = urlsplit(url)
        host = partes.hostname
        porta = partes.port
        if (
            partes.scheme not in ("http", "https")
            or not host
            or partes.username is not None
            or partes.password is not None
        ):
            raise URLBloqueada("URL de webhook inválida")
        porta = porta if porta is not None else (443 if partes.scheme == "https" else 80)
        if not 1 <= porta <= 65535:
            raise URLBloqueada("porta de webhook inválida")
        enderecos = socket.getaddrinfo(
            host, porta, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
        )
        if not enderecos:
            raise URLBloqueada("URL sem endereço público")
        for _familia, _tipo, _protocolo, _canonico, destino in enderecos:
            ip = ipaddress.ip_address(destino[0])
            if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
                ip = ip.ipv4_mapped
            if not ip.is_global:
                raise URLBloqueada("URL aponta para rede não pública")
        return partes, host, porta, enderecos
    except (OSError, ValueError, UnicodeError) as exc:
        if isinstance(exc, URLBloqueada):
            raise
        raise URLBloqueada("URL de webhook inválida") from exc


def is_safe_url(url: str) -> bool:
    try:
        _resolver_url(url)
        return True
    except URLBloqueada:
        return False


def post_seguro(url: str, headers: dict[str, str], corpo: bytes, timeout: float = 5.0) -> int:
    """Conecta ao IP validado, mantendo Host, SNI e verificação TLS pelo nome."""
    partes, host, porta, enderecos = _resolver_url(url)
    conexao_socket = None
    ultimo_erro = None
    inicio = time.monotonic()
    for familia, tipo, protocolo, _canonico, destino in enderecos[:4]:
        restante = timeout - (time.monotonic() - inicio)
        if restante <= 0:
            break
        candidato = None
        try:
            candidato = socket.socket(familia, tipo, protocolo)
            candidato.settimeout(restante)
            candidato.connect(destino)
        except OSError as exc:
            ultimo_erro = exc
            if candidato is not None:
                candidato.close()
            continue
        conexao_socket = candidato
        break
    if conexao_socket is None:
        raise ultimo_erro or OSError("nenhum endereço público acessível")

    conexao = None
    try:
        if partes.scheme == "https":
            contexto = ssl.create_default_context()
            contexto.set_alpn_protocols(["http/1.1"])
            conexao_socket = contexto.wrap_socket(conexao_socket, server_hostname=host)
        # O socket já está conectado ao IP validado. HTTPConnection apenas
        # serializa a requisição e não faz outra resolução de DNS.
        conexao = http.client.HTTPConnection(host, porta, timeout=timeout)
        conexao.sock = conexao_socket
        autoridade = f"[{host}]" if ":" in host else host
        if porta != (443 if partes.scheme == "https" else 80):
            autoridade = f"{autoridade}:{porta}"
        caminho = partes.path or "/"
        if partes.query:
            caminho += f"?{partes.query}"
        conexao.request("POST", caminho, body=corpo, headers={**headers, "Host": autoridade})
        return conexao.getresponse().status
    finally:
        if conexao is not None:
            conexao.close()
        else:
            conexao_socket.close()
