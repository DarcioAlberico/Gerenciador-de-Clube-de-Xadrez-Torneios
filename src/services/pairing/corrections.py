"""Correção de resultado em rodada fechada (ARB-01).

Módulo **puro**: valida o motivo, decide se há desbloqueio válido, descobre as
rodadas que a correção contamina e escreve os textos. Não toca banco, não mede o
relógio — o "agora" chega como parâmetro, o que também torna a expiração
testável sem esperar quinze minutos.

O que estava errado antes: o motivo da correção era uma constante no código
("Correcao em rodada fechada."), então a trilha registrava que houve correção e
nunca por quê; e a permissão vinha de `allow_dangerous_changes`, um interruptor
do torneio inteiro que, ligado uma vez, deixava todas as rodadas fechadas
editáveis até alguém lembrar de desligar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Sequence

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# Janela padrão do desbloqueio. Curta de propósito: o desbloqueio existe para a
# correção que o árbitro está fazendo AGORA, não para deixar a rodada aberta.
DEFAULT_UNLOCK_MINUTES = 15
MAX_UNLOCK_MINUTES = 240

# Motivo curto não é motivo. Quatro caracteres barram "ok", ".", "erro" — que na
# ata de uma apelação valem tanto quanto o campo vazio.
MIN_REASON_LENGTH = 5


def clean_reason(reason: Any) -> str:
    return " ".join(str(reason or "").split())


def correction_reason_error(reason: Any) -> str:
    """Recado quando o motivo não serve; ``""`` quando serve."""
    cleaned = clean_reason(reason)
    if not cleaned:
        return (
            "Descreva o motivo da correção: a rodada está fechada e o registro "
            "vale como prova documental."
        )
    if len(cleaned) < MIN_REASON_LENGTH:
        return (
            f"O motivo da correção precisa de pelo menos {MIN_REASON_LENGTH} "
            "caracteres — descreva o que aconteceu."
        )
    return ""


def unlock_reason_error(reason: Any) -> str:
    """Mesmo critério do motivo da correção: desbloquear também é decisão."""
    cleaned = clean_reason(reason)
    if not cleaned:
        return "Descreva o motivo do desbloqueio da rodada."
    if len(cleaned) < MIN_REASON_LENGTH:
        return (
            f"O motivo do desbloqueio precisa de pelo menos {MIN_REASON_LENGTH} "
            "caracteres."
        )
    return ""


# --- Desbloqueio pontual --------------------------------------------------- #


def unlock_minutes(raw: Any) -> int:
    """Minutos pedidos → janela aceitável. Fora da faixa, volta ao padrão."""
    try:
        minutes = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_UNLOCK_MINUTES
    if minutes < 1 or minutes > MAX_UNLOCK_MINUTES:
        return DEFAULT_UNLOCK_MINUTES
    return minutes


def expiry_from(now: str, minutes: int) -> str:
    """``now + minutes`` no formato de timestamp do banco.

    Timestamp mal formado devolve ``now``: um desbloqueio que nasce expirado é
    mais seguro do que um que nasce eterno.
    """
    try:
        instant = datetime.strptime(str(now), TIMESTAMP_FORMAT)
    except (TypeError, ValueError):
        return str(now)
    return (instant + timedelta(minutes=unlock_minutes(minutes))).strftime(TIMESTAMP_FORMAT)


def unlock_is_live(unlock: Mapping[str, Any], now: str) -> bool:
    """Desbloqueio ainda vale? Revogado não vale; expirado não vale.

    A comparação é de texto porque o formato ``%Y-%m-%d %H:%M:%S`` ordena
    lexicograficamente igual ao tempo — e assim não se paga um parse por linha.
    """
    if str(unlock.get("revoked_at") or "").strip():
        return False
    expires_at = str(unlock.get("expires_at") or "").strip()
    if not expires_at:
        return False
    return str(now) < expires_at


def active_unlock(
    unlocks: Iterable[Mapping[str, Any]], now: str
) -> Mapping[str, Any] | None:
    """O desbloqueio vigente, se houver — o de expiração mais distante."""
    live = [unlock for unlock in unlocks if unlock_is_live(unlock, now)]
    if not live:
        return None
    return max(live, key=lambda item: str(item.get("expires_at") or ""))


@dataclass(frozen=True)
class UnlockState:
    """Retrato para a tela: pode corrigir? por que? até quando?"""

    allowed: bool
    source: str  # "unlock" | "dangerous_changes" | ""
    expires_at: str = ""
    reason: str = ""

    def label(self) -> str:
        if self.source == "unlock":
            return f"Rodada desbloqueada até {self.expires_at} — {self.reason}"
        if self.source == "dangerous_changes":
            return (
                "Mudanças perigosas habilitadas no torneio: qualquer rodada "
                "fechada aceita correção."
            )
        return "Rodada fechada. Desbloqueie para corrigir um resultado."


def unlock_state(
    unlocks: Iterable[Mapping[str, Any]],
    now: str,
    *,
    dangerous_changes: bool,
) -> UnlockState:
    """Decide a permissão, e diz de onde ela veio.

    O desbloqueio pontual vem primeiro porque é a permissão específica; o
    interruptor global do torneio continua valendo (não se tira um caminho que
    torneios em andamento já usam), mas fica em segundo, e a tela deixa claro
    que ele é o amplo.
    """
    vigente = active_unlock(unlocks, now)
    if vigente is not None:
        return UnlockState(
            allowed=True,
            source="unlock",
            expires_at=str(vigente.get("expires_at") or ""),
            reason=clean_reason(vigente.get("reason")),
        )
    if dangerous_changes:
        return UnlockState(allowed=True, source="dangerous_changes")
    return UnlockState(allowed=False, source="")


# --- Cascata --------------------------------------------------------------- #


def cascade_rounds(
    rounds: Sequence[Mapping[str, Any]],
    corrected_number: int,
) -> list[int]:
    """Rodadas posteriores já pareadas sobre o resultado que acabou de mudar.

    "Já pareadas" inclui a rodada apenas gerada: o pareamento dela nasceu do
    placar antigo, e é justamente aí que o árbitro ainda pode reparear. Rodada
    futura sem pareamento não entra — não há nada contaminado.
    """
    afetadas = [
        int(round_data.get("number") or 0)
        for round_data in rounds
        if int(round_data.get("number") or 0) > int(corrected_number)
        and str(round_data.get("status") or "") in ("generated", "closed")
    ]
    return sorted(set(afetadas))


def cascade_message(corrected_number: int, affected: Sequence[int]) -> str:
    """Recado da pendência de cascata — diz o que fazer, não só o que houve."""
    if not affected:
        return ""
    lista = ", ".join(str(number) for number in affected)
    plural = "s" if len(affected) > 1 else ""
    return (
        f"O resultado corrigido na rodada {corrected_number} alimentou o "
        f"pareamento da{plural} rodada{plural} {lista}. Confira o pareamento e "
        "os desempates; se a ordem mudou, considere reparear a rodada seguinte "
        "antes de publicar."
    )


def reconcilable_rounds(
    rounds: Sequence[Mapping[str, Any]],
    corrected_number: int,
) -> list[Mapping[str, Any]]:
    """Rodadas FECHADAS cujo retrato de classificação a correção invalidou.

    Da rodada corrigida para frente, e só as fechadas: rodada aberta não tem
    retrato para reconciliar.
    """
    return sorted(
        (
            round_data
            for round_data in rounds
            if int(round_data.get("number") or 0) >= int(corrected_number)
            and str(round_data.get("status") or "") == "closed"
        ),
        key=lambda item: int(item.get("number") or 0),
    )
