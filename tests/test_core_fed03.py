"""FED-03 — TRF16 de campo completo e modo submissão.

O arquivo saía com cinco problemas que só aparecem do outro lado, depois do
envio: sem `XXR`/`XXC` (o dialeto TRF16 espera essas extensões, e o `142` que
saía no lugar é registro TRF25), com `082 0` em torneio individual (que descreve
um torneio por equipes sem equipes), com o tipo de torneio em texto proprietário,
sem o FIDE Event-ID e sem o FIDE ID dos árbitros — e com mesa pareada ainda sem
resultado exportada como `Z`, que significa "ausência conhecida, zero ponto".

Nada disso bloqueava a geração: o árbitro só descobria quando a federação
recusasse. O modo submissão é a porta que faltava.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.services.constants import AppError
from src.services.federation_exporters.trf16_records import (
    arbiter_text,
    duplicate_fide_ids,
    initial_color,
    pending_result_cells,
    reciprocity_errors,
    record_xxc,
    record_xxe,
    record_xxr,
    tournament_type_text,
)
from tests.support.core_service_base import CoreServiceTestCase


def _linha_001(rank: int, nome: str, celulas: str) -> str:
    base = (
        f"001 {rank:4d} m    {nome:<33} {2000:4d} BRA {'':>11} {'2000/01/01':<10} "
        f"{'0.0':>4} {rank:4d}  "
    )
    return (base + celulas).rstrip().ljust(len(base) + 8)


class RegistrosDoDialetoTest(unittest.TestCase):
    def test_xxr_declara_o_total_de_rodadas(self) -> None:
        self.assertEqual("XXR 9", record_xxr(9))

    def test_xxc_diz_a_cor_do_tabuleiro_1(self) -> None:
        self.assertEqual("XXC white1", record_xxc("white1"))
        self.assertEqual("XXC black1", record_xxc("black1"))
        self.assertEqual("XXC white1", record_xxc("qualquer coisa"))

    def test_cor_inicial_sai_do_que_foi_pareado(self) -> None:
        ranks = {10: 1, 20: 5}
        self.assertEqual(
            "white1",
            initial_color([{"white_player_id": 10, "black_player_id": 20}], ranks),
        )
        self.assertEqual(
            "black1",
            initial_color([{"white_player_id": 20, "black_player_id": 10}], ranks),
        )

    def test_sem_rodada_gerada_assume_brancas(self) -> None:
        self.assertEqual("white1", initial_color([], {}))

    def test_event_id_so_sai_quando_existe(self) -> None:
        self.assertEqual("XXE 12345", record_xxe("12345"))
        self.assertEqual("", record_xxe(""))

    def test_tipo_de_torneio_no_vocabulario_das_federacoes(self) -> None:
        self.assertEqual(
            "Individual: Swiss-System",
            tournament_type_text("individual", "swiss", fide_rated=False),
        )
        self.assertEqual(
            "Team: Round Robin (FIDE-rated)",
            tournament_type_text("team", "round_robin", fide_rated=True),
        )

    def test_arbitro_leva_o_fide_id_quando_existe(self) -> None:
        self.assertEqual("Ana Souza (1234567)", arbiter_text("Ana Souza", "1234567"))
        self.assertEqual("Ana Souza", arbiter_text("Ana Souza", ""))


class ConferenciaDoArquivoTest(unittest.TestCase):
    """As checagens que só o arquivo pronto permite."""

    def test_mesa_coerente_nao_gera_erro(self) -> None:
        linhas = [
            _linha_001(1, "Ana", "   2 w 1  "),
            _linha_001(2, "Bruno", "   1 b 0  "),
        ]
        self.assertEqual([], reciprocity_errors(linhas))

    def test_adversario_que_nao_aponta_de_volta(self) -> None:
        linhas = [
            _linha_001(1, "Ana", "   2 w 1  "),
            _linha_001(2, "Bruno", "   3 b 0  "),
        ]
        erros = reciprocity_errors(linhas)
        self.assertEqual(2, len(erros))
        self.assertIn("Ana", erros[0])

    def test_duas_brancas_na_mesma_mesa(self) -> None:
        linhas = [
            _linha_001(1, "Ana", "   2 w 1  "),
            _linha_001(2, "Bruno", "   1 w 0  "),
        ]
        self.assertTrue(any("os dois com 'w'" in erro for erro in reciprocity_errors(linhas)))

    def test_mesa_sem_resultado_e_listada(self) -> None:
        pendentes = pending_result_cells([_linha_001(1, "Ana", "   2 w    ")])
        self.assertEqual(1, len(pendentes))
        self.assertIn("Ana", pendentes[0])

    def test_bye_nao_conta_como_pendencia(self) -> None:
        self.assertEqual([], pending_result_cells([_linha_001(1, "Ana", "0000 - U  ")]))

    def test_fide_id_repetido_e_apontado(self) -> None:
        duplicados = duplicate_fide_ids(
            [
                {"name": "Ana", "fide_id": "111"},
                {"name": "Bruno", "fide_id": "111"},
                {"name": "Carla", "fide_id": "222"},
                {"name": "Sem ID", "fide_id": ""},
            ]
        )
        self.assertEqual(1, len(duplicados))
        self.assertIn("Ana", duplicados[0])
        self.assertIn("Bruno", duplicados[0])


class ArquivoGeradoTest(CoreServiceTestCase):
    def _exportar(self, **kwargs) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "torneio.trf"
            self.export_service.export_chess_results_trf(self.tournament_id, destino, **kwargs)
            return destino.read_text(encoding="utf-8")

    def _fixture(self, resultados: bool = True) -> None:
        self.db.save_tournament_settings(
            self.tournament_id,
            {
                "federation": "BRA",
                "chief_arbiter": "Arbitro Chefe",
                "fide_event_id": "998877",
            },
        )
        self._create_players(4)
        rodada = self.service.generate_next_round(self.tournament_id)
        if resultados:
            for pairing in self.db.get_pairings_for_round(int(rodada["id"])):
                self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
            self.service.close_round(self.tournament_id, int(rodada["id"]))

    def test_arquivo_traz_xxr_xxc_e_event_id(self) -> None:
        self._fixture()
        conteudo = self._exportar()
        self.assertIn("XXR 5", conteudo)  # torneio configurado com 5 rodadas
        self.assertIn("XXC ", conteudo)
        self.assertIn("XXE 998877", conteudo)

    def test_082_nao_sai_em_torneio_individual(self) -> None:
        self._fixture()
        self.assertNotIn("082 ", self._exportar())

    def test_celulas_de_rodada_batem_com_o_trf25(self) -> None:
        """Os dois arquivos do mesmo torneio tinham contagens diferentes."""
        self._fixture()
        with tempfile.TemporaryDirectory() as tmp:
            trf16 = Path(tmp) / "a.trf"
            trf25 = Path(tmp) / "b.trf"
            self.export_service.export_chess_results_trf(self.tournament_id, trf16)
            self.export_service.export_chess_results_trf25(self.tournament_id, trf25)
            celulas16 = _celulas(trf16.read_text(encoding="utf-8"))
            celulas25 = _celulas(trf25.read_text(encoding="utf-8"))
        self.assertEqual(celulas16, celulas25)

    def test_mesa_sem_resultado_nao_sai_como_ausencia(self) -> None:
        """`Z` significa "ausência conhecida"; a mesa ainda vai ser jogada."""
        self._fixture(resultados=False)
        conteudo = self._exportar()
        linhas = [linha for linha in conteudo.splitlines() if linha.startswith("001")]
        self.assertTrue(linhas)
        for linha in linhas:
            self.assertNotIn(" - Z", linha)

    def test_modo_submissao_recusa_resultado_pendente(self) -> None:
        self._fixture(resultados=False)
        with self.assertRaises(AppError) as erro:
            self._exportar(submission=True)
        self.assertIn("sem resultado", str(erro.exception))
        self.assertIn("Modo submissao", str(erro.exception))

    def test_modo_submissao_recusa_fide_id_repetido(self) -> None:
        self._fixture()
        jogadores = self.db.list_players(self.tournament_id, active_only=False)
        with self.db.connect() as connection:
            for jogador in jogadores[:2]:
                connection.execute(
                    "UPDATE players SET fide_id = ? WHERE id = ?", ("123456", int(jogador["id"]))
                )
        with self.assertRaises(AppError) as erro:
            self._exportar(submission=True)
        self.assertIn("repetido", str(erro.exception))

    def test_modo_normal_gera_com_aviso(self) -> None:
        """Durante o evento o arquivo sai — com o aviso, e sem bloquear."""
        self._fixture(resultados=False)
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "torneio.trf"
            avisos = self.export_service.export_chess_results_trf(self.tournament_id, destino)
            self.assertTrue(destino.exists())
        self.assertTrue(any("sem resultado" in aviso for aviso in avisos))


def _celulas(conteudo: str) -> list[int]:
    """Quantas células de rodada cada linha 001 traz."""
    from src.services.trf_layout import cell_blocks

    return [
        len(cell_blocks(linha))
        for linha in conteudo.splitlines()
        if linha.startswith("001")
    ]


if __name__ == "__main__":
    unittest.main()
