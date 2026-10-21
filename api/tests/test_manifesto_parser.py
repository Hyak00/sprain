import io
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytest

from app.services.manifesto_parser import parse_manifesto_csv

FUSO_SP = ZoneInfo("America/Sao_Paulo")
AGORA_TESTE = datetime(2026, 10, 21, 10, 0, tzinfo=FUSO_SP)


def test_arquivo_limpo_caminho_feliz():
    conteudo = """placa,data_saida,hora_saida,origem,destino,motorista,telefone_motorista,observacao
ABC1D23,2026-10-21,12:30,Ribeirao Preto,Campinas,Joao Silva,16999998888,Carga refrigerada
XYZ-9876,2026-10-21,14:15,Araraquara,Sao Paulo,Marcos Lima,1633334444,Entrega urgente
"""
    res = parse_manifesto_csv(conteudo.encode("utf-8"), tenant_id="transportadora_xyz", referencia_agora=AGORA_TESTE)
    assert res["resumo"]["total_linhas"] == 2
    assert res["resumo"]["validas"] == 2
    assert res["resumo"]["rejeitadas"] == 0
    assert res["resumo"]["com_aviso"] == 0
    assert len(res["linhas_validas"]) == 2

    item1 = res["linhas_validas"][0]
    assert item1["linha_excel"] == 2
    assert item1["placa"] == "ABC1D23"
    assert item1["data_saida"] == "2026-10-21"
    assert item1["hora_saida"] == "12:30"
    assert item1["origem"] == "Ribeirao Preto"
    assert item1["destino"] == "Campinas"
    assert item1["motorista"] == "Joao Silva"
    assert item1["telefone_motorista"] == "16999998888"
    assert item1["observacao"] == "Carga refrigerada"
    assert item1["tenant_id"] == "transportadora_xyz"

    item2 = res["linhas_validas"][1]
    assert item2["linha_excel"] == 3
    assert item2["placa"] == "XYZ9876"
    assert item2["hora_saida"] == "14:15"


def test_arquivo_latin1_ponto_e_virgula_e_utf8_com_bom():
    conteudo_latin1 = "Placa;Data de Sa\u00edda;Hora Sa\u00edda;Origem;Destino\nABC1D23;21/10/2026;11:00;S\u00e3o Carlos;S\u00e3o Paulo\n"
    res1 = parse_manifesto_csv(conteudo_latin1.encode("cp1252"), referencia_agora=AGORA_TESTE)
    assert res1["resumo"]["validas"] == 1
    assert res1["linhas_validas"][0]["origem"] == "S\u00e3o Carlos"
    assert res1["linhas_validas"][0]["destino"] == "S\u00e3o Paulo"

    conteudo_bom = "\ufeffplaca,data_saida,hora_saida,origem,destino\nXYZ1234,21/10/2026,11:30,Araraquara,Santos\n"
    res2 = parse_manifesto_csv(conteudo_bom.encode("utf-8-sig"), referencia_agora=AGORA_TESTE)
    assert res2["resumo"]["validas"] == 1
    assert res2["linhas_validas"][0]["placa"] == "XYZ1234"


def test_validacao_placas_antiga_mercosul_hifen_minuscula_invalida():
    conteudo = """placa,data_saida,hora_saida,origem,destino
abc-1234,2026-10-21,12:00,Araraquara,Campinas
bra2e19,2026-10-21,12:00,Araraquara,Campinas
XYZ-9A88,2026-10-21,12:00,Araraquara,Campinas
PLACA_INVALIDA_123,2026-10-21,12:00,Araraquara,Campinas
1234567,2026-10-21,12:00,Araraquara,Campinas
"""
    res = parse_manifesto_csv(conteudo.encode("utf-8"), referencia_agora=AGORA_TESTE)
    assert res["resumo"]["total_linhas"] == 5
    assert res["resumo"]["validas"] == 3
    assert res["resumo"]["rejeitadas"] == 2

    assert res["linhas_validas"][0]["placa"] == "ABC1234"
    assert res["linhas_validas"][1]["placa"] == "BRA2E19"
    assert res["linhas_validas"][2]["placa"] == "XYZ9A88"

    erros_placa = [e for e in res["erros"] if e["campo"] == "placa"]
    assert len(erros_placa) == 2
    assert erros_placa[0]["linha"] == 5
    assert erros_placa[1]["linha"] == 6


def test_validacao_formatos_data_e_rejeicao_calendario():
    conteudo = """placa,data_saida,hora_saida,origem,destino
ABC1D23,21/10/2026,12:00,Araraquara,Campinas
BRA2E19,21/10/26,12:00,Araraquara,Campinas
XYZ9876,2026-10-21,12:00,Araraquara,Campinas
DEF1234,31/02/2026,12:00,Araraquara,Campinas
GHI5678,2026-02-31,12:00,Araraquara,Campinas
JKL9012,02/25/2026,12:00,Araraquara,Campinas
"""
    res = parse_manifesto_csv(conteudo.encode("utf-8"), referencia_agora=AGORA_TESTE)
    assert res["resumo"]["total_linhas"] == 6
    assert res["resumo"]["validas"] == 3
    assert res["resumo"]["rejeitadas"] == 3

    assert res["linhas_validas"][0]["data_saida"] == "2026-10-21"
    assert res["linhas_validas"][1]["data_saida"] == "2026-10-21"
    assert res["linhas_validas"][2]["data_saida"] == "2026-10-21"

    erros_data = [e for e in res["erros"] if e["campo"] == "data_saida"]
    assert len(erros_data) == 3
    assert erros_data[0]["linha"] == 5
    assert erros_data[1]["linha"] == 6
    assert erros_data[2]["linha"] == 7


def test_validacao_hora_sem_zero_segundos_e_hora_impossivel():
    conteudo = """placa,data_saida,hora_saida,origem,destino
ABC1D23,2026-10-21,2:30,Araraquara,Campinas
BRA2E19,2026-10-21,02:30,Araraquara,Campinas
XYZ9876,2026-10-21,02:30:45,Araraquara,Campinas
DEF1234,2026-10-21,25:99,Araraquara,Campinas
GHI5678,2026-10-21,12:61,Araraquara,Campinas
"""
    res = parse_manifesto_csv(conteudo.encode("utf-8"), referencia_agora=AGORA_TESTE)
    assert res["resumo"]["total_linhas"] == 5
    assert res["resumo"]["validas"] == 3
    assert res["resumo"]["rejeitadas"] == 2

    assert res["linhas_validas"][0]["hora_saida"] == "02:30"
    assert res["linhas_validas"][1]["hora_saida"] == "02:30"
    assert res["linhas_validas"][2]["hora_saida"] == "02:30"

    erros_hora = [e for e in res["erros"] if e["campo"] == "hora_saida"]
    assert len(erros_hora) == 2
    assert erros_hora[0]["linha"] == 5
    assert erros_hora[1]["linha"] == 6


def test_saida_no_passado_erro_acima_24h_aviso_abaixo_24h():
    agora = datetime(2026, 10, 21, 12, 0, tzinfo=FUSO_SP)
    conteudo = """placa,data_saida,hora_saida,origem,destino
ABC1D23,2026-10-21,15:00,Araraquara,Campinas
BRA2E19,2026-10-21,08:00,Araraquara,Campinas
XYZ9876,2026-10-19,10:00,Araraquara,Campinas
"""
    res = parse_manifesto_csv(conteudo.encode("utf-8"), referencia_agora=agora)
    assert res["resumo"]["total_linhas"] == 3
    assert res["resumo"]["validas"] == 2
    assert res["resumo"]["rejeitadas"] == 1
    assert res["resumo"]["com_aviso"] == 1

    avisos_passado = [a for a in res["avisos"] if a["campo"] == "hora_saida"]
    assert len(avisos_passado) == 1
    assert avisos_passado[0]["linha"] == 3

    erros_passado = [e for e in res["erros"] if e["campo"] == "hora_saida"]
    assert len(erros_passado) == 1
    assert erros_passado[0]["linha"] == 4


def test_linhas_em_branco_e_colunas_vazias_no_fim():
    conteudo = """placa;data_saida;hora_saida;origem;destino;

ABC1D23;2026-10-21;12:00;Araraquara;Campinas;
;;;;;
XYZ9876;2026-10-21;13:00;Sao Carlos;Sao Paulo;

"""
    res = parse_manifesto_csv(conteudo.encode("utf-8"), referencia_agora=AGORA_TESTE)
    assert res["resumo"]["total_linhas"] == 2
    assert res["resumo"]["validas"] == 2
    assert res["resumo"]["rejeitadas"] == 0
    assert len(res["linhas_validas"]) == 2
    assert res["linhas_validas"][0]["linha_excel"] == 3
    assert res["linhas_validas"][1]["linha_excel"] == 5


def test_duplicata_no_arquivo_e_duplicata_contra_banco_idempotente():
    conteudo = """placa,data_saida,hora_saida,origem,destino
ABC1D23,2026-10-21,12:00,Araraquara,Campinas
ABC1D23,2026-10-21,12:00,Araraquara,Campinas
XYZ9876,2026-10-21,14:00,Sao Carlos,Sao Paulo
"""
    ja_no_banco = {("XYZ9876", "2026-10-21", "14:00")}
    res = parse_manifesto_csv(conteudo.encode("utf-8"), viagens_existentes=ja_no_banco, referencia_agora=AGORA_TESTE)

    assert res["resumo"]["total_linhas"] == 3
    assert res["resumo"]["validas"] == 2
    assert res["resumo"]["duplicadas"] == 1
    assert res["resumo"]["ja_cadastradas"] == 1
    assert res["resumo"]["rejeitadas"] == 1

    erros_dup = [e for e in res["erros"] if e["campo"] == "placa"]
    assert len(erros_dup) == 1
    assert erros_dup[0]["linha"] == 3
    assert "linha 2" in erros_dup[0]["mensagem"]

    avisos_cad = [a for a in res["avisos"] if a["campo"] == "placa"]
    assert len(avisos_cad) == 1
    assert avisos_cad[0]["linha"] == 4


def test_coluna_obrigatoria_faltando_e_coluna_extra_desconhecida():
    conteudo_sem_destino = """placa,data_saida,hora_saida,origem
ABC1D23,2026-10-21,12:00,Araraquara
"""
    res1 = parse_manifesto_csv(conteudo_sem_destino.encode("utf-8"), referencia_agora=AGORA_TESTE)
    assert res1["resumo"]["validas"] == 0
    assert len(res1["erros"]) == 1
    assert "destino" in res1["erros"][0]["mensagem"]

    conteudo_com_extras = """placa,data_saida,hora_saida,origem,destino,coluna_inutil_1,coluna_inutil_2
ABC1D23,2026-10-21,12:00,Araraquara,Campinas,123,456
"""
    res2 = parse_manifesto_csv(conteudo_com_extras.encode("utf-8"), referencia_agora=AGORA_TESTE)
    assert res2["resumo"]["validas"] == 1
    assert "coluna_inutil_1" in res2["colunas_ignoradas"]
    assert "coluna_inutil_2" in res2["colunas_ignoradas"]


def test_seguranca_contra_injecao_csv_formula():
    conteudo = """placa,data_saida,hora_saida,origem,destino,motorista
=CMD|' /C calc'!A0,2026-10-21,12:00,Araraquara,Campinas,Pedro
ABC1D23,2026-10-21,12:00,@Soma(A1:A5),Campinas,Pedro
BRA2E19,2026-10-21,12:00,Araraquara,+FormulaMaliciosa,Pedro
XYZ9876,2026-10-21,12:00,Araraquara,Campinas,=Malicioso
DEF1234,2026-10-21,12:00,Araraquara,Campinas,-Malicioso
"""
    res = parse_manifesto_csv(conteudo.encode("utf-8"), referencia_agora=AGORA_TESTE)
    assert res["resumo"]["total_linhas"] == 5
    assert res["resumo"]["validas"] == 0
    assert res["resumo"]["rejeitadas"] == 5
    for err in res["erros"]:
        assert "formula" in err["mensagem"]


def test_arquivo_vazio_acima_limite_e_sem_linhas():
    res_vazio = parse_manifesto_csv(b"")
    assert res_vazio["resumo"]["total_linhas"] == 0
    assert "Arquivo vazio" in res_vazio["erros"][0]["mensagem"]

    buffer_grande = b"a" * (5 * 1024 * 1024 + 10)
    res_grande = parse_manifesto_csv(buffer_grande)
    assert "limite maximo de 5 MB" in res_grande["erros"][0]["mensagem"]

    linhas_2005 = ["placa,data_saida,hora_saida,origem,destino"]
    for i in range(2005):
        linhas_2005.append(f"ABC{i:04d},2026-10-21,12:00,Araraquara,Campinas")
    res_muitas_linhas = parse_manifesto_csv("\n".join(linhas_2005).encode("utf-8"), referencia_agora=AGORA_TESTE)
    assert any("2000 linhas" in e["mensagem"] for e in res_muitas_linhas["erros"])


def test_arquivo_sujo_do_enunciado():
    csv_sujo = """Placa;Data de Sa\u00edda;Hora Sa\u00edda;Origem;Destino;Motorista;
abc-1d23 ;21/10/2026;2:30;ribeir\u00e3o preto;CAMPINAS;jo\u00e3o silva;
XYZ9876;21/10/26;03:15:00;Araraquara;S\u00e3o Paulo;;
;;;;;;
ABC1D23;21/10/2026;02:30;Ribeir\u00e3o Preto;Campinas;Jo\u00e3o Silva;
=CMD|' /C calc'!A0;21/10/2026;04:00;Sert\u00e3ozinho;Santos;Pedro;
AAA0000;31/02/2026;25:99;Franca;Santos;Ana;
"""
    ref_agora = datetime(2026, 10, 20, 10, 0, tzinfo=FUSO_SP)
    res = parse_manifesto_csv(csv_sujo.encode("cp1252"), tenant_id="frota_interior", referencia_agora=ref_agora)

    assert res["resumo"]["total_linhas"] == 5
    assert res["resumo"]["validas"] == 2
    assert res["resumo"]["rejeitadas"] == 3
    assert res["resumo"]["duplicadas"] == 1

    item1 = res["linhas_validas"][0]
    assert item1["linha_excel"] == 2
    assert item1["placa"] == "ABC1D23"
    assert item1["data_saida"] == "2026-10-21"
    assert item1["hora_saida"] == "02:30"
    assert item1["origem"] == "Ribeir\u00e3o Preto"
    assert item1["destino"] == "Campinas"
    assert item1["motorista"] == "Jo\u00e3o Silva"
    assert item1["tenant_id"] == "frota_interior"

    item2 = res["linhas_validas"][1]
    assert item2["linha_excel"] == 3
    assert item2["placa"] == "XYZ9876"
    assert item2["data_saida"] == "2026-10-21"
    assert item2["hora_saida"] == "03:15"
    assert item2["origem"] == "Araraquara"
    assert item2["destino"] == "S\u00e3o Paulo"

    erros = res["erros"]
    linhas_com_erro = {e["linha"] for e in erros}
    assert 5 in linhas_com_erro
    assert 6 in linhas_com_erro
    assert 7 in linhas_com_erro


def test_isolamento_de_tenant():
    conteudo = """placa,data_saida,hora_saida,origem,destino
ABC1D23,2026-10-21,12:00,Araraquara,Campinas
"""
    res_tenant_a = parse_manifesto_csv(conteudo.encode("utf-8"), tenant_id="empresa_a", referencia_agora=AGORA_TESTE)
    res_tenant_b = parse_manifesto_csv(conteudo.encode("utf-8"), tenant_id="empresa_b", referencia_agora=AGORA_TESTE)

    assert res_tenant_a["linhas_validas"][0]["tenant_id"] == "empresa_a"
    assert res_tenant_b["linhas_validas"][0]["tenant_id"] == "empresa_b"
