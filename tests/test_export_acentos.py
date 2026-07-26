"""Acentuação das exportações e a fronteira ASCII (B-7).

Duas garantias em tensão, e é a tensão que este arquivo existe para travar:

1. o que **gente** lê (PDF, HTML, XLSX, CSV comum) sai acentuado, igual à tela;
2. o que **máquina** lê (pacote Access, TRF, PGN) continua ASCII.

O risco de regressão é assimétrico: acentuar de novo o que precisa ser ASCII
quebra a importação de um arquivo entregue, e ninguém descobre pelo app — só
pelo usuário, na hora de importar no Access.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.core.services import ExportService, PairingService, TournamentService
from src.services.text_ascii import headers_to_ascii, to_ascii


class DobraParaAsciiTest(unittest.TestCase):
    def test_remove_acento_preservando_a_letra(self) -> None:
        self.assertEqual("Classificacao", to_ascii("Classificação"))
        self.assertEqual("Premiacao", to_ascii("Premiação"))
        self.assertEqual("Arbitro", to_ascii("Árbitro"))
        self.assertEqual("Numero", to_ascii("Número"))

    def test_texto_ja_ascii_passa_intacto(self) -> None:
        self.assertEqual("Jogadores", to_ascii("Jogadores"))

    def test_caractere_sem_equivalente_some(self) -> None:
        """Num arquivo que precisa ser ASCII, sumir é o comportamento certo."""
        self.assertEqual("ok ", to_ascii("ok ✓"))

    def test_cabecalhos_inteiros(self) -> None:
        self.assertEqual(
            ["Pos", "Jogador", "Pontuacao"], headers_to_ascii(["Pos", "Jogador", "Pontuação"])
        )


class ExportacaoAcentuadaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.db = Database(base / "a.db", backup_dir=base / "b")
        self.pairing_service = PairingService(self.db)
        self.export_service = ExportService(self.db, self.pairing_service)
        self.tournament_id = TournamentService(self.db).create_tournament(
            {"name": "Torneio B7", "rounds_count": "3", "bye_points": "1"}
        )
        for nome in ("Ana", "Bruno", "Carla", "Diego"):
            self.db.create_player(
                self.tournament_id, name=nome, rating=1800, club="Clube", category="ABS"
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_titulo_de_secao_sai_acentuado(self) -> None:
        titulo, _headers, _rows = self.export_service._standings_section(self.tournament_id)
        self.assertIn("Classificação", titulo)

    def test_cabecalho_de_coluna_sai_acentuado(self) -> None:
        """A decisão desta tarefa: CSV/XLSX também acompanham a tela."""
        _titulo, headers, _rows = self.export_service._players_section(self.tournament_id)
        self.assertIn("Título", headers)
        self.assertIn("Tags premiação", headers)

    def test_site_html_sai_acentuado(self) -> None:
        destino = Path(self.temp.name) / "site"
        self.export_service.export_site(self.tournament_id, destino)
        html = (destino / "index.html").read_text(encoding="utf-8")
        self.assertIn("Classificação", html)
        self.assertNotIn("<h2>Classificacao</h2>", html)

    def test_pacote_access_continua_em_ascii(self) -> None:
        """A fronteira. Aqui o texto vira nome de coluna lido por driver ODBC."""
        destino = Path(self.temp.name) / "access"
        resultado = self.export_service.export_access(self.tournament_id, destino)

        self.assertIn("Classificacao", resultado["tables"])
        self.assertNotIn("Classificação", resultado["tables"])

        for caminho in resultado["csv_paths"]:
            with self.subTest(arquivo=Path(caminho).name):
                cabecalho = Path(caminho).read_text(encoding="utf-8").splitlines()[0]
                self.assertEqual(
                    cabecalho,
                    to_ascii(cabecalho),
                    "cabecalho do pacote Access voltou a ter acento",
                )

    def test_schema_ini_do_access_e_ascii(self) -> None:
        destino = Path(self.temp.name) / "access"
        resultado = self.export_service.export_access(self.tournament_id, destino)
        conteudo = Path(resultado["schema_ini"]).read_text(encoding="utf-8")
        self.assertEqual(conteudo, to_ascii(conteudo))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
