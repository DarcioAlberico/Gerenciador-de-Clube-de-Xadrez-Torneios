"""Adiar o refiltro até o usuário parar de digitar (B-4 / P2-13).

Cada tecla numa caixa de busca hoje esvazia a tabela e reinsere tudo. Com 6.000
jogadores isso é ~50 ms **por tecla** — o preço não está em uma tecla, está em
digitar dez em sequência e a janela responder a cada uma delas.

O agendamento entra por parâmetro (``schedule``/``cancel``) em vez de o módulo
chamar ``widget.after``: assim a regra — "cancela o anterior, marca o próximo,
executa uma vez só" — é testável sem abrir janela. ``debounce()`` faz a ligação
com o Tk para quem só quer usar.
"""
from __future__ import annotations

from typing import Any, Callable

# 180 ms: acima do intervalo entre teclas de quem digita rápido (~120 ms) e
# abaixo do que o olho lê como travada (~250 ms).
DEFAULT_DELAY_MS = 180


class Debounced:
    """Callable que só executa ``action`` depois de ``delay_ms`` sem novas chamadas.

    Serve direto como callback de ``bind`` (ignora o evento recebido).
    """

    def __init__(
        self,
        action: Callable[[], None],
        schedule: Callable[[int, Callable[[], None]], Any],
        cancel: Callable[[Any], None],
        delay_ms: int = DEFAULT_DELAY_MS,
    ) -> None:
        self._action = action
        self._schedule = schedule
        self._cancel = cancel
        self._delay_ms = max(0, delay_ms)
        self._pending: Any = None
        self.runs = 0

    def __call__(self, *_event: Any) -> None:
        self.cancel()
        self._pending = self._schedule(self._delay_ms, self._fire)

    def flush(self) -> None:
        """Executa agora o que estava agendado (Enter, sair do campo, teste).

        Sem isto, confirmar com Enter esperaria o mesmo tempo de quem parou de
        digitar por acaso — e um teste teria de dormir para ver o resultado.
        """
        if self._pending is not None:
            self.cancel()
            self._fire()

    def cancel(self) -> None:
        """Descarta o agendamento pendente (tela fechando, busca limpa)."""
        if self._pending is not None:
            try:
                self._cancel(self._pending)
            except Exception:
                pass
            self._pending = None

    @property
    def is_pending(self) -> bool:
        return self._pending is not None

    def _fire(self) -> None:
        self._pending = None
        self.runs += 1
        self._action()


def debounce(
    widget: Any, action: Callable[[], None], delay_ms: int = DEFAULT_DELAY_MS
) -> Debounced:
    """``Debounced`` ligado ao laço de eventos de ``widget``.

        entry.bind("<KeyRelease>", debounce(entry, load_players))

    O agendamento morre com o widget: ``after`` de um widget destruído é
    cancelado pelo próprio Tk, então uma tela fechada no meio da digitação não
    deixa o refiltro rodando sobre uma tabela que não existe mais.
    """
    return Debounced(action, lambda ms, fn: widget.after(ms, fn), widget.after_cancel, delay_ms)
