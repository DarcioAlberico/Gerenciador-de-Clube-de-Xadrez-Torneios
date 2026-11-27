"""Pendências de serviço da revisão geral do suíço (fases 0–4).

- ``create_tournament_from_profile`` grava torneio, ajustes e agenda **juntos**
  (``db.transaction()``): uma falha no meio não deixa torneio pela metade.
- O gate de acentos (``scripts/check_ui_accents.py``) também lê o texto que
  sai de ``src/services`` para a tela — ver ``literais_de_servico``.
"""
from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from src.core.database import Database
from src.core.services import CertificateService, PairingService
from src.services.certificates.gallery import build_gallery, model_to_template
from src.services.tournament_service import TournamentService

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_ui_accents", RAIZ / "scripts" / "check_ui_accents.py")
lint = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(lint)


class CriarTorneioAPartirDePerfilTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.caminho = base / "albericus.db"
        self.db = Database(self.caminho, backup_dir=base / "backups")
        self.servico = TournamentService(self.db)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _linhas(self, tabela: str) -> int:
        with closing(sqlite3.connect(self.caminho)) as conexao:
            return int(conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0])

    def _criar(self) -> int:
        return self.servico.create_tournament_from_profile(
            {"name": "Modelo", "rounds_count": "3"},
            {},
            [{"round_number": 1, "round_date": "", "round_time": ""}],
        )

    def test_falha_na_agenda_nao_deixa_torneio_nem_ajustes(self) -> None:
        antes = (self._linhas("tournaments"), self._linhas("tournament_settings"))
        with mock.patch.object(self.db, "save_round_schedule", side_effect=RuntimeError("disco cheio")):
            with self.assertRaises(RuntimeError):
                self._criar()
        self.assertEqual(antes, (self._linhas("tournaments"), self._linhas("tournament_settings")))

    def test_sem_falha_grava_as_tres_partes(self) -> None:
        tournament_id = self._criar()
        self.assertIsNotNone(self.db.get_tournament(tournament_id))
        self.assertIsNotNone(self.db.get_tournament_settings(tournament_id))
        self.assertEqual([1, 2, 3], [int(r["round_number"]) for r in self.db.list_round_schedule(tournament_id)])


class GaleriaDeDiplomasTest(unittest.TestCase):
    """Os nomes da galeria ganharam acento; a semeadura é idempotente POR NOME."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.servico = CertificateService(self.db, PairingService(self.db))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_nome_acentuado(self) -> None:
        self.assertTrue(any(m.name.endswith("· Premiação geral") for m in build_gallery(5)))

    def test_semear_de_novo_reconhece_o_modelo_gravado_sem_acento(self) -> None:
        modelo = next(m for m in build_gallery(5) if lint._sem_acento(m.name) != m.name)
        legado = {**model_to_template(modelo), "name": lint._sem_acento(modelo.name)}
        self.db.create_certificate_template(**legado)
        self.assertEqual(4, self.servico.seed_gallery(5)["created"])


class GateDeAcentosNosServicosTest(unittest.TestCase):
    """O critério de ``literais_de_servico``: só o que comprovadamente vai à tela."""

    def _problemas(self, fonte: str, nome: str = "src/services/x.py") -> list[str]:
        return lint.checar_lista_fechada(lint.literais_de_servico_do_fonte(fonte, nome))

    def _palavras(self, fonte: str, nome: str = "src/services/x.py") -> list[str]:
        return [problema.split("'")[1] for problema in self._problemas(fonte, nome)]

    def test_mensagens_de_excecao_reprovam(self) -> None:
        fonte = (
            "def f():\n"
            "    raise AppError('Rodada nao encontrada')\n"
            "    raise ValueError(f'Numero {n} invalido')\n"
            "    raise PermissionError('Sem permissao')\n"
        )
        self.assertEqual(["Numero", "invalido", "nao", "permissao"], sorted(self._palavras(fonte)))

    def test_rotulo_de_constante_reprova_e_a_chave_fica_de_fora(self) -> None:
        fonte = "METODOS = {'Suico': 'Suico', 'none': 'Sem aceleracao'}\n"
        self.assertEqual(["Suico", "aceleracao"], self._palavras(fonte))

    def test_alerta_do_painel_reprova(self) -> None:
        fonte = "add_alert(f'Previa da {x}', 'info', 'preview_next')\n"
        self.assertEqual(["Previa"], self._palavras(fonte))

    def test_literal_comum_e_log_ficam_de_fora(self) -> None:
        fonte = (
            "def f():\n"
            "    status = 'Nao informado'\n"
            "    logger.info('nao foi possivel')\n"
            "    return {'motivo': 'proxima rodada'}\n"
        )
        self.assertEqual([], self._palavras(fonte))

    def test_modulo_de_texto_le_todo_literal(self) -> None:
        fonte = "def f():\n    return 'O jogador ja usou o bye.'\n"
        self.assertEqual([], self._palavras(fonte))
        self.assertEqual(["ja"], self._palavras(fonte, "src/services/pairing/bye_policy.py"))

    def test_a_varredura_le_alguma_coisa(self) -> None:
        """Lint que não lê nada passa sempre."""
        self.assertGreater(len(lint.literais_de_servico()), 1000)

    def test_nenhum_texto_de_servico_sem_acento(self) -> None:
        problemas = lint.checar_lista_fechada(lint.literais_de_servico())
        self.assertEqual([], problemas, "\n".join(problemas))


if __name__ == "__main__":
    unittest.main()
