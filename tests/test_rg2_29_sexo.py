"""RG2-29 (sexo) — a jogadora sai ``w`` no TRF e entra como feminina nas normas.

O TRF saía ``f`` (``sex[:1].lower()``) onde a FIDE pede ``m``/``w``; as normas
só reconheciam ``F`` e a importação gravava o ``w`` do arquivo como veio — a
jogadora vinda do Swiss-Manager nunca era avaliada para WGM/WIM.

Agora há uma leitura só, ``normalized_sex`` (a das categorias), e uma escrita
só para a FIDE, ``trf_sex``.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.domain.fide_player import trf_sex
from src.services.federation_exporters import TRF16Exporter
from src.services.norms.handbook import applicable_norms
from src.services.trf_layout import NAME, SEX, field
from tests.support.core_service_base import CoreServiceTestCase


class EscritaTest(unittest.TestCase):
    def test_feminino_sai_w_e_masculino_m(self) -> None:
        for valor, esperado in (("F", "w"), ("f", "w"), ("w", "w"), ("Feminino", "w"), ("M", "m"), ("", "")):
            with self.subTest(valor=valor):
                self.assertEqual(esperado, trf_sex(valor))


class NormasTest(unittest.TestCase):
    def test_w_do_trf_e_f_do_cadastro_dao_as_normas_femininas(self) -> None:
        for valor in ("w", "W", "F"):
            with self.subTest(valor=valor):
                self.assertIn("WGM", applicable_norms(valor))
        self.assertNotIn("WGM", applicable_norms("M"))


class TrfTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.db.create_player(
            self.tournament_id, name="Ana Souza", surname="Souza", given_name="Ana", rating=1650, sex="F"
        )
        self.db.create_player(
            self.tournament_id, name="Bruno Lima", surname="Lima", given_name="Bruno", rating=1600, sex="M"
        )

    def test_coluna_10_tem_w_para_a_jogadora(self) -> None:
        linhas = TRF16Exporter(self.export_service).render(self.tournament_id).splitlines()
        sexos = {field(linha, NAME).split(",")[0].strip(): field(linha, SEX) for linha in linhas if linha.startswith("001")}
        self.assertEqual({"Souza": "w", "Lima": "m"}, sexos)

    def test_reimportar_grava_a_jogadora_como_feminina(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "t.trf"
            TRF16Exporter(self.export_service).export(self.tournament_id, destino)
            novo = self.import_service.import_trf(destino)["tournament_id"]
        sexos = {p["surname"]: p["sex"] for p in self.db.list_players(novo, active_only=False)}
        self.assertEqual({"Souza": "F", "Lima": "M"}, sexos)


if __name__ == "__main__":
    unittest.main()
