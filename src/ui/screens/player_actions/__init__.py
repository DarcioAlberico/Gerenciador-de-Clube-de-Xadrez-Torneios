"""Ações na linha do jogador: bye, falta, retirada, reintegração e entrada tardia.

RGS-22, RGS-23 e RGS-24 da Revisão Geral Suíço. O pacote segue o molde da
F1.5: ``state`` (puro), ``controller`` (serviço, sem Tk), e a parte de Tk em
``dialogs``, ``late_entry`` e ``menu``.
"""
from __future__ import annotations

from .menu import PlayerActions

__all__ = ["PlayerActions"]
