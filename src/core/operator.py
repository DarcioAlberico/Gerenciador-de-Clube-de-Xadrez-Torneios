"""Quem está operando o programa — a única fonte (RG2-43, base do RG2-04).

Havia duas: o ``SecurityService`` guardava o usuário logado só na memória
dele, e a auditoria do banco lia ``operator_name``/``operator_role`` de
``app_settings``. Logado como árbitro, a correção de resultado saía como feita
pelo "Administrador".

Agora o ``Database`` guarda o operador (``set_operator``/``current_operator``),
definido pelo login. ``None`` é o **sistema**: fluxos que rodam sem ninguém
logado (migração, ``--self-test``, ``--gacrux``, testes de serviço). A
auditoria os registra como ``SYSTEM_ACTOR``.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Operator", "SYSTEM_ACTOR"]

SYSTEM_ACTOR = "sistema"


@dataclass(frozen=True)
class Operator:
    user_id: int
    name: str
    role: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Operador sem nome.")
        if not self.role.strip():
            raise ValueError("Operador sem papel.")
