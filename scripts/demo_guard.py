"""Verificação do servidor de demonstração antes de qualquer carga."""
import json
import urllib.request
import urllib.parse
import http.client


class SemRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def verificar_api_demo(base):
    u=urllib.parse.urlsplit(base)
    if u.scheme!='http' or u.hostname not in ('localhost','127.0.0.1','::1') or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
        raise SystemExit('Carga de demonstração aceita apenas a API HTTP local, sem credenciais na URL.')
    try:
        with urllib.request.build_opener(SemRedirect).open(base.rstrip('/')+'/api/v1/demonstracao/estado',timeout=10) as r:
            estado=json.load(r)
    except (OSError,ValueError,http.client.HTTPException):
        raise SystemExit('Não foi possível confirmar a API de demonstração. Nenhum dado foi carregado; inicie compose.demo.yml e tente novamente.') from None
    if estado.get('demo_isolada') is not True or estado.get('modo')!='DEMONSTRACAO_ISOLADA':
        raise SystemExit('O servidor não confirmou banco reservado para demonstração. Nenhum dado foi carregado; use compose.demo.yml.')
    return estado
