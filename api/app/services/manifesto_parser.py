from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

MAX_TAMANHO_BYTES = 5 * 1024 * 1024
MAX_LINHAS = 2000
MAX_ERROS_RELATORIO = 200

FUSO_SP = ZoneInfo("America/Sao_Paulo")

SINONIMOS_CABECALHO: Dict[str, List[str]] = {
    "placa": ["placa", "placa_do_veiculo", "veiculo", "placa_veiculo"],
    "data_saida": ["data_saida", "data_de_saida", "data", "saida", "data_viagem"],
    "hora_saida": ["hora_saida", "hora_de_saida", "hora", "horario", "horario_saida", "horario_de_saida"],
    "origem": ["origem", "de", "cidade_origem", "local_origem", "partida"],
    "destino": ["destino", "para", "cidade_destino", "local_destino", "chegada"],
    "motorista": ["motorista", "nome_motorista", "condutor", "nome_condutor"],
    "telefone_motorista": ["telefone_motorista", "telefone", "celular", "contato_motorista", "tel_motorista", "celular_motorista"],
    "observacao": ["observacao", "observacoes", "obs", "nota", "notas"]
}

COLUNAS_OBRIGATORIAS: Tuple[str, ...] = ("placa", "data_saida", "hora_saida", "origem", "destino")

REGEX_PLACA_ANTIGA = re.compile(r"^[A-Z]{3}[0-9]{4}$")
REGEX_PLACA_MERCOSUL = re.compile(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$")
PREPOSICOES: Set[str] = {"de", "da", "do", "das", "dos", "e"}


def _detectar_encoding(conteudo_bytes: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            conteudo_bytes.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def _detectar_separador(primeira_linha: str) -> str:
    contagens = {
        ";": primeira_linha.count(";"),
        ",": primeira_linha.count(","),
        "\t": primeira_linha.count("\t")
    }
    separador_escolhido = max(contagens, key=contagens.get)
    return separador_escolhido if contagens[separador_escolhido] > 0 else ","


def _normalizar_texto(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    limpo = re.sub(r"[^a-zA-Z0-9]+", "_", sem_acento.strip().lower())
    return limpo.strip("_")


def _capitalizar_localidade(texto: str) -> str:
    palavras = re.sub(r"\s+", " ", texto.strip()).split(" ")
    resultado = []
    for i, p in enumerate(palavras):
        p_lower = p.lower()
        if i > 0 and p_lower in PREPOSICOES:
            resultado.append(p_lower)
        else:
            resultado.append(p.capitalize())
    return " ".join(resultado)


def _contem_injecao_csv(valor: str) -> bool:
    if not valor:
        return False
    primeiro = valor.strip()[:1]
    return primeiro in ("=", "+", "-", "@")


def _validar_placa(bruto: str) -> Tuple[bool, str, str]:
    if _contem_injecao_csv(bruto):
        return False, "", "Valor contem caractere suspeito de formula (=, +, -, @)."
    limpo = re.sub(r"[\s\-]+", "", bruto.strip().upper())
    if REGEX_PLACA_ANTIGA.match(limpo) or REGEX_PLACA_MERCOSUL.match(limpo):
        return True, limpo, ""
    return False, bruto.strip(), "Placa invalida. Use o formato ABC1234 ou ABC1D23."


def _validar_data(bruto: str) -> Tuple[bool, Optional[date], str]:
    if _contem_injecao_csv(bruto):
        return False, None, "Valor contem caractere suspeito de formula (=, +, -, @)."
    texto = bruto.strip()
    if "/" in texto:
        partes = texto.split("/")
        if len(partes) != 3:
            return False, None, "Data invalida. Use o formato DD/MM/AAAA."
        dia_s, mes_s, ano_s = partes
        try:
            dia = int(dia_s)
            mes = int(mes_s)
            ano = int(ano_s)
            if ano < 100:
                ano = 2000 + ano
            d = date(ano, mes, dia)
            return True, d, ""
        except ValueError:
            return False, None, "Data invalida ou inexistente no calendario (ex: 31/02)."
    elif "-" in texto:
        partes = texto.split("-")
        if len(partes) != 3:
            return False, None, "Data invalida. Use o formato AAAA-MM-DD."
        ano_s, mes_s, dia_s = partes
        try:
            ano = int(ano_s)
            mes = int(mes_s)
            dia = int(dia_s)
            d = date(ano, mes, dia)
            return True, d, ""
        except ValueError:
            return False, None, "Data invalida ou inexistente no calendario."
    return False, None, "Data invalida. Use o formato DD/MM/AAAA ou AAAA-MM-DD."


def _validar_hora(bruto: str) -> Tuple[bool, Optional[time], str]:
    if _contem_injecao_csv(bruto):
        return False, None, "Valor contem caractere suspeito de formula (=, +, -, @)."
    texto = bruto.strip()
    partes = texto.split(":")
    if len(partes) not in (2, 3):
        return False, None, "Horario invalido. Use o formato HH:MM."
    try:
        hora = int(partes[0])
        minuto = int(partes[1])
        segundo = int(partes[2]) if len(partes) == 3 else 0
        h = time(hora, minuto, segundo)
        return True, h, ""
    except ValueError:
        return False, None, "Horario invalido. Use valores entre 00:00 e 23:59."


def _validar_telefone(bruto: str) -> Tuple[bool, Optional[str], str]:
    if not bruto or not bruto.strip():
        return True, None, ""
    if _contem_injecao_csv(bruto):
        return False, None, "Telefone contem caracteres suspeitos de formula."
    so_digitos = re.sub(r"\D", "", bruto)
    if so_digitos.startswith("55") and len(so_digitos) in (12, 13):
        so_digitos = so_digitos[2:]
    if len(so_digitos) in (10, 11):
        return True, so_digitos, ""
    return False, None, "Telefone com formato estranho; sera ignorado."


def parse_manifesto_csv(
    conteudo_bytes: bytes,
    tenant_id: str = "demo_corp",
    viagens_existentes: Optional[Set[Tuple[str, str, str]]] = None,
    referencia_agora: Optional[datetime] = None
) -> Dict[str, Any]:
    if viagens_existentes is None:
        viagens_existentes = set()

    if not conteudo_bytes or len(conteudo_bytes.strip()) == 0:
        return {
            "resumo": {"total_linhas": 0, "validas": 0, "com_aviso": 0, "rejeitadas": 0, "duplicadas": 0, "ja_cadastradas": 0},
            "colunas_ignoradas": [],
            "linhas_validas": [],
            "erros": [{"linha": 1, "campo": "arquivo", "valor": "", "mensagem": "Arquivo vazio. Envie um arquivo CSV preenchido."}],
            "avisos": [],
            "importadas": 0
        }

    if len(conteudo_bytes) > MAX_TAMANHO_BYTES:
        return {
            "resumo": {"total_linhas": 0, "validas": 0, "com_aviso": 0, "rejeitadas": 0, "duplicadas": 0, "ja_cadastradas": 0},
            "colunas_ignoradas": [],
            "linhas_validas": [],
            "erros": [{"linha": 1, "campo": "arquivo", "valor": "", "mensagem": "Arquivo excede o limite maximo de 5 MB."}],
            "avisos": [],
            "importadas": 0
        }

    encoding = _detectar_encoding(conteudo_bytes)
    texto = conteudo_bytes.decode(encoding, errors="replace")
    linhas_brutas = texto.splitlines()

    primeira_nao_vazia = ""
    for l in linhas_brutas:
        if l.strip():
            primeira_nao_vazia = l
            break

    if not primeira_nao_vazia:
        return {
            "resumo": {"total_linhas": 0, "validas": 0, "com_aviso": 0, "rejeitadas": 0, "duplicadas": 0, "ja_cadastradas": 0},
            "colunas_ignoradas": [],
            "linhas_validas": [],
            "erros": [{"linha": 1, "campo": "arquivo", "valor": "", "mensagem": "Arquivo nao possui linhas de dados."}],
            "avisos": [],
            "importadas": 0
        }

    separador = _detectar_separador(primeira_nao_vazia)
    leitor = csv.reader(io.StringIO(texto), delimiter=separador)

    try:
        cabecalho_bruto = next(leitor)
    except StopIteration:
        return {
            "resumo": {"total_linhas": 0, "validas": 0, "com_aviso": 0, "rejeitadas": 0, "duplicadas": 0, "ja_cadastradas": 0},
            "colunas_ignoradas": [],
            "linhas_validas": [],
            "erros": [{"linha": 1, "campo": "arquivo", "valor": "", "mensagem": "Arquivo sem cabecalho."}],
            "avisos": [],
            "importadas": 0
        }

    mapa_colunas: Dict[str, int] = {}
    colunas_ignoradas: List[str] = []

    for idx, col in enumerate(cabecalho_bruto):
        col_limpa = col.strip()
        norm = _normalizar_texto(col_limpa)
        if not norm:
            continue
        campo_casado = None
        for campo, sinonimos in SINONIMOS_CABECALHO.items():
            if norm in sinonimos:
                if campo_casado is not None and campo_casado != campo:
                    return {
                        "resumo": {"total_linhas": 0, "validas": 0, "com_aviso": 0, "rejeitadas": 0, "duplicadas": 0, "ja_cadastradas": 0},
                        "colunas_ignoradas": [],
                        "linhas_validas": [],
                        "erros": [{"linha": 1, "campo": "cabecalho", "valor": col_limpa, "mensagem": f"Cabecalho ambiguo: '{col_limpa}'. Por favor, renomeie a coluna."}],
                        "avisos": [],
                        "importadas": 0
                    }
                campo_casado = campo
        if campo_casado:
            mapa_colunas[campo_casado] = idx
        else:
            colunas_ignoradas.append(col_limpa)

    faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in mapa_colunas]
    if faltantes:
        msg = f"Coluna obrigatoria ausente: '{faltantes[0]}'. O arquivo precisa conter: placa, data_saida, hora_saida, origem e destino."
        return {
            "resumo": {"total_linhas": 0, "validas": 0, "com_aviso": 0, "rejeitadas": 0, "duplicadas": 0, "ja_cadastradas": 0},
            "colunas_ignoradas": colunas_ignoradas,
            "linhas_validas": [],
            "erros": [{"linha": 1, "campo": "cabecalho", "valor": faltantes[0], "mensagem": msg}],
            "avisos": [],
            "importadas": 0
        }

    agora_sp = referencia_agora if referencia_agora is not None else datetime.now(FUSO_SP)
    limite_passado_erro = agora_sp - timedelta(hours=24)

    total_linhas = 0
    validas = 0
    com_aviso = 0
    rejeitadas = 0
    duplicadas = 0
    ja_cadastradas = 0

    linhas_validas: List[Dict[str, Any]] = []
    erros: List[Dict[str, Any]] = []
    avisos: List[Dict[str, Any]] = []

    chaves_arquivo: Dict[Tuple[str, str, str], int] = {}
    chaves_horarios_placa: Dict[Tuple[str, str], Tuple[str, int]] = {}

    def adicionar_erro(linha_num: int, campo: str, valor: Any, msg: str) -> None:
        if len(erros) < MAX_ERROS_RELATORIO:
            erros.append({"linha": linha_num, "campo": campo, "valor": str(valor or "")[:60], "mensagem": msg})

    def adicionar_aviso(linha_num: int, campo: str, msg: str) -> None:
        avisos.append({"linha": linha_num, "campo": campo, "mensagem": msg})

    numero_linha_excel = 1
    for linha in leitor:
        numero_linha_excel += 1

        if not any(c.strip() for c in linha):
            continue

        total_linhas += 1
        if total_linhas > MAX_LINHAS:
            adicionar_erro(numero_linha_excel, "arquivo", "", f"Arquivo excede o limite maximo de {MAX_LINHAS} linhas de dados.")
            rejeitadas += 1
            break

        linha_invalida = False
        teve_aviso = False

        def obter(campo: str) -> str:
            idx = mapa_colunas.get(campo)
            if idx is not None and idx < len(linha):
                return linha[idx].strip()
            return ""

        placa_bruta = obter("placa")
        ok_placa, placa_norm, msg_placa = _validar_placa(placa_bruta)
        if not ok_placa:
            adicionar_erro(numero_linha_excel, "placa", placa_bruta, msg_placa)
            linha_invalida = True

        data_bruta = obter("data_saida")
        ok_data, data_val, msg_data = _validar_data(data_bruta)
        if not ok_data:
            adicionar_erro(numero_linha_excel, "data_saida", data_bruta, msg_data)
            linha_invalida = True

        hora_bruta = obter("hora_saida")
        ok_hora, hora_val, msg_hora = _validar_hora(hora_bruta)
        if not ok_hora:
            adicionar_erro(numero_linha_excel, "hora_saida", hora_bruta, msg_hora)
            linha_invalida = True

        origem_bruta = obter("origem")
        if not origem_bruta:
            adicionar_erro(numero_linha_excel, "origem", "", "Origem e obrigatoria.")
            linha_invalida = True
        elif _contem_injecao_csv(origem_bruta):
            adicionar_erro(numero_linha_excel, "origem", origem_bruta, "Origem contem caractere suspeito de formula.")
            linha_invalida = True

        destino_bruta = obter("destino")
        if not destino_bruta:
            adicionar_erro(numero_linha_excel, "destino", "", "Destino e obrigatorio.")
            linha_invalida = True
        elif _contem_injecao_csv(destino_bruta):
            adicionar_erro(numero_linha_excel, "destino", destino_bruta, "Destino contem caractere suspeito de formula.")
            linha_invalida = True

        motorista_bruta = obter("motorista")
        if _contem_injecao_csv(motorista_bruta):
            adicionar_erro(numero_linha_excel, "motorista", motorista_bruta, "Motorista contem caractere suspeito de formula.")
            linha_invalida = True

        obs_bruta = obter("observacao")
        if _contem_injecao_csv(obs_bruta):
            adicionar_erro(numero_linha_excel, "observacao", obs_bruta, "Observacao contem caractere suspeito de formula.")
            linha_invalida = True

        tel_bruta = obter("telefone_motorista")
        ok_tel, tel_val, msg_tel = _validar_telefone(tel_bruta)
        if not ok_tel:
            adicionar_aviso(numero_linha_excel, "telefone_motorista", msg_tel)
            teve_aviso = True

        if not linha_invalida and ok_data and ok_hora and data_val is not None and hora_val is not None:
            data_hora_sp = datetime.combine(data_val, hora_val, tzinfo=FUSO_SP)
            if data_hora_sp < limite_passado_erro:
                adicionar_erro(
                    numero_linha_excel,
                    "hora_saida",
                    f"{data_val.strftime('%d/%m/%Y')} {hora_val.strftime('%H:%M')}",
                    "Data e horario de saida estao mais de 24 horas no passado."
                )
                linha_invalida = True
            elif data_hora_sp < agora_sp:
                adicionar_aviso(numero_linha_excel, "hora_saida", "Horario de saida ja passou (dentro das ultimas 24 horas).")
                teve_aviso = True

        if linha_invalida:
            rejeitadas += 1
            continue

        if data_val is None or hora_val is None:
            rejeitadas += 1
            continue

        hora_fmt = hora_val.strftime("%H:%M")
        data_fmt = data_val.isoformat()
        chave_viagem = (placa_norm, data_fmt, hora_fmt)

        if chave_viagem in chaves_arquivo:
            linha_antiga = chaves_arquivo[chave_viagem]
            adicionar_erro(
                numero_linha_excel,
                "placa",
                placa_norm,
                f"Viagem duplicada no proprio arquivo (mesma placa, data e horario da linha {linha_antiga})."
            )
            rejeitadas += 1
            duplicadas += 1
            continue

        chaves_arquivo[chave_viagem] = numero_linha_excel

        if chave_viagem in viagens_existentes:
            adicionar_aviso(numero_linha_excel, "placa", "Viagem ja cadastrada no sistema anteriormente.")
            ja_cadastradas += 1
            teve_aviso = True

        chave_sobreposicao = (placa_norm, data_fmt)
        if chave_sobreposicao in chaves_horarios_placa:
            antigo_destino, antigo_min = chaves_horarios_placa[chave_sobreposicao]
            atual_min = hora_val.hour * 60 + hora_val.minute
            if abs(atual_min - antigo_min) <= 1 and antigo_destino != destino_bruta:
                adicionar_aviso(numero_linha_excel, "hora_saida", "Veiculo possui outra viagem com horario simultaneo no arquivo para destino diferente.")
                teve_aviso = True
        else:
            atual_min = hora_val.hour * 60 + hora_val.minute
            chaves_horarios_placa[chave_sobreposicao] = (destino_bruta, atual_min)

        origem_padrao = _capitalizar_localidade(origem_bruta)[:100]
        destino_padrao = _capitalizar_localidade(destino_bruta)[:100]
        motorista_padrao = _capitalizar_localidade(motorista_bruta)[:100] if motorista_bruta else None
        obs_padrao = obs_bruta[:200] if obs_bruta else None
        if len(obs_bruta) > 200:
            adicionar_aviso(numero_linha_excel, "observacao", "Observacao excedeu 200 caracteres e foi truncada.")
            teve_aviso = True

        data_hora_iso = datetime.combine(data_val, hora_val, tzinfo=FUSO_SP).isoformat()

        linhas_validas.append({
            "linha_excel": numero_linha_excel,
            "placa": placa_norm,
            "data_saida": data_fmt,
            "hora_saida": hora_fmt,
            "data_hora_saida": data_hora_iso,
            "origem": origem_padrao,
            "destino": destino_padrao,
            "motorista": motorista_padrao,
            "telefone_motorista": tel_val,
            "observacao": obs_padrao,
            "tenant_id": tenant_id
        })

        validas += 1
        if teve_aviso:
            com_aviso += 1

    return {
        "resumo": {
            "total_linhas": total_linhas,
            "validas": validas,
            "com_aviso": com_aviso,
            "rejeitadas": rejeitadas,
            "duplicadas": duplicadas,
            "ja_cadastradas": ja_cadastradas
        },
        "colunas_ignoradas": colunas_ignoradas,
        "linhas_validas": linhas_validas,
        "erros": erros,
        "avisos": avisos,
        "importadas": 0
    }
