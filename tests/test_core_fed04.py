"""FED-04 — round-trip TRF fiel.

A importação tratava `U` (bye alocado pelo pareamento) e `F` (bye de ponto
inteiro) como a mesma coisa: um TRF do Swiss-Manager com `U` inflava a pontuação
em todo torneio cujo `bye_points` não fosse 1,0, porque o `F` vale ponto cheio
por definição e o `U` vale o que o regulamento disser. O `Z` (ausência conhecida,
zero ponto) era simplesmente descartado — a rodada sumia do histórico e o TRF
exportado depois já não trazia de volta o que o arquivo original dizia.

Árbitro, calendário de rodadas e seção de equipes eram lidos e jogados fora: o
torneio importado nascia sem nada disso.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.services.trf_import import BYE_RESULTS, build_trf_rounds
from tests.support.core_service_base import CoreServiceTestCase


class ByesDaImportacaoTest(unittest.TestCase):
    def test_u_e_f_deixaram_de_ser_a_mesma_coisa(self) -> None:
        self.assertEqual("BYE", BYE_RESULTS["U"])
        self.assertEqual("F", BYE_RESULTS["F"])

    def test_ausencia_de_zero_ponto_e_preservada(self) -> None:
        """`Z` era descartado: a rodada sumia do histórico do jogador."""
        self.assertEqual("Z", BYE_RESULTS["Z"])
        self.assertEqual("Z", BYE_RESULTS["-"])

    def test_meio_ponto_continua_meio_ponto(self) -> None:
        self.assertEqual("H", BYE_RESULTS["H"])


class RoundTripTest(CoreServiceTestCase):
    """Exportar -> importar -> exportar tem de dar o mesmo arquivo."""

    def _fixture(self) -> None:
        self.db.save_tournament_settings(
            self.tournament_id,
            {
                "federation": "BRA",
                "chief_arbiter": "Arbitro Chefe",
                "arbiters": "Adjunto Um",
            },
        )
        self.db.save_round_schedule(
            self.tournament_id, [{"round_number": 1, "date": "2026-05-24", "time": "10:00"}]
        )
        self._create_players(5)  # impar: garante um bye alocado na rodada
        rodada = self.service.generate_next_round(self.tournament_id)
        for pairing in self.db.get_pairings_for_round(int(rodada["id"])):
            if not pairing["is_bye"]:
                self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(rodada["id"]))

    def _exportar(self, tournament_id: int, destino: Path) -> str:
        self.export_service.export_chess_results_trf(tournament_id, destino)
        return destino.read_text(encoding="utf-8")

    def test_exportar_importar_exportar_da_o_mesmo_arquivo(self) -> None:
        self._fixture()
        with tempfile.TemporaryDirectory() as tmp:
            primeiro = Path(tmp) / "original.trf"
            conteudo_original = self._exportar(self.tournament_id, primeiro)

            importado = self.import_service.import_trf(primeiro)
            segundo = Path(tmp) / "reexportado.trf"
            conteudo_reexportado = self._exportar(int(importado["tournament_id"]), segundo)

        linhas_original = _linhas_de_jogador(conteudo_original)
        linhas_reexportadas = _linhas_de_jogador(conteudo_reexportado)
        self.assertEqual(linhas_original, linhas_reexportadas)

    def test_bye_alocado_sobrevive_a_importacao(self) -> None:
        """Era importado como `F` (ponto cheio) e reexportado como `F`."""
        self._fixture()
        with tempfile.TemporaryDirectory() as tmp:
            origem = Path(tmp) / "original.trf"
            conteudo = self._exportar(self.tournament_id, origem)
            self.assertIn("0000 - U", conteudo)

            importado = self.import_service.import_trf(origem)
            reexportado = self._exportar(int(importado["tournament_id"]), Path(tmp) / "b.trf")
        self.assertIn("0000 - U", reexportado)
        self.assertNotIn("0000 - F", reexportado)

    def test_arbitros_e_calendario_vem_junto(self) -> None:
        self._fixture()
        with tempfile.TemporaryDirectory() as tmp:
            origem = Path(tmp) / "original.trf"
            self._exportar(self.tournament_id, origem)
            importado = self.import_service.import_trf(origem)

        settings = self.db.get_tournament_settings(int(importado["tournament_id"])) or {}
        self.assertEqual("Arbitro Chefe", settings.get("chief_arbiter"))
        self.assertIn("Adjunto Um", str(settings.get("arbiters") or ""))
        agenda = self.db.list_round_schedule(int(importado["tournament_id"]))
        self.assertEqual("2026-05-24", str(agenda[0]["date"]))

    def test_ausencia_de_zero_ponto_volta_como_rodada(self) -> None:
        """O `Z` do arquivo virava nada; o jogador perdia a rodada no histórico."""
        jogadores = [
            {
                "start_rank": 1,
                "name": "Ana",
                "rounds": [{"opponent_rank": "0", "color": "-", "result": "Z"}],
            },
            {
                "start_rank": 2,
                "name": "Bruno",
                "rounds": [{"opponent_rank": "3", "color": "w", "result": "1"}],
            },
            {
                "start_rank": 3,
                "name": "Carla",
                "rounds": [{"opponent_rank": "2", "color": "b", "result": "0"}],
            },
        ]
        rodadas = build_trf_rounds(jogadores, {1: 77, 2: 78, 3: 79})
        self.assertEqual(1, len(rodadas))
        mesa = next(item for item in rodadas[0][1] if item["is_bye"])
        self.assertEqual("Z", mesa["result"])
        self.assertEqual(77, mesa["white_player_id"])

    def test_rodada_so_com_ausencia_nao_e_rodada_jogada(self) -> None:
        """Num TRF em andamento, `0000 - Z` na proxima rodada e DECLARACAO."""
        jogadores = [
            {
                "start_rank": 1,
                "name": "Ana",
                "rounds": [{"opponent_rank": "0", "color": "-", "result": "Z"}],
            }
        ]
        self.assertEqual([], build_trf_rounds(jogadores, {1: 77}))


class EquipesImportadasTest(CoreServiceTestCase):
    def test_secao_de_equipes_vira_equipe_de_verdade(self) -> None:
        conteudo = (
            "012 Interclubes\r\n"
            "142 1\r\n"
            + _linha_jogador(1, "Ana")
            + _linha_jogador(2, "Bruno")
            + "013 Equipe Azul                        1    2\r\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            origem = Path(tmp) / "equipes.trf"
            origem.write_text(conteudo, encoding="utf-8", newline="")
            importado = self.import_service.import_trf(origem)

        self.assertEqual(1, importado["teams_imported"])
        equipes = self.db.list_teams(int(importado["tournament_id"]), active_only=False)
        self.assertEqual(["Equipe Azul"], [str(equipe["name"]) for equipe in equipes])
        membros = self.db.list_team_players(int(equipes[0]["id"]))
        self.assertEqual([1, 2], [int(membro["board_number"]) for membro in membros])

    def test_equipe_sem_jogador_conhecido_e_ignorada(self) -> None:
        conteudo = (
            "012 Interclubes\r\n"
            + _linha_jogador(1, "Ana")
            + "013 Equipe Fantasma                   77   88\r\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            origem = Path(tmp) / "equipes.trf"
            origem.write_text(conteudo, encoding="utf-8", newline="")
            importado = self.import_service.import_trf(origem)
        self.assertEqual(0, importado["teams_imported"])


def _linha_jogador(rank: int, nome: str) -> str:
    return (
        f"001 {rank:4d} m    {nome:<33} {1800:4d} BRA {'':>11} {'2000/01/01':<10} "
        f"{'0.0':>4} {rank:4d}  \r\n"
    )


def _linhas_de_jogador(conteudo: str) -> list[str]:
    """Linhas 001 sem o nome/ID (que o round-trip não promete preservar)."""
    from src.services.trf_layout import ROUND_CELLS_START

    return [
        linha[ROUND_CELLS_START:]
        for linha in conteudo.splitlines()
        if linha.startswith("001")
    ]


if __name__ == "__main__":
    unittest.main()
