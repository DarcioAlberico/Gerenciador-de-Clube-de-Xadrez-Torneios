"""RGS-03: o Gacrux pareia com o placar da classificação, ou recusa antes de rodar.

O TRF do motor escrevia o PAB como ``U`` (1 ponto) e não levava ajustes
manuais; o Gacrux soma as células e deduzia o sistema de pontos delas.
Reproduzido em 2026-11-26: bye de 0,5 → ``KeyError: 'D'`` na R2; bye de 0 → R3
quebra (e a R2 sai com o jogador do PAB num grupo de 1 ponto que a
classificação não mostra).

Fase 0 (contenção): a rodada era recusada com ``GacruxScoreMismatch``.
Fase 3 (definitivo, F3.1): o arquivo do pareamento leva o registro 162 (PAB =
``bye_points``) e um 299 por ajuste; a matriz inteira sai pelo Gacrux, e o
placar que o próprio Gacrux lê do arquivo é o da classificação. A recusa fica
para o que o arquivo não consegue dizer ao motor (ex.: bye de 0,25), e continua
oferecendo o motor reserva, com auditoria.

Roda o Gacrux de verdade (subprocesso): ``pytest -m gacrux``.
"""
from __future__ import annotations

import itertools
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from src.core.database import Database
from src.services.pairing.gacrux_engine import GacruxEngine, GacruxScoreMismatch
from src.services.pairing_service import PairingService
from tests.support.gacrux_scores import gacrux_pairing_scores

pytestmark = pytest.mark.gacrux

ROUNDS = 4
# Ímpar (sempre há PAB). Com 5, alguns resultados deixam a R4 sem nenhum
# pareamento legal pelo C.04.1 (o Gacrux devolve `pairs: []`, RGS-19).
PLAYERS = 7
BYE_POINTS = (0.0, 0.5, 1.0)
SCENARIOS = ("sem_ajuste", "ajuste_mais", "ajuste_menos", "entrada_tardia")
# Valor de PAB que o motor não representa: o Gacrux traduz o `P` do 162 para
# W/D/L/Z, e 0,25 não é nenhum deles.
BYE_SEM_REPRESENTACAO = 0.25


class Torneio:
    def __init__(self, tmp: str, bye_points: float, late_entry_points: float = 0.0) -> None:
        self.db = Database(db_path=str(Path(tmp) / "t.db"), backup_dir=Path(tmp) / "bk")
        self.db.initialize()
        self.service = PairingService(self.db)
        self.tid = self.db.create_tournament("RGS-03", rounds_count=ROUNDS, bye_points=bye_points)
        self.db.save_tournament_settings(
            self.tid,
            {"pairing_system": "gacrux_swiss", "pairing_method": "swiss",
             "late_entry_points": late_entry_points},
        )
        self.ids = [
            self.db.create_player(self.tid, f"J{i}", rating=2000 - 50 * i, sex="m",
                                  birth_date="2000-01-01")
            for i in range(PLAYERS)
        ]

    def jogar(self, reserve_engine: bool = False) -> dict:
        rodada = self.service.generate_next_round(self.tid, reserve_engine=reserve_engine)
        for mesa in self.db.get_pairings_for_round(rodada["id"]):
            if not mesa.get("is_bye"):
                self.service.update_result(self.tid, mesa["id"], "1-0")
        self.service.close_round(self.tid, rodada["id"])
        return rodada

    def fallbacks(self) -> list[dict]:
        return self.db.list_audit_events(self.tid, action="pairing_engine_fallback", limit=50)

    def placar_do_gacrux(self, numero: int) -> dict[int, float]:
        """``{player_id: pontos}`` com que o Gacrux parearia a rodada ``numero``."""
        with tempfile.TemporaryDirectory() as tmp:
            trf = Path(tmp) / "pareamento.trf"
            rank_para_jogador = GacruxEngine(self.db).write_pairing_trf(self.tid, numero, trf)
            pontos = gacrux_pairing_scores(trf, closed_rounds=numero - 1)
        return {rank_para_jogador[rank]: valor for rank, valor in pontos.items()}

    def placar_da_classificacao(self) -> dict[int, float]:
        return {
            int(item["player_id"]): float(item["points"])
            for item in self.service.standings(self.tid)
        }


def _preparar(torneio: Torneio, cenario: str, numero: int) -> None:
    """Aplica o cenario antes da rodada ``numero``."""
    if numero != 2:
        return
    if cenario in ("ajuste_mais", "ajuste_menos"):
        torneio.db.add_point_adjustment(
            torneio.tid, round_number=1, player_id=torneio.ids[2],
            game_points=0.5 if cenario == "ajuste_mais" else -0.5, reason="teste RGS-03",
        )
    elif cenario == "entrada_tardia":
        torneio.ids.append(torneio.db.create_player(torneio.tid, "Tardio", rating=1990, sex="m"))


class MatrizPeloGacruxTest(unittest.TestCase):
    def test_toda_a_matriz_sai_pelo_gacrux_com_o_placar_da_classificacao(self) -> None:
        original = GacruxEngine.pair_round
        for bye, cenario in itertools.product(BYE_POINTS, SCENARIOS):
            with self.subTest(bye_points=bye, cenario=cenario), tempfile.TemporaryDirectory() as tmp:
                late = 0.5 if cenario == "entrada_tardia" else 0.0
                torneio = Torneio(tmp, bye, late_entry_points=late)
                pelo_gacrux: list[int] = []

                def espiao(motor, tournament_id, to_pair, round_number, **kwargs):
                    pareamentos = original(motor, tournament_id, to_pair, round_number, **kwargs)
                    pelo_gacrux.append(int(round_number))
                    return pareamentos

                with mock.patch.object(GacruxEngine, "pair_round", autospec=True, side_effect=espiao):
                    for numero in range(1, ROUNDS + 1):
                        _preparar(torneio, cenario, numero)
                        if numero > 1:
                            self.assertEqual(
                                torneio.placar_da_classificacao(),
                                torneio.placar_do_gacrux(numero),
                                f"rodada {numero}",
                            )
                        torneio.jogar()  # GacruxScoreMismatch aqui = regressão
                self.assertEqual(list(range(1, ROUNDS + 1)), pelo_gacrux)
                self.assertEqual(ROUNDS, len(torneio.db.list_rounds(torneio.tid)))
                self.assertEqual([], torneio.fallbacks())


class RecusaDoQueNaoTemRepresentacaoTest(unittest.TestCase):
    """O caminho de recusa continua, para o que o arquivo não diz ao motor."""

    def test_bye_sem_representacao_e_recusado_na_rodada_2_sem_gravar_nada(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            torneio = Torneio(tmp, BYE_SEM_REPRESENTACAO)
            torneio.jogar()
            with self.assertRaises(GacruxScoreMismatch) as ctx:
                torneio.jogar()
            recusa = ctx.exception
            self.assertEqual(2, recusa.round_number)
            self.assertIn("Gacrux", str(recusa))
            self.assertIn("motor reserva", str(recusa))
            self.assertNotIn("Traceback", str(recusa))
            self.assertTrue(any("0.25" in item for item in recusa.details))
            self.assertEqual(1, len(torneio.db.list_rounds(torneio.tid)))
            self.assertEqual([], torneio.fallbacks())

    def test_previa_tambem_recusa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            torneio = Torneio(tmp, BYE_SEM_REPRESENTACAO)
            torneio.jogar()
            with self.assertRaises(GacruxScoreMismatch):
                torneio.service.preview_next_round(torneio.tid)

    def test_motor_reserva_fica_na_auditoria_depois_da_rodada(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            torneio = Torneio(tmp, BYE_SEM_REPRESENTACAO)
            torneio.jogar()
            rodada = torneio.jogar(reserve_engine=True)
            (evento,) = torneio.fallbacks()
            self.assertEqual(int(rodada["id"]), int(evento["round_id"]))


class OfertaMotorReservaTest(unittest.TestCase):
    """A tela transforma a recusa em pergunta; outro erro segue o caminho normal."""

    def _tela(self):
        from src.ui.screens.pairing_results.view import PairingResultsMixin

        chamadas = []

        class Tela(PairingResultsMixin):
            def _start_round_generation(self, tournament_id, *, reserve_engine):
                chamadas.append((tournament_id, reserve_engine))

        return Tela(), chamadas

    def test_confirmar_gera_pelo_motor_reserva(self) -> None:
        from unittest import mock

        tela, chamadas = self._tela()
        recusa = GacruxScoreMismatch(2, ["J4: 1 no motor, 0,5 na classificacao"])
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=True) as dialogo:
            self.assertTrue(tela._offer_reserve_engine(7, recusa))
        self.assertEqual([(7, True)], chamadas)
        self.assertIn("J4", dialogo.call_args.args[2])

    def test_cancelar_nao_gera_nada(self) -> None:
        from unittest import mock

        tela, chamadas = self._tela()
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=False):
            self.assertTrue(tela._offer_reserve_engine(7, GacruxScoreMismatch(2, ["x"])))
        self.assertEqual([], chamadas)

    def test_outro_erro_nao_e_tratado_aqui(self) -> None:
        tela, chamadas = self._tela()
        self.assertFalse(tela._offer_reserve_engine(7, RuntimeError("outro")))
        self.assertEqual([], chamadas)


if __name__ == "__main__":
    unittest.main()
