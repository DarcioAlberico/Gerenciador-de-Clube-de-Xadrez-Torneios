from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.ui import support

# Cada cor dos presets deve ser um hex #RRGGBB valido.
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _is_hex(value: object) -> bool:
    return isinstance(value, str) and bool(HEX_RE.match(value))


class AppearancePalettesTest(unittest.TestCase):
    """Valida as paletas de Aparencia (destaque / fundo / fundo dos frames)."""

    def test_each_category_offers_at_least_twelve_options(self) -> None:
        self.assertGreaterEqual(len(support.ACCENT_PRESETS), 12)
        self.assertGreaterEqual(len(support.BG_COLOR_PRESETS), 12)
        self.assertGreaterEqual(len(support.FRAME_BG_PRESETS), 12)

    def test_accent_presets_have_wellformed_colors(self) -> None:
        for key, preset in support.ACCENT_PRESETS.items():
            with self.subTest(accent=key):
                self.assertTrue(preset.get("label"), f"{key} sem label")
                for slot in ("l", "d", "hl", "hd"):
                    self.assertTrue(
                        _is_hex(preset.get(slot)),
                        f"{key}.{slot}={preset.get(slot)!r} nao e hex #RRGGBB",
                    )

    def test_background_presets_have_wellformed_light_dark_pairs(self) -> None:
        for key, preset in support.BG_COLOR_PRESETS.items():
            with self.subTest(bg=key):
                for slot in ("app", "statusbar"):
                    pair = preset.get(slot)
                    self.assertIsInstance(pair, tuple, f"{key}.{slot} deve ser tupla")
                    self.assertEqual(len(pair), 2, f"{key}.{slot} precisa de (claro, escuro)")
                    self.assertTrue(
                        all(_is_hex(color) for color in pair),
                        f"{key}.{slot}={pair!r} tem cor invalida",
                    )

    def test_frame_presets_have_wellformed_light_dark_pairs(self) -> None:
        for key, preset in support.FRAME_BG_PRESETS.items():
            with self.subTest(frame=key):
                for slot in ("panel", "tree"):
                    pair = preset.get(slot)
                    self.assertIsInstance(pair, tuple, f"{key}.{slot} deve ser tupla")
                    self.assertEqual(len(pair), 2, f"{key}.{slot} precisa de (claro, escuro)")
                    self.assertTrue(
                        all(_is_hex(color) for color in pair),
                        f"{key}.{slot}={pair!r} tem cor invalida",
                    )

    def test_labels_cover_exactly_the_preset_keys(self) -> None:
        self.assertEqual(set(support.ACCENT_PRESET_LABELS), set(support.ACCENT_PRESETS))
        self.assertEqual(set(support.BG_COLOR_PRESET_LABELS), set(support.BG_COLOR_PRESETS))
        self.assertEqual(set(support.FRAME_BG_PRESET_LABELS), set(support.FRAME_BG_PRESETS))

    def test_labels_are_unique_and_nonempty(self) -> None:
        for name, labels in (
            ("accent", support.ACCENT_PRESET_LABELS),
            ("bg", support.BG_COLOR_PRESET_LABELS),
            ("frame", support.FRAME_BG_PRESET_LABELS),
        ):
            with self.subTest(group=name):
                values = list(labels.values())
                self.assertTrue(all(value.strip() for value in values), "ha label vazio")
                self.assertEqual(len(values), len(set(values)), "ha labels duplicados")

    def test_fallback_keys_exist(self) -> None:
        # Chaves usadas como default em app.py / settings.py.
        self.assertIn("blue", support.ACCENT_PRESETS)
        self.assertIn("slate", support.BG_COLOR_PRESETS)
        self.assertIn("slate", support.FRAME_BG_PRESETS)


class ApplyPresetThemeGlobalsTest(unittest.TestCase):
    """Aplicar um preset deve atualizar as variaveis globais de tema."""

    def tearDown(self) -> None:
        # Restaura o tema padrao para nao vazar estado entre testes/modulos.
        support.apply_accent_preset("blue")
        support.apply_bg_preset("slate")
        support.apply_frame_bg_preset("slate")

    def test_apply_accent_preset_sets_theme_accent(self) -> None:
        support.apply_accent_preset("emerald")
        preset = support.ACCENT_PRESETS["emerald"]
        self.assertEqual(support.THEME_ACCENT, (preset["l"], preset["d"]))

    def test_apply_bg_preset_sets_app_and_statusbar(self) -> None:
        support.apply_bg_preset("forest")
        preset = support.BG_COLOR_PRESETS["forest"]
        self.assertEqual(support.THEME_APP_BG, preset["app"])
        self.assertEqual(support.THEME_STATUSBAR_BG, preset["statusbar"])

    def test_apply_frame_bg_preset_sets_panel_and_tree(self) -> None:
        support.apply_frame_bg_preset("navy")
        preset = support.FRAME_BG_PRESETS["navy"]
        self.assertEqual(support.THEME_PANEL_BG, preset["panel"])
        self.assertEqual(support.THEME_TREE_BG, preset["tree"])

    def test_unknown_preset_falls_back_to_default(self) -> None:
        support.apply_accent_preset("nao-existe")
        blue = support.ACCENT_PRESETS["blue"]
        self.assertEqual(support.THEME_ACCENT, (blue["l"], blue["d"]))

        support.apply_bg_preset("nao-existe")
        self.assertEqual(support.THEME_APP_BG, support.BG_COLOR_PRESETS["slate"]["app"])

        support.apply_frame_bg_preset("nao-existe")
        self.assertEqual(support.THEME_PANEL_BG, support.FRAME_BG_PRESETS["slate"]["panel"])


class ColorSettingsPersistenceTest(unittest.TestCase):
    """O preset escolhido precisa sobreviver ao ciclo Salvar -> reabrir."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_accent_bg_and_frame_presets_round_trip(self) -> None:
        self.db.save_app_settings(
            {
                "accent_preset": "emerald",
                "bg_preset": "forest",
                "frame_bg_preset": "navy",
            }
        )
        reloaded = self.db.get_app_settings()
        self.assertEqual(reloaded.get("accent_preset"), "emerald")
        self.assertEqual(reloaded.get("bg_preset"), "forest")
        self.assertEqual(reloaded.get("frame_bg_preset"), "navy")

    def test_persisted_keys_are_known_presets(self) -> None:
        self.db.save_app_settings(
            {"accent_preset": "teal", "bg_preset": "sepia", "frame_bg_preset": "rose_f"}
        )
        reloaded = self.db.get_app_settings()
        self.assertIn(reloaded.get("accent_preset"), support.ACCENT_PRESETS)
        self.assertIn(reloaded.get("bg_preset"), support.BG_COLOR_PRESETS)
        self.assertIn(reloaded.get("frame_bg_preset"), support.FRAME_BG_PRESETS)


if __name__ == "__main__":
    unittest.main()
