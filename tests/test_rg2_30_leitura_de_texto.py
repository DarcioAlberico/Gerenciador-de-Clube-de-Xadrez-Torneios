"""RG2-30 — um leitor de texto só para os importadores: UTF-8, depois Windows-1252, depois erro claro.

Antes: o CSV salvo pelo Excel em português (cp1252) com "João" derrubava a
importação com ``UnicodeDecodeError`` cru; o TRF caía em ``latin-1`` (que
nunca falha e troca letra calado); os downloads liam a resposta inteira, sem
teto; e um ``csv.Error`` no meio do arquivo subia como traceback.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from src.services import text_files
from src.services.constants import AppError
from src.services.text_files import MAX_DOWNLOAD_BYTES, download_text, read_text_file
from tests.support.core_service_base import CoreServiceTestCase

BYTE_INVALIDO = b"Nome\nJo\x81o\n"  # 0x81 não é UTF-8 nem existe no cp1252


class _Resposta:
    def __init__(self, conteudo: bytes) -> None:
        self.conteudo = conteudo

    def __enter__(self) -> "_Resposta":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limite: int = -1) -> bytes:
        return self.conteudo if limite < 0 else self.conteudo[:limite]


class LeitorDeArquivoTest(CoreServiceTestCase):
    def _arquivo(self, nome: str, conteudo: bytes) -> Path:
        caminho = Path(self.temp_dir.name) / nome
        caminho.write_bytes(conteudo)
        return caminho

    def test_arquivo_do_excel_em_cp1252_importa_joao(self) -> None:
        caminho = self._arquivo("jogadores.csv", "Nome;Rating\nJoão Gonçalves;1500\n".encode("cp1252"))
        resultado = self.import_service.import_players_csv(self.tournament_id, caminho)
        self.assertEqual(1, resultado["imported"])
        nomes = [jogador["name"] for jogador in self.db.list_players(self.tournament_id)]
        self.assertIn("João Gonçalves", nomes)

    def test_lista_oficial_em_cp1252_importa_joao(self) -> None:
        conteudo = "ID FIDE;Nome;Federação;Rating\n123;João Gonçalves;BRA;1500\n".encode("cp1252")
        resultado = self.official_rating_service.import_official_csv(self._arquivo("fide.csv", conteudo), "FIDE")
        self.assertEqual(1, resultado["imported"], resultado["errors"])
        self.assertEqual("João Gonçalves", self.db.find_latest_official_player(fide_id="123")["name"])

    def test_utf8_com_bom_continua_lido_como_utf8(self) -> None:
        caminho = self._arquivo("bom.csv", "Nome\nJoão\n".encode("utf-8-sig"))
        self.assertEqual("Nome\nJoão\n", read_text_file(caminho))

    def test_byte_invalido_vira_apperror_e_nao_unicodedecodeerror(self) -> None:
        caminho = self._arquivo("ruim.csv", BYTE_INVALIDO)
        with self.assertRaises(AppError) as contexto:
            self.import_service.import_players_csv(self.tournament_id, caminho)
        self.assertIn("ruim.csv", str(contexto.exception))

    def test_csv_error_no_meio_do_arquivo_vira_apperror(self) -> None:
        campo_gigante = "x" * 200_000  # maior que o limite de campo do módulo csv
        caminho = self._arquivo("gigante.csv", f"Nome;Rating\nAna;1500\n{campo_gigante};1\n".encode())
        with self.assertRaises(AppError):
            self.import_service.import_players_csv(self.tournament_id, caminho)


class DownloadComTetoTest(unittest.TestCase):
    def test_download_acima_do_teto_e_recusado(self) -> None:
        grande = _Resposta(b"a" * (MAX_DOWNLOAD_BYTES + 10))
        with mock.patch.object(text_files, "urlopen", return_value=grande):
            with self.assertRaisesRegex(AppError, "10 MB"):
                download_text("https://exemplo.test/lista.csv", timeout=5, label="a lista")

    def test_download_dentro_do_teto_decodifica_cp1252(self) -> None:
        with mock.patch.object(text_files, "urlopen", return_value=_Resposta("João".encode("cp1252"))):
            self.assertEqual("João", download_text("https://exemplo.test/l.csv", timeout=5, label="a lista"))

    def test_falha_de_rede_vira_apperror(self) -> None:
        with mock.patch.object(text_files, "urlopen", side_effect=OSError("sem rede")):
            with self.assertRaisesRegex(AppError, "a lista"):
                download_text("https://exemplo.test/l.csv", timeout=5, label="a lista")


if __name__ == "__main__":
    unittest.main()
