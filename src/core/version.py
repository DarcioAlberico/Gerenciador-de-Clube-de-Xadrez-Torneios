"""Versão do aplicativo — fonte única.

Antes o número aparecia cravado no título da janela e em mais nenhum lugar, e o
`pyproject.toml` trazia outro valor (`0.1.0`, a versão de **empacotamento**).
Quem exibe versão para o usuário — título, tela de login, suporte — lê daqui.

Ao subir a versão, mude aqui **e** no `pyproject.toml`: são coisas diferentes
(uma é o que o usuário vê, a outra é metadado de build), mas devem contar a
mesma história.
"""
from __future__ import annotations

APP_VERSION = "1.0"
APP_NAME = "Albericus"
APP_TAGLINE = "Emparceiramento e gestão de torneios de xadrez"
APP_SITE = "albericuschessmanager.com.br"


def app_title() -> str:
    """Título da janela principal."""
    return f"{APP_NAME} - Emparceiramento de Xadrez v{APP_VERSION}"


def version_label(schema_version: int | None = None) -> str:
    """Rótulo curto para rodapé/suporte. Com o schema, vira ``1.0 · banco v43``
    — saber a versão do banco encurta muito o diagnóstico de um chamado."""
    if schema_version is None:
        return f"v{APP_VERSION}"
    return f"v{APP_VERSION} · banco v{schema_version}"
