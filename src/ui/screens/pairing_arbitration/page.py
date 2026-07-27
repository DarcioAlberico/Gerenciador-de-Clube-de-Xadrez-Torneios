"""O contrato de um cadastro TRF25 — o que a casca de [`registry`](registry.py) pede.

Uma classe de dado (``Field``) e uma base (``RegistryPage``) com os oito
métodos que distinguem um cadastro do outro. Não importa Tk: uma página é
descrição mais chamada de controlador, e o teste exercita as duas sem janela.

A base **não** tem implementação padrão para nada que seja específico. Um
cadastro que esquecesse de dizer como exclui herdaria um "não faz nada"
silencioso; aqui ele explode na hora, no teste.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Field:
    """Um campo do formulário: rótulo, tipo e o que ele oferece."""

    OPTION = "option"
    ENTRY = "entry"

    key: str
    label: str
    kind: str = ENTRY
    values: tuple[str, ...] = field(default_factory=tuple)
    placeholder: str = ""
    initial: str = ""


class RegistryPage:
    """O que cada cadastro TRF25 precisa dizer sobre si."""

    # ---- Texto ------------------------------------------------------------ #

    def title(self) -> str:
        raise NotImplementedError

    def subtitle(self) -> str:
        raise NotImplementedError

    def form_title(self) -> str:
        raise NotImplementedError

    def table_title(self) -> str:
        raise NotImplementedError

    def hint(self) -> str:
        """Explicação abaixo do formulário. Vazio esconde o rótulo."""
        return ""

    def added_message(self) -> str:
        raise NotImplementedError

    def removed_message(self) -> str:
        raise NotImplementedError

    def select_error(self) -> str:
        raise NotImplementedError

    def confirm_texts(self) -> tuple[str, str]:
        """Título e pergunta do diálogo de exclusão."""
        raise NotImplementedError

    # ---- Forma ------------------------------------------------------------ #

    def fields(self) -> list[Field]:
        raise NotImplementedError

    def columns(self) -> dict[str, tuple[str, int]]:
        """Código da coluna → (título, largura), na ordem de exibição."""
        raise NotImplementedError

    def clear_on_add(self) -> tuple[str, ...]:
        """Campos que esvaziam depois de um lançamento bem-sucedido.

        Os seletores **não** entram: quem lança três ajustes seguidos para o
        mesmo jogador não quer reescolhê-lo três vezes.
        """
        return ()

    # ---- Dados ------------------------------------------------------------ #

    def rows(self) -> list[tuple[int, tuple[str, ...]]]:
        """``(id do registro, valores da linha)`` na ordem da tabela."""
        raise NotImplementedError

    def add(self, values: dict[str, str]) -> None:
        """Valida e grava. Levanta ``AppError`` com o recado ao usuário."""
        raise NotImplementedError

    def snapshot(self, record_id: int) -> dict[str, Any] | None:
        raise NotImplementedError

    def delete(self, record_id: int) -> None:
        raise NotImplementedError

    def restore(self, record: dict[str, Any]) -> None:
        raise NotImplementedError


class TournamentRegistryPage(RegistryPage):
    """Base dos três cadastros: todos pendem de um torneio e do tipo dele.

    ``is_team`` decide o substantivo da tela **e** o par de funções do banco que
    o controlador chama. Guardá-lo aqui, uma vez, é o que impede a tela de dizer
    "Jogador" enquanto grava numa tabela de equipes.
    """

    def __init__(self, controller: Any, tournament_id: int, tournament: dict[str, Any] | None) -> None:
        self.controller = controller
        self.tournament_id = int(tournament_id)
        self.tournament = tournament
        self.is_team = controller.is_team(tournament)
        self.targets: dict[str, int] = controller.targets(self.tournament_id, self.is_team)

    def subtitle(self) -> str:
        from ...i18n import t

        return t("arbitration.subtitle", torneio=(self.tournament or {}).get("name") or "")

    def target_id(self, label: str) -> int | None:
        """Id do rótulo escolhido no seletor. ``None`` quando não é um alvo real.

        O seletor mostra "(sem jogadores)" quando não há ninguém inscrito, e
        esse texto não é um alvo — devolver ``None`` aqui é o que faz o
        formulário recusar com um recado em vez de gravar lixo.
        """
        return self.targets.get(label)

    def target_labels(self, empty_label: str) -> tuple[str, ...]:
        return tuple(self.targets) or (empty_label,)
