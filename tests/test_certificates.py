from __future__ import annotations

import unittest
from collections import Counter

from src.services.certificates import gallery, layout, palettes, styles, text
from src.services.certificates.adapter import build_inputs


class CertificatesPackageTest(unittest.TestCase):
    def test_ten_style_presets(self) -> None:
        self.assertEqual(len(styles.STYLE_PRESETS), 10)
        for key in ("classic", "playful", "modern", "elegant", "vintage",
                    "royal", "laurel", "geometric", "kids", "mono"):
            self.assertIn(key, styles.STYLE_PRESETS)

    def test_resolve_preset_fallback(self) -> None:
        self.assertEqual(styles.resolve_preset("inexistente").key, "classic")
        self.assertEqual(styles.resolve_preset("royal").key, "royal")

    def test_palettes_resolve(self) -> None:
        self.assertGreaterEqual(len(palettes.PALETTES), 12)
        self.assertEqual(palettes.resolve_palette("", "classic").key, "navy_gold")
        self.assertEqual(palettes.resolve_palette("sepia", "vintage").key, "sepia")
        custom = palettes.palette_from_colors("#112233", "#445566")
        self.assertEqual(custom.ink, "#112233")
        self.assertEqual(custom.accent, "#445566")

    def test_gallery_50_unique_and_distributed(self) -> None:
        models = gallery.build_gallery(50)
        self.assertEqual(len(models), 50)
        keys = {(m.style_preset, m.palette_key, m.certificate_type) for m in models}
        self.assertEqual(len(keys), 50)  # todos unicos
        self.assertEqual(set(Counter(m.style_preset for m in models).values()), {5})

    def test_gallery_limit_smaller(self) -> None:
        self.assertEqual(len(gallery.build_gallery(20)), 20)

    def test_gallery_model_to_template(self) -> None:
        model = gallery.build_gallery(1)[0]
        payload = gallery.model_to_template(model)
        self.assertEqual(payload["style_preset"], model.style_preset)
        self.assertEqual(payload["palette_key"], model.palette_key)
        self.assertIn("{", payload["body_template"])

    def test_text_variables(self) -> None:
        variables = text.build_variables({"name": "Ana", "position_label": "1o", "points": "6"})
        self.assertEqual(text.render_plain("{nome} - {posicao} ({pontos})", variables), "Ana - 1o (6)")

    def test_adapter_build_inputs(self) -> None:
        template = {
            "style_preset": "royal", "palette_key": "burgundy_gold", "certificate_type": "overall_award",
            "title_template": "Premiacao", "body_template": "conquistou a {posicao} colocacao",
            "seal_enabled": 1, "watermark_enabled": 1, "medal_by_placement": 1,
        }
        recipient = {"name": "Ana", "position": 1, "position_label": "1o", "tournament": "Torneio X"}
        preset, palette, content, options = build_inputs(template, recipient)
        self.assertEqual(preset.key, "royal")
        self.assertEqual(palette.key, "burgundy_gold")
        self.assertEqual(content.name, "Ana")
        self.assertEqual(content.position, 1)
        self.assertEqual(content.intro, "Certificamos que")
        self.assertNotIn("{posicao}", content.body)
        self.assertTrue(options.seal_enabled)

    def test_adapter_palette_from_colors_when_no_key(self) -> None:
        template = {"style_preset": "classic", "certificate_type": "participation",
                    "title_template": "T", "body_template": "x", "primary_color": "#101010", "accent_color": "#A0A0A0"}
        _, palette, _, _ = build_inputs(template, {"name": "X"})
        self.assertEqual(palette.ink, "#101010")

    def test_layout_zones(self) -> None:
        zones = layout.compute_zones(842, 595, "classic")
        self.assertGreater(zones.content_width, 0)
        self.assertTrue(layout.is_landscape(842, 595))
        self.assertFalse(layout.is_landscape(595, 842))


if __name__ == "__main__":
    unittest.main()
