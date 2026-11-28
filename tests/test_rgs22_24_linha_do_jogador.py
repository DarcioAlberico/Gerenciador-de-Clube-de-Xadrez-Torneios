"""RGS-22/23/24 — a ação mora na linha do jogador (camada de serviço).

- RGS-22: "Faltar só à rodada N" é um bye Z solicitado (o status não muda);
  retirar e reintegrar passam pelo serviço de participação; o
  ``db.update_player`` deixa de mudar status.
- RGS-23: o saldo da política de bye numa linha, e o W.O. oferecido quando a
  rodada já foi gerada.
- RGS-24: entrada tardia com as rodadas anteriores como células derivadas —
  nada gravado em rodada fechada, limite de bye intocado.

A parte de tela (menus, diálogos, contagem de ações) está em
``test_ui_rgs22_24_linha_do_jogador.py``.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from src.services.constants import AppError
from src.services.pairing.bye_policy import ByePolicy
from src.services.pairing.participation import (
    PARTICIPATION_STATUSES,
    STATUS_ACTIVE,
    STATUS_WITHDRAWN,
    status_description,
)
from src.services.pairing.player_round import (
    bye_balance,
    late_entry_plan,
    walkover_result,
)
from tests.support.core_service_base import CoreServiceTestCase

# --------------------------------------------------------------------------- #
# Parte pura
# --------------------------------------------------------------------------- #


class SaldoDeByeTest(unittest.TestCase):
    def test_limite_e_ultima_rodada(self) -> None:
        politica = ByePolicy(max_requested_byes=2, last_requested_bye_round=5)
        usados = [{"bye_type": "H", "round_number": 2}, {"bye_type": "Z", "round_number": 3}]
        self.assertEqual(
            "1 de 2 byes usados; último permitido na R5", bye_balance(politica, usados)
        )

    def test_sem_limite_diz_que_nao_ha(self) -> None:
        self.assertEqual("Sem limite de byes; nenhum usado", bye_balance(ByePolicy(), []))

    def test_so_ultima_rodada(self) -> None:
        politica = ByePolicy(last_requested_bye_round=4)
        self.assertEqual(
            "1 bye usado; último permitido na R4",
            bye_balance(politica, [{"bye_type": "H", "round_number": 1}]),
        )


class WalkoverTest(unittest.TestCase):
    def test_quem_falta_perde_por_wo_na_cor_certa(self) -> None:
        mesa = {"white_player_id": 7, "black_player_id": 9}
        self.assertEqual("0F-1F", walkover_result(mesa, 7))
        self.assertEqual("1F-0F", walkover_result(mesa, 9))


class PlanoDeEntradaTardiaTest(unittest.TestCase):
    def test_depois_da_r3_entra_na_r4_com_tres_rodadas_derivadas(self) -> None:
        plano = late_entry_plan(latest_round_number=3, rounds_count=7, per_round_points=0.5)
        self.assertEqual(4, plano.entry_round)
        self.assertEqual([1, 2, 3], plano.missed_rounds)
        self.assertEqual(1.5, plano.starting_points)
        self.assertEqual("", plano.error)

    def test_rodada_ja_gerada_empurra_para_a_seguinte(self) -> None:
        """Se a rodada N já foi gerada, o jogador entra na N+1."""
        plano = late_entry_plan(latest_round_number=4, rounds_count=7, per_round_points=0.0)
        self.assertEqual(5, plano.entry_round)

    def test_valor_sem_celula_no_trf_e_recusado(self) -> None:
        """0,25 por rodada não tem letra no TRF (Z/H/F): o Gacrux recusaria."""
        plano = late_entry_plan(latest_round_number=2, rounds_count=7, per_round_points=0.25)
        self.assertIn("0, ½ ou 1", plano.error)

    def test_torneio_sem_rodada_restante(self) -> None:
        plano = late_entry_plan(latest_round_number=5, rounds_count=5, per_round_points=0.5)
        self.assertIn("todas as rodadas", plano.error)


class DescricaoDosStatusTest(unittest.TestCase):
    def test_rotulos_com_acento_e_descricao(self) -> None:
        self.assertEqual("Não emparceirado", PARTICIPATION_STATUSES["inactive"])
        for status in ("withdrawn", "absent", "inactive"):
            self.assertTrue(status_description(status), status)
        # Ausente NÃO é desistência e não perde prêmio (RGS-35).
        self.assertIn("prêmio", status_description("absent"))


# --------------------------------------------------------------------------- #
# Serviço
# --------------------------------------------------------------------------- #


def _jogar(test: CoreServiceTestCase, rodada: dict) -> None:
    for mesa in test.db.get_pairings_for_round(int(rodada["id"])):
        if not mesa["is_bye"]:
            test.service.update_result(test.tournament_id, int(mesa["id"]), "1-0")
    test.service.close_round(test.tournament_id, int(rodada["id"]))


def _pareados(test: CoreServiceTestCase, rodada: dict) -> set[int]:
    ids: set[int] = set()
    for mesa in test.db.get_pairings_for_round(int(rodada["id"])):
        if mesa["is_bye"]:
            continue
        ids.add(int(mesa["white_player_id"]))
        ids.add(int(mesa["black_player_id"]))
    return ids


class FaltarSoUmaRodadaTest(CoreServiceTestCase):
    """Aceite RGS-22: "Faltar só à R4" → bye Z na R4, status inalterado, pareado na R5."""

    def setUp(self) -> None:
        super().setUp()
        # 8, não 6: com 6, depois da R4 não sobra pareamento da R5 sem repetir
        # confronto. O motor antigo repetia; desde o RG2-07b ele recusa.
        self.ids = self._create_players(8)

    def test_bye_z_na_r4_e_pareado_na_r5(self) -> None:
        for _ in range(3):
            _jogar(self, self.service.generate_next_round(self.tournament_id))
        alvo = self.ids[2]

        self.service.miss_round(self.tournament_id, alvo, 4, "consulta médica")

        self.assertEqual(STATUS_ACTIVE, self.db.get_player(alvo)["player_status"])
        (bye,) = self.db.list_requested_byes(self.tournament_id)
        self.assertEqual(("Z", 4, alvo), (bye["bye_type"], bye["round_number"], bye["player_id"]))
        r4 = self.service.generate_next_round(self.tournament_id)
        self.assertNotIn(alvo, _pareados(self, r4))
        _jogar(self, r4)
        r5 = self.service.generate_next_round(self.tournament_id)
        self.assertIn(alvo, _pareados(self, r5))
        self.assertEqual([], self.service.participation_history(self.tournament_id, alvo))

    def test_faltar_nao_consome_o_limite(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"max_requested_byes": 1})
        self.service.miss_round(self.tournament_id, self.ids[0], 1, "viagem")
        self.service.request_bye(self.tournament_id, self.ids[0], 2, "H", "pedido")
        self.assertIn("1 de 1", self.service.bye_balance(self.tournament_id, self.ids[0]))

    def test_rodada_gerada_aponta_a_mesa_para_o_wo(self) -> None:
        rodada = self.service.generate_next_round(self.tournament_id)
        alvo = self.ids[0]

        situacao = self.service.player_round_situation(self.tournament_id, alvo, 1)

        self.assertEqual("generated", situacao["round_status"])
        self.assertTrue(situacao["board_number"])
        self.assertFalse(situacao["has_result"])
        with self.assertRaisesRegex(AppError, "já foi gerada"):
            self.service.miss_round(self.tournament_id, alvo, 1, "viagem")

        feito = self.service.forfeit_absent_player(self.tournament_id, alvo, 1, "não compareceu")

        mesa = next(
            m for m in self.db.get_pairings_for_round(int(rodada["id"]))
            if alvo in (m["white_player_id"], m["black_player_id"])
        )
        self.assertEqual(feito["result"], mesa["result"])
        self.assertIn(mesa["result"], ("0F-1F", "1F-0F"))
        self.assertEqual(STATUS_ACTIVE, self.db.get_player(alvo)["player_status"])

    def test_wo_recusado_em_mesa_com_resultado(self) -> None:
        rodada = self.service.generate_next_round(self.tournament_id)
        mesa = next(m for m in self.db.get_pairings_for_round(int(rodada["id"])) if not m["is_bye"])
        self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        with self.assertRaisesRegex(AppError, "já tem resultado"):
            self.service.forfeit_absent_player(
                self.tournament_id, int(mesa["white_player_id"]), 1, "x"
            )


class SaldoNoServicoTest(CoreServiceTestCase):
    def test_saldo_com_politica(self) -> None:
        (jogador,) = self._create_players(1)
        self.db.save_tournament_settings(
            self.tournament_id, {"max_requested_byes": 2, "last_requested_bye_round": 5}
        )
        self.service.request_bye(self.tournament_id, jogador, 2, "H", "")
        self.assertEqual(
            "1 de 2 byes usados; último permitido na R5",
            self.service.bye_balance(self.tournament_id, jogador),
        )


class DesistenciaComMotivoTest(CoreServiceTestCase):
    """Glossário: "Retirada (desistência) — saída definitiva … com motivo"."""

    def test_desistencia_sem_motivo_e_recusada(self) -> None:
        (pid,) = self._create_players(1)
        with self.assertRaisesRegex(AppError, "descreva o motivo"):
            self.service.set_player_participation(self.tournament_id, pid, STATUS_WITHDRAWN, "  ")
        self.assertEqual(STATUS_ACTIVE, self.db.get_player(pid)["player_status"])

    def test_ausencia_continua_sem_exigir_motivo(self) -> None:
        (pid,) = self._create_players(1)
        self.service.set_player_participation(self.tournament_id, pid, "absent")
        self.assertEqual("absent", self.db.get_player(pid)["player_status"])


class StatusSoPeloServicoTest(CoreServiceTestCase):
    """Aceite RGS-22: ``db.update_player(..., status=...)`` → ``TypeError``."""

    def _base(self, pid: int) -> dict:
        return {"name": "Ana", "club": "C", "rating": 1500, "category": "Absoluto"}

    def test_update_player_nao_aceita_status(self) -> None:
        (pid,) = self._create_players(1)
        for chave, valor in (("status", "withdrawn"), ("player_status", "withdrawn"), ("active", 0)):
            with self.subTest(chave=chave), self.assertRaises(TypeError):
                self.db.update_player(pid, **self._base(pid), **{chave: valor})

    def test_update_player_preserva_o_status(self) -> None:
        (pid,) = self._create_players(1)
        self.service.set_player_participation(self.tournament_id, pid, STATUS_WITHDRAWN, "viagem")
        self.db.update_player(pid, **self._base(pid))
        jogador = self.db.get_player(pid)
        self.assertEqual(STATUS_WITHDRAWN, jogador["player_status"])
        self.assertEqual(0, int(jogador["active"]))
        self.assertEqual("Ana", jogador["name"])


class EntradaTardiaTest(CoreServiceTestCase):
    """Aceite RGS-24: após a R3 fechada → a R4 o inclui, pontos configurados, nada em R1-R3."""

    def setUp(self) -> None:
        super().setUp()
        self.ids = self._create_players(5)
        self.db.save_tournament_settings(self.tournament_id, {"late_entry_points": 0.5})

    def test_inscrever_apos_r3(self) -> None:
        for _ in range(3):
            _jogar(self, self.service.generate_next_round(self.tournament_id))
        with self.db.connect() as conexao:
            antes = conexao.execute(
                "SELECT COUNT(*) FROM pairings p JOIN rounds r ON r.id = p.round_id "
                "WHERE r.tournament_id = ? AND r.number <= 3",
                (self.tournament_id,),
            ).fetchone()[0]

        feito = self.service.register_late_entry(
            self.tournament_id, {"name": "Tardio", "rating": 1990}
        )

        self.assertEqual(4, feito["entry_round"])
        self.assertEqual(1.5, feito["starting_points"])
        jogador = self.db.get_player(feito["player_id"])
        self.assertEqual(4, int(jogador["entry_round"]))
        r4 = self.service.generate_next_round(self.tournament_id)
        self.assertIn(feito["player_id"], {
            int(m["white_player_id"]) for m in self.db.get_pairings_for_round(int(r4["id"]))
        } | {
            int(m["black_player_id"] or 0) for m in self.db.get_pairings_for_round(int(r4["id"]))
        })
        with self.db.connect() as conexao:
            depois = conexao.execute(
                "SELECT COUNT(*) FROM pairings p JOIN rounds r ON r.id = p.round_id "
                "WHERE r.tournament_id = ? AND r.number <= 3",
                (self.tournament_id,),
            ).fetchone()[0]
        self.assertEqual(antes, depois)
        self.assertEqual([], self.db.list_requested_byes(self.tournament_id))
        pontos = {int(i["player_id"]): float(i["points"]) for i in self.service.standings(self.tournament_id)}
        self.assertEqual(1.5, pontos[feito["player_id"]])
        acoes = {e["action"] for e in self.db.list_audit_events(self.tournament_id, limit=50)}
        self.assertIn("late_entry_registered", acoes)

    def test_rodada_gerada_entra_na_seguinte_com_os_pontos_das_rodadas_perdidas(self) -> None:
        _jogar(self, self.service.generate_next_round(self.tournament_id))
        self.service.generate_next_round(self.tournament_id)  # R2 gerada, aberta

        plano = self.service.late_entry_plan(self.tournament_id)
        feito = self.service.register_late_entry(
            self.tournament_id, {"name": "Tardio"}, per_round_points=0.5
        )

        self.assertEqual(3, plano.entry_round)
        self.assertEqual(3, feito["entry_round"])
        self.assertEqual(1.0, feito["starting_points"])

    def test_inscricao_comum_conta_as_mesmas_rodadas_que_o_assistente(self) -> None:
        """Adicionar pela tela de Jogadores e pelo assistente dá o mesmo placar.

        Com a R2 gerada e aberta, o jogador entra na R3: perdeu R1 e R2. O
        cálculo padrão contava só as FECHADAS (0,5), enquanto as células
        derivadas do TRF são duas — o assistente diria 1,0.
        """
        _jogar(self, self.service.generate_next_round(self.tournament_id))
        self.service.generate_next_round(self.tournament_id)

        pid = self.db.create_player(self.tournament_id, name="Comum")

        self.assertEqual(3, int(self.db.get_player(pid)["entry_round"]))
        self.assertEqual(
            self.service.late_entry_plan(self.tournament_id).starting_points,
            float(self.db.get_player(pid)["starting_points"]),
        )

    def test_valor_sem_representacao_e_recusado_sem_gravar(self) -> None:
        _jogar(self, self.service.generate_next_round(self.tournament_id))
        antes = len(self.db.list_players(self.tournament_id, active_only=False))
        with self.assertRaisesRegex(AppError, "0, ½ ou 1"):
            self.service.register_late_entry(
                self.tournament_id, {"name": "Tardio"}, per_round_points=0.25
            )
        self.assertEqual(antes, len(self.db.list_players(self.tournament_id, active_only=False)))

    def test_nome_obrigatorio(self) -> None:
        with self.assertRaisesRegex(AppError, "nome"):
            self.service.register_late_entry(self.tournament_id, {"name": "  "})


@pytest.mark.gacrux
class EntradaTardiaPeloGacruxTest(unittest.TestCase):
    """Aceite RGS-24 (marcador gacrux): com 0,5 de entrada, a R4 sai pelo Gacrux.

    Depende do RGS-03 definitivo: as rodadas 1–3 do entrante viram células
    ``H`` no TRF do pareamento (`reconcile_scores`) e o 162 declara o PAB; sem
    isso o Gacrux recusaria o arquivo e a rodada cairia no motor reserva.
    """

    def test_r4_com_entrante_de_meio_ponto_sai_pelo_gacrux(self) -> None:
        from src.core.database import Database
        from src.services.pairing.gacrux_engine import GacruxEngine
        from src.services.pairing_service import PairingService

        with tempfile.TemporaryDirectory() as tmp:
            db = Database(db_path=str(Path(tmp) / "t.db"), backup_dir=Path(tmp) / "bk")
            db.initialize()
            service = PairingService(db)
            tid = db.create_tournament("RGS-24", rounds_count=5, bye_points=1.0)
            db.save_tournament_settings(
                tid,
                {"pairing_system": "gacrux_swiss", "pairing_method": "swiss", "late_entry_points": 0.5},
            )
            for i in range(7):
                db.create_player(tid, f"J{i}", rating=2000 - 50 * i, sex="m", birth_date="2000-01-01")
            pelo_gacrux: list[int] = []
            original = GacruxEngine.pair_round

            def espiao(motor, tournament_id, to_pair, round_number, **kwargs):
                pareamentos = original(motor, tournament_id, to_pair, round_number, **kwargs)
                pelo_gacrux.append(int(round_number))
                return pareamentos

            with mock.patch.object(GacruxEngine, "pair_round", autospec=True, side_effect=espiao):
                for _ in range(3):
                    rodada = service.generate_next_round(tid)
                    for mesa in db.get_pairings_for_round(int(rodada["id"])):
                        if not mesa["is_bye"]:
                            service.update_result(tid, int(mesa["id"]), "1-0")
                    service.close_round(tid, int(rodada["id"]))
                feito = service.register_late_entry(
                    tid, {"name": "Tardio", "rating": 1990}, per_round_points=0.5
                )
                r4 = service.generate_next_round(tid)

            self.assertEqual([1, 2, 3, 4], pelo_gacrux)
            self.assertEqual([], db.list_audit_events(tid, action="pairing_engine_fallback", limit=10))
            mesas = db.get_pairings_for_round(int(r4["id"]))
            self.assertIn(
                feito["player_id"],
                {int(m["white_player_id"]) for m in mesas} | {int(m["black_player_id"] or 0) for m in mesas},
            )
            self.assertEqual(1.5, feito["starting_points"])


if __name__ == "__main__":
    unittest.main()
