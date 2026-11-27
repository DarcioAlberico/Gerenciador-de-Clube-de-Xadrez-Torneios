"""Ações na linha do jogador — dado puro (RGS-22, RGS-23).

"A ação mora onde está o objeto": bye, falta, retirada e reintegração são
coisas que se fazem A UM JOGADOR, e por isso aparecem no menu da linha dele —
em Jogadores, na Classificação e na chamada da tela de Rodadas. Antes elas
moravam num seletor de status no formulário de cadastro (o "Atualizar" gravava
o status cru no banco) e numa tela de cadastro TRF25 sem busca.

Aqui só o que é decisão: quais itens o menu mostra para este jogador, quais
escopos a retirada oferece e o texto de cada um. Sem Tk e sem banco.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.services.pairing.participation import (
    STATUS_ABSENT,
    STATUS_ACTIVE,
    STATUS_INACTIVE,
    STATUS_WITHDRAWN,
    is_out,
)

from ...i18n import t

# Chaves das ações do menu. O teste de contagem de ações fala nelas.
ACTION_BYE = "bye"
ACTION_MISS_ROUND = "miss_round"
ACTION_WITHDRAW = "withdraw"
ACTION_REINSTATE = "reinstate"

# Escopos da retirada: só uma rodada (bye Z, status intacto) ou mudança de
# estado de participação pelo serviço (ARB-05).
SCOPE_ROUND = "round"
SCOPE_ABSENT = STATUS_ABSENT
SCOPE_WITHDRAWN = STATUS_WITHDRAWN
SCOPE_INACTIVE = STATUS_INACTIVE

# Tipos de bye que o menu oferece (RGS-23: "H ½ / Z 0"). O F, quando o
# regulamento permite, continua no cadastro do painel.
BYE_TYPES = ("H", "Z")


@dataclass(frozen=True)
class MenuEntry:
    key: str
    label: str
    enabled: bool = True


def player_menu(player: Mapping[str, Any], *, absence_round: int) -> list[MenuEntry | None]:
    """Itens do menu da linha; ``None`` é separador.

    Quem está fora (desistente, ausente, não emparceirado) não recebe bye nem
    "faltar só a uma rodada" — o pedido seria descartado na geração. Para ele
    o que faz sentido é Reintegrar, e só para ele.
    """
    status = str(player.get("player_status") or STATUS_ACTIVE)
    fora = is_out(status)
    return [
        MenuEntry(ACTION_BYE, t("player_actions.menu.bye"), not fora),
        MenuEntry(
            ACTION_MISS_ROUND,
            t("player_actions.menu.miss_round", rodada=int(absence_round)),
            not fora,
        ),
        None,
        MenuEntry(ACTION_WITHDRAW, t("player_actions.menu.withdraw"), status != STATUS_WITHDRAWN),
        MenuEntry(ACTION_REINSTATE, t("player_actions.menu.reinstate"), fora),
    ]


def scope_labels(round_number: int) -> dict[str, str]:
    """Escopo → rótulo do seletor da retirada, na ordem da tela."""
    return {
        SCOPE_ROUND: t("player_actions.scope.round", rodada=int(round_number)),
        SCOPE_ABSENT: t("player_actions.scope.absent"),
        SCOPE_WITHDRAWN: t("player_actions.scope.withdrawn"),
        SCOPE_INACTIVE: t("player_actions.scope.inactive"),
    }


def bye_type_labels() -> dict[str, str]:
    """Código → rótulo do seletor de tipo do bye."""
    return {
        "H": t("player_actions.bye.type.half"),
        "Z": t("player_actions.bye.type.zero"),
    }


def points_text(value: float) -> str:
    """``1.5`` → ``"1,5"``; ``0.5`` → ``"½"``. É o que o salão lê."""
    if abs(value - 0.5) < 1e-9:
        return "½"
    texto = f"{value:.1f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")
