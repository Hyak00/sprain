import urllib.request
import json

url_api = 'https://dadosabertos.artesp.sp.gov.br/api/3/action/package_show?id=acidentes'
req = urllib.request.Request(url_api, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as resp:
    dados = json.loads(resp.read().decode('utf-8'))

url_csv = ''
for rec in dados['result']['resources']:
    if rec['format'].upper() == 'CSV':
        url_csv = rec['url']
        break

if url_csv:
    req_csv = urllib.request.Request(url_csv, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req_csv) as resp_csv:
        linhas = resp_csv.read(5000).decode('utf-8-sig', errors='replace').splitlines()
        for linha in linhas[:6]:
            print(linha)