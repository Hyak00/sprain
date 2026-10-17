"""Auditoria de jobs públicos, sem conteúdo de arquivos, URLs, credenciais ou exceções."""
from pathlib import Path
from uuid import uuid4

SCHEMA = Path(__file__).resolve().parents[1]/'db/ci/11_importacoes_monitor.sql'


def executar_auditado(executar, conectar, fonte):
    identificador = str(uuid4())

    def gravar(sql, valores):
        conn = conectar()
        try:
            with conn.cursor() as cursor:
                cursor.execute(SCHEMA.read_text(encoding='utf-8'))
                cursor.execute(sql, valores)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    # Sem auditoria inicial não inicia a escrita: não oculta execução não rastreável.
    gravar("INSERT INTO monitor_importacoes(id,fonte,status) VALUES (%s,%s,'EM_EXECUCAO')", (identificador,fonte))
    try:
        resultado = executar()
    except BaseException:
        try:
            gravar("UPDATE monitor_importacoes SET status='FALHA',encerrado_em=now(),motivo_codigo='EXECUCAO_INTERROMPIDA' WHERE id=%s", (identificador,))
        except Exception:
            # Mantém EM_EXECUCAO se o banco caiu; a tela indica encerramento desconhecido.
            pass
        raise
    resumo = resultado if isinstance(resultado,dict) else {}
    falhas = resumo.get('falhas',0)
    status = 'PARCIAL' if falhas and resumo.get('registros',0) else 'FALHA' if falhas else 'CONCLUIDO'
    gravar('UPDATE monitor_importacoes SET status=%s,encerrado_em=now(),registros=%s,falhas=%s,motivo_codigo=%s WHERE id=%s',
           (status,resumo.get('registros'),falhas,'COLETA_INDISPONIVEL' if falhas else None,identificador))
    return resultado
