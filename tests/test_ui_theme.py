"""Testes da camada de tema (``src/ui/theme.py``).

O ponto central da F1.1: trocar um preset tem de alcançar **quem já importou o
token**, sem o antigo `_propagate_theme_globals` (que reescrevia `sys.modules`).
Isso só funciona porque o token é um objeto mutado no lugar — é exatamente essa
propriedade que os testes abaixo protegem.
"""
from __future__ import annotations

import unittest

from src.ui import support, theme


class ColorTokenTest(unittest.TestCase):
    def test_e_par_claro_escuro(self) -> None:
        token = theme.ColorToken("#111111", "#222222")
        self.assertEqual(["#111111", "#222222"], list(token))
        self.assertEqual("#111111", token[0])
        self.assertEqual("#222222", token[1])

    def test_set_troca_valor_mantendo_o_objeto(self) -> None:
        token = theme.ColorToken("#111111", "#222222")
        referencia = token  # como faria um `from theme import TOKEN`
        token.set("#333333", "#444444")
        self.assertIs(referencia, token, "o objeto nao pode ser substituido")
        self.assertEqual(["#333333", "#444444"], list(referencia))


class TemaPropagaTest(unittest.TestCase):
    """Cada teste restaura os presets padrão — os tokens são globais do processo."""

    def tearDown(self) -> None:
        theme.apply_accent_preset("blue")
        theme.apply_bg_preset("slate")
        theme.apply_frame_bg_preset("slate")
        theme._listeners.clear()

    def test_support_reexporta_o_mesmo_objeto(self) -> None:
        self.assertIs(theme.THEME_ACCENT, support.THEME_ACCENT)
        self.assertIs(theme.THEME_PANEL_BG, support.THEME_PANEL_BG)

    def test_trocar_accent_alcanca_quem_importou_antes(self) -> None:
        # simula o `from ..support import *` que as telas fazem na importacao
        token_importado = support.THEME_ACCENT
        theme.apply_accent_preset("emerald")
        esperado = theme.ACCENT_PRESETS["emerald"]
        self.assertEqual([esperado["l"], esperado["d"]], list(token_importado))

    def test_trocar_fundo_de_frame_alcanca_painel_e_tree(self) -> None:
        painel, tree = support.THEME_PANEL_BG, support.THEME_TREE_BG
        theme.apply_frame_bg_preset("carbon")
        self.assertEqual(list(theme.FRAME_BG_PRESETS["carbon"]["panel"]), list(painel))
        self.assertEqual(list(theme.FRAME_BG_PRESETS["carbon"]["tree"]), list(tree))

    def test_preset_desconhecido_cai_no_padrao(self) -> None:
        theme.apply_accent_preset("nao-existe")
        padrao = theme.ACCENT_PRESETS["blue"]
        self.assertEqual([padrao["l"], padrao["d"]], list(theme.THEME_ACCENT))

    def test_listeners_sao_avisados_em_cada_troca(self) -> None:
        avisos: list[str] = []
        theme.on_theme_change(lambda: avisos.append("x"))
        theme.apply_accent_preset("red")
        theme.apply_bg_preset("navy")
        theme.apply_frame_bg_preset("navy")
        self.assertEqual(3, len(avisos))

    def test_listener_registrado_duas_vezes_avisa_uma(self) -> None:
        avisos: list[str] = []

        def ouvinte() -> None:
            avisos.append("x")

        theme.on_theme_change(ouvinte)
        theme.on_theme_change(ouvinte)
        theme.apply_accent_preset("red")
        self.assertEqual(1, len(avisos))

    def test_off_theme_change_cancela(self) -> None:
        avisos: list[str] = []

        def ouvinte() -> None:
            avisos.append("x")

        theme.on_theme_change(ouvinte)
        theme.off_theme_change(ouvinte)
        theme.apply_accent_preset("red")
        self.assertEqual([], avisos)

    def test_listener_quebrado_nao_derruba_a_troca(self) -> None:
        ok: list[str] = []

        def explode() -> None:
            raise RuntimeError("listener ruim")

        theme.on_theme_change(explode)
        theme.on_theme_change(lambda: ok.append("segundo"))
        theme.apply_accent_preset("teal")  # nao pode levantar
        self.assertEqual(["segundo"], ok, "o listener seguinte ainda roda")
        teal = theme.ACCENT_PRESETS["teal"]
        self.assertEqual([teal["l"], teal["d"]], list(theme.THEME_ACCENT))


class SemHackDeGlobaisTest(unittest.TestCase):
    def test_propagate_theme_globals_nao_existe_mais(self) -> None:
        """P0-5: a troca de tema não pode voltar a reescrever `sys.modules`."""
        self.assertFalse(hasattr(theme, "_propagate_theme_globals"))
        self.assertFalse(hasattr(support, "_propagate_theme_globals"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
