"""Base das ações da tela de Jogadores (B-6).

Vinte e cinco botões, e cada um deles abria com o mesmo ``try`` e fechava com o
mesmo ``except Exception as exc: self._show_error(exc)``. Repetição dessa
natureza não é só ruído: numa das ações o ``try`` cobria só metade do corpo, e
ninguém tinha como notar lendo 1.600 linhas.

Aqui o laço vira o decorador ``guarded``, e o "qual é o torneio corrente" vira
uma propriedade que **reclama** em vez de estourar `TypeError` lá dentro.
"""
from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

from src.services.constants import AppError

from ...i18n import t

F = TypeVar("F", bound=Callable[..., Any])


def guarded(method: F) -> F:
    """Erro da ação vira recado do app (toast ou modal), nunca traceback na tela."""

    @functools.wraps(method)
    def wrapper(self: "ScreenActions", *args: Any, **kwargs: Any) -> Any:
        try:
            return method(self, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — o destino é o _show_error unificado (F2.2)
            self.host._show_error(exc)
            return None

    return wrapper  # type: ignore[return-value]


class ScreenActions:
    """Ações que precisam do app (arquivo, background, diálogo) e do torneio."""

    def __init__(self, host: Any, on_changed: Callable[[], None] | None = None) -> None:
        self.host = host
        self._on_changed = on_changed or (lambda: None)

    @property
    def tournament_id(self) -> int:
        """Torneio corrente. Sem torneio, recado claro em vez de `TypeError`."""
        if not self.host.current_tournament_id:
            raise AppError(t("players.error.select_tournament"))
        return int(self.host.current_tournament_id)

    def changed(self) -> None:
        """Avisa a tela de que a lista mudou (recarrega tabela e sócios)."""
        self._on_changed()

    def background(
        self,
        work: Callable[[], Any],
        done: Callable[[Any], None],
        message: str,
    ) -> None:
        """Trabalho longo fora da thread da UI, com a barra da statusbar (F2.3)."""
        self.host._run_background(work, done, message)

    @staticmethod
    def with_errors(
        message: str,
        errors: list[str],
        limit: int = 10,
        label: str | None = None,
    ) -> str:
        """Mensagem de resultado com a lista de pendências, truncada.

        Trunca porque um relatório de 400 linhas num alerta modal não é
        relatório: é uma parede. O log guarda o resto. ``label`` distingue o que
        impediu a importação ("Erros:") do que só merece atenção ("Avisos:") —
        distinção que a tela já fazia e que se perderia num helper único.
        """
        if not errors:
            return message
        titulo = label or t("players.import.errors")
        return message + "\n\n" + titulo + "\n" + "\n".join(errors[:limit])
