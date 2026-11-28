"""RG2-20 — exportar CSV/XLSX não executa fórmula vinda de um nome.

Nomes chegam do Google Forms; ``=HYPERLINK(...)`` ou ``=cmd|calc!A1`` iam crus
para a planilha. A neutralização é na fronteira de saída, sem estragar o
telefone ("+55 11 …"): no XLSX a célula vira texto **sem mudar o texto**; no
CSV o texto ganha um ``'`` na frente, que o importador do Albericus retira.
"""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from src.services.export_writers import ReportWritersMixin
from src.services.spreadsheet_safety import csv_cell, unguard_csv_cell


class XlsxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.caminho = Path(self.temp.name) / "saida.xlsx"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _celulas(self) -> list:
        planilha = load_workbook(self.caminho).active
        return list(planilha.iter_rows(min_row=2, values_only=False))[0]

    def test_formula_vira_texto_sem_mudar_o_texto(self) -> None:
        ReportWritersMixin._write_xlsx(
            self.caminho, "T", ["Nome", "Fone", "Rating"],
            [['=HYPERLINK("http://x","clique")', "+55 11 9999", 1850]],
        )
        nome, fone, rating = self._celulas()
        self.assertEqual("s", nome.data_type)
        self.assertEqual('=HYPERLINK("http://x","clique")', nome.value)
        self.assertEqual("s", fone.data_type)
        self.assertEqual("+55 11 9999", fone.value)
        self.assertEqual(1850, rating.value)

    def test_relatorio_composto_tambem(self) -> None:
        ReportWritersMixin._write_multi_xlsx(self.caminho, [("Seção", ["Nome"], [["=1+1"]])])
        (celula,) = self._celulas()
        self.assertEqual("s", celula.data_type)
        self.assertEqual("=1+1", celula.value)


class CsvTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.caminho = Path(self.temp.name) / "saida.csv"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _linhas(self) -> list[list[str]]:
        with self.caminho.open(encoding="utf-8-sig", newline="") as arquivo:
            return list(csv.reader(arquivo, delimiter=";"))

    def test_formula_ganha_apostrofo_e_numero_nao_muda(self) -> None:
        ReportWritersMixin._write_csv(self.caminho, ["Nome", "Rating"], [["=1+1", 1850], ["Ana", 1600]])
        self.assertEqual([["Nome", "Rating"], ["'=1+1", "1850"], ["Ana", "1600"]], self._linhas())

    def test_relatorio_composto_tambem(self) -> None:
        ReportWritersMixin._write_multi_csv(self.caminho, [("Seção", ["Nome"], [["@SUM(A1)"]])])
        self.assertEqual("'@SUM(A1)", self._linhas()[2][0])

    def test_o_importador_retira_o_apostrofo(self) -> None:
        for original in ("=1+1", "+55 11 9999", "-x", "@y"):
            with self.subTest(original=original):
                self.assertEqual(original, unguard_csv_cell(csv_cell(original)))
        self.assertEqual("'comum", unguard_csv_cell("'comum"))
        self.assertEqual(1850, csv_cell(1850))

    def test_importar_o_csv_exportado_devolve_o_texto_original(self) -> None:
        from src.services.import_service import ImportService

        ReportWritersMixin._write_csv(self.caminho, ["name", "phone"], [["=1+1", "+55 11 9999"]])
        tabela = ImportService._tabular_from_csv_text(
            ImportService.__new__(ImportService), self.caminho.read_text(encoding="utf-8-sig")
        )
        _linha, registro = tabela["rows"][0]
        self.assertEqual({"name": "=1+1", "phone": "+55 11 9999"}, registro)
