"""A permissão mora no serviço (RG2-04) — e o operador, no banco (RG2-43).

Antes só a tela checava, handler a handler: o painel do árbitro, os ajustes de
pontos e o QR gravavam direto, e um ``viewer`` lançava 1-0, adiava mesa e dava
+1 ponto. Agora todo método público de serviço que grava passa por
``require_permission``, que lê o operador do ``Database``
(``current_operator``, definido pelo login). A tela continua desabilitando o
botão — só como conforto.

Sem operador é o **sistema** (migração, ``--self-test``, ``--gacrux``,
backup automático, testes de serviço): passa. O app abre na tela de login, então
nenhuma ação de usuário chega aqui sem operador.

``@requires(acao)`` vai **por fora** de ``@atomic``: a recusa é auditada em
``audit_logs`` e não pode ser desfeita junto com a transação.

A varredura ``tests/test_rg2_04_permissoes.py`` descobre por AST os métodos que
gravam e reprova o que não tem ``@requires`` nem isenção declarada.
"""
from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from src.config.permissions import ROLE_PERMISSIONS
from src.services.constants import AppError

F = TypeVar("F", bound=Callable[..., Any])

__all__ = ["PERMISSION_DENIED", "has_permission", "require_permission", "requires"]

PERMISSION_DENIED = "Permissão negada para realizar esta ação."


def has_permission(db: Any, action: str) -> bool:
    operator = db.current_operator()
    if operator is None:
        return True  # o sistema
    if operator.role == "admin":
        return True
    return action in ROLE_PERMISSIONS.get(operator.role, [])


def require_permission(db: Any, action: str) -> None:
    """Recusa (e audita a recusa) quando o operador não tem ``action``."""
    if has_permission(db, action):
        return
    operator = db.current_operator()
    db.create_audit_log(
        action="permission_denied",
        actor=operator.name,
        role=operator.role,
        description=f"Acesso negado para ação: {action}",
    )
    raise AppError(PERMISSION_DENIED)


def requires(action: str) -> Callable[[F], F]:
    """Decorador de método de serviço (``self.db``): checa ``action`` antes de tudo."""

    def decorator(method: F) -> F:
        @functools.wraps(method)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            require_permission(self.db, action)
            return method(self, *args, **kwargs)

        wrapper.__required_permission__ = action  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator
