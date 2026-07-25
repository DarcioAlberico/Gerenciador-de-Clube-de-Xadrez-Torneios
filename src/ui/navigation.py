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
from typing import Any, Iterable

logger = logging.getLogger("src.ui.navigation")


@dataclass(frozen=True)
class Destination:
    """Um destino navegável. ``method`` é o nome do ``show_*`` na aplicação."""

    key: str
    label: str
    method: str
    keywords: str = ""
    icon: str | None = None
    group: str = ""


# Ordem = ordem de exibição no palette (e, mais adiante, na sidebar da F3.1).
DESTINATIONS: tuple[Destination, ...] = (
    # Clube
    Destination("visual_dashboard", "Dashboard Visual", "show_visual_dashboard", "inicio painel home", "dashboard", "Clube"),
    Destination("club", "Perfil do Clube", "show_club", "clube unidade", "clube", "Clube"),
    Destination("members", "Membros", "show_members", "socios alunos pessoas", "membros", "Clube"),
    Destination("learning_levels", "Níveis de Aprendizagem", "show_learning_levels", "niveis turmas", "aulas", "Clube"),
    Destination("guardians", "Responsáveis", "show_guardians", "guardian pais", "membros", "Clube"),
    # Treinamento — Aulas e Exercícios seguem DESATIVADOS (ver _build_menu).
    Destination("free_tournament", "Torneio | Livre", "show_free_tournament_mode", "modo livre escolar casual amistoso bagunca", "torneios", "Treinamento"),
    Destination("library", "Biblioteca Pedagógica", "show_library", "biblioteca acervo", "biblioteca", "Treinamento"),
    # Gestão
    Destination("referees", "Árbitros", "show_referees", "arbitros juiz", "arbitros", "Gestão"),
    Destination("inventory", "Inventário", "show_inventory", "estoque material", "integracoes", "Gestão"),
    Destination("finance", "Financeiro", "show_finance", "caixa contas dinheiro", "financeiro", "Gestão"),
    Destination("calendar", "Calendário", "show_calendar", "agenda eventos datas", "calendario", "Gestão"),
    Destination("internal_ranking", "Ranking Interno", "show_internal_ranking", "rating classificacao", "dashboard", "Gestão"),
    # Torneio
    Destination("tournaments", "Torneios", "show_tournaments", "lista campeonatos", "torneios", "Torneio"),
    Destination("tournament_dashboard", "Central do Torneio", "show_tournament_dashboard", "dashboard torneio", "emparceiramento", "Torneio"),
    Destination("arbitration_panel", "Painel do Árbitro", "show_arbitration_panel", "arbitragem pendencias", "arbitros", "Torneio"),
    Destination("tournament_settings", "Configurações do Torneio", "show_tournament_settings", "config torneio", "configuracoes", "Torneio"),
    Destination("players", "Jogadores", "show_players", "participantes inscritos", "membros", "Torneio"),
    Destination("teams", "Equipes", "show_teams", "times equipe", "clube", "Torneio"),
    Destination("pairings", "Rodadas / Emparceiramento", "show_pairings", "pairings round chave", "emparceiramento", "Torneio"),
    Destination("standings", "Classificação", "show_standings", "tabela standings ranking", "dashboard", "Torneio"),
    Destination("certificates", "Diplomas / Certificados", "show_certificates", "certificado diploma", "relatorios", "Torneio"),
    # Ferramentas
    Destination("export", "Exportar", "show_export", "trf16 pdf csv chess-results", "integracoes", "Ferramentas"),
    Destination("admin_reports", "Relatórios Administrativos", "show_administrative_reports", "relatorio admin", "relatorios", "Ferramentas"),
    Destination("financial_reports", "DRE Financeiro", "show_financial_reports", "dre financeiro relatorio", "financeiro", "Ferramentas"),
    Destination("communication", "Comunicação", "show_communication", "mensagem whatsapp comunicado", "comunicacao", "Ferramentas"),
    Destination("integrations", "Integrações Operacionais", "show_integrations", "qr relogio sync clock", "integracoes", "Ferramentas"),
    # Configurações
    Destination("app_settings", "Configurações do App", "show_app_settings", "preferencias config", "configuracoes", "Configurações"),
    Destination("audit", "Auditoria Completa", "show_audit_logs", "log auditoria historico", "auditoria", "Configurações"),
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
        if method_name.startswith("show_"):
            self._current = method_name

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
        self._current = method_name
        return True

    def refresh_current(self) -> bool:
        """Recarrega a tela atual (o que o F5 faz). ``False`` se não há tela."""
        if not self._current:
            return False
        return self.go(self._current)
