"""Estado das telas de arbitragem — dado puro (B-6, molde da F1.5).

Sem Tk, sem banco. Aqui moram as decisões que a tela tomava dentro de
``show_*``: quais cartões o painel mostra, qual é o **próximo passo
recomendado**, o que cada formulário TRF25 aceita e o que ele recusa.

Três dessas coisas viviam em cadeias ``if/elif`` no meio da montagem de widgets,
e a única forma de exercitar "o que o painel recomenda quando a rodada está
pronta para fechar" era abrir a janela e olhar. Aqui são função, e o teste roda
em milissegundos.

O texto vem do catálogo (**B-3**): este módulo é puro, e
[`i18n`](../../i18n.py) também é — importar um do outro não fura camada nenhuma.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...i18n import t

# Chaves de ação que o painel entende. O serviço já emite estas oito nos alertas
# (`alerts_detailed[*]["action"]`) e o checklist de fechamento acrescenta
# `lineups`. Ficam aqui, e não soltas na view, porque há um teste que cobra que
# **toda** ação emitida pelo serviço tenha comando — deep link quebrado no
# painel do árbitro é pior do que alerta nenhum (mesma lição da F3.2).
ACTION_BLOCKING_ISSUES = "blocking_issues"
ACTION_PENDING_RESULTS = "pending_results"
ACTION_READY_TO_CLOSE = "ready_to_close"
ACTION_INITIAL_CALL = "initial_call"
ACTION_ABSENT_PLAYERS = "absent_players"
ACTION_CORRECTIONS = "corrections"
ACTION_QR_PENDING = "qr_pending"
ACTION_PREVIEW_NEXT = "preview_next"
ACTION_LINEUPS = "lineups"

PANEL_ACTIONS: tuple[str, ...] = (
    ACTION_BLOCKING_ISSUES,
    ACTION_PENDING_RESULTS,
    ACTION_READY_TO_CLOSE,
    ACTION_INITIAL_CALL,
    ACTION_ABSENT_PLAYERS,
    ACTION_CORRECTIONS,
    ACTION_QR_PENDING,
    ACTION_PREVIEW_NEXT,
    ACTION_LINEUPS,
)

# Opções dos dois seletores de preferência do painel, com os limites que o
# `_bounded_int_setting` cobra na volta. Valor fora da faixa vira o padrão.
REFRESH_INTERVAL_CHOICES: tuple[str, ...] = ("10", "15", "30", "60", "120")
REFRESH_INTERVAL_DEFAULT = 15
REFRESH_INTERVAL_MIN = 10
REFRESH_INTERVAL_MAX = 120

INLINE_LIMIT_CHOICES: tuple[str, ...] = ("10", "20", "30", "40", "50")
INLINE_LIMIT_DEFAULT = 20
INLINE_LIMIT_MIN = 10
INLINE_LIMIT_MAX = 50

# Tipos de bye solicitado que o TRF25 aceita (F/H/Z). Qualquer outro código é
# recusado no formulário, não no banco.
REQUESTED_BYE_CODES = frozenset({"F", "H", "Z"})


# ---- Painel do árbitro ---------------------------------------------------- #


@dataclass(frozen=True)
class PanelCard:
    """Um cartão de KPI: título, número em destaque, legenda e para onde leva."""

    title: str
    value: str
    subtitle: str
    action: str


@dataclass(frozen=True)
class NextStep:
    """O passo recomendado — rótulo e ação, decididos por ``next_step``."""

    label: str
    action: str


def panel_cards(metrics: dict[str, Any]) -> list[PanelCard]:
    """Os seis cartões do painel, na ordem em que a tela os desenha."""
    return [
        PanelCard(
            t("arbitration.card.rounds"),
            f"{metrics['closed_rounds']}/{metrics['rounds_count']}",
            t("arbitration.card.rounds.sub", geradas=metrics["generated_rounds"]),
            ACTION_PENDING_RESULTS,
        ),
        PanelCard(
            t("arbitration.card.pending"),
            str(metrics["pending_results"]),
            t("arbitration.card.pending.sub"),
            ACTION_PENDING_RESULTS,
        ),
        PanelCard(
            t("arbitration.card.byes"),
            str(metrics["byes"]),
            t("arbitration.card.byes.sub"),
            ACTION_PENDING_RESULTS,
        ),
        PanelCard(
            t("arbitration.card.absent"),
            str(metrics["absent_players"]),
            t("arbitration.card.absent.sub"),
            ACTION_ABSENT_PLAYERS,
        ),
        PanelCard(
            t("arbitration.card.corrections"),
            str(metrics["corrections"]),
            t("arbitration.card.corrections.sub"),
            ACTION_CORRECTIONS,
        ),
        PanelCard(
            t("arbitration.card.clock"),
            str(metrics["round_duration_label"]),
            t(
                "arbitration.card.clock.sub",
                inicio=metrics["round_started_label"],
                estado=str(metrics["round_clock_status"]).replace("_", " "),
            ),
            ACTION_PENDING_RESULTS,
        ),
    ]


def next_step(metrics: dict[str, Any]) -> NextStep:
    """O que o árbitro deveria fazer agora, em ordem de urgência.

    A ordem **é** a regra: pendência bloqueante vem antes de lançar resultado,
    que vem antes de fechar rodada. Estava numa cadeia ``if/elif`` no meio da
    montagem de widgets, onde só a janela conseguia exercitá-la.
    """
    if metrics["blocking_issues"] or metrics["submitted_results"]:
        return NextStep(t("arbitration.next.blocking"), ACTION_BLOCKING_ISSUES)
    if metrics["pending_results"]:
        return NextStep(
            t("arbitration.next.pending", quantidade=metrics["pending_results"]),
            ACTION_PENDING_RESULTS,
        )
    if metrics["ready_to_close"]:
        return NextStep(
            t("arbitration.next.close", rodada=metrics["latest_round_number"]),
            ACTION_READY_TO_CLOSE,
        )
    if metrics["can_preview_next_round"]:
        return NextStep(t("arbitration.next.preview"), ACTION_PREVIEW_NEXT)
    return NextStep(t("arbitration.next.initial_call"), ACTION_INITIAL_CALL)


def progress_ratio(metrics: dict[str, Any]) -> float | None:
    """Fração de mesas resolvidas (0..1), ou ``None`` quando não há mesas.

    ``None`` e não ``0.0``: rodada sem mesa nenhuma não é rodada 0% resolvida —
    é rodada que ainda não começou, e a tela esconde a barra em vez de mostrar
    uma barra vazia que parece atraso.
    """
    total = int(metrics.get("total_results") or 0)
    if not total:
        return None
    percentual = int(metrics.get("round_progress_percent") or 0)
    return max(0.0, min(1.0, percentual / 100))


# ---- Rótulos de seleção --------------------------------------------------- #


def target_label(record: dict[str, Any]) -> str:
    """"Nome (#id)" — o rótulo dos seletores de jogador/equipe.

    O ``#id`` não é enfeite: dois jogadores homônimos existem, e sem ele o
    árbitro escolheria no escuro.
    """
    nome = str(record.get("name") or "").strip() or t("arbitration.common.unnamed")
    return f"{nome} (#{record['id']})"


def targets_by_label(records: list[dict[str, Any]]) -> dict[str, int]:
    """Rótulo → id, na ordem alfabética que a tela mostra."""
    ordenados = sorted(records, key=lambda item: str(item.get("name") or "").casefold())
    return {target_label(item): int(item["id"]) for item in ordenados}


def round_window_label(first_round: int, last_round: int) -> str:
    """Janela de rodadas de uma proibição: "3", "1-5" ou "2+" (aberta)."""
    if last_round == 0:
        return f"{first_round}+"
    if first_round == last_round:
        return str(first_round)
    return f"{first_round}-{last_round}"


def aat_type_labels() -> dict[str, str]:
    """Rótulo amigável → código TRF25 §7.3 do tipo de atribuição anormal.

    Função e não constante de módulo, como em Jogadores: constante congelaria o
    texto no idioma carregado durante o *import*, e a promessa da B-3 é que
    trocar o catálogo troque a tela. Escrito chave a chave, porque
    ``t(f"...{codigo}")`` é invisível para o `test_ui_i18n`.
    """
    return {
        t("arbitration.aat.points"): "",
        t("arbitration.aat.win"): "W",
        t("arbitration.aat.draw"): "D",
        t("arbitration.aat.loss"): "L",
        t("arbitration.aat.bye_full"): "F",
        t("arbitration.aat.bye_half"): "H",
        t("arbitration.aat.bye_zero"): "Z",
        t("arbitration.aat.walkover_for"): "+",
        t("arbitration.aat.walkover_against"): "-",
    }


def requested_bye_labels() -> dict[str, str]:
    """Rótulo → código (F/H/Z) do bye solicitado."""
    return {
        t("arbitration.bye.full"): "F",
        t("arbitration.bye.half"): "H",
        t("arbitration.bye.zero"): "Z",
    }


def issue_filter_labels() -> dict[str, str]:
    """Rótulo → código do filtro da Central de pendências."""
    return {
        t("arbitration.issues.filter.all"): "all",
        t("arbitration.issues.filter.decision"): "decision",
        t("arbitration.issues.filter.qr"): "qr",
        t("arbitration.issues.filter.sync"): "sync",
        t("arbitration.issues.filter.clock"): "clock",
        t("arbitration.issues.filter.tiebreak"): "tiebreak",
        t("arbitration.issues.filter.correction"): "correction",
    }


def round_labels(numbers: list[int], *, include_all: bool) -> dict[str, int]:
    """Rótulo → número da rodada. ``include_all`` acrescenta "Todas" como 0."""
    rotulos: dict[str, int] = {}
    if include_all:
        rotulos[t("arbitration.round.all")] = 0
    for numero in numbers:
        rotulos[t("arbitration.round.one", numero=numero)] = int(numero)
    return rotulos


# ---- Formulários ---------------------------------------------------------- #


def parse_points(text: str) -> float | None:
    """Texto do formulário → pontos. ``None`` quando não é número.

    Vazio é zero (lançar só o tipo de atribuição é legítimo) e a vírgula vale
    como separador decimal, porque é o que o teclado brasileiro produz. Quem
    chama transforma o ``None`` em recado; antes, `float("abc")` subia como
    ``ValueError`` — e a tela dizia "Erro inesperado", com código de log, para
    um erro de digitação previsível.
    """
    limpo = (text or "").strip().replace(",", ".")
    if not limpo:
        return 0.0
    try:
        return float(limpo)
    except ValueError:
        return None


def parse_round(text: str, default: int) -> int | None:
    """Texto → número de rodada. ``None`` quando não é inteiro ou é negativo."""
    limpo = (text or "").strip()
    if not limpo:
        return default
    try:
        valor = int(limpo)
    except ValueError:
        return None
    return valor if valor >= 0 else None


@dataclass(frozen=True)
class AdjustmentForm:
    """Retrato do formulário de ajuste de pontos (TRF25 §7.3)."""

    target_id: int | None
    round_number: int
    aat_type: str
    match_points_text: str
    game_points_text: str
    reason: str
    is_team: bool = False

    def validation_error(self) -> str:
        if not self.target_id:
            return t("arbitration.adjustments.error.target")
        if self.game_points() is None:
            return t("arbitration.error.points")
        if self.is_team and self.match_points() is None:
            return t("arbitration.error.points")
        if not self.aat_type and not self.match_points() and not self.game_points():
            return t("arbitration.adjustments.error.empty")
        return ""

    def match_points(self) -> float | None:
        return parse_points(self.match_points_text) if self.is_team else 0.0

    def game_points(self) -> float | None:
        return parse_points(self.game_points_text)

    def payload(self) -> dict[str, Any]:
        """O que o banco recebe. Só chame depois de ``validation_error`` vazio."""
        return {
            "round_number": self.round_number,
            "player_id": None if self.is_team else self.target_id,
            "team_id": self.target_id if self.is_team else None,
            "aat_type": self.aat_type,
            "match_points": self.match_points() or 0.0,
            "game_points": self.game_points() or 0.0,
            "reason": self.reason.strip(),
        }


@dataclass(frozen=True)
class RequestedByeForm:
    """Retrato do formulário de bye solicitado (TRF25)."""

    target_id: int | None
    round_number: int | None
    bye_type: str
    reason: str
    is_team: bool = False

    def validation_error(self) -> str:
        if not self.target_id:
            return (
                t("arbitration.byes.error.target_team")
                if self.is_team
                else t("arbitration.byes.error.target_player")
            )
        if not self.round_number:
            return t("arbitration.byes.error.round")
        if self.bye_type not in REQUESTED_BYE_CODES:
            return t("arbitration.byes.error.type")
        return ""


@dataclass(frozen=True)
class ProhibitionForm:
    """Retrato do formulário de proibição de pareamento (TRF25 registro 260)."""

    target_a_id: int | None
    target_b_id: int | None
    first_round_text: str
    last_round_text: str
    reason: str
    is_team: bool = False

    def validation_error(self) -> str:
        if not self.target_a_id or not self.target_b_id:
            return (
                t("arbitration.prohibitions.error.target_team")
                if self.is_team
                else t("arbitration.prohibitions.error.target_player")
            )
        if self.target_a_id == self.target_b_id:
            return (
                t("arbitration.prohibitions.error.same_team")
                if self.is_team
                else t("arbitration.prohibitions.error.same_player")
            )
        if self.first_round() is None or self.last_round() is None:
            return t("arbitration.error.round")
        primeira, ultima = self.first_round() or 1, self.last_round() or 0
        if ultima and ultima < primeira:
            return t("arbitration.prohibitions.error.window")
        return ""

    def first_round(self) -> int | None:
        return parse_round(self.first_round_text, 1)

    def last_round(self) -> int | None:
        return parse_round(self.last_round_text, 0)

    def payload(self) -> dict[str, Any]:
        """O que o banco recebe. Só chame depois de ``validation_error`` vazio."""
        return {
            "first_round": (self.first_round() or 1) or 1,
            "last_round": self.last_round() or 0,
            "reason": self.reason.strip(),
        }
