"""Janela informativa de manutenção, configurada pelo ambiente do servidor."""

from datetime import datetime, timezone

from app.config import settings


def _instante(valor: str) -> datetime:
    try:
        instante = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("janela de manutenção exige data ISO 8601 com fuso") from exc
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("janela de manutenção exige data com fuso")
    return instante.astimezone(timezone.utc)


def carregar_janela() -> tuple[datetime, datetime, str] | None:
    inicio = settings.MANUTENCAO_INICIO.strip()
    fim = settings.MANUTENCAO_FIM.strip()
    aviso = settings.MANUTENCAO_AVISO.strip()
    if not any((inicio, fim, aviso)):
        return None
    if not all((inicio, fim, aviso)) or len(aviso) > 240:
        raise ValueError("janela de manutenção exige início, fim e aviso de até 240 caracteres")
    inicio_em, fim_em = _instante(inicio), _instante(fim)
    if inicio_em >= fim_em:
        raise ValueError("fim da manutenção deve ser posterior ao início")
    return inicio_em, fim_em, aviso


def estado_manutencao(agora: datetime | None = None) -> dict:
    agora = agora or datetime.now(timezone.utc)
    janela = carregar_janela()
    resultado = {"consultado_em": agora, "situacao": "SEM_JANELA", "inicio_em": None,
                 "fim_em": None, "aviso": None}
    if janela is None:
        return resultado
    inicio, fim, aviso = janela
    if agora >= fim:
        return resultado
    resultado.update(situacao="PROGRAMADA" if agora < inicio else "EM_ANDAMENTO",
                     inicio_em=inicio, fim_em=fim, aviso=aviso)
    return resultado
