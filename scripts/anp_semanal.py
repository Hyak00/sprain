"""Leitor restrito da planilha publica ANP, sem instalar biblioteca de planilhas."""
import csv
import io
import re
import zipfile
from datetime import date, timedelta
from xml.etree import ElementTree as ET

CATALOGO = 'https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def descobrir_url(html):
    links = re.findall(r'https://www\.gov\.br/anp/[^"\s<>]+/revendas_lpc_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.xlsx', html)
    validos = [item for item in links if date.fromisoformat(item[1]) <= date.today()]
    if not validos:
        raise ValueError('Planilha semanal ANP nao encontrada.')
    inicio, fim = max(validos, key=lambda item: item[1])
    match = re.search(r'https://www\.gov\.br/anp/[^"\s<>]+/revendas_lpc_' + inicio + '_' + fim + r'\.xlsx', html)
    return match.group(0)


def para_csv(dados):
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=';')
    escritor.writerow(['Estado - Sigla','Municipio','Revenda','CNPJ da Revenda','Nome da Rua',
                        'Numero Rua','Produto','Data da Coleta','Valor de Venda','Bairro','Cep'])
    with zipfile.ZipFile(io.BytesIO(dados)) as arquivo:
        if sum(i.file_size for i in arquivo.infolist()) > 150_000_000:
            raise ValueError('Planilha descompactada excede limite de 150 MB.')
        compartilhadas = []
        if 'xl/sharedStrings.xml' in arquivo.namelist():
            raiz = ET.fromstring(arquivo.read('xl/sharedStrings.xml'))
            compartilhadas = [''.join(t.text or '' for t in si.iter(NS+'t')) for si in raiz]
        cabecalho = False
        with arquivo.open('xl/worksheets/sheet1.xml') as planilha:
            for _, elemento in ET.iterparse(planilha, events=('end',)):
                if elemento.tag != NS+'row':
                    continue
                celulas = {}
                for c in elemento.findall(NS+'c'):
                    coluna = re.sub(r'\d', '', c.get('r', ''))
                    valor = c.findtext(NS+'v', '')
                    if c.get('t') == 's':
                        valor = compartilhadas[int(valor)]
                    elif c.get('t') == 'inlineStr':
                        valor = ''.join(t.text or '' for t in c.iter(NS+'t'))
                    celulas[coluna] = valor
                if celulas.get('A') == 'CNPJ':
                    if celulas.get('J') != 'ESTADO' or celulas.get('L') != 'PRODUTO' or celulas.get('O') != 'DATA DA COLETA':
                        raise ValueError('Colunas da planilha semanal ANP mudaram; revisar importador.')
                    cabecalho = True
                elif cabecalho and celulas.get('J') == 'SAO PAULO':
                    coleta = celulas.get('O', '')
                    if re.fullmatch(r'\d+(\.\d+)?', coleta):
                        coleta = (date(1899,12,30) + timedelta(days=int(float(coleta)))).strftime('%d/%m/%Y')
                    escritor.writerow(['SP',celulas.get('I'),celulas.get('B'),celulas.get('A','').zfill(14),
                        celulas.get('D'),celulas.get('E'),celulas.get('L'),coleta,celulas.get('N'),
                        celulas.get('G'),celulas.get('H')])
                elemento.clear()
        if not cabecalho:
            raise ValueError('Cabecalho CNPJ ausente da planilha ANP.')
    return saida.getvalue().encode('utf-8')
