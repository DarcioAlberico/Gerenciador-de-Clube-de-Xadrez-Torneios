"""RGS-14 (F3.8) — cor inicial sorteada UMA vez, gravada e enviada ao Gacrux.

Antes: sem o registro 152, o Gacrux sorteava a cor do tabuleiro 1 a cada
chamada (`random.random()` em `pairing.py`) e ignorava o `XXC`. A prévia e a
geração da R1 davam cores diferentes (6 planos: B, P, P, B, B, B). O motor
reserva dava sempre brancas ao nº 1, sem sorteio nenhum.

Agora a cor é sorteada quando o torneio nasce (ou escolhida pelo árbitro),
gravada em ``tournament_settings.initial_color`` e usada igual pela prévia,
pela geração, pelo TRF do Gacrux (``152 W|B``) e pela R1 do motor reserva.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

import pytest

from src.core.database import Database
from src.services.constants import AppError
from src.services.export_service import ExportService
from src.services.federation_exporters.trf16 import TRF16Exporter
from src.services.pairing.constraints import choose_colors
from src.services.pairing.gacrux_engine import GacruxEngine
from src.services.pairing.initial_color import resolve_initial_color
from src.services.pairing_service import PairingService
from src.services.tournament_service import TournamentService


class _Torneio(unittest.TestCase):
    SISTEMA = "fide_dutch"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base = Path(self._tmp.name)
        self.db = Database(db_path=base / "t.db", backup_dir=base / "bk")
        self.service = PairingService(self.db)
        self.tid = self.db.create_tournament("RGS-14", rounds_count=5, bye_points=1.0)
        self.db.save_tournament_settings(self.tid, {"pairing_method": "swiss", "pairing_system": self.SISTEMA})
        self.ids = [
            self.db.create_player(self.tid, nome, rating=rating, sex="m", birth_date="2000")
            for nome, rating in (("A", 2400), ("B", 2300), ("C", 2200), ("D", 2100), ("E", 2000), ("F", 1900))
        ]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _cor(self, cor: str) -> None:
        self.db.save_tournament_settings(self.tid, {"initial_color": cor})

    def _gravada(self) -> str:
        return str((self.db.get_tournament_settings(self.tid) or {}).get("initial_color") or "")

    @staticmethod
    def _cor_do_numero_1(mesas: list[dict], numero_1: int) -> str:
        for mesa in mesas:
            if mesa.get("is_bye"):
                continue
            if int(mesa["white_player_id"]) == numero_1:
                return "W"
            if int(mesa.get("black_player_id") or 0) == numero_1:
                return "B"
        raise AssertionError("o nº 1 não está em mesa nenhuma")

    def _linhas_trf(self, rodada: int) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "r.trf"
            GacruxEngine(self.db).write_pairing_trf(self.tid, rodada, caminho)
            return caminho.read_text(encoding="utf-8").splitlines()


class SorteioNaCriacaoTest(_Torneio):
    def test_torneio_novo_nasce_com_a_cor_sorteada(self) -> None:
        self.assertIn(self._gravada(), {"W", "B"})

    def test_o_sorteio_e_o_da_criacao(self) -> None:
        with mock.patch.dict(os.environ, {"ALBERICUS_INITIAL_COLOR": "B"}):
            tid = self.db.create_tournament("Outro", rounds_count=3)
            self.assertEqual("B", self.db.get_tournament_settings(tid)["initial_color"])


class RegistroGacruxTest(_Torneio):
    SISTEMA = "gacrux_swiss"

    def test_trf_do_pareamento_leva_o_152_da_configuracao(self) -> None:
        self._cor("B")
        self.assertIn("152 B", self._linhas_trf(1))
        self._cor("W")
        linhas = self._linhas_trf(1)
        self.assertIn("152 W", linhas)
        self.assertEqual(1, sum(1 for linha in linhas if linha.startswith("152")))

    def test_xxc_do_trf16_antes_da_r1_segue_a_configuracao(self) -> None:
        """O comentário dizia que o motor assume brancas; ele sorteava."""
        self._cor("B")
        conteudo = TRF16Exporter(ExportService(self.db, self.service)).render(self.tid)
        self.assertIn("XXC black1", conteudo)


class MotorReservaTest(_Torneio):
    def test_r1_do_reserva_usa_a_cor_gravada(self) -> None:
        self._cor("B")
        rodada = self.service.generate_next_round(self.tid)
        mesas = self.db.get_pairings_for_round(int(rodada["id"]))
        self.assertEqual("B", self._cor_do_numero_1(mesas, self.ids[0]))

    def test_vinte_previas_e_a_geracao_dao_a_mesma_cor(self) -> None:
        self._cor("B")
        cores = {
            self._cor_do_numero_1(self.service.preview_next_round(self.tid)["pairings"], self.ids[0])
            for _ in range(20)
        }
        rodada = self.service.generate_next_round(self.tid)
        cores.add(self._cor_do_numero_1(self.db.get_pairings_for_round(int(rodada["id"])), self.ids[0]))
        self.assertEqual({"B"}, cores)

    def test_trocar_a_configuracao_antes_da_r1_troca_a_cor(self) -> None:
        self._cor("W")
        antes = self._cor_do_numero_1(self.service.preview_next_round(self.tid)["pairings"], self.ids[0])
        self._cor("B")
        depois = self._cor_do_numero_1(self.service.preview_next_round(self.tid)["pairings"], self.ids[0])
        self.assertEqual(("W", "B"), (antes, depois))

    def test_e5_nas_rodadas_seguintes_usa_a_cor_inicial(self) -> None:
        """C.04.3 E.5: sem preferência, o mais bem classificado ímpar recebe a cor inicial."""
        a = {"id": 1, "rating": 2000}
        b = {"id": 2, "rating": 1900}
        ranking = {1: (-1.0, 1), 2: (-1.0, 2)}
        self.assertEqual((1, 2), choose_colors(a, b, {}, ranking))
        self.assertEqual((2, 1), choose_colors(a, b, {}, ranking, initial_color="B"))


class LegadoTest(_Torneio):
    def _apagar_cor(self) -> None:
        with closing(sqlite3.connect(self.db.db_path)) as conexao:
            conexao.execute("UPDATE tournament_settings SET initial_color = '' WHERE tournament_id = ?", (self.tid,))
            conexao.commit()

    def test_sem_cor_e_com_r1_a_cor_vem_da_r1(self) -> None:
        self._cor("B")
        self.service.generate_next_round(self.tid)
        self._apagar_cor()
        with mock.patch.dict(os.environ, {"ALBERICUS_INITIAL_COLOR": "W"}):
            self.assertEqual("B", resolve_initial_color(self.db, self.tid))

    def test_sem_cor_e_sem_r1_sorteia_uma_vez_e_grava(self) -> None:
        self._apagar_cor()
        with mock.patch.dict(os.environ, {"ALBERICUS_INITIAL_COLOR": "B"}):
            self.assertEqual("B", resolve_initial_color(self.db, self.tid))
        self.assertEqual("B", self._gravada())
        eventos = self.db.list_audit_events(self.tid, action="initial_color_drawn")
        self.assertEqual(1, len(eventos))


class ConfiguracaoTest(_Torneio):
    def setUp(self) -> None:
        super().setUp()
        self.tournament_service = TournamentService(self.db)

    def _salvar(self, **ajustes) -> None:
        self.tournament_service.save_profile(
            self.tid,
            {"name": "RGS-14", "scope": "standalone", "competition_type": "individual", "rounds_count": "5", "bye_points": "1"},
            ajustes,
            [],
        )

    def test_arbitro_escolhe_a_cor(self) -> None:
        self._salvar(initial_color="B")
        self.assertEqual("B", self._gravada())
        self._salvar(initial_color="W")
        self.assertEqual("W", self._gravada())

    def test_cor_invalida_e_recusada(self) -> None:
        with self.assertRaises(AppError):
            self._salvar(initial_color="X")

    def test_depois_da_r1_a_cor_nao_muda(self) -> None:
        self._cor("W")
        self.service.generate_next_round(self.tid)
        with self.assertRaises(AppError):
            self._salvar(initial_color="B")
        self._salvar(initial_color="W")  # reenviar a mesma não é mudança
        self.assertEqual("W", self._gravada())


class MigracaoV57Test(unittest.TestCase):
    def test_v56_para_v57_sorteia_so_quem_nao_tem_r1(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base = Path(tmp)
            db = Database(db_path=base / "t.db", backup_dir=base / "bk")
            service = PairingService(db)
            sem_r1 = db.create_tournament("Sem R1", rounds_count=3)
            com_r1 = db.create_tournament("Com R1", rounds_count=3)
            for numero in range(4):
                db.create_player(com_r1, f"J{numero}", rating=2000 - numero, sex="m", birth_date="2000")
            service.generate_next_round(com_r1)
            with closing(sqlite3.connect(db.db_path)) as conexao:
                conexao.execute("ALTER TABLE tournament_settings DROP COLUMN initial_color")
                conexao.execute("PRAGMA user_version = 56")
                conexao.commit()

            with mock.patch.dict(os.environ, {"ALBERICUS_INITIAL_COLOR": "B"}):
                migrado = Database(db_path=base / "t.db", backup_dir=base / "bk")
            self.assertEqual("B", migrado.get_tournament_settings(sem_r1)["initial_color"])
            # Com R1 a cor já aconteceu: fica vazia e é lida da própria R1.
            self.assertEqual("", migrado.get_tournament_settings(com_r1)["initial_color"])
            self.assertEqual("W", resolve_initial_color(migrado, com_r1))


@pytest.mark.gacrux
class GacruxRealTest(_Torneio):
    SISTEMA = "gacrux_swiss"

    def test_vinte_previas_e_a_geracao_dao_a_mesma_cor(self) -> None:
        self._cor("B")
        cores = {
            self._cor_do_numero_1(self.service.preview_next_round(self.tid)["pairings"], self.ids[0])
            for _ in range(20)
        }
        rodada = self.service.generate_next_round(self.tid)
        cores.add(self._cor_do_numero_1(self.db.get_pairings_for_round(int(rodada["id"])), self.ids[0]))
        self.assertEqual({"B"}, cores)

    def test_trocar_a_configuracao_antes_da_r1_troca_a_cor(self) -> None:
        self._cor("W")
        antes = self._cor_do_numero_1(self.service.preview_next_round(self.tid)["pairings"], self.ids[0])
        self._cor("B")
        depois = self._cor_do_numero_1(self.service.preview_next_round(self.tid)["pairings"], self.ids[0])
        self.assertEqual(("W", "B"), (antes, depois))


if __name__ == "__main__":
    unittest.main()
