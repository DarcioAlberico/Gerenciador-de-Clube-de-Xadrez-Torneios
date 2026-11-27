"""Trabalhador que reconcilia os retratos de classificação (RGS-10).

A correção de resultado só MARCA os retratos (`reconcile_pending=1`); o
recálculo — uma classificação por rodada, com o Gacrux — roda aqui, numa
thread, para a tela não travar. Três regras:

- **Fala com a tela só por ``notify``** (na UI, uma fila que a thread da tela
  esvazia num ``after()`` periódico — ver ``_start_snapshot_reconciler``):
  ``on_done`` e ``on_error`` nunca são chamados da thread de trabalho.
- **Idempotente e retomável:** a pendência mora no banco, não aqui. Ligar o
  trabalhador sem nada pendente não faz nada; interrompido no meio (falha,
  app fechado), o que sobrou é terminado na próxima abertura.
- **Um por vez:** um pedido que chega com o trabalho em andamento não abre
  outra thread — marca "de novo", e a mesma thread dá mais uma volta.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)

Notify = Callable[[Callable[[], None]], Any]


class SnapshotReconciler:
    def __init__(
        self,
        service: Any,
        *,
        notify: Notify,
        on_done: Callable[[int], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._service = service
        self._notify = notify
        self._on_done = on_done
        self._on_error = on_error
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._again = False
        self._idle = threading.Event()
        self._idle.set()

    @property
    def running(self) -> bool:
        return not self._idle.is_set()

    def start(self, tournament_id: int | None = None) -> None:
        """Pede uma reconciliação. Não bloqueia; o argumento é só informativo.

        Reconcilia TODOS os pendentes, de qualquer torneio: é o que torna a
        abertura do app (sem torneio escolhido) igual a um pedido da correção.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                self._again = True
                return
            self._again = False
            self._idle.clear()
            self._thread = threading.Thread(
                target=self._run, name="albericus-reconcilia-retratos", daemon=True
            )
            self._thread.start()
        logger.debug("Reconciliacao de retratos pedida (torneio %s)", tournament_id)

    def wait(self, timeout: float | None = None) -> bool:
        """Espera o trabalho acabar. True se acabou. Para testes e self-test."""
        return self._idle.wait(timeout)

    def _run(self) -> None:
        while True:
            total = 0
            erro: Exception | None = None
            while True:
                try:
                    total += int(self._service.reconcile_pending_snapshots() or 0)
                except Exception as exc:  # a tela decide o que mostrar; a pendência fica
                    logger.exception("Falha ao reconciliar retratos de classificacao")
                    erro = exc
                with self._lock:
                    if erro is None and self._again:
                        self._again = False
                        continue
                break
            if erro is not None:
                self._deliver(self._on_error, erro)
            elif total:
                self._deliver(self._on_done, total)
            with self._lock:
                # Pedido que chegou enquanto o aviso saia: mais uma volta. Depois
                # de erro, não — repetir em laço a mesma falha não ajuda; a
                # pendência fica no banco para o próximo pedido.
                if erro is None and self._again:
                    self._again = False
                    continue
                self._again = False
                self._thread = None
                self._idle.set()
                return

    def _deliver(self, callback: Callable[[Any], None] | None, value: Any) -> None:
        if callback is None:
            return
        try:
            self._notify(lambda: callback(value))
        except Exception:  # janela fechada no meio: nada a quem avisar
            logger.debug("Aviso da reconciliacao descartado (tela indisponivel)", exc_info=True)
