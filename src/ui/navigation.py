"""Navegação: registro único de destinos e o ``Navigator``.

Antes, a lista de destinos existia **duas vezes** — uma no `tk.Menu` e outra no
command palette — e o "onde estou" era descoberto inspecionando o frame do
chamador. Aqui os destinos viram dado puro (``DESTINATIONS``), testável sem Tk,
e o ``Navigator`` centraliza ir para um destino e recarregar o atual (ESPEC_UI_UX
§3.2 / achado P0-1).

O registro guarda o **nome** do método de tela, não o método ligado: assim ele
pode ser importado e testado sem instanciar a aplicação.

    navigator.go("pairings")        # ou "show_pairings"
    navigator.refresh_current()     # o que o F5 faz
"""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .i18n import t

logger = logging.getLogger("src.ui.navigation")


@dataclass(frozen=True)
class Destination:
    """Um destino navegável. ``method`` é o nome do ``show_*`` na aplicação.

    Rótulo, palavras-chave e grupo **não** ficam guardados aqui: são lidos do
    catálogo de textos na hora de exibir (B-3). O registro guarda a identidade
    (``key``) e o comportamento (``method``); o texto é conteúdo, e conteúdo
    mora no catálogo. É isso que permite trocar de idioma sem reconstruir o
    registro — e é por isso que são propriedades, não campos.
    """

    key: str
    method: str
    icon: str | None = None
    group_key: str = ""

    @property
    def label(self) -> str:
        return t(f"nav.{self.key}.label")

    @property
    def keywords(self) -> str:
        return t(f"nav.{self.key}.keywords")

    @property
    def group(self) -> str:
        return t(f"nav.group.{self.group_key}") if self.group_key else ""


# Ordem = ordem de exibição no palette (e, mais adiante, na sidebar da F3.1).
DESTINATIONS: tuple[Destination, ...] = (
    # Inicio — pendencias acionaveis; e a tela que abre depois do login (F3.2).
    Destination("home", "show_home", "dashboard", "club"),
    # Clube
    Destination("visual_dashboard", "show_visual_dashboard", "dashboard", "club"),
    Destination("club", "show_club", "clube", "club"),
    Destination("members", "show_members", "membros", "club"),
    Destination("learning_levels", "show_learning_levels", "aulas", "club"),
    Destination("guardians", "show_guardians", "membros", "club"),
    # Treinamento — Aulas e Exercícios seguem DESATIVADOS (ver _build_menu).
    Destination("free_tournament", "show_free_tournament_mode", "torneios", "training"),
    Destination("library", "show_library", "biblioteca", "training"),
    # Gestão
    Destination("referees", "show_referees", "arbitros", "management"),
    Destination("inventory", "show_inventory", "integracoes", "management"),
    Destination("finance", "show_finance", "financeiro", "management"),
    Destination("calendar", "show_calendar", "calendario", "management"),
    Destination("internal_ranking", "show_internal_ranking", "dashboard", "management"),
    # Torneio
    Destination("tournaments", "show_tournaments", "torneios", "tournament"),
    Destination("tournament_dashboard", "show_tournament_dashboard", "emparceiramento", "tournament"),
    Destination("arbitration_panel", "show_arbitration_panel", "arbitros", "tournament"),
    Destination("tournament_settings", "show_tournament_settings", "configuracoes", "tournament"),
    Destination("players", "show_players", "membros", "tournament"),
    Destination("teams", "show_teams", "clube", "tournament"),
    Destination("pairings", "show_pairings", "emparceiramento", "tournament"),
    Destination("standings", "show_standings", "dashboard", "tournament"),
    Destination("certificates", "show_certificates", "relatorios", "tournament"),
    # Ferramentas
    Destination("export", "show_export", "integracoes", "tools"),
    Destination("admin_reports", "show_administrative_reports", "relatorios", "tools"),
    Destination("financial_reports", "show_financial_reports", "financeiro", "tools"),
    Destination("communication", "show_communication", "comunicacao", "tools"),
    Destination("integrations", "show_integrations", "integracoes", "tools"),
    # Configurações
    Destination("app_settings", "show_app_settings", "configuracoes", "settings"),
    Destination("audit", "show_audit_logs", "auditoria", "settings"),
)

_BY_KEY = {destination.key: destination for destination in DESTINATIONS}
_BY_METHOD = {destination.method: destination for destination in DESTINATIONS}


def _fold(text: str) -> str:
    """Minúsculas sem acento — para buscar 'orgao' e achar 'Órgão'."""
    normalizado = unicodedata.normalize("NFD", text.casefold())
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn")


def find(key_or_method: str) -> Destination | None:
    """Destino por chave (``"pairings"``) ou por método (``"show_pairings"``)."""
    return _BY_KEY.get(key_or_method) or _BY_METHOD.get(key_or_method)


def search(query: str, destinations: Iterable[Destination] = DESTINATIONS) -> list[Destination]:
    """Filtra por rótulo ou palavras-chave, ignorando acento e caixa. Função
    pura: é ela que o command palette usa, e dá para testar sem abrir janela."""
    termo = _fold(query).strip()
    if not termo:
        return list(destinations)
    return [
        destination
        for destination in destinations
        if termo in _fold(destination.label) or termo in _fold(destination.keywords)
    ]


def by_group(destinations: Iterable[Destination] = DESTINATIONS) -> dict[str, list[Destination]]:
    """Destinos agrupados, preservando a ordem do registro (base da F3.1)."""
    grupos: dict[str, list[Destination]] = {}
    for destination in destinations:
        grupos.setdefault(destination.group, []).append(destination)
    return grupos


class Navigator:
    """Navegação central de uma janela: ir para um destino e recarregar o atual.

    Guarda apenas o **nome** do método atual, então sobrevive à reconstrução da
    tela (troca de tema, F5) sem segurar widget nenhum.
    """

    def __init__(self, host: Any) -> None:
        self._host = host
        self._current: str | None = None
        self._subscribers: list[Callable[[str | None], None]] = []

    def subscribe(self, callback: Callable[[str | None], None]) -> None:
        """Registra quem quer saber da tela ativa (a sidebar destaca o item).

        Chamado na hora com o valor corrente, para o inscrito já nascer em dia.
        """
        if callback not in self._subscribers:
            self._subscribers.append(callback)
        self._announce(callback)

    def clear_subscribers(self) -> None:
        """Esquece os inscritos. A janela e reconstruída em algumas situações
        (troca de tema), e um inscrito preso a widget morto só acumula erro."""
        self._subscribers.clear()

    def _announce(self, only: Callable[[str | None], None] | None = None) -> None:
        for callback in ([only] if only else list(self._subscribers)):
            try:
                callback(self._current)
            except Exception:
                logger.exception("Falha ao avisar inscrito da navegacao")

    @property
    def current(self) -> str | None:
        """Nome do ``show_*`` da tela em exibição (``None`` antes da primeira)."""
        return self._current

    @property
    def current_destination(self) -> Destination | None:
        return find(self._current) if self._current else None

    def record(self, method_name: str) -> None:
        """Anota a tela atual. Chamado ao limpar o conteúdo, então vale também
        para telas abertas por caminhos que não passam por ``go`` (um botão que
        chama ``show_pairings`` direto, por exemplo)."""
        if method_name.startswith("show_") and method_name != self._current:
            self._current = method_name
            self._announce()

    def go(self, key_or_method: str) -> bool:
        """Abre um destino. Devolve ``False`` se não existe ou não é chamável —
        o chamador decide se isso é erro (atalho quebrado) ou silêncio."""
        destination = find(key_or_method)
        method_name = destination.method if destination else key_or_method
        method = getattr(self._host, method_name, None)
        if not callable(method):
            logger.warning("Destino desconhecido na navegacao: %s", key_or_method)
            return False
        method()
        if method_name != self._current:
            self._current = method_name
        self._announce()
        return True

    def refresh_current(self) -> bool:
        """Recarrega a tela atual (o que o F5 faz). ``False`` se não há tela."""
        if not self._current:
            return False
        return self.go(self._current)
