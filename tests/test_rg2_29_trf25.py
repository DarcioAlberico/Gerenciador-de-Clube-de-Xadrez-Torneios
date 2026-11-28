"""RG2-29 (TRF25) — o TRF25 reaproveita o cabeçalho do TRF16 e grava sem meio arquivo.

O TRF25 montava o cabeçalho à parte, e a cópia divergiu: torneio individual
saía com ``082 0`` (um torneio por equipes com zero equipes), o 102 sem o FIDE
ID do árbitro, o arquivo pronto não passava por ``_file_problems`` (resultado
pendente e mesa que não confere ficavam calados) e a escrita ia direto para o
destino — um erro no meio deixava meio arquivo onde estava o anterior.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

from src.services.federation_exporters import TRF16Exporter, TRF25Exporter
from tests.support.core_service_base import CoreServiceTestCase


class Trf25Test(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.db.save_tournament_settings(self.tournament_id, {"federation": "BRA", "chief_arbiter": "Carla Dias"})
        arbitra = self.db.insert_referee({"name": "Carla Dias", "fide_id": "9876543"})
        self.db.assign_tournament_referee(self.tournament_id, arbitra, "chief")
        self._create_players(4)
        self.rodada = self.service.generate_next_round(self.tournament_id)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _exportar(self) -> tuple[list[str], list[str]]:
        destino = Path(self.tmp.name) / "t.trf"
        avisos = TRF25Exporter(self.export_service).export(self.tournament_id, destino)
        return destino.read_text(encoding="utf-8").splitlines(), avisos

    def _registros(self, linhas: list[str], codigo: str) -> list[str]:
        return [linha for linha in linhas if linha.startswith(codigo + " ")]

    def test_individual_nao_tem_082(self) -> None:
        linhas, _ = self._exportar()
        self.assertEqual([], self._registros(linhas, "082"))

    def test_102_traz_o_fide_id_do_arbitro_como_no_trf16(self) -> None:
        linhas, _ = self._exportar()
        trf16 = TRF16Exporter(self.export_service).render(self.tournament_id).splitlines()
        (registro,) = self._registros(linhas, "102")
        self.assertIn("9876543", registro)
        self.assertEqual(self._registros(trf16, "102"), [registro])

    def test_cabecalho_igual_ao_do_trf16(self) -> None:
        linhas, _ = self._exportar()
        trf16 = TRF16Exporter(self.export_service).render(self.tournament_id).splitlines()
        for codigo in ("012", "022", "032", "042", "052", "062", "072", "092", "102", "122", "132"):
            with self.subTest(codigo=codigo):
                self.assertEqual(self._registros(trf16, codigo), self._registros(linhas, codigo))
        self.assertEqual(
            [linha for linha in trf16 if linha.startswith("001")], [linha for linha in linhas if linha.startswith("001")]
        )

    def test_resultado_pendente_vira_aviso(self) -> None:
        _, avisos = self._exportar()
        trf16 = TRF16Exporter(self.export_service)
        esperados = trf16._file_problems(trf16.render(self.tournament_id), trf16.players(self.tournament_id))
        self.assertTrue(esperados, "o cenário precisa ter mesa sem resultado")
        for problema in esperados:
            self.assertIn(problema, avisos)

    def test_falha_no_meio_nao_estraga_o_arquivo_anterior(self) -> None:
        destino = Path(self.tmp.name) / "t.trf"
        destino.write_text("arquivo anterior", encoding="utf-8")
        with mock.patch.object(TRF25Exporter, "_point_adjustment_records_299", side_effect=RuntimeError("falhou")):
            with self.assertRaises(RuntimeError):
                TRF25Exporter(self.export_service).export(self.tournament_id, destino)
        self.assertEqual("arquivo anterior", destino.read_text(encoding="utf-8"))
        self.assertEqual(["t.trf"], sorted(p.name for p in Path(self.tmp.name).iterdir()))
