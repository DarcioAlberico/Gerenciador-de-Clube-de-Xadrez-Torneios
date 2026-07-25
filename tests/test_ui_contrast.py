"""Auditoria de contraste WCAG AA (B-2 / P2-11).

Nenhum destes abre janela: contraste é cor, e cor é dado.

O teste que vale é o `todos_os_temas_curados_passam_em_AA`: ele **falhou 77
vezes** quando foi escrito, e cada falha virou um ajuste de token. Deixá-lo no
lugar é o que impede um tema novo — ou um retoque de paleta — de reintroduzir
texto ilegível sem ninguém notar.
"""
from __future__ import annotations

import unittest

from src.ui.contrast import (
    AA_NORMAL_TEXT,
    INK_DARK,
    INK_LIGHT,
    SURFACE,
    ContrastPair,
    best_ink,
    contrast_ratio,
    failures,
    parse_hex,
    relative_luminance,
)
from src.ui.theme import (
    ACCENT_PRESETS,
    BG_COLOR_PRESETS,
    CURATED_THEMES,
    FRAME_BG_PRESETS,
    HIGH_CONTRAST_THEMES,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    apply_bg_preset,
)
from src.ui.theme_audit import all_combination_pairs, curated_pairs

AAA_NORMAL_TEXT = 7.0


class AritmeticaTest(unittest.TestCase):
    def test_extremos_conhecidos(self) -> None:
        self.assertAlmostEqual(21.0, contrast_ratio("#000000", "#FFFFFF"), places=2)
        self.assertAlmostEqual(1.0, contrast_ratio("#7F7F7F", "#7F7F7F"), places=2)

    def test_ordem_dos_argumentos_nao_importa(self) -> None:
        self.assertEqual(
            round(contrast_ratio("#123456", "#ABCDEF"), 6),
            round(contrast_ratio("#ABCDEF", "#123456"), 6),
        )

    def test_luminancia_nos_extremos(self) -> None:
        self.assertEqual(0.0, relative_luminance("#000000"))
        self.assertAlmostEqual(1.0, relative_luminance("#FFFFFF"), places=6)

    def test_forma_curta_e_equivalente(self) -> None:
        self.assertEqual(parse_hex("#FFF"), parse_hex("#FFFFFF"))
        self.assertEqual(parse_hex("abc"), parse_hex("#AABBCC"))

    def test_cor_invalida_reclama(self) -> None:
        for cor in ("#12345", "vermelho", "", "#GGGGGG"):
            with self.subTest(cor=cor):
                with self.assertRaises(ValueError):
                    parse_hex(cor)

    def test_valor_de_referencia_da_wcag(self) -> None:
        """#767676 sobre branco é o cinza-limite citado pela WCAG: 4.54:1."""
        self.assertAlmostEqual(4.54, contrast_ratio("#767676", "#FFFFFF"), places=2)


class TintaCalculadaTest(unittest.TestCase):
    def test_fundo_escuro_pede_tinta_clara(self) -> None:
        self.assertEqual(INK_LIGHT, best_ink("#1D4ED8"))

    def test_fundo_claro_pede_tinta_escura(self) -> None:
        self.assertEqual(INK_DARK, best_ink("#FACC15"))

    def test_a_tinta_escolhida_e_sempre_a_de_maior_contraste(self) -> None:
        for preset in ACCENT_PRESETS.values():
            for cor in (preset["l"], preset["d"]):
                with self.subTest(cor=cor):
                    escolhida = best_ink(cor)
                    outra = INK_DARK if escolhida == INK_LIGHT else INK_LIGHT
                    self.assertGreaterEqual(
                        contrast_ratio(escolhida, cor), contrast_ratio(outra, cor)
                    )

    def test_todo_accent_fica_legivel_com_a_tinta_calculada(self) -> None:
        """A promessa do best_ink: nenhum dos 30 valores de accent reprova."""
        for nome, preset in ACCENT_PRESETS.items():
            for face, cor in (("clara", preset["l"]), ("escura", preset["d"])):
                with self.subTest(accent=nome, face=face):
                    razao = contrast_ratio(best_ink(cor), cor)
                    self.assertGreaterEqual(round(razao, 2), AA_NORMAL_TEXT)


class TemasCuradosTest(unittest.TestCase):
    def test_todos_os_temas_curados_passam_em_aa(self) -> None:
        """O gate da B-2. Tema curado é o que o app entrega pronto."""
        problemas: list[str] = []
        for chave, _face, pares in curated_pairs():
            for par in failures(pares):
                problemas.append(f"{chave}: {par.describe()}")
        self.assertEqual([], problemas, "\n".join(["Contraste abaixo de AA:", *problemas]))

    def test_todo_tema_curado_aponta_para_presets_que_existem(self) -> None:
        for chave, tema in CURATED_THEMES.items():
            with self.subTest(tema=chave):
                self.assertIn(tema["accent"], ACCENT_PRESETS)
                self.assertIn(tema["bg"], BG_COLOR_PRESETS)
                self.assertIn(tema["frame"], FRAME_BG_PRESETS)

    def test_combinacoes_livres_tambem_passam(self) -> None:
        """As 5.070 combinações do modo avançado, não só as curadas.

        Não era obrigatório — o usuário pode montar o que quiser —, mas passou
        a valer depois que os accents claros foram para a faixa 600/700: se
        alguma combinação voltar a reprovar, é sinal de que um token saiu da
        faixa, e é melhor saber pelo teste do que pelo usuário.
        """
        problemas: list[str] = []
        for nome, _face, pares in all_combination_pairs():
            for par in failures(pares):
                problemas.append(f"{nome}: {par.describe()}")
        self.assertEqual(
            [], problemas, "\n".join(["Combinacoes abaixo de AA:", *problemas[:20]])
        )


class AltoContrasteTest(unittest.TestCase):
    def tearDown(self) -> None:
        # O preset mexe em tokens globais (mutados no lugar): sem devolver o
        # padrão, o proximo teste do arquivo herdaria o preto puro.
        apply_bg_preset("slate")

    def test_existe_e_esta_registrado(self) -> None:
        self.assertTrue(HIGH_CONTRAST_THEMES)
        for chave in HIGH_CONTRAST_THEMES:
            self.assertIn(chave, CURATED_THEMES)

    def test_superficies_passam_em_aaa(self) -> None:
        """Prometer "alto contraste" e entregar o mesmo AA dos outros seria
        vender o nome sem o conteúdo. O nível exigido é o AAA (7:1)."""
        for chave, _face, pares in curated_pairs():
            if chave not in HIGH_CONTRAST_THEMES:
                continue
            for par in (p for p in pares if p.kind == SURFACE):
                with self.subTest(tema=chave, papel=par.role):
                    self.assertGreaterEqual(round(par.ratio, 2), AAA_NORMAL_TEXT)

    def test_aplicar_o_preset_troca_a_cor_do_texto(self) -> None:
        apply_bg_preset("contrast")
        self.assertEqual(["#000000", "#FFFFFF"], list(THEME_TEXT_MAIN))
        self.assertEqual(["#1F2937", "#E5E7EB"], list(THEME_TEXT_SUB))

    def test_sair_do_alto_contraste_devolve_o_texto_padrao(self) -> None:
        """Sem isto, o preto puro ficaria grudado no próximo tema escolhido."""
        apply_bg_preset("contrast")
        apply_bg_preset("slate")
        self.assertEqual(["#0F172A", "#F1F5F9"], list(THEME_TEXT_MAIN))
        self.assertEqual(["#526070", "#94A3B8"], list(THEME_TEXT_SUB))


class ContratoDePareTest(unittest.TestCase):
    """A auditoria só vale pelo contrato; estes casos guardam o contrato."""

    def test_par_reprovado_e_relatado_com_nome_e_numero(self) -> None:
        par = ContrastPair("texto de teste", "#AAAAAA", "#FFFFFF")
        self.assertFalse(par.passes)
        texto = par.describe()
        self.assertIn("texto de teste", texto)
        self.assertIn("#AAAAAA", texto)
        self.assertIn("4.5", texto)

    def test_limite_e_comparado_com_o_valor_exibido(self) -> None:
        """4.4999 exibido como "4.50" e reprovado seria relatório que se contradiz."""
        par = ContrastPair("borda", "#767676", "#FFFFFF")  # 4.54:1
        self.assertTrue(par.passes)

    def test_failures_ordena_do_pior_para_o_melhor(self) -> None:
        pares = [
            ContrastPair("quase", "#767676", "#FFFFFF"),  # passa
            ContrastPair("ruim", "#BBBBBB", "#FFFFFF"),
            ContrastPair("pior", "#EEEEEE", "#FFFFFF"),
        ]
        ruins = failures(pares)
        self.assertEqual(["pior", "ruim"], [p.role for p in ruins])

    def test_o_contrato_cobre_todo_token_de_superficie_e_preenchimento(self) -> None:
        """Guarda contra o ponto cego: par que existe na tela e não na lista.

        Não dá para provar automaticamente que nenhum encontro foi esquecido —
        mas dá para exigir que cada cor auditável apareça em algum par, o que
        pega o caso comum de alguém acrescentar um token e esquecer daqui.
        """
        cores_no_contrato: set[str] = set()
        for _nome, _face, pares in curated_pairs():
            for par in pares:
                cores_no_contrato.update({par.foreground.upper(), par.background.upper()})

        esperadas = {
            THEME_TEXT_MAIN[0].upper(),
            THEME_TEXT_SUB[0].upper(),
            FRAME_BG_PRESETS["slate"]["panel"][0].upper(),
            BG_COLOR_PRESETS["slate"]["app"][0].upper(),
            BG_COLOR_PRESETS["slate"]["statusbar"][0].upper(),
        }
        self.assertTrue(esperadas <= cores_no_contrato, esperadas - cores_no_contrato)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
