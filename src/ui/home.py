"""Pendências acionáveis da tela inicial — regras puras.

O app abria em "Perfil do Clube", uma tela de cadastro: quem entrava para
trabalhar tinha de descobrir sozinho o que estava pendente (achado P1-8). Aqui
ficam as **regras** que transformam uma fotografia do estado em uma lista de
pendências, cada uma com o destino para onde levar (*deep link* pelo registro da
F1.3, ver ESPEC_UI_UX §5.3).

Nada aqui toca banco nem Tk: ``HomeSnapshot`` é dado simples e
``build_pendencies`` é função pura. Quem lê o banco é ``collect_snapshot``, na
tela — assim as regras dão para testar sem torneio, sem janela e sem serviço.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Severidades, da mais para a menos urgente. A ordem da lista de pendências sai
# daqui: o que trava o trabalho aparece primeiro.
URGENT = "urgent"
ATTENTION = "attention"
INFO = "info"

_ORDEM = {URGENT: 0, ATTENTION: 1, INFO: 2}


@dataclass(frozen=True)
class Pendency:
    """Uma pendência acionável. ``destination`` é chave do registro de navegação."""

    key: str
    title: str
    detail: str
    destination: str
    severity: str = INFO
    action_label: str = "Abrir"


@dataclass(frozen=True)
class HomeSnapshot:
    """Fotografia do estado, em dado simples. Preenchida por quem lê o banco."""

    has_tournament: bool = False
    tournament_name: str = ""
    rounds_count: int = 0
    generated_rounds: int = 0
    closed_rounds: int = 0
    pending_results: int = 0
    blocking_issues: int = 0
    qr_pending: int = 0
    absent_players: int = 0
    players_count: int = 0
    defaulters: int = 0
    upcoming_events: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    open_announcements: int = 0


def _plural(quantidade: int, singular: str, plural: str) -> str:
    return singular if quantidade == 1 else plural


def build_pendencies(snapshot: HomeSnapshot) -> list[Pendency]:
    """Traduz a fotografia em pendências, da mais urgente para a menos.

    Lista vazia significa "nada pendente" — a tela mostra o estado de tudo em
    dia, que é informação, não ausência de informação.
    """
    itens: list[Pendency] = []

    if not snapshot.has_tournament:
        itens.append(
            Pendency(
                "sem_torneio",
                "Nenhum torneio selecionado",
                "Abra ou crie um torneio para comecar a trabalhar.",
                "tournaments",
                ATTENTION,
                action_label="Ver torneios",
            )
        )
    else:
        if snapshot.blocking_issues:
            itens.append(
                Pendency(
                    "bloqueios",
                    f"{snapshot.blocking_issues} pendencia(s) de arbitragem bloqueante(s)",
                    f"A rodada atual de '{snapshot.tournament_name}' nao fecha antes de resolver.",
                    "arbitration_panel",
                    URGENT,
                    action_label="Resolver",
                )
            )
        if snapshot.qr_pending:
            itens.append(
                Pendency(
                    "qr",
                    f"{snapshot.qr_pending} resultado(s) por QR aguardando aprovacao",
                    "Enviados pelas mesas; precisam de conferencia do arbitro.",
                    "arbitration_panel",
                    URGENT,
                    action_label="Conferir",
                )
            )
        if snapshot.pending_results:
            rotulo = _plural(snapshot.pending_results, "resultado", "resultados")
            itens.append(
                Pendency(
                    "resultados",
                    f"{snapshot.pending_results} {rotulo} a lancar",
                    f"Rodada aberta de '{snapshot.tournament_name}'.",
                    "pairings",
                    URGENT,
                    action_label="Lancar",
                )
            )
        if snapshot.generated_rounds == 0:
            detalhe = (
                f"'{snapshot.tournament_name}' tem {snapshot.players_count} jogador(es) inscrito(s)."
                if snapshot.players_count
                else f"'{snapshot.tournament_name}' ainda nao tem jogadores inscritos."
            )
            itens.append(
                Pendency(
                    "sem_rodadas",
                    "Torneio sem rodadas geradas",
                    detalhe,
                    "players" if not snapshot.players_count else "pairings",
                    ATTENTION,
                    action_label="Inscrever" if not snapshot.players_count else "Gerar rodada",
                )
            )
        elif snapshot.rounds_count and snapshot.closed_rounds >= snapshot.rounds_count:
            itens.append(
                Pendency(
                    "torneio_concluido",
                    "Torneio concluido",
                    f"Todas as {snapshot.rounds_count} rodadas de '{snapshot.tournament_name}' fecharam.",
                    "certificates",
                    INFO,
                    action_label="Emitir diplomas",
                )
            )

    if snapshot.defaulters:
        rotulo = _plural(snapshot.defaulters, "mensalidade", "mensalidades")
        itens.append(
            Pendency(
                "financeiro",
                f"{snapshot.defaulters} {rotulo} em atraso",
                "Cobrancas vencidas e ainda em aberto.",
                "finance",
                ATTENTION,
                action_label="Ver financeiro",
            )
        )

    if snapshot.upcoming_events:
        data, titulo = snapshot.upcoming_events[0]
        restantes = len(snapshot.upcoming_events) - 1
        detalhe = f"{data} — {titulo}"
        if restantes > 0:
            detalhe += f" (+{restantes} no calendario)"
        itens.append(
            Pendency("eventos", "Proximo evento", detalhe, "calendar", INFO, action_label="Calendario")
        )

    itens.sort(key=lambda item: _ORDEM.get(item.severity, len(_ORDEM)))
    return itens
