"""Sonda de leitura do ambiente de demonstracao; nao registra/simula viagens."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url', default='http://127.0.0.1:18000')
    args = p.parse_args()
    url = urllib.parse.urlsplit(args.base_url)
    if url.hostname not in ('127.0.0.1', 'localhost', '::1') or url.scheme not in ('http', 'https') or url.username or url.password or url.query or url.fragment:
        p.error('Esta sonda e exclusiva de ambiente local isolado, sem credenciais na URL.')
    chave = os.environ.get('SPRAIN_API_KEY', 'key_viewer_demo')
    resultados = []
    for caminho in ['/api/v1/health/readiness', '/static/b2b.html', '/static/portal-operacional.js',
                    '/api/v1/logistica/operacoes', '/api/v1/logistica/relatorios/sumario-executivo',
                    '/api/v1/indicadores/qualidade', '/api/v1/dados-publicos/fontes', '/api/v1/alertas/precisao',
                    '/api/v1/painel/corredores', '/api/v1/painel/consultas', '/api/v1/painel/eventos',
                    '/static/painel-fluxo.js', '/static/painel-corredores.js', '/static/painel-eventos.js',
                    '/api/v1/acesso/configuracao','/static/painel-homologacao.js',
                    '/api/v1/administracao/financeiro','/static/painel-administracao.js',
                    '/api/v1/painel/relatorios/piloto','/api/v1/painel/relatorios/decisoes',
                    '/static/painel-relatorios.js','/api/v1/demonstracao/estado','/static/painel-demonstracao.js']:
        req = urllib.request.Request(args.base_url.rstrip('/') + caminho, headers={'X-API-Key': chave} if caminho.startswith('/api/') else {})
        try:
            # Nao seguir redirecionamento para outro host com a chave.
            class SemRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *args, **kwargs):
                    return None
            with urllib.request.build_opener(SemRedirect).open(req, timeout=30) as resposta:
                corpo = resposta.read()
                if caminho.startswith('/api/'):
                    json.loads(corpo)
                resultados.append({'endpoint': caminho, 'status': resposta.status, 'ok': True})
        except (urllib.error.URLError, TimeoutError, ValueError):
            resultados.append({'endpoint': caminho, 'ok': False})
    print(json.dumps({'verificado_em': datetime.now(timezone.utc).isoformat(), 'ambiente': 'LOCAL_DEMONSTRACAO', 'resultados': resultados}, ensure_ascii=False, indent=2))
    return 0 if all(r['ok'] for r in resultados) else 1


if __name__ == '__main__':
    sys.exit(main())
