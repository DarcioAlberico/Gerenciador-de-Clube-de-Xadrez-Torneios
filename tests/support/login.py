"""Entrar como administrador num banco de teste (RG2-37).

Banco novo nasce com ``admin`` SEM senha: o primeiro acesso define a senha. Os
testes de tela entravam com ``admin``/``admin``; agora passam pelo mesmo fluxo.
"""
from __future__ import annotations

from typing import Any

SENHA_DE_TESTE = "admin"


def entrar_como_admin(security_service: Any, senha: str = SENHA_DE_TESTE) -> None:
    if security_service.needs_first_password():
        security_service.set_first_password("admin", senha)
    if not security_service.login("admin", senha):
        raise AssertionError("login do administrador de teste falhou")
