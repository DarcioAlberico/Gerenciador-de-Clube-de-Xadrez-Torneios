"""Suíço por equipes — ESPEC_SUICO_EQUIPES.md (EQ-01 a EQ-04, referência RGS-30).

Mais duas pendências do caminho de equipes: o TRF do desempate (E5) e o corte
de entrante tardio nos retratos de classificação (E6).

Ordem do arquivo = ordem da §4 da especificação: primeiro a caracterização do
caminho feliz (o que não pode mudar), depois EQ-02, EQ-03/EQ-04 e EQ-01.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

import pytest

from src.core.database import Database
from src.services.pairing import histories, team_swiss
from tests.support.core_service_base import CoreServiceTestCase


def _vitoria_das_brancas(board: dict) -> str:
    """Brancas da EQUIPE vencem: tabuleiro ímpar 1-0, par 0-1 (cores invertidas)."""
    return "1-0" if int(board["board_number"]) % 2 == 1 else "0-1"


def _mudar_rating(db: Database, player_id: int, rating: int) -> None:
    """Atualização de lista no meio do evento (só o rating muda)."""
    with db.connect() as connection:
        connection.execute("UPDATE players SET rating = ? WHERE id = ?", (rating, player_id))


class _TorneioDeEquipes(CoreServiceTestCase):
    def _jogar_rodada(self, tournament_id: int, resultado=_vitoria_das_brancas) -> int:
        rodada = self.service.generate_next_round(tournament_id)
        round_id = int(rodada["id"])
        for match in self.db.list_team_matches_for_round(round_id):
            for board in self.db.list_team_boards(int(match["id"])):
                self.service.update_result(tournament_id, int(board["id"]), resultado(board))
        self.service.close_round(tournament_id, round_id)
        return round_id

    def _confrontos(self, round_id: int, numero: dict[int, int]) -> list[tuple[int, int | None]]:
        return [
            (numero[int(m["white_team_id"])], numero.get(int(m["black_team_id"] or 0)))
            for m in self.db.list_team_matches_for_round(round_id)
        ]

    def _jogador(self, team_id: int, board: int) -> int:
        return int(
            next(
                item["player_id"]
                for item in self.db.list_team_players(team_id)
                if item["board_number"] == board
            )
        )

    def _reserva(self, tournament_id: int, team_id: int, rating: int = 1500) -> int:
        player_id = self.db.create_player(tournament_id, name=f"Reserva {team_id}", rating=rating)
        self.team_service.add_player(team_id, player_id, role="reserve")
        return player_id


# --------------------------------------------------------------------------- #
# §2 — caracterização: o caminho feliz não muda
# --------------------------------------------------------------------------- #


class CaminhoFelizTest(_TorneioDeEquipes):
    def test_tres_rodadas_completas_pareiam_como_antes(self) -> None:
        """Pinado ANTES das mudanças: equipes completas, todos os confrontos jogados."""
        tournament_id, team_ids = self._create_team_tournament(teams_count=6, boards_count=2)
        numero = {team_id: index for index, team_id in enumerate(team_ids, start=1)}
        rodadas = [self._confrontos(self._jogar_rodada(tournament_id), numero) for _ in range(3)]
        self.assertEqual(
            [
                [(1, 4), (5, 2), (3, 6)],
                [(1, 3), (4, 5), (2, 6)],
                [(2, 1), (6, 4), (3, 5)],
            ],
            rodadas,
        )


# --------------------------------------------------------------------------- #
# EQ-02 — titular ausente não derruba a rodada do torneio inteiro
# --------------------------------------------------------------------------- #


def _escalado(board: int, player_id: int, *, role: str = "starter", status: str = "active",
              rating: int = 2000, assignment_id: int | None = None) -> dict:
    return {
        "id": assignment_id or player_id,
        "role": role,
        "board_number": board if role == "starter" else None,
        "player_status": status,
        "player_id": player_id,
        "player_rating": rating,
    }


class EscalacaoPuraTest(unittest.TestCase):
    def test_titulares_completos_sentam_no_proprio_tabuleiro(self) -> None:
        elenco = [_escalado(1, 10), _escalado(2, 11), _escalado(0, 12, role="reserve")]
        self.assertEqual({1: 10, 2: 11}, team_swiss.team_lineup(elenco, 2))

    def test_reserva_ativa_senta_no_lugar_do_ausente(self) -> None:
        elenco = [
            _escalado(1, 10, status="withdrawn"),
            _escalado(2, 11),
            _escalado(3, 12),
            _escalado(0, 20, role="reserve"),
        ]
        self.assertEqual({1: 20, 2: 11, 3: 12}, team_swiss.team_lineup(elenco, 3))

    def test_reservas_sobem_na_ordem_declarada(self) -> None:
        elenco = [
            _escalado(1, 10, status="withdrawn"),
            _escalado(2, 11, status="absent"),
            _escalado(0, 21, role="reserve", assignment_id=31),
            _escalado(0, 20, role="reserve", assignment_id=30),
        ]
        self.assertEqual({1: 20, 2: 21}, team_swiss.team_lineup(elenco, 2))

    def test_sem_reserva_os_de_baixo_sobem_e_a_vaga_fica_no_fim(self) -> None:
        elenco = [
            _escalado(1, 10, status="withdrawn"),
            _escalado(2, 11),
            _escalado(3, 12),
            _escalado(4, 13),
        ]
        self.assertEqual({1: 11, 2: 12, 3: 13, 4: None}, team_swiss.team_lineup(elenco, 4))

    def test_equipe_sem_ninguem_tem_todos_os_tabuleiros_vazios(self) -> None:
        elenco = [_escalado(1, 10, status="withdrawn")]
        self.assertEqual({1: None, 2: None}, team_swiss.team_lineup(elenco, 2))

    def test_semente_e_a_media_dos_titulares_declarados(self) -> None:
        """A semente não depende de quem está presente (base do TPN, EQ-01)."""
        elenco = [
            _escalado(1, 10, rating=2000),
            _escalado(2, 11, rating=1900, status="withdrawn"),
            _escalado(0, 12, role="reserve", rating=2500),
        ]
        self.assertEqual(1950, team_swiss.team_seed(elenco, 2))

    def test_tabuleiro_vazio_nasce_marcado_como_wo(self) -> None:
        rosters = {1: {1: 10, 2: 11}, 2: {1: 20, 2: None}}
        confronto = team_swiss.team_match_payload(1, 1, 2, rosters, 2)
        # Tabuleiro 2 inverte as cores: a vaga da equipe 2 está nas brancas.
        self.assertEqual(["", "0F-1F"], [board["result"] for board in confronto["boards"]])
        invertido = team_swiss.team_match_payload(1, 2, 1, rosters, 2)
        self.assertEqual(["", "1F-0F"], [board["result"] for board in invertido["boards"]])
        vazio = team_swiss.team_match_payload(1, 1, 2, {1: {1: None}, 2: {1: None}}, 1)
        self.assertEqual(["0F-0F"], [board["result"] for board in vazio["boards"]])


class EscalacaoServicoTest(_TorneioDeEquipes):
    def setUp(self) -> None:
        super().setUp()
        self.tid, self.team_ids = self._create_team_tournament(teams_count=4, boards_count=2)
        self.equipe_c = self.team_ids[2]

    def _tabuleiros_da_equipe(self, round_id: int, team_id: int) -> dict[int, int | None]:
        elenco = {int(item["player_id"]) for item in self.db.list_team_players(team_id)}
        for match in self.db.list_team_matches_for_round(round_id):
            if team_id not in (match["white_team_id"], match["black_team_id"]):
                continue
            saida: dict[int, int | None] = {}
            for board in self.db.list_team_boards(int(match["id"])):
                da_equipe = [
                    pid for pid in (board["white_player_id"], board["black_player_id"])
                    if pid in elenco
                ]
                saida[int(board["board_number"])] = da_equipe[0] if da_equipe else None
            return saida
        raise AssertionError("equipe sem confronto")

    def test_titular_desistente_da_lugar_a_reserva_e_a_rodada_sai(self) -> None:
        titular_1 = self._jogador(self.equipe_c, 1)
        titular_2 = self._jogador(self.equipe_c, 2)
        reserva = self._reserva(self.tid, self.equipe_c)
        self.db.set_player_status(titular_1, "withdrawn")

        rodada = self.service.generate_next_round(self.tid)

        self.assertEqual(
            {1: reserva, 2: titular_2},
            self._tabuleiros_da_equipe(int(rodada["id"]), self.equipe_c),
        )

    def test_sem_reserva_o_ultimo_tabuleiro_sai_por_wo_e_a_previa_avisa(self) -> None:
        titular_2 = self._jogador(self.equipe_c, 2)
        self.db.set_player_status(self._jogador(self.equipe_c, 1), "withdrawn")

        previa = self.service.preview_next_round(self.tid)
        avisos = [
            alerta for match in previa["matches"] for alerta in match["alerts"]
        ]
        self.assertIn("Escalação incompleta", avisos)
        explicacao = " ".join(match["explanation"] for match in previa["matches"])
        self.assertIn("tabuleiro 2", explicacao)
        # E no topo da prévia, que a tela mostra antes da lista de confrontos.
        self.assertEqual(["Equipe 3: tabuleiro 2 sem jogador presente (W.O.)."], previa["warnings"])

        rodada = self.service.generate_next_round(self.tid)
        round_id = int(rodada["id"])
        self.assertEqual({1: titular_2, 2: None}, self._tabuleiros_da_equipe(round_id, self.equipe_c))
        confronto = next(
            m for m in self.db.list_team_matches_for_round(round_id)
            if self.equipe_c in (m["white_team_id"], m["black_team_id"])
        )
        vaga = self.db.list_team_boards(int(confronto["id"]))[1]
        self.assertIn(vaga["result"], {"1F-0F", "0F-1F"})

        # O painel do árbitro (checklist, ação `lineups`) também acusa.
        item = next(i for i in self.service.closing_checklist(self.tid) if i["action"] == "lineups")
        self.assertFalse(item["ok"])

        # E a rodada fecha: o tabuleiro vazio já tem resultado.
        for match in self.db.list_team_matches_for_round(round_id):
            for board in self.db.list_team_boards(int(match["id"])):
                if not board["result"]:
                    self.service.update_result(self.tid, int(board["id"]), "1/2-1/2")
        self.service.close_round(self.tid, round_id)

    def test_equipe_sem_jogador_pede_confirmacao_e_nada_e_gravado(self) -> None:
        for board in (1, 2):
            self.db.set_player_status(self._jogador(self.equipe_c, board), "withdrawn")

        with self.assertRaises(team_swiss.TeamWithoutPlayersError) as erro:
            self.service.generate_next_round(self.tid)
        self.assertIn("Equipe 3", str(erro.exception))
        self.assertEqual([], self.db.list_rounds(self.tid))
        self.assertEqual([], self.db.list_team_matches_for_tournament(self.tid))

        # Confirmado o W.O. do confronto inteiro, a rodada sai com tudo marcado.
        rodada = self.service.generate_next_round(self.tid, forfeit_empty_teams=True)
        self.assertEqual(
            {1: None, 2: None}, self._tabuleiros_da_equipe(int(rodada["id"]), self.equipe_c)
        )


# --------------------------------------------------------------------------- #
# EQ-03 / EQ-04 — confronto inteiro por W.O. não é confronto jogado
# --------------------------------------------------------------------------- #


def _confronto(match_id: int, white: int, black: int, white_mp: float, black_mp: float,
               round_number: int = 1) -> dict:
    return {
        "id": match_id, "round_number": round_number, "white_team_id": white,
        "black_team_id": black, "white_match_points": white_mp,
        "black_match_points": black_mp, "is_bye": 0,
    }


def _tabuleiros(*resultados: str) -> list[dict]:
    return [{"board_number": n, "result": r} for n, r in enumerate(resultados, start=1)]


class ConfrontoNaoJogadoPuroTest(unittest.TestCase):
    def test_so_o_confronto_inteiro_por_wo_e_nao_jogado(self) -> None:
        match = _confronto(1, 10, 20, 2.0, 0.0)
        self.assertTrue(histories.team_match_unplayed(match, _tabuleiros("1F-0F", "0F-1F")))
        self.assertTrue(histories.team_match_unplayed(match, _tabuleiros("0F-0F", "0F-0F")))
        self.assertFalse(histories.team_match_unplayed(match, _tabuleiros("1F-0F", "1-0")))
        self.assertFalse(histories.team_match_unplayed(match, _tabuleiros("1-0", "0-1")))
        self.assertFalse(histories.team_match_unplayed(match, []))
        self.assertFalse(histories.team_match_unplayed({**match, "is_bye": 1}, []))

    def test_wo_inteiro_sai_dos_pares_e_das_cores(self) -> None:
        matches = [_confronto(1, 10, 20, 2.0, 0.0), _confronto(2, 30, 40, 2.0, 0.0)]
        boards = {1: _tabuleiros("1F-0F", "0F-1F"), 2: _tabuleiros("1F-0F", "1-0")}
        self.assertEqual({frozenset((30, 40))}, histories.team_played_pairs(matches, boards))
        cores = histories.team_color_histories(matches, boards)
        self.assertEqual([], cores.get(10, []))
        self.assertEqual([], cores.get(20, []))
        self.assertEqual(["W"], cores[30])

    def test_wo_inteiro_e_downfloat_de_quem_pontuou_e_nada_para_o_outro(self) -> None:
        matches = [_confronto(1, 10, 20, 2.0, 0.0)]
        historico = histories.team_float_histories(matches, {1: _tabuleiros("1F-0F", "0F-1F")})
        self.assertEqual(["down"], historico[10])
        self.assertEqual([], historico[20])
        dupla = histories.team_float_histories(
            [_confronto(1, 10, 20, 0.0, 0.0)], {1: _tabuleiros("0F-0F", "0F-0F")}
        )
        self.assertEqual([], dupla[10])
        self.assertEqual([], dupla[20])

    def test_vencedor_por_wo_nao_recebe_o_bye_alocado(self) -> None:
        matches = [_confronto(1, 10, 20, 2.0, 0.0)]
        boards = {1: _tabuleiros("1F-0F", "0F-1F")}
        self.assertEqual({10}, histories.team_bye_ids(matches, boards))
        self.assertEqual(set(), histories.team_bye_ids(matches, {1: _tabuleiros("1-0", "0-1")}))

    def test_bye_vai_para_outra_equipe_quando_a_ultima_venceu_por_wo(self) -> None:
        equipes = [{"id": i, "name": f"E{i}"} for i in (10, 20, 30, 40, 50)]
        rosters = {i: {1: i * 10 + 1} for i in (10, 20, 30, 40, 50)}
        seeds = {10: -1, 20: -2, 30: -3, 40: -4, 50: -5}
        # A (50) está sozinha no último grupo — e venceu a R1 por W.O.
        standings = {
            10: {"match_points": 4.0, "position": 1}, 20: {"match_points": 4.0, "position": 2},
            30: {"match_points": 2.0, "position": 3}, 40: {"match_points": 2.0, "position": 4},
            50: {"match_points": 0.0, "position": 5},
        }
        bloqueadas = histories.team_bye_ids(
            [_confronto(1, 50, 40, 2.0, 0.0)], {1: _tabuleiros("1F-0F")}
        )
        rodada = team_swiss.swiss_team_matches(
            equipes, rosters, seeds, 1, {}, standings, {}, set(), bloqueadas,
            max_exhaustive_pairing_teams=8, repeat_pairing_penalty=1000,
            score_group_float_penalty=100, score_diff_penalty=10,
        )
        bye = next(m for m in rodada if m["is_bye"])
        self.assertNotEqual(50, bye["white_team_id"])


class ConfrontoNaoJogadoServicoTest(_TorneioDeEquipes):
    def _dois_times_r1(self, resultado) -> tuple[int, list[int]]:
        tid, team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        self._jogar_rodada(tid, resultado)
        return tid, team_ids

    def test_wo_inteiro_pode_repetir_e_nao_conta_cor(self) -> None:
        def wo(board: dict) -> str:
            return "1F-0F" if int(board["board_number"]) % 2 == 1 else "0F-1F"

        tid, team_ids = self._dois_times_r1(wo)
        self.assertEqual(set(), self.service._team_played_pairs(tid))
        previa = self.service.preview_next_round(tid)
        self.assertEqual([], previa["matches"][0]["alerts"])
        # Sem cor da R1 por W.O., a R2 repete a cor da semente (a de cima de brancas).
        self.assertEqual(team_ids[0], previa["matches"][0]["white_team_id"])
        self.assertIn(team_ids[0], self.service._team_bye_ids(tid))

    def test_wo_parcial_e_confronto_jogado(self) -> None:
        def parcial(board: dict) -> str:
            return "1F-0F" if int(board["board_number"]) == 1 else "0-1"

        tid, team_ids = self._dois_times_r1(parcial)
        self.assertEqual({frozenset(team_ids)}, self.service._team_played_pairs(tid))
        previa = self.service.preview_next_round(tid)
        self.assertIn("Confronto repetido", previa["matches"][0]["alerts"])


# --------------------------------------------------------------------------- #
# EQ-01 — o TPN é dado do torneio, gravado na R1
# --------------------------------------------------------------------------- #


class NumeroDeEmparceiramentoPuroTest(unittest.TestCase):
    def test_tpn_segue_a_semente_e_o_gravado_nao_muda(self) -> None:
        equipes = [
            {"id": 1, "name": "B", "pairing_number": None},
            {"id": 2, "name": "A", "pairing_number": None},
            {"id": 3, "name": "C", "pairing_number": None},
        ]
        self.assertEqual({2: 1, 1: 2, 3: 3}, team_swiss.assign_team_pairing_numbers(equipes, {1: 1900, 2: 1900, 3: 1800}))
        gravadas = [
            {"id": 1, "name": "B", "pairing_number": 2},
            {"id": 2, "name": "A", "pairing_number": 1},
            {"id": 4, "name": "Tardia", "pairing_number": None},
        ]
        # A tardia vem no fim, mesmo sendo a mais forte (C.04.2: sem renumerar).
        self.assertEqual({2: 1, 1: 2, 4: 3}, team_swiss.assign_team_pairing_numbers(gravadas, {1: 1, 2: 1, 4: 9999}))

    def _rodada_1(self, total: int, metodo: str) -> list[dict]:
        equipes = [{"id": i * 7, "name": f"E{i}"} for i in range(1, total + 1)]
        seeds = {int(e["id"]): 3000 - i for i, e in enumerate(equipes)}
        rosters = {int(e["id"]): {1: int(e["id"]) * 10} for e in equipes}
        if metodo == "round_robin":
            return team_swiss.round_robin_team_matches(equipes, rosters, seeds, 1, {}, 1)
        return team_swiss.first_round_team_matches(equipes, rosters, seeds, 1, {})

    def test_tpn_e_lido_da_r1_ja_gerada(self) -> None:
        for metodo in ("swiss", "round_robin"):
            for total in (2, 3, 4, 5, 6, 7):
                with self.subTest(metodo=metodo, total=total):
                    esperado = {i * 7: i for i in range(1, total + 1)}
                    self.assertEqual(esperado, team_swiss.tpn_from_first_round(self._rodada_1(total, metodo), metodo))


class NumeroDeEmparceiramentoServicoTest(_TorneioDeEquipes):
    def _r2_apos_r1(self, mexer_no_rating: bool) -> list[tuple[int, int | None]]:
        tid, team_ids = self._create_team_tournament(teams_count=6, boards_count=2)
        numero = {team_id: index for index, team_id in enumerate(team_ids, start=1)}

        def empate(board: dict) -> str:
            return "1/2-1/2"

        self._jogar_rodada(tid, empate)
        if mexer_no_rating:
            _mudar_rating(self.db, self._jogador(team_ids[5], 1), 2900)
        rodada = self.service.generate_next_round(tid)
        return self._confrontos(int(rodada["id"]), numero)

    def test_rating_novo_depois_da_r1_nao_reordena_as_equipes(self) -> None:
        self.assertEqual(self._r2_apos_r1(False), self._r2_apos_r1(True))

    def test_tpn_do_trf25_e_o_numero_que_o_motor_usou(self) -> None:
        tid, team_ids = self._create_team_tournament(teams_count=4, boards_count=2)
        self._jogar_rodada(tid)
        _mudar_rating(self.db, self._jogador(team_ids[3], 1), 2900)
        gravado = {int(t["name"].split()[-1]): int(t["pairing_number"]) for t in self.db.list_teams(tid)}
        destino = Path(self.temp_dir.name) / "equipes.trf"
        from src.services.federation_exporters.trf25 import TRF25Exporter

        TRF25Exporter(self.export_service).export(tid, destino)
        no_arquivo: dict[int, int] = {}
        for linha in destino.read_text(encoding="utf-8").splitlines():
            if linha.startswith("310 "):
                tpn = int(linha[4:7])
                nome = linha[8:40].strip()
                no_arquivo[int(nome.split()[-1])] = tpn
        self.assertEqual(gravado, no_arquivo)

    def test_todos_contra_todos_nao_muda_quando_uma_equipe_sai(self) -> None:
        def calendario(desativar: bool) -> list[tuple[int, int | None]]:
            tid, team_ids = self._create_team_tournament(teams_count=4, boards_count=2)
            self.db.save_tournament_settings(tid, {"team_pairing_method": "round_robin"})
            numero = {team_id: index for index, team_id in enumerate(team_ids, start=1)}
            self._jogar_rodada(tid)
            if desativar:
                team = self.db.get_team(team_ids[3])
                self.db.update_team(team_ids[3], team["name"], active=0)
            rodada = self.service.generate_next_round(tid)
            if desativar:
                fora = next(
                    m for m in self.db.list_team_matches_for_round(int(rodada["id"]))
                    if team_ids[3] in (m["white_team_id"], m["black_team_id"])
                )
                self.assertTrue(all(
                    b["result"] in {"1F-0F", "0F-1F"} for b in self.db.list_team_boards(int(fora["id"]))
                ))
            return self._confrontos(int(rodada["id"]), numero)

        self.assertEqual(calendario(False), calendario(True))


class MigracaoTpnTest(unittest.TestCase):
    def test_torneio_em_andamento_grava_o_tpn_da_r1_sem_recalcular(self) -> None:
        from src.services.pairing_service import PairingService
        from src.services.tournament_service import TeamService, TournamentService

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base = Path(tmp)
            db = Database(db_path=base / "t.db", backup_dir=base / "bk")
            tournaments = TournamentService(db)
            teams = TeamService(db)
            tid = tournaments.create_tournament(
                {"name": "Equipes", "competition_type": "team", "rounds_count": "5", "bye_points": "1"}
            )
            db.save_tournament_settings(tid, {"team_boards_count": "1", "team_pairing_method": "swiss"})
            ids = []
            for index in range(5):
                team_id = teams.create_team(tid, {"name": f"Equipe {index + 1}"})
                player = db.create_player(tid, name=f"J{index}", rating=2000 - index * 50)
                teams.add_player(team_id, player, board_number="1", role="starter")
                ids.append((team_id, player))
            PairingService(db).generate_next_round(tid)
            esperado = {int(t["id"]): int(t["pairing_number"]) for t in db.list_teams(tid)}
            # Rating muda depois da R1: a migração NÃO pode recalcular por ele.
            _mudar_rating(db, ids[4][1], 2999)
            with closing(sqlite3.connect(db.db_path)) as conexao:
                for coluna in ("pairing_number", "seed_rating", "entry_round"):
                    conexao.execute(f"ALTER TABLE teams DROP COLUMN {coluna}")
                conexao.execute("PRAGMA user_version = 57")
                conexao.commit()

            migrado = Database(db_path=base / "t.db", backup_dir=base / "bk")
            gravado = {int(t["id"]): int(t["pairing_number"]) for t in migrado.list_teams(tid)}
            self.assertEqual(esperado, gravado)
            self.assertEqual({1}, {int(t["entry_round"]) for t in migrado.list_teams(tid)})
            # Idempotente: rodar de novo não muda nada.
            from src.database.migrations.legacy_migrations import LegacyMigrations

            with migrado.connect() as conexao:
                LegacyMigrations(migrado)._ensure_current_schema(conexao)
            self.assertEqual(
                gravado, {int(t["id"]): int(t["pairing_number"]) for t in migrado.list_teams(tid)}
            )


# --------------------------------------------------------------------------- #
# E5 — o TRF do desempate de equipes leva o placar recortado (162 + 299)
# --------------------------------------------------------------------------- #


def _meio_a_meio(board: dict) -> str:
    return "1-0" if int(board["board_number"]) % 2 == 1 else "1/2-1/2"


class _DesempateDeEquipes(_TorneioDeEquipes):
    CODES = ["match_points", "game_points", "buchholz", "wins"]

    def _duas_rodadas(self, *, vaga: bool = False) -> int:
        """4 equipes, 2 rodadas. `vaga`: a Equipe 3 joga a R1 sem o tabuleiro 1."""
        tid, team_ids = self._create_team_tournament(teams_count=4, boards_count=2)
        titular = self._jogador(team_ids[2], 1)
        if vaga:
            self.db.set_player_status(titular, "withdrawn")

        def resultado(board: dict) -> str:
            return board["result"] or _meio_a_meio(board)

        self._jogar_rodada(tid, resultado)
        self.db.set_player_status(titular, "active")
        self._jogar_rodada(tid, resultado)
        return tid

    def _trf_do_desempate(self, tid: int, current_round: int | None = None) -> list[str]:
        from src.services.pairing.gacrux_tiebreak_engine import GacruxTiebreakEngine

        job = GacruxTiebreakEngine(self.db).prepare_teams(tid, self.CODES, current_round=current_round)
        return job.trf.decode("utf-8").splitlines()


class TrfDoDesempateDeEquipesTest(_DesempateDeEquipes):
    def test_retrato_da_r1_declara_os_pontos_das_celulas_da_r1(self) -> None:
        """Sem o recorte, a linha 001 dizia os pontos de HOJE e as células só a R1."""
        from src.services.pairing.gacrux_trf import declared_points, implied_points, is_player_line

        linhas = self._trf_do_desempate(self._duas_rodadas(), current_round=1)
        self.assertTrue(any(linha.startswith("162") for linha in linhas))
        for linha in filter(is_player_line, linhas):
            self.assertEqual(implied_points(linha), declared_points(linha), linha)

    def test_retrato_numera_os_jogadores_como_o_arquivo(self) -> None:
        """Reserva inscrita depois da R1: o arquivo da R1 não a traz (RGS-10).

        Se o mapa de números do desempate viesse da lista SEM corte, o número 1
        seria o da reserva (rating mais alto) e os pontos de entrada dela iriam
        para quem é o n.º 1 no arquivo — o TRF não fecha e o Gacrux é recusado.
        """
        from src.services.pairing.gacrux_trf import declared_points, implied_points, is_player_line

        tid = self._duas_rodadas()
        tardia = self.db.create_player(tid, name="Reserva tardia", rating=2900, starting_points=1.0)
        self.team_service.add_player(self.db.list_teams(tid)[0]["id"], tardia, role="reserve")
        linhas = [linha for linha in self._trf_do_desempate(tid, current_round=1) if is_player_line(linha)]
        self.assertEqual(8, len(linhas))
        for linha in linhas:
            self.assertEqual(implied_points(linha), declared_points(linha), linha)

    def test_ponto_do_tabuleiro_vazio_chega_ao_jogador_no_trf(self) -> None:
        """EQ-02 no TRF: quem venceu o tabuleiro vazio pontuou sem jogar.

        A mesa sem adversário era descartada e a célula do jogador saía `Z`
        (zero): o Gacrux somava um ponto de jogo a menos para a equipe.
        """
        from src.services.pairing.gacrux_trf import declared_points, is_player_line

        tid = self._duas_rodadas(vaga=True)
        linhas = [linha for linha in self._trf_do_desempate(tid) if is_player_line(linha)]
        sem_jogo = [linha for linha in linhas if "0000 - F" in linha]
        self.assertEqual(1, len(sem_jogo), "um jogador venceu o tabuleiro vazio")
        por_equipe = {
            int(item["team_id"]): float(item["game_points"])
            for item in self.service.team_standings(tid)
        }
        self.assertEqual(sum(por_equipe.values()), sum(declared_points(linha) for linha in linhas))


@pytest.mark.gacrux
class TrfDoDesempateDeEquipesGacruxTest(_DesempateDeEquipes):
    def test_gacrux_calcula_o_retrato_da_r1(self) -> None:
        """Antes: "Erro no cálculo de desempates do Gacrux: Erro desconhecido"."""
        from src.services.pairing.gacrux_tiebreak_engine import GacruxTiebreakEngine

        tid = self._duas_rodadas()
        retrato = GacruxTiebreakEngine(self.db).compute_teams(tid, self.CODES, current_round=1)
        self.assertEqual(4, len(retrato))
        self.assertEqual({2.0, 0.0}, {item["scores"]["match_points"] for item in retrato.values()})

    def test_gacrux_conta_o_ponto_do_tabuleiro_vazio(self) -> None:
        from src.services.pairing.gacrux_tiebreak_engine import GacruxTiebreakEngine

        tid = self._duas_rodadas(vaga=True)
        gacrux = GacruxTiebreakEngine(self.db).compute_teams(tid, self.CODES)
        proprio = {
            int(item["team_id"]): float(item["game_points"])
            for item in self.service._team_standings(tid)
        }
        self.assertEqual(
            proprio, {team_id: item["scores"]["game_points"] for team_id, item in gacrux.items()}
        )


# --------------------------------------------------------------------------- #
# E6 — o retrato da rodada N não traz a equipe que entrou depois
# --------------------------------------------------------------------------- #


class EntranteTardioDeEquipeTest(_TorneioDeEquipes):
    def test_equipe_inscrita_depois_da_r1_fica_fora_do_retrato_da_r1(self) -> None:
        tid, team_ids = self._create_team_tournament(teams_count=2, boards_count=1)
        self._jogar_rodada(tid)
        tardia = self.team_service.create_team(tid, {"name": "Tardia"})
        self.assertEqual(2, int(self.db.get_team(tardia)["entry_round"]))
        retrato = {int(item["team_id"]) for item in self.service._team_standings(tid, up_to_round=1)}
        self.assertEqual(set(team_ids), retrato)
        self.assertIn(tardia, {int(item["team_id"]) for item in self.service._team_standings(tid)})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class OfertaWoDaEquipeSemJogadoresTest(unittest.TestCase):
    """EQ-02.4 na tela: a recusa vira pergunta; confirmar gera com o W.O."""

    def _tela(self):
        from src.ui.screens.pairing_results.view import PairingResultsMixin

        chamadas = []

        class Tela(PairingResultsMixin):
            def _start_round_generation(self, tournament_id, *, reserve_engine, forfeit_empty_teams=False):
                chamadas.append((tournament_id, reserve_engine, forfeit_empty_teams))

        return Tela(), chamadas

    def test_confirmar_gera_com_o_wo_do_confronto(self) -> None:
        tela, chamadas = self._tela()
        erro = team_swiss.TeamWithoutPlayersError(["Equipe 3"])
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=True) as dialogo:
            self.assertTrue(tela._offer_round_way_out(7, erro))
        self.assertEqual([(7, False, True)], chamadas)
        self.assertIn("Equipe 3", dialogo.call_args.args[2])

    def test_cancelar_nao_gera_nada(self) -> None:
        tela, chamadas = self._tela()
        erro = team_swiss.TeamWithoutPlayersError(["Equipe 3"])
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=False):
            self.assertTrue(tela._offer_round_way_out(7, erro))
        self.assertEqual([], chamadas)

    def test_recusa_do_gacrux_continua_oferecendo_o_motor_reserva(self) -> None:
        from src.services.pairing.gacrux_engine import GacruxScoreMismatch

        tela, chamadas = self._tela()
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=True):
            self.assertTrue(tela._offer_round_way_out(7, GacruxScoreMismatch(2, ["x"])))
        self.assertEqual([(7, True, False)], chamadas)

    def test_outro_erro_nao_e_tratado_aqui(self) -> None:
        tela, chamadas = self._tela()
        self.assertFalse(tela._offer_round_way_out(7, RuntimeError("outro")))
        self.assertEqual([], chamadas)


# --------------------------------------------------------------------------- #
# EQ-05 — bye solicitado H/Z não bloqueia o bye alocado (C.04.6 [C2])
# --------------------------------------------------------------------------- #


def _bye(match_id: int, team_id: int, tipo: str, round_number: int = 1) -> dict:
    return {
        "id": match_id, "round_number": round_number, "white_team_id": team_id,
        "black_team_id": None, "white_match_points": 0.0, "black_match_points": 0.0,
        "is_bye": 1, "result": tipo,
    }


class ByeSolicitadoDeEquipeTest(unittest.TestCase):
    def test_so_bye_alocado_e_bye_de_ponto_cheio_bloqueiam_o_bye_alocado(self) -> None:
        matches = [_bye(1, 10, "BYE"), _bye(2, 20, "F"), _bye(3, 30, "H"), _bye(4, 40, "Z")]
        self.assertEqual({10, 20}, histories.team_bye_ids(matches))


class ByeSolicitadoDeEquipeServicoTest(_TorneioDeEquipes):
    def test_equipe_que_pediu_bye_h_ainda_pode_receber_o_bye_alocado(self) -> None:
        """3 equipes; a 3ª pede H na R1 e as outras empatam. Na R2, todas com 1
        ponto de match, o bye alocado vai para a de maior TPN — a 3ª."""
        tid, equipes = self._create_team_tournament(teams_count=3, boards_count=2)
        self.db.add_requested_team_bye(tid, equipes[2], 1, "H")
        self._jogar_rodada(tid, lambda board: "1/2-1/2")
        previa = self.service.preview_next_round(tid)
        bye = next(m for m in previa["matches"] if m.get("is_bye"))
        self.assertEqual(equipes[2], int(bye["white_team_id"]))


# --------------------------------------------------------------------------- #
# EQ-06 — entrante tardio no todos-contra-todos por equipes: aviso, calendário fixo
# --------------------------------------------------------------------------- #


class EntranteTardioNoTodosContraTodosTest(_TorneioDeEquipes):
    def _r2(self, com_tardia: bool) -> tuple[list[tuple[int, int | None]], dict]:
        tid, team_ids = self._create_team_tournament(teams_count=4, boards_count=2)
        self.db.save_tournament_settings(tid, {"team_pairing_method": "round_robin"})
        numero = {team_id: index for index, team_id in enumerate(team_ids, start=1)}
        self._jogar_rodada(tid)
        if com_tardia:
            self.tardia = self.team_service.create_team(tid, {"name": "Tardia"})
            for tabuleiro in (1, 2):
                jogador = self.db.create_player(tid, name=f"Tardia {tabuleiro}", rating=2500)
                self.team_service.add_player(
                    self.tardia, jogador, board_number=str(tabuleiro), role="starter"
                )
        previa = self.service.preview_next_round(tid)
        rodada = self.service.generate_next_round(tid)
        return self._confrontos(int(rodada["id"]), numero), previa

    def test_equipe_inscrita_depois_da_r1_e_avisada_e_nao_muda_o_calendario(self) -> None:
        sem, _ = self._r2(False)
        com, previa = self._r2(True)
        self.assertEqual(sem, com)
        self.assertTrue(any("Tardia" in aviso and "calend" in aviso for aviso in previa["warnings"]))
        self.assertIsNone(self.db.get_team(self.tardia)["pairing_number"])
        tid = int(self.db.get_team(self.tardia)["tournament_id"])
        registrados = [
            evento for evento in self.db.list_audit_events(tid, limit=50)
            if evento["action"] == "pairing_warning"
        ]
        self.assertEqual(1, len(registrados))


# --------------------------------------------------------------------------- #
# EQ-01.5 — correção de TPN pelo árbitro: troca entre duas equipes, com motivo
# --------------------------------------------------------------------------- #


class CorrecaoDeTpnTest(_TorneioDeEquipes):
    MOTIVO = "Rating da inscrição estava errado"

    def _tpn(self, team_id: int):
        return self.db.get_team(team_id)["pairing_number"]

    def _depois_da_r1(self, metodo: str = "swiss") -> tuple[int, list[int]]:
        tid, team_ids = self._create_team_tournament(teams_count=4, boards_count=2)
        self.db.save_tournament_settings(tid, {"team_pairing_method": metodo})
        self._jogar_rodada(tid)
        return tid, team_ids

    def test_troca_os_tpn_de_duas_equipes_e_registra_o_motivo(self) -> None:
        tid, (a, b, c, d) = self._depois_da_r1()
        self.assertEqual((1, 2), (self._tpn(a), self._tpn(b)))
        self.team_service.swap_pairing_numbers(a, b, reason=self.MOTIVO)
        self.assertEqual((2, 1, 3, 4), tuple(self._tpn(t) for t in (a, b, c, d)))
        evento = next(
            e for e in self.db.list_audit_events(tid, limit=50)
            if e["action"] == "team_pairing_number_corrected"
        )
        self.assertEqual(self.MOTIVO, evento["reason"])
        # A R2 usa o número corrigido.
        self.assertEqual({a: 2, b: 1, c: 3, d: 4}, self.service._team_next_round_plan(
            tid, self.db.get_tournament(tid))["pairing_numbers"])

    def test_sem_motivo_e_recusado_e_nada_muda(self) -> None:
        _tid, (a, b, _c, _d) = self._depois_da_r1()
        with self.assertRaisesRegex(Exception, "motivo"):
            self.team_service.swap_pairing_numbers(a, b, reason="   ")
        self.assertEqual((1, 2), (self._tpn(a), self._tpn(b)))

    def test_com_rodada_aberta_e_recusado(self) -> None:
        tid, (a, b, _c, _d) = self._depois_da_r1()
        self.service.generate_next_round(tid)
        with self.assertRaisesRegex(Exception, "Feche a rodada 2"):
            self.team_service.swap_pairing_numbers(a, b, reason=self.MOTIVO)
        self.assertEqual((1, 2), (self._tpn(a), self._tpn(b)))

    def test_antes_da_r1_nao_ha_tpn_para_corrigir(self) -> None:
        _tid, (a, b, _c, _d) = self._create_team_tournament(teams_count=4, boards_count=2)
        with self.assertRaisesRegex(Exception, "1ª rodada"):
            self.team_service.swap_pairing_numbers(a, b, reason=self.MOTIVO)

    def test_no_todos_contra_todos_o_calendario_e_fixo(self) -> None:
        _tid, (a, b, _c, _d) = self._depois_da_r1("round_robin")
        with self.assertRaisesRegex(Exception, "calendário"):
            self.team_service.swap_pairing_numbers(a, b, reason=self.MOTIVO)
        self.assertEqual((1, 2), (self._tpn(a), self._tpn(b)))


# --------------------------------------------------------------------------- #
# EQ-07 — Baku (FIDE C.04.7) no Suíço por equipes
# --------------------------------------------------------------------------- #


class BakuDeEquipesPuroTest(unittest.TestCase):
    def test_exemplo_2_do_handbook_onze_rodadas_com_match_points(self) -> None:
        """C.04.7 1.4.4, Exemplo 2: 11 rodadas, 2 MP a vitória → GA recebe 2 MP
        virtuais nas R1–R3 e 1 MP nas R4–R6."""
        from src.services.pairing.acceleration import baku_team_accelerated_ids

        tpn = list(range(101, 109))  # 8 equipes, já na ordem do TPN
        vps = []
        for rodada in range(1, 12):
            ids, vp = baku_team_accelerated_ids(
                tpn, tpn, 11, rodada, primary_score="match_points",
                win_points=2.0, draw_points=1.0, loss_points=0.0,
            )
            vps.append(vp)
            if vp:
                self.assertEqual(tpn[:4], ids)  # GA = 2 × ⌈8/4⌉
        self.assertEqual([2.0, 2.0, 2.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], vps)

    def test_game_points_como_score_principal_recusa_baku(self) -> None:
        """Nota do Exemplo 2: com game points como score principal, não há Baku."""
        from src.services.constants import AppError
        from src.services.pairing.acceleration import baku_team_accelerated_ids

        with self.assertRaisesRegex(AppError, "Baku"):
            baku_team_accelerated_ids(
                [1, 2, 3, 4], [1, 2, 3, 4], 5, 1, primary_score="game_points",
                win_points=2.0, draw_points=1.0, loss_points=0.0,
            )

    def test_pontuacao_de_match_fora_de_dois_para_um_recusa_baku(self) -> None:
        from src.services.constants import AppError
        from src.services.pairing.acceleration import baku_team_accelerated_ids

        with self.assertRaisesRegex(AppError, "dois empates"):
            baku_team_accelerated_ids(
                [1, 2, 3, 4], [1, 2, 3, 4], 5, 1, primary_score="match_points",
                win_points=3.0, draw_points=1.0, loss_points=0.0,
            )


class BakuDeEquipesServicoTest(_TorneioDeEquipes):
    def _torneio(self, **ajustes: str) -> tuple[int, list[int], dict[int, int]]:
        tid, team_ids = self._create_team_tournament(teams_count=8, boards_count=2)
        self.db.save_tournament_settings(tid, {"acceleration_method": "baku", **ajustes})
        numero = {team_id: index for index, team_id in enumerate(team_ids, start=1)}
        return tid, team_ids, numero

    def test_r1_pareia_dentro_do_ga_e_dentro_do_gb(self) -> None:
        """8 equipes: GA = TPN 1–4, GB = TPN 5–8. Sem Baku a R1 seria 1×5, 6×2, 3×7, 8×4."""
        tid, _ids, numero = self._torneio()
        rodada = self.service.generate_next_round(tid)
        self.assertEqual(
            [(1, 3), (4, 2), (5, 7), (8, 6)], self._confrontos(int(rodada["id"]), numero)
        )

    def test_vp_entra_no_score_de_pareamento_e_nunca_na_classificacao(self) -> None:
        """R1 (Baku): vencem 1, 4, 5 e 8. Na R2 (5 rodadas → VP 2 ainda) o score de
        pareamento de 1 e 4 é 4, sozinhos no topo: 1×4. Sem o VP, 1, 4, 5 e 8
        estariam juntos com 2 pontos."""
        tid, ids, numero = self._torneio()
        self._jogar_rodada(tid)
        classificacao = {int(i["team_id"]): float(i["match_points"]) for i in self.service._team_standings(tid)}
        self.assertEqual({2.0, 0.0}, set(classificacao.values()))
        self.assertEqual(2.0, classificacao[ids[0]])
        rodada = self.service.generate_next_round(tid)
        pares = {frozenset(par) for par in self._confrontos(int(rodada["id"]), numero)}
        self.assertIn(frozenset((1, 4)), pares)

    def test_game_points_como_score_principal_recusa_a_rodada(self) -> None:
        tid, _ids, _numero = self._torneio(team_standing_primary="game_points")
        with self.assertRaisesRegex(Exception, "Baku"):
            self.service.preview_next_round(tid)

    def test_aceleracao_classica_por_equipes_avisa_que_nao_se_aplica(self) -> None:
        tid, _ids, numero = self._torneio(acceleration_method="accelerated")
        previa = self.service.preview_next_round(tid)
        self.assertTrue(any("Baku" in aviso for aviso in previa["warnings"]))


class BakuDeEquipesNoTrf25Test(_TorneioDeEquipes):
    """O TRF25 de equipes declara o Baku que o motor aplicou (EQ-07, C.04.7).

    8 equipes, 5 rodadas: GA = TPN 1–4; aceleradas R1–R3, VP cheio (2 MP) nas
    R1–R2 e meio VP (1 MP) na R3 — o Exemplo 2 de 1.4.4, em match points.
    """

    def _exportar(self, aceleracao: str) -> list[str]:
        tid, _team_ids = self._create_team_tournament(teams_count=8, boards_count=2)
        self.db.save_tournament_settings(tid, {"acceleration_method": aceleracao})
        self._jogar_rodada(tid)
        destino = Path(self.temp_dir.name) / f"equipes_{aceleracao}.trf"
        from src.services.federation_exporters.trf25 import TRF25Exporter

        TRF25Exporter(self.export_service).export(tid, destino)
        return destino.read_text(encoding="utf-8").splitlines()

    @staticmethod
    def _blocos_250(linhas: list[str]) -> list[tuple[str, str, int, int, int, int]]:
        return [
            (
                linha[4:8].strip(), linha[9:13].strip(),
                int(linha[14:17]), int(linha[18:21]), int(linha[22:26]), int(linha[27:31]),
            )
            for linha in linhas
            if linha.startswith("250 ")
        ]

    def test_250_em_match_points_sobre_o_ga(self) -> None:
        linhas = self._exportar("baku")
        self.assertEqual(
            [("2.0", "", 1, 2, 1, 4), ("1.0", "", 3, 3, 1, 4)], self._blocos_250(linhas)
        )

    def test_192_leva_o_sufixo_baku(self) -> None:
        linhas = self._exportar("baku")
        codigo = next(linha[4:].strip() for linha in linhas if linha.startswith("192 "))
        self.assertEqual("FIDE_TEAM_TYPEA_MP_GP_BAKU", codigo)

    def test_sem_baku_nao_ha_250_nem_sufixo(self) -> None:
        linhas = self._exportar("none")
        self.assertEqual([], self._blocos_250(linhas))
        codigo = next(linha[4:].strip() for linha in linhas if linha.startswith("192 "))
        self.assertFalse(codigo.endswith("_BAKU"))
