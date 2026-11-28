"""RG2-29 (fonte) — o PDF escreve "Łukasz Ćwik Şahin Nguyễn", não "■ukasz ■wik".

Os PDFs usavam só as fontes embutidas do ReportLab (Helvetica, Times), que não
têm ``Ł``, ``Ć``, ``Ş`` nem ``ễ``: o nome saía com quadrados — no IT3, que a FIDE
exige com os adversários estrangeiros, inclusive. Agora a DejaVu vai junto com o
programa (``assets/fonts``) e ``install_pdf_fonts`` a registra nos nomes que o
código já usa, uma vez, para todo escritor de PDF.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from src.core.resources import bundled_resource
from src.services import pdf_fonts
from tests.support.core_service_base import CoreServiceTestCase

NOME = "Łukasz Ćwik Şahin Nguyễn"


def _texto(caminho: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(caminho).pages)


def _fontes(caminho: Path) -> set[str]:
    nomes: set[str] = set()
    for page in PdfReader(caminho).pages:
        fontes = page.get("/Resources", {}).get("/Font", {})
        for fonte in fontes.values():
            nomes.add(str(fonte.get_object().get("/BaseFont")))
    return nomes


class VarreduraTest(unittest.TestCase):
    def test_quem_cria_pdf_instala_as_fontes(self) -> None:
        raiz = Path(__file__).resolve().parents[1] / "src"
        faltando = []
        for arquivo in sorted(raiz.rglob("*.py")):
            texto = arquivo.read_text(encoding="utf-8")
            if re.search(r"\bCanvas\(|DocTemplate\(", texto) and "install_pdf_fonts()" not in texto:
                faltando.append(str(arquivo.relative_to(raiz)))
        self.assertEqual([], faltando)


class FonteEmpacotadaTest(CoreServiceTestCase):
    def test_a_fonte_vai_com_o_programa(self) -> None:
        for arquivo in pdf_fonts.FONT_FILES.values():
            with self.subTest(arquivo=arquivo):
                self.assertTrue(bundled_resource(f"assets/fonts/{arquivo}").is_file())

    def test_lista_de_jogadores_em_pdf_escreve_o_nome(self) -> None:
        self.db.create_player(self.tournament_id, name=NOME, surname="Ćwik", given_name="Łukasz", rating=1500)
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "lista.pdf"
            self.export_service.export_initial_player_list(self.tournament_id, destino)
            self.assertIn("Łukasz", _texto(destino))
            self.assertTrue(any("DejaVu" in nome for nome in _fontes(destino)), _fontes(destino))

    def test_diploma_escreve_o_nome(self) -> None:
        jogador = self.db.create_player(
            self.tournament_id, name=NOME, surname="Ćwik Şahin Nguyễn", given_name="Łukasz", rating=1500
        )
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "diplomas.pdf"
            self.certificate_service.export_tournament_certificates(
                self.tournament_id, destino, certificate_type="participation", player_ids=[jogador]
            )
            texto = _texto(destino)
        self.assertIn("Łukasz", texto)
        self.assertIn("Nguyễn", texto)
