"""Conferência da rodada gravada contra o holandês do Gacrux (RGS-16) — funções puras.

O ``pairingchecker`` do Gacrux tem um modo de VERIFICAÇÃO (``-c``): recebe o TRF
com a rodada já pareada e devolve, para ela, o par que o motor holandês
(C.04.3) produziria (``pairs``) ao lado do que está no arquivo (``current``).

- Rodada **gerada** pelo Gacrux: as duas listas têm de ser iguais; diferença é
  defeito (de integração, de dados ou do motor) e vira aviso bloqueante.
- Rodada **ajustada à mão**: a diferença é esperada (C.04.2: a alteração
  manual é registrada) e vai, como está, para o evento
  ``pairing_manual_adjustment``.

A comparação é por CONFRONTO e COR — o conjunto de pares ``(brancas, pretas)``,
com o PAB como ``(jogador, 0)``. A ordem das mesas fica de fora: o checker
numera as mesas pela regra dele e o Albericus grava as mesas na ordem em que
o motor as devolveu; mesmo confronto em outra mesa não é outra rodada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from src.services.constants import RESERVE_ENGINE_LABEL

Pair = tuple[int, int]


@dataclass(frozen=True)
class PairingCheck:
    """O que o verificador disse sobre uma rodada.

    ``stored``/``expected`` são pares ``(brancas, pretas)`` em ``player_id``
    (``0`` = PAB). ``checked`` é falso quando o verificador não rodou (motor
    ausente, arquivo que não representa a pontuação...) — ``error`` diz por quê.
    """

    round_number: int
    checked: bool
    stored: tuple[Pair, ...] = ()
    expected: tuple[Pair, ...] = ()
    error: str = ""
    names: Mapping[int, str] = field(default_factory=dict, compare=False)

    @property
    def matches(self) -> bool:
        return self.checked and set(self.stored) == set(self.expected)

    @property
    def diverges(self) -> bool:
        return self.checked and not self.matches

    def only_stored(self) -> list[Pair]:
        return sorted(set(self.stored) - set(self.expected))

    def only_expected(self) -> list[Pair]:
        return sorted(set(self.expected) - set(self.stored))

    def differences(self) -> list[str]:
        """Linhas legíveis: o que está gravado e o holandês não faria, e vice-versa."""
        if not self.checked:
            return [f"Rodada {self.round_number} não verificada: {self.error}"]
        linhas = [f"Gravado: {self._pair_label(pair)}" for pair in self.only_stored()]
        linhas += [f"Holandês (Gacrux): {self._pair_label(pair)}" for pair in self.only_expected()]
        return linhas

    def summary(self) -> str:
        if not self.checked:
            return f"Rodada {self.round_number}: verificador holandês não rodou ({self.error})."
        if self.matches:
            return f"Rodada {self.round_number}: confere com o holandês (Gacrux, modo verificação)."
        return (
            f"Rodada {self.round_number} difere do que o holandês (Gacrux) produziria: "
            + "; ".join(self.differences())
        )

    def as_dict(self) -> dict[str, Any]:
        """Para o evento de auditoria (JSON)."""
        return {
            "round_number": int(self.round_number),
            "checked": bool(self.checked),
            "matches": bool(self.matches),
            "error": self.error,
            "stored": [list(pair) for pair in sorted(self.stored)],
            "expected": [list(pair) for pair in sorted(self.expected)],
            "only_stored": [list(pair) for pair in self.only_stored()],
            "only_expected": [list(pair) for pair in self.only_expected()],
            "differences": self.differences(),
        }

    def _pair_label(self, pair: Pair) -> str:
        white, black = pair
        if not black:
            return f"{self._name(white)} — bye (PAB)"
        return f"{self._name(white)} (brancas) x {self._name(black)} (pretas)"

    def _name(self, player_id: int) -> str:
        return self.names.get(int(player_id)) or f"#{int(player_id)}"


def unchecked(round_number: int, error: str) -> PairingCheck:
    return PairingCheck(round_number=int(round_number), checked=False, error=str(error))


def stored_pairs(pairings: Iterable[Mapping[str, Any]]) -> tuple[Pair, ...]:
    """Pares da rodada gravada que o holandês decide: mesas e PAB.

    Bye solicitado (``F``/``H``/``Z``) não é pareamento — o jogador vai no
    ``-u`` do verificador e fica fora da comparação.
    """
    pairs: list[Pair] = []
    for pairing in pairings:
        white = int(pairing.get("white_player_id") or 0)
        if not white:
            continue
        if pairing.get("is_bye") or not pairing.get("black_player_id"):
            if is_pairing_allocated_bye(pairing):
                pairs.append((white, 0))
            continue
        pairs.append((white, int(pairing["black_player_id"])))
    return tuple(pairs)


def is_pairing_allocated_bye(pairing: Mapping[str, Any]) -> bool:
    return str(pairing.get("result") or "").strip().upper() in {"", "BYE", "U"}


def paired_player_ids(pairings: Iterable[Mapping[str, Any]]) -> set[int]:
    """Quem o pareamento desta rodada pôs numa mesa ou no PAB."""
    ids: set[int] = set()
    for white, black in stored_pairs(pairings):
        ids.add(white)
        if black:
            ids.add(black)
    return ids


def pairs_from_checker(
    rank_pairs: Sequence[Sequence[int]],
    rank_to_player_id: Mapping[int, int],
) -> tuple[Pair, ...]:
    """Pares do JSON do checker (start-rank) em ``player_id`` (``0`` = PAB).

    Número sem mapeamento vira ``-rank``: a divergência aparece em vez de sumir.
    """
    pairs: list[Pair] = []
    for item in rank_pairs:
        white, black = (int(value) for value in item)
        if not white and not black:
            continue
        if not white:
            white, black = black, 0
        pairs.append((
            int(rank_to_player_id.get(white, -white)),
            int(rank_to_player_id.get(black, -black)) if black else 0,
        ))
    return tuple(pairs)


def checker_round(data: Mapping[str, Any], round_number: int) -> Mapping[str, Any] | None:
    """O bloco da rodada no JSON do ``pairingchecker -c``."""
    result = data.get("pairingResult")
    rounds = result.get("roundpairing", []) if isinstance(result, Mapping) else result or []
    for item in rounds:
        if int(item.get("round") or 0) == int(round_number):
            return item
    return None


def reserve_round_notice(round_number: int) -> str:
    """Aviso permanente da rodada pareada pelo motor reserva (RGS-18)."""
    return (
        f"Rodada {int(round_number)} pareada pelo {RESERVE_ENGINE_LABEL}: o "
        "emparceiramento não foi feito pelo holandês FIDE (C.04.3) e pode diferir "
        "do que o motor homologado produziria."
    )


def manual_adjustment_reason_error(reason: Any) -> str:
    """Recado quando falta o motivo do ajuste manual da mesa; ``""`` quando serve.

    C.04.2: toda alteração manual do emparceiramento — trocar jogador ou
    inverter as cores — é registrada com motivo (RGS-16). O serviço recusa sem
    ele, e a tela usa esta mesma regra no diálogo de motivo.
    """
    if " ".join(str(reason or "").split()):
        return ""
    return (
        "Informe o motivo do ajuste manual da mesa: a alteração do "
        "emparceiramento fica registrada na auditoria (FIDE C.04.2)."
    )


def tpn_correction_reason_error(reason: Any) -> str:
    """Recado quando falta o motivo da correção de TPN; ``""`` quando serve (EQ-01.5).

    O TPN, uma vez definido, só muda por decisão do árbitro-chefe (C.04.6,
    art. 1.1.3), e a decisão fica na auditoria com o motivo. A regra de "texto
    em branco não serve" é a do ajuste manual da mesa; muda só o recado.
    """
    if not manual_adjustment_reason_error(reason):
        return ""
    return (
        "Informe o motivo da correção do número de emparceiramento (TPN): a "
        "decisão do árbitro-chefe fica registrada na auditoria (FIDE C.04.6)."
    )
