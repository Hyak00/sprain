import time
import logging
import asyncio
from typing import Any, Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app import database
from app.services.medicao_processamento import registrar_atendimento

logger = logging.getLogger(__name__)
_medicoes_pendentes: set[asyncio.Task] = set()
MAX_MEDICOES_PENDENTES = 1000


async def _persistir_medicao(tenant_id: str, status_code: int, duracao_ms: float,
                             metodo: str, rota_template: str):
    try:
        if database.db_pool is not None:
            async with database.db_pool.acquire() as conn:
                async with conn.transaction():
                    await registrar_atendimento(conn, tenant_id, status_code, duracao_ms,
                                                metodo=metodo, rota_template=rota_template)
    except Exception as erro:
        logger.warning("Metrica de processamento nao persistida: %s", type(erro).__name__)


def _agendar_medicao(tenant_id: str, status_code: int, duracao_ms: float,
                     metodo: str, rota_template: str):
    # A escrita nao pode bloquear a resposta enquanto a rota ainda detem uma conexao.
    if len(_medicoes_pendentes) >= MAX_MEDICOES_PENDENTES:
        return
    tarefa = asyncio.create_task(_persistir_medicao(
        tenant_id, status_code, duracao_ms, metodo, rota_template))
    _medicoes_pendentes.add(tarefa)
    tarefa.add_done_callback(_medicoes_pendentes.discard)


class MetricsCollector:
    """Métricas em memória separadas pela empresa autenticada."""

    _states: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _new_state() -> Dict[str, Any]:
        return {
            "total_requisicoes": 0,
            "total_erros": 0,
            "tempo_total_ms": 0.0,
            "rotas_lentas": [],
            "erros_recentes": [],
            "latencias_por_rota": {},
        }

    @classmethod
    def registrar(
        cls, tenant_id: str, metodo: str, rota: str, status_code: int, duracao_ms: float
    ) -> None:
        state = cls._states.setdefault(tenant_id, cls._new_state())
        state["total_requisicoes"] += 1
        state["tempo_total_ms"] += duracao_ms

        if status_code >= 400:
            state["total_erros"] += 1
            erros = state["erros_recentes"]
            if len(erros) >= 50:
                erros.pop(0)
            erros.append({
                "metodo": metodo,
                "rota": rota,
                "status_code": status_code,
                "duracao_ms": round(duracao_ms, 2),
                "timestamp": time.time(),
            })

        if duracao_ms >= 500.0:
            lentas = state["rotas_lentas"]
            if len(lentas) >= 50:
                lentas.pop(0)
            lentas.append({
                "metodo": metodo,
                "rota": rota,
                "duracao_ms": round(duracao_ms, 2),
                "timestamp": time.time(),
            })

        chave_rota = f"{metodo} {rota}"
        info = state["latencias_por_rota"].setdefault(chave_rota, {
            "chamadas": 0,
            "tempo_total_ms": 0.0,
            "max_ms": duracao_ms,
            "min_ms": duracao_ms,
        })
        info["chamadas"] += 1
        info["tempo_total_ms"] += duracao_ms
        info["max_ms"] = max(info["max_ms"], duracao_ms)
        info["min_ms"] = min(info["min_ms"], duracao_ms)

    @classmethod
    def obter_metricas(cls, tenant_id: str) -> Dict[str, Any]:
        state = cls._states.get(tenant_id) or cls._new_state()
        total = state["total_requisicoes"]
        media_global = round(state["tempo_total_ms"] / total, 2) if total else 0.0
        taxa_erro = round((state["total_erros"] / total) * 100.0, 2) if total else 0.0
        resumo_rotas = {}
        for rota, dados in state["latencias_por_rota"].items():
            resumo_rotas[rota] = {
                "chamadas": dados["chamadas"],
                "latencia_media_ms": round(dados["tempo_total_ms"] / dados["chamadas"], 2),
                "min_ms": round(dados["min_ms"], 2),
                "max_ms": round(dados["max_ms"], 2),
            }
        return {
            "status_monitor": "OPERACIONAL",
            "total_requisicoes": total,
            "total_erros": state["total_erros"],
            "taxa_erro_pct": taxa_erro,
            "latencia_media_global_ms": media_global,
            "rotas_lentas_detectadas": len(state["rotas_lentas"]),
            "historico_rotas_lentas": state["rotas_lentas"][-10:],
            "erros_recentes": state["erros_recentes"][-10:],
            "detalhamento_por_rota": resumo_rotas,
        }

    @classmethod
    def resetar(cls, tenant_id: str) -> None:
        cls._states.pop(tenant_id, None)


class ObservabilidadeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        inicio = time.perf_counter()
        status_code = None
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # Falhas sem resposta HTTP ainda precisam aparecer como erro do endpoint.
            status_code = 500
            raise
        finally:
            duracao_ms = (time.perf_counter() - inicio) * 1000.0
            tenant_id = getattr(request.state, "authenticated_tenant_id", None)
            if tenant_id and status_code is not None:
                # O template da rota não contém IDs de operações nem outros valores da URL.
                route = request.scope.get("route")
                route_template = getattr(route, "path", "<sem_rota>")
                MetricsCollector.registrar(
                    tenant_id=tenant_id,
                    metodo=request.method,
                    rota=route_template,
                    status_code=status_code,
                    duracao_ms=duracao_ms,
                )
                _agendar_medicao(tenant_id, status_code, duracao_ms,
                                 request.method, route_template)

        response.headers["X-Process-Time-Ms"] = str(round(duracao_ms, 2))
        return response
