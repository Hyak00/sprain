import argparse
import calendar
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import time as sys_time
import urllib.parse
import urllib.error
import urllib.request
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path

ARTESP_CATALOGO = "https://dadosabertos.artesp.sp.gov.br/api/3/action/package_show?id=acidentes"
ANP_CATALOGO = "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/shpc/dsan"
ANP_CADASTRO = "https://revendedoresapi.anp.gov.br/v1/combustivel?uf=SP"
SSP_TRIMESTRAL = "https://www.ssp.sp.gov.br/assets/estatistica/trimestral/arquivos"
MIGRACAO = Path(__file__).resolve().parents[1] / "db/ci/04_dados_riscos_combustiveis.sql"
MAX_DOWNLOAD = 40000000

def baixar(url: str) -> bytes:
    if urllib.parse.urlparse(url).scheme != "https":
        raise ValueError("A fonte remota deve usar HTTPS.")
    pedido = urllib.request.Request(url, headers={"User-Agent": "SPRain-dados-publicos/1.0"})
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(pedido, timeout=45) as resposta:
                dados = resposta.read(MAX_DOWNLOAD + 1)
            break
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or tentativa == 2:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if tentativa == 2:
                raise
        sys_time.sleep(5 * (tentativa + 1))
    if len(dados) > MAX_DOWNLOAD:
        raise ValueError("Arquivo excede limite.")
    return dados

def texto_csv(dados: bytes) -> str:
    return dados.decode("utf-8-sig", errors="replace")

def _numero(valor: str) -> float:
    numero = float(str(valor).strip().replace(",", "."))
    if not math.isfinite(numero):
        raise ValueError("numero nao finito")
    return numero

def _chave(*campos: object) -> str:
    texto = "|".join(str(campo or "").strip() for campo in campos)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()

def caminhoes_envolvidos(texto: str) -> int:
    total = 0
    for tipo, quantidade in re.findall(r"([^=;,|]+)=\s*(\d+)", texto.upper()):
        tipo = tipo.strip()
        if tipo.startswith("CAMINHONETE"):
            continue
        if tipo.startswith(("CAMINH", "CARRETA", "BITREM")):
            total += int(quantidade)
    return total

EQUIVALENCIAS_ARTESP = {
    "BOM": "BOA",
    "ANIZO": "GRANIZO",
    "N\u00c3O IDENT": "N\u00c3O INFORMADO",
    "N\u00c3O IDENTIFICADO": "N\u00c3O INFORMADO",
    "NEBLINA/NEVOEIRO": "NEBLINA",
}

def _maiusculas(texto) -> str:
    return (texto or "").strip().upper()

def _padronizar(texto) -> str:
    limpo = re.sub(r"^\d+\s+", "", _maiusculas(texto))
    return EQUIVALENCIAS_ARTESP.get(limpo, limpo)

def _data_artesp(texto: str) -> date:
    texto = texto.strip().split(" ")[0]
    if "/" in texto:
        dia, mes, ano = texto.split("/")
        return date(int(ano), int(mes), int(dia))
    return date.fromisoformat(texto)

def _rodovia_artesp(texto: str) -> str:
    bruta = texto.strip().upper()
    limpa = re.sub(r"[\s-]", "", bruta)
    principal = re.fullmatch(r"SP(\d{1,3})", limpa)
    return f"SP-{principal.group(1)}" if principal else bruta

def ler_artesp(dados: bytes, url_fonte: str) -> tuple[list[dict], dict]:
    texto = texto_csv(dados)
    primeira = texto.splitlines()[0] if texto else ""
    separador = ";" if primeira.count(";") > primeira.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto, newline=""), delimiter=separador)
    campos = leitor.fieldnames or []
    exigidos = {"DATA", "HORA", "RODOVIA", "KM", "SENTIDO", "LATITUDE", "LONGITUDE",
                "CLASSE", "SUBCLASSE", "MUNICIPIO", "VEICULOS_ENVOLVIDOS"}
    faltando = sorted(exigidos - set(campos))
    if faltando:
        raise ValueError(f"Colunas ARTESP ausentes: {faltando}. Lidas: {campos}")
    registros: dict[str, dict] = {}
    resumo = {"linhas": 0, "invalidos": 0, "sem_km": 0, "sem_caminhao": 0,
              "sem_coordenadas": 0, "duplicados": 0, "com_caminhao": 0}
    for linha in leitor:
        resumo["linhas"] += 1
        try:
            data = _data_artesp(linha["DATA"] or "")
            hora_texto = (linha["HORA"] or "").strip()
            hora = time.fromisoformat(hora_texto) if hora_texto else None
            km_texto = (linha["KM"] or "").strip()
            km = _numero(km_texto) if km_texto else None
        except (ValueError, TypeError):
            resumo["invalidos"] += 1
            continue
        if km is None:
            resumo["sem_km"] += 1
            continue
        veiculos = (linha["VEICULOS_ENVOLVIDOS"] or "").strip()
        caminhoes = caminhoes_envolvidos(veiculos)
        if caminhoes == 0:
            resumo["sem_caminhao"] += 1
            continue
        latitude = longitude = None
        try:
            lat, lon = _numero(linha["LATITUDE"]), _numero(linha["LONGITUDE"])
            if -26 <= lat <= -19 and -54 <= lon <= -44:
                latitude, longitude = lat, lon
        except (ValueError, TypeError):
            pass
        if latitude is None:
            resumo["sem_coordenadas"] += 1
            continue
        rodovia = _rodovia_artesp(linha["RODOVIA"] or "")
        sentido = _maiusculas(linha["SENTIDO"])
        classe = _maiusculas(linha["CLASSE"])
        subclasse = _maiusculas(linha["SUBCLASSE"])
        chave = _chave(data, hora, rodovia, km, sentido, classe, subclasse, veiculos, latitude, longitude)
        if chave in registros:
            resumo["duplicados"] += 1
            continue
        registros[chave] = {
            "id_fonte": chave, "data": data, "hora": hora, "rodovia": rodovia, "km": km,
            "sentido": sentido, "municipio": _maiusculas(linha["MUNICIPIO"]),
            "classe": classe, "subclasse": subclasse, "caminhoes": caminhoes,
            "veiculos": veiculos, "url_fonte": url_fonte,
            "latitude": latitude, "longitude": longitude,
            "condicao": _padronizar(linha.get("CONDICAO_METERIOLOGICA")) or None,
            "visibilidade": _padronizar(linha.get("VISIBILIDADE")) or None,
        }
    resumo["com_caminhao"] = len(registros)
    return list(registros.values()), resumo

def ler_anp(dados: bytes, url_fonte: str, uf: str = "SP") -> tuple[list[dict], dict]:
    leitor = csv.DictReader(io.StringIO(texto_csv(dados), newline=""), delimiter=";")
    exigidos = {"Estado - Sigla", "Municipio", "Revenda", "CNPJ da Revenda", "Nome da Rua",
                "Produto", "Data da Coleta", "Valor de Venda"}
    if not exigidos.issubset(leitor.fieldnames or []):
        raise ValueError("Colunas ANP ausentes")
    registros: list[dict] = []
    resumo = {"linhas": 0, "precos_validos": 0, "invalidos": 0}
    for linha in leitor:
        resumo["linhas"] += 1
        if (linha.get("Estado - Sigla") or "").strip().upper() != uf.upper():
            continue
        try:
            cnpj = re.sub(r"\D", "", linha.get("CNPJ da Revenda") or "")
            if len(cnpj) != 14:
                raise ValueError("CNPJ invalido")
            data = datetime.strptime((linha.get("Data da Coleta") or "").strip(), "%d/%m/%Y").date()
            preco = Decimal((linha.get("Valor de Venda") or "").strip().replace(",", "."))
            if not preco.is_finite() or preco <= 0:
                raise ValueError("preco invalido")
            if not (linha.get("Revenda") or "").strip() or not (linha.get("Produto") or "").strip():
                raise ValueError("posto ou produto ausente")
        except (ValueError, InvalidOperation):
            resumo["invalidos"] += 1
            continue
        rua = (linha.get("Nome da Rua") or "").strip()
        numero = (linha.get("Numero Rua") or "").strip()
        registros.append({
            "cnpj": cnpj, "nome": (linha.get("Revenda") or "").strip(), "uf": uf.upper(),
            "municipio": (linha.get("Municipio") or "").strip(),
            "endereco": f"{rua}, {numero}".strip(" ,"),
            "bairro": (linha.get("Bairro") or "").strip(), "cep": (linha.get("Cep") or "").strip(),
            "produto": (linha.get("Produto") or "").strip().upper(), "data": data,
            "preco": preco, "url_fonte": url_fonte,
        })
    resumo["precos_validos"] = len(registros)
    return registros, resumo

def baixar_cadastro_anp() -> bytes:
    paginas = []
    primeira = json.loads(baixar(ANP_CADASTRO + "&numeropagina=1"))
    filtro = primeira.get("searchPageFilter") or {}
    total = int(filtro.get("totalPagina", 0))
    if not primeira.get("succeeded") or not 1 <= total <= 20:
        raise ValueError("Paginacao da API cadastral ANP inesperada.")
    paginas.append(primeira)
    for pagina in range(2, total + 1):
        seguinte = json.loads(baixar(ANP_CADASTRO + f"&numeropagina={pagina}"))
        if not seguinte.get("succeeded") or seguinte.get("searchPageFilter", {}).get("numeroPagina") != pagina:
            raise ValueError("Resposta da API cadastral ANP nao corresponde a pagina solicitada.")
        paginas.append(seguinte)
    registros = [item for pagina in paginas for item in pagina.get("data", [])]
    if len(registros) != int(filtro.get("totalRegistro", 0)):
        raise ValueError("Quantidade de postos cadastrais ANP mudou durante a paginacao.")
    return json.dumps({"data": registros}, ensure_ascii=False, sort_keys=True).encode("utf-8")

def ler_anp_cadastro(dados: bytes) -> tuple[list[dict], dict]:
    documento = json.loads(texto_csv(dados))
    itens = documento.get("data")
    if not isinstance(itens, list):
        raise ValueError("Formato cadastral ANP inesperado.")
    registros = {}
    resumo = {"postos": 0, "coordenadas_candidatas_nao_validadas": 0, "sem_coordenadas": 0,
              "coordenadas_rejeitadas": 0}
    for item in itens:
        cnpj = re.sub(r"\D", "", str(item.get("cnpj") or ""))
        if len(cnpj) != 14 or item.get("uf") != "SP" or not item.get("razaoSocial"):
            raise ValueError("Cadastro ANP contem CNPJ, UF ou nome invalido.")
        latitude = longitude = None
        srid = str(item.get("srid") or "").strip()
        if item.get("latitude") and item.get("longitude"):
            try:
                latitude, longitude = _numero(item["latitude"]), _numero(item["longitude"])
                if not (-26 <= latitude <= -19 and -54 <= longitude <= -44) or srid not in {"4326", "4674"}:
                    raise ValueError("coordenada fora de SP ou SRID inesperado")
                resumo["coordenadas_candidatas_nao_validadas"] += 1
            except (ValueError, TypeError):
                latitude = longitude = None
                resumo["coordenadas_rejeitadas"] += 1
        else:
            resumo["sem_coordenadas"] += 1
        acuracia = None
        if item.get("estimativaAcuracia"):
            try:
                valor = _numero(item["estimativaAcuracia"])
                acuracia = valor if 0 < valor <= 1000 else None
            except (ValueError, TypeError):
                pass
        obtida = None
        if item.get("dataObtencao"):
            try:
                obtida = datetime.strptime(item["dataObtencao"], "%d/%m/%Y").date()
            except ValueError:
                pass
        registros[cnpj] = {"cnpj": cnpj, "nome": item["razaoSocial"].strip(),
                           "uf": "SP", "municipio": str(item.get("municipio") or "").strip(),
                           "endereco": str(item.get("endereco") or "").strip(),
                           "bairro": str(item.get("bairro") or "").strip(),
                           "cep": str(item.get("cep") or "").strip(),
                           "latitude": latitude, "longitude": longitude, "srid": srid,
                           "acuracia": acuracia, "obtida": obtida,
                           "url_fonte": "https://revendedoresapi.anp.gov.br/v1/combustivel?cnpj=" + cnpj}
    resumo["postos"] = len(registros)
    return list(registros.values()), resumo

def ler_coordenadas_postos(dados: bytes) -> tuple[list[dict], dict]:
    leitor = csv.DictReader(io.StringIO(texto_csv(dados), newline=""))
    exigidos = {"cnpj", "latitude", "longitude", "fonte", "verificado_em"}
    if not exigidos.issubset(leitor.fieldnames or []):
        raise ValueError("Colunas de coordenadas ausentes")
    registros = []
    for linha in leitor:
        cnpj = re.sub(r"\D", "", linha["cnpj"])
        latitude = _numero(linha["latitude"])
        longitude = _numero(linha["longitude"])
        fonte = linha["fonte"].strip()
        verificado_em = datetime.fromisoformat(linha["verificado_em"].strip())
        if (len(cnpj) != 14 or not (-90 <= latitude <= 90 and -180 <= longitude <= 180)
                or not fonte.startswith("https://") or verificado_em.utcoffset() is None
                or verificado_em > datetime.now(timezone.utc)):
            raise ValueError("Coordenada de posto invalida ou sem fonte data verificavel.")
        registros.append({"cnpj": cnpj, "latitude": latitude, "longitude": longitude,
                          "fonte": fonte, "verificado_em": verificado_em})
    return registros, {"coordenadas_verificadas": len(registros)}

def ler_roubo_agregado(dados: bytes, url_fonte: str) -> tuple[list[dict], dict]:
    leitor = csv.DictReader(io.StringIO(texto_csv(dados), newline=""))
    exigidos = {"nivel_geografico", "area", "periodo_inicio", "periodo_fim", "ocorrencias"}
    if not exigidos.issubset(leitor.fieldnames or []):
        raise ValueError("Colunas de roubo ausentes")
    registros = []
    for linha in leitor:
        nivel = linha["nivel_geografico"].strip().upper()
        area = linha["area"].strip()
        inicio = date.fromisoformat(linha["periodo_inicio"].strip())
        fim = date.fromisoformat(linha["periodo_fim"].strip())
        quantidade = int(linha["ocorrencias"])
        if nivel not in {"ESTADO", "REGIAO", "MUNICIPIO"} or not area or fim < inicio or quantidade < 0:
            raise ValueError("Agregado de roubo invalido.")
        registros.append({"id_fonte": _chave(url_fonte, nivel, area, inicio, fim),
                          "nivel": nivel, "area": area, "inicio": inicio, "fim": fim,
                          "ocorrencias": quantidade, "url_fonte": url_fonte})
    return registros, {"agregados": len(registros), "sem_localizacao_pontual": len(registros)}

class _TabelaSSP(HTMLParser):
    def __init__(self):
        super().__init__()
        self.linhas: list[list[str]] = []
        self.linha: list[str] | None = None
        self.celula: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.linha = []
        elif tag in {"td", "th"} and self.linha is not None:
            self.celula = []

    def handle_data(self, dado):
        if self.celula is not None:
            self.celula.append(dado)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.celula is not None and self.linha is not None:
            self.linha.append(" ".join("".join(self.celula).split()))
            self.celula = None
        elif tag == "tr" and self.linha is not None:
            if self.linha:
                self.linhas.append(self.linha)
            self.linha = None

def ler_ssp_trimestral(dados: bytes, url_fonte: str) -> tuple[list[dict], dict]:
    match = re.search(r"/(20\d{2})-(0[1-4])\.htm$", url_fonte)
    if not match or not url_fonte.startswith(SSP_TRIMESTRAL + "/"):
        raise ValueError("URL SSP trimestral inesperada.")
    ano, trimestre = map(int, match.groups())
    tabela = _TabelaSSP()
    tabela.feed(texto_csv(dados))
    cabecalhos = [linha for linha in tabela.linhas if "Capital" in linha and "Deinter 1" in linha and "Estado" in linha]
    roubos = [linha for linha in tabela.linhas if "Roubo de Carga" in linha]
    if not cabecalhos or len(roubos) != 1:
        raise ValueError("Tabela SSP de roubo de carga nao encontrada ou ambigua.")
    cabecalho, linha = cabecalhos[0], roubos[0]
    if len(cabecalho) != len(linha):
        raise ValueError("Colunas SSP nao correspondem ao cabecalho.")
    valores = {nome: int(valor.replace(".", "")) for nome, valor in zip(cabecalho[2:], linha[2:])}
    nomes = {"Capital": "CAPITAL", "Gde SP(1)": "GRANDE SP",
             **{f"Deinter {n}": f"DEINTER {n}" for n in range(1, 11)}}
    if not set(nomes).issubset(valores) or "Estado" not in valores or "Interior" not in valores:
        raise ValueError("Regioes SSP ausentes do trimestre.")
    if sum(valores[nome] for nome in nomes) != valores["Estado"]:
        raise ValueError("Soma das regioes SSP difere do total do estado.")
    mes_inicio, mes_fim = (trimestre - 1) * 3 + 1, trimestre * 3
    inicio = date(ano, mes_inicio, 1)
    fim = date(ano, mes_fim, calendar.monthrange(ano, mes_fim)[1])
    registros = []
    for nome, area in [*nomes.items(), ("Estado", "SAO PAULO")]:
        nivel = "ESTADO" if nome == "Estado" else "REGIAO"
        registros.append({"id_fonte": _chave(url_fonte, nivel, area, inicio, fim),
                          "nivel": nivel, "area": area, "inicio": inicio, "fim": fim,
                          "ocorrencias": valores[nome], "url_fonte": url_fonte})
    return registros, {"trimestre": f"{ano}-Q{trimestre}", "total_estado": valores["Estado"],
                       "regioes_disjuntas": len(nomes), "agregados": len(registros)}

class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.extend(valor for chave, valor in attrs if chave == "href" and valor)

def fontes_artesp(anos: list[int]) -> list[tuple[int, str]]:
    catalogo = json.loads(baixar(ARTESP_CATALOGO))["result"]["resources"]
    urls = []
    for ano in anos:
        candidatos = [r for r in catalogo if r.get("name", "").strip() == f"Acidentes em {ano}"
                      and r.get("format", "").upper() == "CSV"]
        if not candidatos:
            continue
        urls.append((ano, candidatos[0]["url"]))
    if not urls:
        raise ValueError("CSV de acidentes ARTESP ausente do catalogo para os anos informados.")
    return urls

def fontes_anp(ano: int) -> list[str]:
    links: set[str] = set()
    for inicio in range(0, 100, 20):
        pagina = f"{ANP_CATALOGO}/{ano}?b_start:int={inicio}"
        parser = _Links()
        parser.feed(baixar(pagina).decode("utf-8", errors="replace"))
        novos = {urllib.parse.urljoin(pagina, link) for link in parser.links
                 if f"/dsan/{ano}/" in link and ".csv/view" in link.lower()
                 and ("diesel" in link.lower() or "gasolina" in link.lower())}
        links.update(novos)
        if inicio and not novos:
            break
    escolhidos = []
    for produto in ("diesel", "gasolina"):
        candidatos = [url for url in links if produto in url.lower()]
        if not candidatos:
            raise ValueError("CSV ANP ausente do catalogo.")
        def mes(url):
            nome = urllib.parse.urlparse(url).path.split("/")[-2]
            encontrado = re.match(r"(\d{2})-", nome)
            return int(encontrado.group(1)) if encontrado else -1
        ultimo = max(candidatos, key=lambda url: (mes(url), url))
        escolhidos.append(ultimo.replace("/view", "/@@download/file"))
    return escolhidos

def arquivos_ssp(anos: list[int]) -> list[tuple[str, bytes]]:
    arquivos = []
    for ano in anos:
        for trimestre in range(1, 5):
            if ano == date.today().year and trimestre > (date.today().month - 1) // 3 + 1:
                break
            url = f"{SSP_TRIMESTRAL}/{ano}-{trimestre:02d}.htm"
            try:
                arquivos.append((url, baixar(url)))
            except urllib.error.HTTPError as exc:
                if exc.code == 404 and ano == date.today().year:
                    continue
                raise
    if not arquivos:
        raise ValueError("Nenhum trimestre SSP oficial disponivel.")
    return arquivos

def conectar():
    import psycopg2
    nomes = ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME")
    ausentes = [nome for nome in nomes if not os.getenv(nome)]
    if ausentes:
        raise ValueError("Configure variaveis de ambiente de banco antes de usar --aplicar.")
    return psycopg2.connect(host=os.environ["DB_HOST"], port=os.environ["DB_PORT"],
                            user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                            dbname=os.environ["DB_NAME"], connect_timeout=10)

def aplicar(fonte: str, url: str, dados: bytes, registros: list[dict], resumo: dict):
    from psycopg2.extras import execute_values
    sha = hashlib.sha256(dados).hexdigest()
    with conectar() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '120s'")
            cursor.execute(MIGRACAO.read_text(encoding="utf-8"))
            cursor.execute("SELECT hash_sha256,registros_importados FROM fontes_dados_externos WHERE nome=%s", (fonte,))
            anterior = cursor.fetchone()
            if anterior and anterior[0] == sha and anterior[1] == len(registros):
                cursor.execute("UPDATE fontes_dados_externos SET ultimo_sucesso_em=now() WHERE nome=%s", (fonte,))
                return {"fonte": fonte, "sem_alteracoes": True, "registros": len(registros)}
            if fonte.startswith("ARTESP"):
                if not registros or (anterior and anterior[1] and len(registros) < anterior[1] / 2):
                    raise ValueError("Arquivo ARTESP vazio ou com queda superior a 50 porcento")
                cursor.execute("UPDATE tombamentos_caminhao SET ativo=false WHERE url_fonte=%s", (url,))
                valores = [(r["id_fonte"], r["data"], r["hora"], r["rodovia"], r["km"], r["sentido"],
                            r["municipio"], r["classe"], r["subclasse"], r["caminhoes"], r["veiculos"],
                            r["url_fonte"], r["condicao"], r["visibilidade"],
                            r["longitude"], r["longitude"], r["latitude"])
                           for r in registros]
                execute_values(cursor, "INSERT INTO tombamentos_caminhao "
                    "(id_fonte,data_ocorrencia,hora_ocorrencia,rodovia,km,sentido,municipio,classe,subclasse,"
                    "caminhoes_envolvidos,veiculos_envolvidos,url_fonte,condicao_meteorologica,visibilidade,geom) VALUES %s "
                    "ON CONFLICT (id_fonte) DO UPDATE SET ativo=true,url_fonte=EXCLUDED.url_fonte,"
                    "rodovia=EXCLUDED.rodovia,km=EXCLUDED.km,municipio=EXCLUDED.municipio,"
                    "classe=EXCLUDED.classe,subclasse=EXCLUDED.subclasse,"
                    "caminhoes_envolvidos=EXCLUDED.caminhoes_envolvidos,"
                    "veiculos_envolvidos=EXCLUDED.veiculos_envolvidos,"
                    "condicao_meteorologica=EXCLUDED.condicao_meteorologica,"
                    "visibilidade=EXCLUDED.visibilidade,geom=EXCLUDED.geom", valores,
                    template="(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                             "CASE WHEN %s::float8 IS NULL THEN NULL "
                             "ELSE ST_SetSRID(ST_MakePoint(%s::float8,%s::float8),4326) END)")
            elif fonte.startswith("ANP"):
                if fonte == "ANP_CADASTRO":
                    postos = {r["cnpj"]: r for r in registros}
                    valores_postos = [(r["cnpj"], r["nome"], r["uf"], r["municipio"], r["endereco"],
                                      r["bairro"], r["cep"]) for r in postos.values()]
                    if valores_postos:
                        execute_values(cursor, "INSERT INTO postos_combustivel "
                            "(cnpj,nome,uf,municipio,endereco,bairro,cep) VALUES %s "
                            "ON CONFLICT (cnpj) DO UPDATE SET nome=EXCLUDED.nome,uf=EXCLUDED.uf,"
                            "municipio=EXCLUDED.municipio,endereco=EXCLUDED.endereco,bairro=EXCLUDED.bairro,"
                            "cep=EXCLUDED.cep,atualizado_em=now()", valores_postos)
                    candidatos = [(r["cnpj"], r["longitude"], r["latitude"], int(r["srid"]),
                                   r["url_fonte"], r["obtida"], r["acuracia"])
                                  for r in registros if r["latitude"] is not None]
                    if candidatos:
                        execute_values(cursor, "UPDATE postos_combustivel p SET "
                            "geom=ST_Transform(ST_SetSRID(ST_MakePoint(v.longitude::float8,"
                              "v.latitude::float8),v.srid::integer),4326),"
                            "localizacao_fonte=v.fonte,localizacao_obtida_em=v.obtida::date,"
                            "localizacao_acuracia_m=v.acuracia::numeric,"
                            "localizacao_validacao='NAO_VALIDADA_PELA_ANP',atualizado_em=now() "
                            "FROM (VALUES %s) AS v(cnpj,longitude,latitude,srid,fonte,obtida,acuracia) "
                            "WHERE p.cnpj=v.cnpj AND p.localizacao_verificada_em IS NULL "
                              "AND (p.localizacao_obtida_em IS NULL OR v.obtida::date IS NULL "
                                   "OR v.obtida::date >= p.localizacao_obtida_em)", candidatos)
                else:
                    postos = {r["cnpj"]: r for r in registros}
                    valores_postos = [(r["cnpj"], r["nome"], r["uf"], r["municipio"], r["endereco"],
                                      r["bairro"], r["cep"]) for r in postos.values()]
                    if valores_postos:
                        execute_values(cursor, "INSERT INTO postos_combustivel "
                            "(cnpj,nome,uf,municipio,endereco,bairro,cep) VALUES %s "
                            "ON CONFLICT (cnpj) DO UPDATE SET nome=EXCLUDED.nome,uf=EXCLUDED.uf,"
                            "municipio=EXCLUDED.municipio,endereco=EXCLUDED.endereco,bairro=EXCLUDED.bairro,"
                            "cep=EXCLUDED.cep,atualizado_em=now()", valores_postos)
                    precos = {(r["cnpj"], r["produto"], r["data"]): r for r in registros}
                    valores_preco = [(r["cnpj"], r["produto"], r["data"], r["preco"], r["url_fonte"])
                                     for r in precos.values()]
                    if valores_preco:
                        execute_values(cursor, "INSERT INTO precos_combustivel "
                            "(cnpj,produto,data_coleta,preco_litro,url_fonte) VALUES %s "
                            "ON CONFLICT (cnpj,produto,data_coleta) DO UPDATE SET "
                            "preco_litro=EXCLUDED.preco_litro,url_fonte=EXCLUDED.url_fonte", valores_preco)
            elif fonte in {"ROUBO_CARGA", "SSP_ROUBO"} or fonte.startswith("SSP_ROUBO_"):
                valores = [(r["id_fonte"], r["nivel"], r["area"], r["inicio"], r["fim"],
                            r["ocorrencias"], r["url_fonte"]) for r in registros]
                if valores:
                    execute_values(cursor, "INSERT INTO roubo_carga_agregados "
                        "(id_fonte,nivel_geografico,area,periodo_inicio,periodo_fim,ocorrencias,url_fonte) "
                        "VALUES %s ON CONFLICT (id_fonte) DO UPDATE SET ocorrencias=EXCLUDED.ocorrencias", valores)
            elif fonte == "COORDENADAS_POSTOS":
                for r in registros:
                    cursor.execute("UPDATE postos_combustivel SET "
                        "geom=ST_SetSRID(ST_MakePoint(%s,%s),4326),localizacao_fonte=%s,"
                        "localizacao_verificada_em=%s,localizacao_obtida_em=%s::timestamptz::date,"
                        "localizacao_acuracia_m=NULL,localizacao_validacao='CONFERIDA',atualizado_em=now() "
                        "WHERE cnpj=%s AND (localizacao_verificada_em IS NULL OR localizacao_verificada_em <= %s)",
                        (r["longitude"], r["latitude"], r["fonte"], r["verificado_em"], r["verificado_em"],
                         r["cnpj"], r["verificado_em"]))
            else:
                raise ValueError("Fonte inesperada")
            cursor.execute("INSERT INTO fontes_dados_externos "
                "(nome,url,hash_sha256,registros_importados,resumo_importacao) VALUES (%s,%s,%s,%s,%s::jsonb) "
                "ON CONFLICT (nome) DO UPDATE SET url=EXCLUDED.url,hash_sha256=EXCLUDED.hash_sha256,"
                "registros_importados=EXCLUDED.registros_importados,"
                "resumo_importacao=EXCLUDED.resumo_importacao,ultimo_sucesso_em=now()",
                (fonte, url, sha, len(registros), json.dumps(resumo)))
    return {"fonte": fonte, "sem_alteracoes": False, "registros": len(registros)}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fonte", choices=("artesp", "anp", "anp-semanal", "anp-cadastro", "ssp-roubo", "roubo-carga", "coordenadas-postos", "todas"))
    parser.add_argument("--anos", nargs="+", type=int, help="Anos ARTESP; padrao: atual e dois anteriores")
    parser.add_argument("--anos-ssp", nargs="+", type=int, help="Anos SSP; padrao: atual e anterior")
    parser.add_argument("--arquivo", type=Path, help="CSV local para uma unica fonte")
    parser.add_argument("--url-fonte", help="URL oficial do CSV local ou URL para baixar")
    parser.add_argument("--aplicar", action="store_true", help="Grava em tabelas novas; padrao: so valida")
    args = parser.parse_args()
    if args.fonte == "todas" and (args.arquivo or args.url_fonte):
        parser.error("--arquivo e --url-fonte exigem uma unica fonte.")
    if args.fonte == "roubo-carga" and (not args.arquivo or not args.url_fonte):
        parser.error("Roubo de carga requer CSV agregado oficial e --url-fonte.")
    if args.fonte == "coordenadas-postos" and not args.arquivo:
        parser.error("Coordenadas de postos requerem CSV conferido com fonte por linha.")
    if args.fonte == "anp-cadastro" and (args.arquivo or args.url_fonte):
        parser.error("Cadastro ANP deve ser consultado diretamente na API oficial.")
    if args.arquivo and not args.url_fonte and args.fonte != "coordenadas-postos":
        parser.error("Informe --url-fonte para registrar a procedencia do arquivo.")
    if args.url_fonte and urllib.parse.urlparse(args.url_fonte).scheme != "https":
        parser.error("--url-fonte deve ser uma URL HTTPS verificavel.")


    tarefas: list[tuple[str, str, bytes]] = []
    if args.arquivo:
        tarefas.append((args.fonte.upper().replace("-", "_"), args.url_fonte or "FONTES_POR_LINHA",
                        args.arquivo.read_bytes()))
    elif args.url_fonte:
        tarefas.append((args.fonte.upper().replace("-", "_"), args.url_fonte, baixar(args.url_fonte)))
    else:
        if args.fonte in ("artesp", "todas"):
            anos = args.anos or list(range(date.today().year - 2, date.today().year + 1))
            for ano, url in fontes_artesp(anos):
                tarefas.append((f"ARTESP_{ano}", url, baixar(url)))
        if args.fonte in ("anp", "todas"):
            for url in fontes_anp(date.today().year):
                produto = "DIESEL" if "diesel" in url.lower() else "GASOLINA"
                tarefas.append((f"ANP_{produto}", url, baixar(url)))
        if args.fonte in ("anp-semanal", "todas"):
            from anp_semanal import CATALOGO, descobrir_url
            url = descobrir_url(baixar(CATALOGO).decode('utf-8'))
            tarefas.append(('ANP_SEMANAL', url, baixar(url)))
        if args.fonte in ("anp-cadastro", "todas"):
            tarefas.append(("ANP_CADASTRO", ANP_CADASTRO, baixar_cadastro_anp()))
        if args.fonte in ("ssp-roubo", "todas"):
            for url, dados in arquivos_ssp(args.anos_ssp or [date.today().year - 1, date.today().year]):
                match = re.search(r"/(20\d{2})-(0[1-4])\.htm$", url)
                assert match is not None
                tarefas.append((f"SSP_ROUBO_{match.group(1)}_Q{int(match.group(2))}", url, dados))

    resultados = []
    for fonte, url, dados in tarefas:
        if fonte.startswith("ARTESP"):
            registros, resumo = ler_artesp(dados, url)
        elif fonte == "ANP_CADASTRO":
            registros, resumo = ler_anp_cadastro(dados)
        elif fonte == 'ANP_SEMANAL':
            from anp_semanal import para_csv
            registros, resumo = ler_anp(para_csv(dados), url)
            if not registros or resumo['invalidos']:
                raise ValueError('Planilha semanal ANP vazia ou com linhas invalidas; importacao cancelada.')
        elif fonte.startswith("ANP"):
            registros, resumo = ler_anp(dados, url)
        elif fonte == "COORDENADAS_POSTOS":
            registros, resumo = ler_coordenadas_postos(dados)
        elif fonte == "SSP_ROUBO" or fonte.startswith("SSP_ROUBO_"):
            registros, resumo = ler_ssp_trimestral(dados, url)
        else:
            registros, resumo = ler_roubo_agregado(dados, url)
        resultado = {"fonte": fonte, "url": url, "sha256": hashlib.sha256(dados).hexdigest(),
                     "resumo": resumo, "gravado": False}
        if args.aplicar:
            resultado.update(aplicar(fonte, url, dados, registros, resumo))
            resultado["gravado"] = True
        resultados.append(resultado)
    print(json.dumps(resultados, ensure_ascii=False, default=str, indent=2))

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Falha na sincronizacao: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc