"""Qual motor calculou a classificação, e o que dizer quando ele trocou (TBK-02).

Módulo **puro**: não roda motor, não lê banco, não abre tela. Recebe o estado do
último cálculo e devolve o retrato (`EngineReport`) mais os textos que a tela, a
trilha de auditoria e o painel usam para falar a mesma coisa.

Por que existe: até aqui, se o subprocesso do Gacrux falhasse, o
`pairing_service` logava um *warning* e passava a calcular pelo motor próprio. O
mesmo torneio podia publicar duas classificações diferentes entre rodadas sem
nenhum aviso ao árbitro — e o log de um app de mesa não é lido por ninguém no
meio de uma rodada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.services.constants import TIEBREAK_ENGINES

ENGINE_GACRUX = "gacrux"
ENGINE_ALBERICUS = "albericus"


def engine_label(code: str) -> str:
    """Código do motor → nome que o árbitro lê. Código desconhecido volta cru."""
    return TIEBREAK_ENGINES.get(str(code or ""), str(code or ""))


@dataclass(frozen=True)
class EngineReport:
    """Retrato do último cálculo de desempate de um torneio.

    Três estados, e a diferença entre eles importa:

    - **normal** — ``used == configured``: o motor escolhido calculou;
    - **degradado** (`fallback`) — o Gacrux falhou e o motor próprio assumiu.
      A classificação está publicada, mas não é a que o árbitro configurou;
    - **bloqueado** (`blocked`) — ``used`` vazio: o Gacrux falhou em modo
      estrito e o cálculo não aconteceu. Nada foi publicado.
    """

    configured: str
    used: str
    error: str = ""

    @property
    def fallback(self) -> bool:
        return bool(self.used) and self.used != self.configured

    @property
    def blocked(self) -> bool:
        return not self.used

    @property
    def healthy(self) -> bool:
        return not self.fallback and not self.blocked


def report_engine_ok(engine: str) -> EngineReport:
    """O motor configurado calculou (ou não havia nada a calcular)."""
    return EngineReport(configured=engine, used=engine)


def report_engine_fallback(configured: str, error: str) -> EngineReport:
    """O motor configurado falhou e o motor próprio assumiu."""
    return EngineReport(configured=configured, used=ENGINE_ALBERICUS, error=str(error or ""))


def report_engine_blocked(configured: str, error: str) -> EngineReport:
    """O motor configurado falhou em modo estrito: não há classificação."""
    return EngineReport(configured=configured, used="", error=str(error or ""))


@dataclass(frozen=True)
class EngineOutcome:
    """O que o cache guarda: os desempates **e** o retrato de quem os produziu.

    A falha entra no cache junto com o sucesso, e isso é decisão, não descuido:
    antes, um motor quebrado era re-executado a cada `standings()` — dezenas de
    subprocessos por tela — e cada execução era um evento de auditoria novo. Com
    a falha cacheada, o motor roda uma vez por estado do torneio, e o árbitro
    recebe um aviso por estado, não uma enxurrada.
    """

    report: EngineReport
    tiebreaks: dict[int, dict[str, Any]] | None


# --- Textos ---------------------------------------------------------------- #
#
# Um lugar só para cada frase, porque ela sai por três portas — a faixa da tela
# de classificação, o evento de auditoria e a pendência do painel do árbitro — e
# árbitro que lê três redações do mesmo fato desconfia das três.

BADGE_TONE_OK = "ok"
BADGE_TONE_WARNING = "warning"
BADGE_TONE_DANGER = "danger"


def engine_badge(report: EngineReport) -> dict[str, str]:
    """Faixa permanente da tela: ``{"label", "tone", "detail"}``.

    Permanente de propósito, inclusive no estado normal. Um aviso que só aparece
    quando algo deu errado ensina o árbitro a não olhar para aquele canto; uma
    faixa que sempre diz qual motor assinou a tabela é um lugar onde se olha.
    """
    if report.blocked:
        return {
            "label": f"Classificação bloqueada — o motor {engine_label(report.configured)} falhou",
            "tone": BADGE_TONE_DANGER,
            "detail": _detail_blocked(report),
        }
    if report.fallback:
        return {
            "label": (
                f"Motor: {engine_label(report.used)} — "
                f"o {engine_label(report.configured)} falhou e foi substituído"
            ),
            "tone": BADGE_TONE_WARNING,
            "detail": _detail_fallback(report),
        }
    return {
        "label": f"Motor de desempate: {engine_label(report.used)}",
        "tone": BADGE_TONE_OK,
        "detail": "",
    }


def _detail_fallback(report: EngineReport) -> str:
    return (
        "A classificação publicada não é a do motor configurado. O motor próprio "
        "não aplica o adversário virtual da FIDE, então a ordem dos empatados "
        "pode diferir da que sairá quando o motor voltar. "
        f"Falha: {report.error or 'sem mensagem do motor'}."
    )


def _detail_blocked(report: EngineReport) -> str:
    return (
        "O torneio está em modo estrito: em vez de trocar de motor em silêncio, "
        "o cálculo para. Resolva a falha ou desligue o modo estrito nas "
        f"configurações do torneio. Falha: {report.error or 'sem mensagem do motor'}."
    )


def fallback_audit_reason(report: EngineReport) -> str:
    """Motivo do evento de auditoria — é o que sai no relatório de auditoria."""
    return (
        f"Motor de desempate {engine_label(report.configured)} falhou; "
        f"classificação calculada por {engine_label(report.used)}. "
        f"Falha: {report.error or 'sem mensagem do motor'}"
    )


def strict_block_message(configured: str, error: str) -> str:
    """Texto do ``AppError`` que segura a publicação em modo estrito."""
    return (
        f"O motor de desempate {engine_label(configured)} falhou e este torneio "
        "está em modo estrito (falhar em vez de degradar). A classificação não "
        "foi calculada para não publicar uma ordem diferente da configurada. "
        f"Falha: {error or 'sem mensagem do motor'}"
    )
