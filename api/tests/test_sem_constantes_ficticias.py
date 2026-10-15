from pathlib import Path
import re

PADROES_BANIDOS = [
    (r"\b18\.4\b", "Constante ficticia de km de desvio (18.4) encontrada"),
    (r"\b2800(?:\.00?)?\b", "Constante ficticia de prejuizo/economia (2800) encontrada"),
    (r"0\.35\s*\*\s*6\.5", "Formula ficticia de custo de desvio (0.35 * 6.5) encontrada"),
    (r"0\.20\s*\+\s*\(fator_chuva\s*\*\s*0\.70\)", "Formula de probabilidade fixa de atraso encontrada"),
    (r"0\.10\s*\+\s*\(fator_chuva\s*\*\s*0\.80\)", "Formula de probabilidade fixa de bloqueio encontrada"),
    (r"0\.45\s*\+\s*\(fator_chuva\s*\*\s*0\.50\)", "Formula de probabilidade fixa encontrada"),
    (r"0\.25\s*\+\s*\(fator_chuva\s*\*\s*0\.35\)", "Formula de probabilidade fixa encontrada")
]

def test_nenhuma_constante_ficticia_no_codigo_da_api():
    app_dir = Path(__file__).resolve().parent.parent / "app"
    arquivos_py = list(app_dir.rglob("*.py"))
    assert len(arquivos_py) > 0

    violacoes = []
    for arquivo in arquivos_py:
        texto = arquivo.read_text(encoding="utf-8")
        for padrao, mensagem in PADROES_BANIDOS:
            matches = list(re.finditer(padrao, texto))
            if matches:
                violacoes.append(f"{arquivo.name}: {mensagem} (linhas: {[texto[:m.start()].count(chr(10)) + 1 for m in matches]})")

    assert not violacoes, "Violacoes de dados ficticios detectadas:\n" + "\n".join(violacoes)