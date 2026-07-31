"""ARB-02 — resultados arbitrais completos no painel.

Três lacunas do fluxo de salão, que se encontram na mesma tela:

1. W.O. só era lançável na tela `Rodadas` — justamente a que o árbitro não tem à
   mão quando está em pé decidindo uma ausência;
2. não havia estado "partida adiada": ela e a mesa esquecida eram a mesma linha
   em branco, travando a rodada com o mesmo recado;
3. faltavam os códigos `W`/`D`/`L` do TRF — partida DISPUTADA e não ratável
   (resultado por decisão do árbitro). Sem eles, o árbitro escolhia entre mentir
   no rating (lançar `1-0`) ou mentir no Buchholz e no pareamento (lançar W.O.,
   que a FIDE trata como partida não disputada).
"""

from __future__ import annotations

import unittest

from src.services.constants import FINAL_RESULTS, RESULT_POINTS, RESULTS, AppError
from src.services.pairing import calculate_player_standings
from src.services.pairing.postponement import (
    blocking_message,
    clean_note,
    describe_pairing,
    issue_from_pairing,
    postpone_error,
    postponed_label,
    resume_error,
)
from src.services.results_registry import (
    RATED_RESULTS,
    RESULT_CODES,
    UNRATED_RESULTS,
    WALKOVER_RESULTS,
    code_from_trf_letter,
    is_played_result,
    is_rated_result,
    trf_letters,
)
from tests.support.core_service_base import CoreServiceTestCase


class RegistroDeResultadosTest(unittest.TestCase):
    """Uma definição por código, e os recortes derivados dela."""

    def test_as_tres_familias_do_trf(self) -> None:
        # normal: jogada e ratável | decisão do árbitro: jogada e não ratável
        # W.O.: nem jogada nem ratável.
        self.assertEqual({"1-0", "0-1", "1/2-1/2"}, RATED_RESULTS)
        self.assertEqual({"1U-0U", "0U-1U", "1/2U-1/2U"}, UNRATED_RESULTS)
        self.assertEqual({"1F-0F", "0F-1F", "0F-0F"}, WALKOVER_RESULTS)

    def test_decisao_do_arbitro_e_partida_jogada(self) -> None:
        """É o que separa `W`/`D`/`L` de `+`/`-` no TRF, e muda Buchholz e SB."""
        self.assertTrue(is_played_result("1U-0U"))
        self.assertFalse(is_rated_result("1U-0U"))
        self.assertFalse(is_played_result("1F-0F"))

    def test_os_pontos_sao_os_mesmos_do_resultado_normal(self) -> None:
        self.assertEqual(RESULT_POINTS["1-0"], RESULT_POINTS["1U-0U"])
        self.assertEqual(RESULT_POINTS["0-1"], RESULT_POINTS["0U-1U"])
        self.assertEqual(RESULT_POINTS["1/2-1/2"], RESULT_POINTS["1/2U-1/2U"])

    def test_os_recortes_derivam_do_registro(self) -> None:
        """Guarda: um código novo não pode precisar de seis edições."""
        self.assertEqual(set(RESULT_CODES), set(RESULT_POINTS))
        self.assertTrue(set(RESULT_CODES).issubset(FINAL_RESULTS))
        self.assertEqual("", RESULTS[0], "a tela precisa do vazio para limpar")
        for code in RESULT_CODES:
            self.assertIn(code, RESULTS, code)

    def test_letras_trf_de_cada_lado(self) -> None:
        self.assertEqual(("W", "L"), trf_letters("1U-0U"))
        self.assertEqual(("L", "W"), trf_letters("0U-1U"))
        self.assertEqual(("D", "D"), trf_letters("1/2U-1/2U"))
        self.assertEqual(("+", "-"), trf_letters("1F-0F"))
        self.assertIsNone(trf_letters("nao-existe"))

    def test_a_letra_volta_para_o_codigo_da_mesa(self) -> None:
        """Ler a linha das brancas ou a das pretas dá o MESMO código."""
        self.assertEqual("1U-0U", code_from_trf_letter("W", is_white=True))
        self.assertEqual("1U-0U", code_from_trf_letter("L", is_white=False))
        self.assertEqual("0U-1U", code_from_trf_letter("L", is_white=True))
        self.assertEqual("1/2U-1/2U", code_from_trf_letter("D", is_white=True))
        self.assertEqual("1-0", code_from_trf_letter("1", is_white=True))
        self.assertEqual("0-1", code_from_trf_letter("1", is_white=False))
        self.assertEqual("", code_from_trf_letter("", is_white=True))
        self.assertEqual("", code_from_trf_letter("Q", is_white=True))


class DecisaoDoArbitroNaClassificacaoTest(unittest.TestCase):
    """A partida aconteceu: conta como jogo em tudo, menos no rating."""

    def _standings(self, resultado: str) -> dict[int, dict]:
        jogadores = [
            {
                "id": i, "name": f"J{i}", "club": "C", "rating": 2000, "category": "ABS",
                "active": 1, "starting_points": 0.0,
            }
            for i in (1, 2)
        ]
        partidas = [{
            "id": 1, "round_number": 1, "white_player_id": 1, "black_player_id": 2,
            "result": resultado, "is_bye": 0,
        }]
        return {
            int(item["player_id"]): item
            for item in calculate_player_standings({"bye_points": 1.0}, jogadores, partidas)
        }

    def test_vale_ponto_e_conta_vitoria(self) -> None:
        """Ao contrário do W.O.: o `WON` da FIDE é vitória no tabuleiro, e esta foi."""
        decisao = self._standings("1U-0U")
        self.assertEqual(1.0, decisao[1]["points"])
        self.assertEqual(1, decisao[1]["wins"])

    def test_o_walkover_continua_sem_contar_vitoria(self) -> None:
        walkover = self._standings("1F-0F")
        self.assertEqual(1.0, walkover[1]["points"])
        self.assertEqual(0, walkover[1]["wins"], "W.O. nao e vitoria no tabuleiro (TBK-03)")

    def test_o_adversario_entra_no_buchholz(self) -> None:
        """A mesa aconteceu, entao ela conta como confronto."""
        decisao = self._standings("1U-0U")
        self.assertEqual([2], decisao[1]["opponents"])


class RegrasDoAdiamentoTest(unittest.TestCase):
    """Módulo puro: quando se pode adiar, e o que se diz."""

    def _mesa(self, **campos) -> dict:
        base = {
            "id": 7, "board_number": 4, "round_status": "generated", "is_bye": 0,
            "result": "", "postponed": 0, "postponed_note": "",
            "white_player_name": "Ana Souza", "black_player_name": "Bruno Lima",
        }
        base.update(campos)
        return base

    def test_mesa_em_aberto_pode_ser_adiada(self) -> None:
        self.assertEqual("", postpone_error(self._mesa()))

    def test_rodada_fechada_nao(self) -> None:
        erro = postpone_error(self._mesa(round_status="closed"))
        self.assertIn("rodada esta fechada", erro)

    def test_bye_nao(self) -> None:
        self.assertIn("nao e partida", postpone_error(self._mesa(is_bye=1)))

    def test_mesa_com_resultado_nao(self) -> None:
        self.assertIn("ja tem resultado", postpone_error(self._mesa(result="1-0")))

    def test_mesa_inexistente_nao(self) -> None:
        self.assertIn("nao encontrada", postpone_error(None))

    def test_so_se_retoma_o_que_esta_adiado(self) -> None:
        self.assertEqual("", resume_error(self._mesa(postponed=1)))
        self.assertIn("nao esta marcada", resume_error(self._mesa()))

    def test_a_nota_e_normalizada_e_limitada(self) -> None:
        self.assertEqual("sabado 14h", clean_note("  sabado   14h \n"))
        self.assertEqual(120, len(clean_note("x" * 300)))
        self.assertEqual("", clean_note(None))

    def test_o_recado_do_fechamento_nomeia_as_mesas(self) -> None:
        """O genérico manda procurar o que o árbitro já sabe que está em aberto."""
        recado = blocking_message([self._mesa(postponed=1)])
        self.assertIn("1 partida adiada", recado)
        self.assertIn("Mesa 4", recado)
        self.assertIn("Ana Souza", recado)

    def test_o_recado_pluraliza(self) -> None:
        recado = blocking_message([self._mesa(postponed=1), self._mesa(id=8, board_number=5)])
        self.assertIn("2 partidas adiadas", recado)

    def test_rotulo_curto_com_e_sem_nota(self) -> None:
        self.assertEqual("Adiada", postponed_label(self._mesa(postponed=1)))
        self.assertEqual(
            "Adiada — sabado 14h",
            postponed_label(self._mesa(postponed=1, postponed_note="sabado 14h")),
        )

    def test_a_pendencia_do_painel_nao_bloqueia_por_si(self) -> None:
        """Quem barra o fechamento é a mesa sem resultado, com o recado próprio.

        `decision` aqui faria a mesma coisa aparecer duas vezes, com dois textos.
        """
        pendencia = issue_from_pairing(self._mesa(postponed=1), round_id=3, round_number=2)
        self.assertEqual("attention", pendencia["severity"])
        self.assertEqual("postponed:pairing:7", pendencia["issue_key"])
        self.assertEqual(3, pendencia["round_id"])

    def test_descricao_sobrevive_a_mesa_sem_nomes(self) -> None:
        self.assertEqual(
            "Mesa 4", describe_pairing({"board_number": 4})
        )


class AdiamentoNoServicoTest(CoreServiceTestCase):
    """O fluxo inteiro: adiar, ver no painel, tentar fechar, resolver."""

    def setUp(self) -> None:
        super().setUp()
        self._create_players(4)
        self.round_data = self.service.generate_next_round(self.tournament_id)
        self.mesas = [
            item
            for item in self.db.get_pairings_for_round(int(self.round_data["id"]))
            if not item["is_bye"]
        ]

    def _fechar(self) -> None:
        self.service.close_round(self.tournament_id, int(self.round_data["id"]))

    def test_adiar_marca_a_mesa_e_registra_auditoria(self) -> None:
        self.service.postpone_pairing(
            self.tournament_id, int(self.mesas[0]["id"]), "sabado 14h"
        )

        mesa = self.db.get_pairing(int(self.mesas[0]["id"]))
        self.assertEqual(1, int(mesa["postponed"]))
        self.assertEqual("sabado 14h", mesa["postponed_note"])
        acoes = {
            evento["action"]
            for evento in self.db.list_audit_events(self.tournament_id, limit=50)
        }
        self.assertIn("pairing_postponed", acoes)

    def test_o_fechamento_nomeia_a_mesa_adiada(self) -> None:
        for mesa in self.mesas[1:]:
            self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.service.postpone_pairing(self.tournament_id, int(self.mesas[0]["id"]), "amanha")

        with self.assertRaises(AppError) as contexto:
            self._fechar()
        recado = str(contexto.exception)
        self.assertIn("partida adiada", recado)
        self.assertIn("Mesa", recado)
        self.assertNotIn("Preencha todos os resultados", recado)

    def test_sem_adiamento_o_recado_continua_o_de_antes(self) -> None:
        with self.assertRaisesRegex(AppError, "Preencha todos os resultados"):
            self._fechar()

    def test_lancar_o_resultado_desfaz_o_adiamento(self) -> None:
        """Adiada com placar preenchido é um estado que não existe no salão."""
        self.service.postpone_pairing(self.tournament_id, int(self.mesas[0]["id"]), "amanha")
        self.service.update_result(self.tournament_id, int(self.mesas[0]["id"]), "1-0")

        mesa = self.db.get_pairing(int(self.mesas[0]["id"]))
        self.assertEqual(0, int(mesa["postponed"]))
        self.assertEqual("", mesa["postponed_note"])

    def test_a_rodada_fecha_depois_de_resolvida(self) -> None:
        self.service.postpone_pairing(self.tournament_id, int(self.mesas[0]["id"]), "amanha")
        for mesa in self.mesas:
            self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")

        self._fechar()

        self.assertEqual("closed", self.db.get_round(int(self.round_data["id"]))["status"])

    def test_retomar_desfaz_e_audita(self) -> None:
        self.service.postpone_pairing(self.tournament_id, int(self.mesas[0]["id"]), "amanha")
        self.service.resume_pairing(self.tournament_id, int(self.mesas[0]["id"]))

        self.assertEqual(0, int(self.db.get_pairing(int(self.mesas[0]["id"]))["postponed"]))
        acoes = {
            evento["action"]
            for evento in self.db.list_audit_events(self.tournament_id, limit=50)
        }
        self.assertIn("pairing_resumed", acoes)

    def test_adiar_mesa_de_outro_torneio_e_recusado(self) -> None:
        outro = self.tournament_service.create_tournament(
            {"name": "Outro", "rounds_count": "3", "bye_points": "1"}
        )
        with self.assertRaisesRegex(AppError, "nao encontrada"):
            self.service.postpone_pairing(outro, int(self.mesas[0]["id"]))

    def test_a_mesa_adiada_aparece_no_painel_com_o_combinado(self) -> None:
        self.service.postpone_pairing(
            self.tournament_id, int(self.mesas[0]["id"]), "sabado 14h"
        )

        painel = self.service.arbitration_dashboard(self.tournament_id)
        pendentes = {int(item["pairing_id"]): item for item in painel["pending_items"]}
        self.assertEqual("Adiada — sabado 14h", pendentes[int(self.mesas[0]["id"])]["context"])
        chaves = {
            item["issue_key"]
            for item in self.service.arbitration_issues(self.tournament_id)["issues"]
        }
        self.assertIn(f"postponed:pairing:{int(self.mesas[0]['id'])}", chaves)


class DecisaoDoArbitroNoTrfTest(CoreServiceTestCase):
    """Ida e volta pelo TRF: as letras `W`/`D`/`L` são lidas e escritas."""

    def test_o_trf16_escreve_as_letras_da_decisao(self) -> None:
        from pathlib import Path

        from src.services.federation_exporters import TRF16Exporter

        self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        mesas = [
            item
            for item in self.db.get_pairings_for_round(int(round_data["id"]))
            if not item["is_bye"]
        ]
        self.service.update_result(self.tournament_id, int(mesas[0]["id"]), "1U-0U")
        self.service.update_result(self.tournament_id, int(mesas[1]["id"]), "1/2U-1/2U")
        self.service.close_round(self.tournament_id, int(round_data["id"]))

        destino = Path(self.temp_dir.name) / "decisao.trf"
        TRF16Exporter(self.export_service).export(self.tournament_id, destino)
        linhas = [
            linha
            for linha in destino.read_text(encoding="utf-8").splitlines()
            if linha.startswith("001 ")
        ]

        letras = "".join(linha.strip()[-1] for linha in linhas)
        self.assertIn("W", letras)
        self.assertIn("L", letras)
        self.assertIn("D", letras)

    def test_o_resumo_conta_como_partida_jogada_e_nao_como_ausencia(self) -> None:
        from src.services.federation_exporters.trf16 import TRF16Exporter

        resumo = {"played": 0, "forfeits": 0, "double_absences": 0, "pending": 0, "byes": 0}
        TRF16Exporter._count_result(resumo, "1U-0U", is_bye=False)
        TRF16Exporter._count_result(resumo, "1F-0F", is_bye=False)

        self.assertEqual(1, resumo["played"])
        self.assertEqual(1, resumo["forfeits"])


class DecisaoDoArbitroNaoVemDoCelularTest(CoreServiceTestCase):
    """Quem decidiu é quem lança: o QR é para o que a mesa observou."""

    def test_o_qr_recusa_resultado_por_decisao_do_arbitro(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        mesa = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        payload = self.qr_result_service.result_url_for_pairing(
            self.tournament_id, int(mesa["id"])
        )

        with self.assertRaisesRegex(AppError, "invalido para envio por QR"):
            self.qr_result_service.submit_result(payload["token"], "1U-0U")

    def test_o_qr_continua_aceitando_placar_e_ausencia(self) -> None:
        self._create_players(2)
        round_data = self.service.generate_next_round(self.tournament_id)
        mesa = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        payload = self.qr_result_service.result_url_for_pairing(
            self.tournament_id, int(mesa["id"])
        )

        envio = self.qr_result_service.submit_result(payload["token"], "1-0")

        self.assertEqual("1-0", envio["submitted_result"])


class DecisaoDoArbitroForaDoRatingTest(unittest.TestCase):
    def test_a_partida_por_decisao_nao_entra_no_relatorio_de_rating(self) -> None:
        from src.services.fide_rating import build_fide_report_rows

        jogadores = [
            {"id": 1, "name": "A", "rating": 2000, "surname": "", "given_name": ""},
            {"id": 2, "name": "B", "rating": 2000, "surname": "", "given_name": ""},
        ]

        def linhas(resultado: str) -> list[dict]:
            partidas = [{
                "white_player_id": 1, "black_player_id": 2,
                "result": resultado, "is_bye": 0,
            }]
            return build_fide_report_rows(jogadores, partidas)

        self.assertEqual([], linhas("1U-0U"), "decisao do arbitro nao e ratavel")
        self.assertTrue(linhas("1-0"), "o resultado normal continua ratavel")


if __name__ == "__main__":
    unittest.main()
