"""RG2-29 (ASCII) — "Łukasz Øster" sai "Lukasz Oster" e a linha 001 é ASCII puro.

O "ASCII" do TRF só tirava as marcas combinantes: ``Ø``, ``Ł``, ``ß`` e ``æ``
não se decompõem e passavam inteiros, num arquivo UTF-8. Quem lê o TRF contando
bytes (como a especificação manda) via rating, federação e FIDE ID fora do
lugar. Agora a transliteração é uma só (``fide_ascii``) e o que sobrar vira
``?`` — a linha nunca tem mais bytes que caracteres.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.domain.fide_player import fide_ascii
from src.services.federation_exporters import TRF16Exporter, TRF25Exporter
from src.services.federation_exporters.trf25_records import trf_ascii
from src.services.trf_layout import FIDE_ID, NAME, field
from tests.support.core_service_base import CoreServiceTestCase


class TransliteracaoTest(unittest.TestCase):
    def test_letras_que_nao_se_decompoem(self) -> None:
        self.assertEqual("Lukasz Oster", fide_ascii("Łukasz Øster"))
        self.assertEqual("Strasse Aerenlund Oeuvre", fide_ascii("Straße Ærenlund Œuvre"))
        self.assertEqual("Joao Sahin Nguyen Dorte", fide_ascii("João Şahin Nguyễn Dörte"))
        self.assertEqual("Thorsson", fide_ascii("Þorsson"))

    def test_o_que_nao_tem_traducao_vira_interrogacao(self) -> None:
        self.assertEqual("? ?", fide_ascii("中 ☃"))

    def test_trf25_usa_a_mesma_transliteracao(self) -> None:
        self.assertEqual(fide_ascii("Łukasz  Øster\n"), trf_ascii("Łukasz  Øster\n"))


class Linha001Test(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.db.create_player(
            self.tournament_id,
            name="Łukasz Øster",
            surname="Øster",
            given_name="Łukasz",
            rating=2100,
            international_rating=2100,
            fide_id="12345678",
            federation_id="NOR",
            sex="M",
        )
        self.db.create_player(self.tournament_id, name="Ana Souza", surname="Souza", given_name="Ana", rating=1600)

    def _linhas_001(self, conteudo: bytes) -> list[bytes]:
        return [linha for linha in conteudo.split(b"\r\n") if linha.startswith(b"001")]

    def test_trf16_e_trf25_saem_em_ascii_com_o_fide_id_no_lugar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for nome, exportador in (("TRF16", TRF16Exporter), ("TRF25", TRF25Exporter)):
                with self.subTest(formato=nome):
                    destino = Path(tmp) / f"{nome}.trf"
                    exportador(self.export_service).export(self.tournament_id, destino)
                    (linha,) = [item for item in self._linhas_001(destino.read_bytes()) if b"Oster" in item]
                    linha.decode("ascii")  # nenhum byte fora do ASCII
                    texto = linha.decode("ascii")
                    self.assertEqual("Oster, Lukasz", field(texto, NAME).strip())
                    self.assertEqual("12345678", field(texto, FIDE_ID).strip())
                    self.assertEqual(b"12345678", linha[FIDE_ID[0] : FIDE_ID[1]].strip())


if __name__ == "__main__":
    unittest.main()
