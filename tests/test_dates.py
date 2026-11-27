"""RGS-06 — a regra única de data (`src/domain/dates.py`).

O campo de data apagava ou corrompia em silêncio: `2010/05/12` virava
`0512-10-20`, `2026-11-13 08:00` virava vazio e `1985` (o ano que a lista da
FIDE publica) sumia ao salvar. Cada fronteira tinha a sua regra (RGS-07).

Esta suíte é a tabela da spec, linha a linha. Uma fronteira nova que precise de
data usa `parse_date`; se a tabela mudar, muda aqui primeiro.
"""

from __future__ import annotations

import dataclasses
import unittest
from datetime import date

import pytest

from src.domain.dates import (
    Ano,
    Data,
    DataInvalida,
    DataVazia,
    DateError,
    is_iso_date,
    normalize_date,
    parse_date,
    parse_trf_date,
    parse_trf_round_date,
    storage_text,
)

# (entrada, permite_ano, esperado). `DataInvalida` compara só o tipo: o motivo
# é texto para gente, testado à parte.
TABELA: list[tuple[object, bool, object]] = [
    # "" -> DataVazia
    ("", False, DataVazia()),
    ("   ", False, DataVazia()),
    (None, False, DataVazia()),
    # aaaa-mm-dd -> Data
    ("2026-11-13", False, Data(date(2026, 11, 13))),
    ("2026-1-5", False, Data(date(2026, 1, 5))),
    # aaaa-mm-dd[ T]HH:MM[:SS] -> Data (a hora é descartada)
    ("2026-11-13 08:00", False, Data(date(2026, 11, 13))),
    ("2026-11-13T08:00", False, Data(date(2026, 11, 13))),
    ("2026-11-13 08:00:59", False, Data(date(2026, 11, 13))),
    ("2026-11-13T23:59:00", False, Data(date(2026, 11, 13))),
    # dd/mm/aaaa, d/m/aaaa, dd-mm-aaaa -> Data
    ("13/11/2026", False, Data(date(2026, 11, 13))),
    ("1/2/2026", False, Data(date(2026, 2, 1))),
    ("13-11-2026", False, Data(date(2026, 11, 13))),
    # aaaa/mm/dd -> Data
    ("2010/05/12", False, Data(date(2010, 5, 12))),
    # aaaa -> Ano, somente com permite_ano
    ("1985", True, Ano(1985)),
    ("1985", False, DataInvalida),
    # Ano com mês e dia zerados é "só o ano" (TRF, lista da FIDE)
    ("1985-00-00", True, Ano(1985)),
    ("1985/00/00", True, Ano(1985)),
    ("1985-00-00", False, DataInvalida),
    # Data completa continua Data com permite_ano
    ("1985-03-07", True, Data(date(1985, 3, 7))),
    # ano com 2 dígitos: não se adivinha século
    ("13/11/26", False, DataInvalida),
    ("13/11/26", True, DataInvalida),
    ("85", True, DataInvalida),
    # data impossível
    ("2026-02-30", False, DataInvalida),
    ("30/02/2026", False, DataInvalida),
    ("2026-13-01", False, DataInvalida),
    ("00/01/2026", False, DataInvalida),
    ("2026-11-13 25:00", False, DataInvalida),
    ("2026-11-13 08:61", False, DataInvalida),
    # lixo (inclui o que a máscara antiga produzia)
    ("lixo", False, DataInvalida),
    ("20/26/1113", False, DataInvalida),
    ("0512-10-20", False, DataInvalida),
    ("12/05/20", False, DataInvalida),
    ("2026.11.13", False, DataInvalida),
    ("13/11/2026 abc", False, DataInvalida),
    ("2026-11-13-", False, DataInvalida),
]


@pytest.mark.parametrize(("entrada", "permite_ano", "esperado"), TABELA)
def test_tabela_da_spec(entrada: object, permite_ano: bool, esperado: object) -> None:
    resultado = parse_date(entrada, permite_ano=permite_ano)
    if esperado is DataInvalida:
        assert isinstance(resultado, DataInvalida), resultado
        assert resultado.texto == str(entrada).strip()
        assert resultado.motivo
    else:
        assert resultado == esperado


class EstadosIlegaisTest(unittest.TestCase):
    def test_resultados_sao_imutaveis(self) -> None:
        resultado = parse_date("2026-11-13")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            resultado.valor = date(2000, 1, 1)  # type: ignore[union-attr,misc]

    def test_ano_fora_de_quatro_digitos_nao_existe(self) -> None:
        for valor in (0, 999, 10000, -1985):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                Ano(valor)

    def test_data_exige_date_de_verdade(self) -> None:
        with self.assertRaises(TypeError):
            Data("2026-11-13")  # type: ignore[arg-type]

    def test_data_invalida_exige_motivo(self) -> None:
        with self.assertRaises(ValueError):
            DataInvalida("x", "")


class GravacaoTest(unittest.TestCase):
    """O texto que vai para o banco: ISO, o ano, ou nada."""

    def test_storage_text(self) -> None:
        self.assertEqual("", storage_text(DataVazia()))
        self.assertEqual("2010-05-12", storage_text(parse_date("2010/05/12")))
        self.assertEqual("1985", storage_text(parse_date("1985", permite_ano=True)))
        with self.assertRaises(DateError):
            storage_text(parse_date("2026-02-30"))

    def test_normalize_date_recusa_com_motivo(self) -> None:
        self.assertEqual("2026-11-13", normalize_date("13/11/2026"))
        self.assertEqual("", normalize_date(""))
        self.assertEqual("1985", normalize_date("1985", permite_ano=True))
        with self.assertRaises(DateError) as contexto:
            normalize_date("13/11/26")
        self.assertIn("13/11/26", str(contexto.exception))
        self.assertIsInstance(contexto.exception, ValueError)

    def test_is_iso_date_so_aceita_a_forma_canonica(self) -> None:
        self.assertTrue(is_iso_date("2026-11-13"))
        self.assertFalse(is_iso_date("13/11/2026"))
        self.assertFalse(is_iso_date("2026-1-5"))
        self.assertFalse(is_iso_date("2026-02-30"))
        self.assertFalse(is_iso_date(""))


class TrfTest(unittest.TestCase):
    """Fronteira TRF16: `YYYY/MM/DD` nos campos de data, `YY/MM/DD` no 132."""

    def test_data_do_cabecalho(self) -> None:
        self.assertEqual(Data(date(2026, 2, 28)), parse_trf_date("2026/02/28"))
        self.assertEqual(Data(date(2026, 2, 28)), parse_trf_date("2026.02.28"))
        self.assertIsInstance(parse_trf_date("2026.02.30"), DataInvalida)
        self.assertEqual(DataVazia(), parse_trf_date(""))
        self.assertEqual(DataVazia(), parse_trf_date("0000/00/00"))

    def test_nascimento_aceita_so_o_ano(self) -> None:
        self.assertEqual(Ano(1985), parse_trf_date("1985/00/00", permite_ano=True))
        self.assertEqual(Ano(1985), parse_trf_date("1985", permite_ano=True))

    def test_registro_132_e_aa_mm_dd(self) -> None:
        # TRF16: o 132 é YY/MM/DD. `26/11/13` é 13 de novembro de 2026.
        self.assertEqual(Data(date(2026, 11, 13)), parse_trf_round_date("26/11/13"))
        self.assertIsInstance(parse_trf_round_date("26/02/30"), DataInvalida)
        self.assertEqual(DataVazia(), parse_trf_round_date("  "))
        # Arquivo que já traz o ano com 4 dígitos continua valendo.
        self.assertEqual(Data(date(2026, 11, 13)), parse_trf_round_date("2026/11/13"))


if __name__ == "__main__":
    unittest.main()
