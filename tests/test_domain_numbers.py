"""Fronteira numérica (RG2-46, RG2-14, RG2-27, RG2-10): a leitura única de número.

O ponto de milhar brasileiro era lido como decimal ("1.500" → 1,5; prêmio
"1.000" → R$ 1,00; rating "1.850" → 1), texto inválido virava 0 calado e
``valor or padrão`` transformava o 0 legítimo em 1.
"""
from __future__ import annotations

import math
import unittest

from src.domain.numbers import (
    NumberError,
    parse_decimal,
    parse_decimal_br,
    parse_points,
    parse_rating,
    setting_number,
)


class DecimalBrTest(unittest.TestCase):
    def test_aceite_da_espec(self) -> None:
        self.assertEqual(1500.0, parse_decimal_br("1.500"))
        self.assertEqual(1500.5, parse_decimal_br("1.500,50"))
        self.assertEqual(1.5, parse_decimal_br("1,5"))
        with self.assertRaises(NumberError):
            parse_decimal_br("nan")

    def test_milhar_varias_casas_espaco_e_sinal(self) -> None:
        self.assertEqual(1_000_000.0, parse_decimal_br("1.000.000"))
        self.assertEqual(1_234_567.89, parse_decimal_br("1.234.567,89"))
        self.assertEqual(1500.0, parse_decimal_br("1 500"))
        self.assertEqual(-20.0, parse_decimal_br("-20"))
        self.assertEqual(150.0, parse_decimal_br("  150  "))

    def test_ponto_com_um_ou_dois_digitos_e_decimal(self) -> None:
        """O valor gravado volta para a tela como "1500.0"; salvar de novo não pode falhar."""
        self.assertEqual(1.5, parse_decimal_br("1.5"))
        self.assertEqual(150.5, parse_decimal_br("150.50"))
        self.assertEqual(1500.0, parse_decimal_br(str(1500.0)))
        self.assertEqual(1000.0, parse_decimal_br("1.000"))

    def test_vazio_e_none(self) -> None:
        self.assertIsNone(parse_decimal_br(""))
        self.assertIsNone(parse_decimal_br("   "))
        self.assertIsNone(parse_decimal_br(None))

    def test_numero_ja_numerico_passa(self) -> None:
        self.assertEqual(12.5, parse_decimal_br(12.5))
        self.assertEqual(7.0, parse_decimal_br(7))

    def test_ambiguo_e_lixo_recusados_com_o_texto_na_mensagem(self) -> None:
        for texto in ("1.5000", "1.5000,0", "12.34,5.6", "1,2,3", "abc", "1.500.5", "inf", "-inf", "1e3", "R$ 10", "1. 500"):
            with self.subTest(texto=texto), self.assertRaises(NumberError) as caught:
                parse_decimal_br(texto)
            self.assertIn(texto.strip(), str(caught.exception))
        with self.assertRaises(NumberError) as caught:
            parse_decimal_br("1.5000")
        self.assertIn('"1,5" ou "1.500"', str(caught.exception))

    def test_float_nao_finito_e_bool_recusados(self) -> None:
        for valor in (math.nan, math.inf, True):
            with self.subTest(valor=valor), self.assertRaises(NumberError):
                parse_decimal_br(valor)


class DecimalSimplesTest(unittest.TestCase):
    def test_ponto_e_virgula_sao_decimais(self) -> None:
        self.assertEqual(8.5, parse_decimal("8,5"))
        self.assertEqual(8.5, parse_decimal("8.5"))
        self.assertEqual(12.0, parse_decimal("12"))
        self.assertIsNone(parse_decimal(""))

    def test_milhar_e_lixo_e_nao_finito_recusados(self) -> None:
        for texto in ("1.500,5", "1 500", "abc", "nan", "inf", "1e3"):
            with self.subTest(texto=texto), self.assertRaises(NumberError):
                parse_decimal(texto)


class RatingTest(unittest.TestCase):
    def test_aceite_da_espec(self) -> None:
        self.assertEqual(1850, parse_rating("1.850"))
        self.assertEqual(1850, parse_rating("1 850"))
        self.assertEqual(1850, parse_rating("1850"))
        with self.assertRaises(NumberError):
            parse_rating("abc")

    def test_vazio_e_planilha(self) -> None:
        self.assertIsNone(parse_rating(""))
        self.assertIsNone(parse_rating(None))
        self.assertEqual(1850, parse_rating(1850))
        self.assertEqual(1850, parse_rating(1850.0))
        self.assertEqual(1850, parse_rating("1850.0"))

    def test_quebrado_negativo_e_separador_errado_recusados(self) -> None:
        for texto in ("1,850", "2 000 0", "1850,5", "-10", 1850.5, "1.85"):
            with self.subTest(texto=texto), self.assertRaises(NumberError):
                parse_rating(texto)


class PointsTest(unittest.TestCase):
    BYE = (0.0, 0.5, 1.0)

    def test_valores_da_faixa(self) -> None:
        self.assertEqual(0.5, parse_points("0,5", self.BYE))
        self.assertEqual(0.5, parse_points("0.5", self.BYE))
        self.assertEqual(1.0, parse_points("1", self.BYE))
        self.assertEqual(0.0, parse_points("0", self.BYE))
        self.assertEqual(0.5, parse_points(0.5, self.BYE))

    def test_os_quatro_casos_da_espec_citam_a_faixa(self) -> None:
        for texto in ("inf", "0,3", "7", "-1", "nan", "0,25"):
            with self.subTest(texto=texto), self.assertRaises(NumberError) as caught:
                parse_points(texto, self.BYE)
            self.assertIn("0; 0,5; 1", str(caught.exception))

    def test_sem_faixa_aceita_multiplo_de_meio_nao_negativo(self) -> None:
        self.assertEqual(3.0, parse_points("3", None))
        self.assertEqual(1.5, parse_points("1,5", None))
        for texto in ("-1", "0,3", "inf"):
            with self.subTest(texto=texto), self.assertRaises(NumberError):
                parse_points(texto, None)

    def test_vazio_devolve_none(self) -> None:
        self.assertIsNone(parse_points("", self.BYE))


class SettingNumberTest(unittest.TestCase):
    def test_zero_gravado_continua_zero(self) -> None:
        self.assertEqual(0.0, setting_number({"bye_points": 0.0}, "bye_points", 1.0))
        self.assertEqual(0.0, setting_number({"bye_points": 0}, "bye_points", 1.0))
        self.assertEqual(0.0, setting_number({"bye_points": "0"}, "bye_points", 1.0))

    def test_ausente_none_e_vazio_viram_padrao(self) -> None:
        self.assertEqual(1.0, setting_number({}, "bye_points", 1.0))
        self.assertEqual(1.0, setting_number({"bye_points": None}, "bye_points", 1.0))
        self.assertEqual(1.0, setting_number({"bye_points": ""}, "bye_points", 1.0))
        self.assertEqual(1.0, setting_number(None, "bye_points", 1.0))

    def test_valor_gravado_invalido_levanta(self) -> None:
        with self.assertRaises(NumberError):
            setting_number({"x": "abc"}, "x", 1.0)

    def test_valor_gravado_volta_como_float(self) -> None:
        self.assertEqual(0.5, setting_number({"x": "0.5"}, "x", 1.0))
        self.assertEqual(2.0, setting_number({"x": 2}, "x", 1.0))


if __name__ == "__main__":
    unittest.main()
