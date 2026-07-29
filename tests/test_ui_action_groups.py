"""Agrupamento de ações de formulário (F5.6 / P3-7).

Nenhum destes abre janela: o agrupamento é **dado**, e é justamente por ser dado
que dá para provar o que importa — que recolher 25 botões em 8 controles não
perdeu nenhuma ação pelo caminho.
"""
from __future__ import annotations

import json
import pathlib
import unittest

from src.ui.components.action_group import (
    ActionGroup,
    DangerAction,
    flatten_actions,
    visible_controls,
)
from src.ui.screens.tournament_players.menu import ACTION_KEYS, player_actions

RAIZ = pathlib.Path(__file__).resolve().parents[1]

# Teto de controles visíveis no mesmo nível (ESPEC_UI_UX §10.11).
MAX_CONTROLES = 8


def _handlers() -> dict[str, object]:
    """Um callable distinto por chave — permite rastrear cada ação até o destino."""
    return {chave: (lambda c=chave: c) for chave in ACTION_KEYS}


class VocabularioTest(unittest.TestCase):
    def test_grupo_conta_como_um_controle(self) -> None:
        acoes = [
            ("Solto", lambda: None),
            ActionGroup("Menu", [("A", lambda: None), None, ("B", lambda: None)]),
        ]
        self.assertEqual(2, visible_controls(acoes))

    def test_flatten_alcanca_itens_de_dentro_do_menu(self) -> None:
        acoes = [
            ("Solto", lambda: None),
            ActionGroup("Menu", [("A", lambda: None), None, ("B", lambda: None)]),
            DangerAction("Excluir", lambda: None),
        ]
        self.assertEqual(["Solto", "A", "B", "Excluir"], flatten_actions(acoes))

    def test_separador_nao_vira_acao(self) -> None:
        grupo = ActionGroup("Menu", [None, ("A", lambda: None), None])
        self.assertEqual(["A"], flatten_actions([grupo]))


class MuroDeJogadoresTest(unittest.TestCase):
    """O caso que motivou a F5.6: 25 botões idênticos numa coluna."""

    def setUp(self) -> None:
        self.acoes = player_actions(_handlers())

    def test_cabe_no_teto_de_controles_visiveis(self) -> None:
        self.assertLessEqual(visible_controls(self.acoes), MAX_CONTROLES)

    def test_nenhuma_das_25_acoes_se_perdeu(self) -> None:
        """A prova que sustenta o reagrupamento: recolher não é sumir."""
        catalogo = json.loads((RAIZ / "i18n" / "pt_BR.json").read_text(encoding="utf-8"))
        esperados = {
            valor
            for chave, valor in catalogo.items()
            if chave.startswith("players.action.") and not chave.endswith(".tip")
        }
        self.assertEqual(len(ACTION_KEYS), len(esperados))
        self.assertEqual(esperados, set(flatten_actions(self.acoes)))

    def test_cada_acao_chega_ao_proprio_handler(self) -> None:
        """Recolher no menu certo não pode trocar o comando de lugar."""
        por_rotulo: dict[str, object] = {}
        for acao in self.acoes:
            if isinstance(acao, ActionGroup):
                por_rotulo.update({i[0]: i[1] for i in acao.items if i is not None})
            elif isinstance(acao, DangerAction):
                por_rotulo[acao.label] = acao.command
            else:
                por_rotulo[acao[0]] = acao[1]

        catalogo = json.loads((RAIZ / "i18n" / "pt_BR.json").read_text(encoding="utf-8"))
        for chave in ACTION_KEYS:
            rotulo = catalogo[f"players.action.{chave}"]
            with self.subTest(acao=chave):
                self.assertEqual(chave, por_rotulo[rotulo]())

    def test_excluir_e_a_unica_destrutiva_e_fica_por_ultimo(self) -> None:
        destrutivas = [a for a in self.acoes if isinstance(a, DangerAction)]
        self.assertEqual(1, len(destrutivas))
        self.assertIs(self.acoes[-1], destrutivas[0])

    def test_menus_declarados_nao_nascem_vazios(self) -> None:
        grupos = [a for a in self.acoes if isinstance(a, ActionGroup)]
        self.assertEqual(3, len(grupos))
        for grupo in grupos:
            with self.subTest(grupo=grupo.label):
                # Menu de um item só é hierarquia sem ganho: seria um botão.
                self.assertGreater(len([i for i in grupo.items if i is not None]), 1)
                self.assertTrue(grupo.tip, "grupo recolhido precisa dizer o que guarda")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
