"""Pendências de emparceiramento das fases 0–4 (RGS-13, RGS-16, RGS-10, RGS-18/19).

1. **Seeding único (RGS-13).** A lista inicial do relatório, a chamada inicial
   da tela e a divisão em grupos ordenavam por conta própria (rating e nome,
   sem título e, no relatório, sem ``initial_order``). Agora todas usam
   ``seeding_key``: com rating igual, o GM sai antes de "Alpha" sem título.
2. **Trocar cores pede motivo (RGS-16).** Inverter as cores de uma mesa é
   alteração manual do emparceiramento (C.04.2): motivo obrigatório e o mesmo
   evento ``pairing_manual_adjustment`` da troca de jogador.
3. **Entrante tardio fora do retrato antigo (RGS-10).** O TRF da rodada N
   (``render(up_to_round=N)``) — o que o desempate Gacrux lê — não tem quem só
   se inscreveu depois de N.
4. **Saída do Gacrux vazia ou inválida (RGS-18/19).** Vira recusa com a oferta
   do motor reserva, como a ``GacruxScoreMismatch``, e não um erro simples.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.services.constants import RESERVE_ENGINE_LABEL, AppError
from src.services.federation_exporters.trf16 import TRF16Exporter
from src.services.pairing import gacrux_engine
from src.services.pairing.gacrux_engine import GacruxEngine
from src.services.pairing.gacrux_tiebreak_engine import GacruxTiebreakEngine
from tests.support.core_service_base import CoreServiceTestCase


# ---------------------------------------------------------------------- #
# 1. Seeding único
# ---------------------------------------------------------------------- #
class SeedingUnicoTest(CoreServiceTestCase):
    """Rating igual, títulos diferentes: a mesma ordem em todo ponto de seeding."""

    def setUp(self) -> None:
        super().setUp()
        self.db.save_tournament_settings(self.tournament_id, {"pairing_method": "swiss"})
        self.alpha = self.db.create_player(self.tournament_id, "Alpha", rating=2000)
        self.zeta = self.db.create_player(self.tournament_id, "Zeta", rating=2000, title="GM")
        self.gama = self.db.create_player(self.tournament_id, "Gama", rating=2000, title="FM")
        self.esperado = [self.zeta, self.gama, self.alpha]

    def _ordem_do_trf(self) -> list[int]:
        with tempfile.TemporaryDirectory() as tmp:
            rank = GacruxEngine(self.db).write_pairing_trf(self.tournament_id, 1, Path(tmp) / "r1.trf")
        return [rank[numero] for numero in sorted(rank)]

    def _ordem_do_relatorio(self) -> list[int]:
        _titulo, _colunas, linhas = self.export_service._initial_player_list_section(self.tournament_id)
        por_nome = {"Alpha": self.alpha, "Zeta": self.zeta, "Gama": self.gama}
        return [por_nome[linha[1]] for linha in linhas]

    def _ordem_da_chamada_inicial(self) -> list[int]:
        jogadores = self.db.list_players(self.tournament_id, active_only=False)
        return [int(p["id"]) for p in self.export_service.initial_ranked_players(self.tournament_id, jogadores)]

    def _ordem_dos_grupos(self) -> list[str]:
        filhos = self.tournament_service.split_tournament(self.tournament_id, 3)
        return [self.db.list_players(filho, active_only=False)[0]["name"] for filho in filhos]

    def test_todos_os_pontos_de_seeding_dao_a_mesma_ordem(self) -> None:
        self.assertEqual(self.esperado, self._ordem_do_trf())
        self.assertEqual(self.esperado, self._ordem_do_relatorio())
        self.assertEqual(self.esperado, self._ordem_da_chamada_inicial())
        self.assertEqual(["Zeta", "Gama", "Alpha"], self._ordem_dos_grupos())

    def test_relatorio_segue_a_ordem_inicial_do_torneio(self) -> None:
        """``initial_order=national_rating``: o relatório numera como o TRF."""
        self.db.save_tournament_settings(
            self.tournament_id, {"pairing_method": "swiss", "initial_order": "national_rating"}
        )
        nacional = self.db.create_player(self.tournament_id, "Nacional", rating=1000, national_rating=2500)
        self.assertEqual(nacional, self._ordem_do_trf()[0])
        self.assertEqual(self._ordem_do_trf(), self._ordem_da_chamada_inicial())


# ---------------------------------------------------------------------- #
# 2. Trocar cores pede motivo e audita como ajuste manual
# ---------------------------------------------------------------------- #
class TrocaDeCoresComMotivoTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._create_players(4)
        self.round_id = int(self.service.generate_next_round(self.tournament_id)["id"])
        self.pairing = self.db.get_pairings_for_round(self.round_id)[0]

    def _trocar(self, motivo: str) -> None:
        self.service.swap_pairing_colors(
            self.tournament_id, self.round_id, int(self.pairing["id"]), reason=motivo
        )

    def test_sem_motivo_e_recusada_e_nada_muda(self) -> None:
        with self.assertRaises(AppError) as erro:
            self._trocar("   ")
        self.assertIn("motivo", str(erro.exception))
        depois = self.db.get_pairing(int(self.pairing["id"]))
        self.assertEqual(self.pairing["white_player_id"], depois["white_player_id"])

    def test_com_motivo_grava_o_ajuste_manual(self) -> None:
        branca = int(self.pairing["white_player_id"])
        preta = int(self.pairing["black_player_id"])
        self._trocar("Cores trocadas por erro de digitação")

        depois = self.db.get_pairing(int(self.pairing["id"]))
        self.assertEqual((preta, branca), (int(depois["white_player_id"]), int(depois["black_player_id"])))
        (evento,) = self.db.list_audit_events(
            self.tournament_id, action="pairing_manual_adjustment", limit=5
        )
        self.assertEqual("Cores trocadas por erro de digitação", evento["reason"])
        depois_json = json.loads(evento["after_json"])
        self.assertIn([preta, branca], depois_json["pairs"])
        self.assertEqual("colors_swapped", depois_json["change"]["kind"])
        self.assertIn([branca, preta], json.loads(evento["before_json"])["pairs"])


class TrocaDeCoresNaTelaTest(unittest.TestCase):
    """A tela pede o motivo no diálogo de motivo e o repassa ao serviço."""

    def _host(self):
        host = mock.Mock()
        host.pairing_team_mode = False
        host.current_tournament_id = 7
        host.current_round_id = 3
        host._selected_pairing_id.return_value = 11
        return host

    def test_motivo_digitado_vai_ao_servico(self) -> None:
        from src.ui.screens.pairing_results.swaps import BoardSwapActions

        host = self._host()
        with mock.patch(
            "src.ui.screens.pairing_results.swaps.reason_dialog",
            return_value="Pedido do árbitro", create=True,
        ) as dialogo:
            BoardSwapActions(host).swap_colors()
        dialogo.assert_called_once()
        host.pairing_service.swap_pairing_colors.assert_called_once_with(
            7, 3, 11, reason="Pedido do árbitro"
        )
        host._show_error.assert_not_called()

    def test_cancelar_o_dialogo_nao_troca(self) -> None:
        from src.ui.screens.pairing_results.swaps import BoardSwapActions

        host = self._host()
        with mock.patch(
            "src.ui.screens.pairing_results.swaps.reason_dialog", return_value=None, create=True
        ):
            BoardSwapActions(host).swap_colors()
        host.pairing_service.swap_pairing_colors.assert_not_called()


# ---------------------------------------------------------------------- #
# 3. Entrante tardio fora do retrato antigo
# ---------------------------------------------------------------------- #
class EntranteTardioNoRetratoTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._create_players(4)
        self._jogar_rodada()
        self.tardio = self.db.create_player(self.tournament_id, "Tardio", rating=2500)
        self._jogar_rodada()

    def _jogar_rodada(self) -> None:
        rodada = self.service.generate_next_round(self.tournament_id)
        for mesa in self.db.get_pairings_for_round(int(rodada["id"])):
            if not mesa.get("is_bye"):
                self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(rodada["id"]))

    @staticmethod
    def _linhas_001(trf: str) -> list[str]:
        return [linha for linha in trf.splitlines() if linha.startswith("001")]

    def test_retrato_da_rodada_1_nao_tem_o_entrante_da_rodada_2(self) -> None:
        self.assertEqual(2, int(self.db.get_player(self.tardio)["entry_round"]))
        exportador = TRF16Exporter(self.export_service)
        retrato = exportador.render(self.tournament_id, up_to_round=1)
        self.assertEqual(4, len(self._linhas_001(retrato)))
        self.assertNotIn("Tardio", retrato)
        self.assertIn("062 4", retrato)
        # O arquivo de hoje continua com ele.
        self.assertIn("Tardio", exportador.render(self.tournament_id))

    def test_desempate_gacrux_da_rodada_1_numera_sem_ele(self) -> None:
        job = GacruxTiebreakEngine(self.db).prepare(self.tournament_id, ["buchholz"], current_round=1)
        ids = [player_id for _cid, player_id in job.cid_to_id]
        self.assertNotIn(self.tardio, ids)
        self.assertEqual(4, len(self._linhas_001(job.trf.decode("utf-8"))))


# ---------------------------------------------------------------------- #
# 4. Saída vazia ou inválida do Gacrux oferece o motor reserva
# ---------------------------------------------------------------------- #
def _gacrux_falso(dados: dict | None):
    """``subprocess.run`` falso: grava ``dados`` como saída (``None``: não grava)."""

    def run(cmd, **_kwargs):
        if dados is not None:
            Path(cmd[cmd.index("-o") + 1]).write_text(json.dumps(dados), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return run


SAIDA_VAZIA = {"status": {"code": 0}, "pairingResult": {"pairs": []}}


class SaidaDoGacruxRecusadaTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.db.save_tournament_settings(
            self.tournament_id, {"pairing_system": "gacrux_swiss", "pairing_method": "swiss"}
        )
        self._create_players(4)

    def _parear(self, dados: dict | None, **kwargs):
        with mock.patch(
            "src.services.pairing.gacrux_engine.subprocess.run", side_effect=_gacrux_falso(dados)
        ):
            return self.service.generate_next_round(self.tournament_id, **kwargs)

    def test_saida_vazia_e_recusa_com_oferta_do_motor_reserva(self) -> None:
        with self.assertRaises(gacrux_engine.GacruxRefusal) as ctx:
            self._parear(SAIDA_VAZIA)
        self.assertEqual(1, ctx.exception.round_number)
        self.assertIn(RESERVE_ENGINE_LABEL, str(ctx.exception))
        self.assertEqual([], self.db.list_rounds(self.tournament_id))

    def test_saida_ausente_ou_ilegivel_tambem_e_recusa(self) -> None:
        with self.assertRaises(gacrux_engine.GacruxRefusal):
            self._parear(None)
        with self.assertRaises(gacrux_engine.GacruxRefusal):
            self._parear({"status": {"code": 0}, "pairingResult": {"pairs": [[1, 2], [2, 3]]}})

    def test_confirmada_a_rodada_sai_pelo_motor_reserva_com_auditoria(self) -> None:
        rodada = self._parear(SAIDA_VAZIA, reserve_engine=True)
        self.assertEqual(2, len(self.db.get_pairings_for_round(int(rodada["id"]))))
        (fallback,) = self.db.list_audit_events(
            self.tournament_id, action="pairing_engine_fallback", limit=5
        )
        self.assertIn("saída", fallback["reason"])
        self.assertEqual(
            1, len(self.db.list_audit_events(self.tournament_id, action="pairing_reserve_engine", limit=5))
        )


class OfertaNaTelaTest(unittest.TestCase):
    def test_saida_recusada_abre_a_mesma_oferta(self) -> None:
        from src.ui.screens.pairing_results.view import PairingResultsMixin

        chamadas = []

        class Tela(PairingResultsMixin):
            def _start_round_generation(self, tournament_id, *, reserve_engine):
                chamadas.append((tournament_id, reserve_engine))

        recusa = gacrux_engine.GacruxOutputRejected(2, ["jogador(es) faltando: SNo 3"])
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=True) as dialogo:
            self.assertTrue(Tela()._offer_reserve_engine(7, recusa))
        self.assertEqual([(7, True)], chamadas)
        self.assertIn("Parear com o motor reserva", dialogo.call_args.kwargs["confirm_text"])


if __name__ == "__main__":
    unittest.main()
