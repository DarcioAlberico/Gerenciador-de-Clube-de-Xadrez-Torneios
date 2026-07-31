"""ARB-03 — registro disciplinar de incidentes.

Não existia módulo nenhum: celular (art. 11.3.2), lance ilegal (7.5), atraso
além do tempo de tolerância (6.7) e conduta (12.x) eram anotados no PAPEL, na
tabela do manual operacional. `point_adjustments` já existia, mas sem catálogo
de infrações e sem vínculo com o jogador reincidente — uma dedução era um número
com texto livre ao lado, e a segunda advertência do mesmo artigo ao mesmo
jogador não era encontrável por ninguém.
"""

from __future__ import annotations

import unittest

from src.services.constants import AppError
from src.services.pairing.incidents import (
    DECISION_DEDUCTION,
    DECISION_LOSS,
    DECISION_WARNING,
    INFRACTIONS,
    clock_event_needs_decision,
    decided_clock_event_ids,
    decision_label,
    describe,
    forfeit_result,
    infraction_label,
    register_error,
    repeat_count,
    repeat_offenders,
)
from tests.support.core_service_base import CoreServiceTestCase


def _erro(**campos) -> str:
    base = dict(
        infraction="mobile_phone",
        decision=DECISION_WARNING,
        player_id=7,
        pairing_id=None,
        deduction_points=0.0,
        notes="",
    )
    base.update(campos)
    return register_error(**base)


class CatalogoTest(unittest.TestCase):
    """O catálogo nomeia o ARTIGO; a sanção é do árbitro."""

    def test_as_infracoes_de_salao_estao_no_catalogo(self) -> None:
        for code in ("mobile_phone", "illegal_move", "default_time", "conduct"):
            self.assertIn(code, INFRACTIONS, code)

    def test_o_rotulo_traz_o_artigo(self) -> None:
        self.assertEqual(
            "Telefone celular / dispositivo eletronico (art. 11.3.2)",
            infraction_label("mobile_phone"),
        )
        self.assertEqual("Outro (descrever nas observacoes)", infraction_label("other"))

    def test_infracao_desconhecida_devolve_o_proprio_codigo(self) -> None:
        self.assertEqual("inventada", infraction_label("inventada"))

    def test_cada_infracao_sugere_uma_decisao_valida(self) -> None:
        from src.services.pairing.incidents import INCIDENT_DECISIONS

        for code, item in INFRACTIONS.items():
            self.assertIn(item.suggested, INCIDENT_DECISIONS, code)

    def test_a_descricao_junta_rodada_mesa_e_decisao(self) -> None:
        linha = describe(
            {
                "infraction": "illegal_move",
                "round_number": 3,
                "board_number": 5,
                "decision": DECISION_WARNING,
            }
        )
        self.assertIn("Lance ilegal (art. 7.5)", linha)
        self.assertIn("R3", linha)
        self.assertIn("mesa 5", linha)
        self.assertIn("Advertencia", linha)

    def test_partida_perdida_e_W_O_e_nao_decisao_do_arbitro(self) -> None:
        """Quem perde por regulamento NAO JOGOU a partida aos olhos da FIDE.

        Por isso `1F-0F`, e nao o `1U-0U` da ARB-02: o adversario nao ganha uma
        vitoria no tabuleiro nem a partida entra no rating.
        """
        self.assertEqual("0F-1F", forfeit_result(is_white=True))
        self.assertEqual("1F-0F", forfeit_result(is_white=False))


class ValidacaoTest(unittest.TestCase):
    def test_incidente_simples_passa(self) -> None:
        self.assertEqual("", _erro())

    def test_infracao_e_decisao_precisam_existir(self) -> None:
        self.assertIn("Infracao invalida", _erro(infraction="ferias"))
        self.assertIn("Decisao invalida", _erro(decision="tapa"))

    def test_jogador_e_obrigatorio(self) -> None:
        self.assertIn("Informe o jogador", _erro(player_id=None))

    def test_outro_exige_descricao(self) -> None:
        """E ela que a ata cita no lugar do artigo."""
        self.assertIn("exige descricao", _erro(infraction="other"))
        self.assertEqual("", _erro(infraction="other", notes="conversa no salao"))

    def test_partida_perdida_exige_mesa(self) -> None:
        erro = _erro(decision=DECISION_LOSS)
        self.assertIn("precisa da MESA", erro)
        self.assertEqual("", _erro(decision=DECISION_LOSS, pairing_id=4))

    def test_deducao_exige_valor(self) -> None:
        self.assertIn("valor diferente de zero", _erro(decision=DECISION_DEDUCTION))
        self.assertEqual("", _erro(decision=DECISION_DEDUCTION, deduction_points=0.5))


class ReincidenciaTest(unittest.TestCase):
    """O número que o catálogo existe para produzir."""

    def _incidentes(self) -> list[dict]:
        return [
            {"player_id": 1, "infraction": "mobile_phone"},
            {"player_id": 1, "infraction": "mobile_phone"},
            {"player_id": 1, "infraction": "conduct"},
            {"player_id": 2, "infraction": "illegal_move"},
        ]

    def test_conta_por_jogador_e_por_infracao(self) -> None:
        self.assertEqual(3, repeat_count(self._incidentes(), 1))
        self.assertEqual(2, repeat_count(self._incidentes(), 1, "mobile_phone"))
        self.assertEqual(1, repeat_count(self._incidentes(), 2))

    def test_reincidentes_sao_os_com_mais_de_um(self) -> None:
        self.assertEqual({1: 3}, repeat_offenders(self._incidentes()))

    def test_sem_incidente_nao_ha_reincidente(self) -> None:
        self.assertEqual({}, repeat_offenders([]))


class AlertaDeRelogioTest(unittest.TestCase):
    def test_so_seta_e_ausencia_exigem_decisao(self) -> None:
        self.assertTrue(clock_event_needs_decision("flag_fall"))
        self.assertTrue(clock_event_needs_decision("absence"))
        self.assertFalse(clock_event_needs_decision("time_warning"))

    def test_o_evento_com_incidente_ja_esta_decidido(self) -> None:
        self.assertEqual(
            {12}, decided_clock_event_ids([{"clock_event_id": 12}, {"clock_event_id": None}])
        )


class IncidenteNoServicoTest(CoreServiceTestCase):
    """O caminho inteiro: registrar, deduzir, perder a partida, sair na ata."""

    def setUp(self) -> None:
        super().setUp()
        self.player_ids = self._create_players(4)
        self.round_data = self.service.generate_next_round(self.tournament_id)
        self.mesas = [
            item
            for item in self.db.get_pairings_for_round(int(self.round_data["id"]))
            if not item["is_bye"]
        ]

    def test_advertencia_registra_sem_mexer_em_ponto(self) -> None:
        resultado = self.service.register_incident(
            self.tournament_id,
            player_id=self.player_ids[0],
            infraction="illegal_move",
            decision=DECISION_WARNING,
            round_number=1,
            notes="segundo lance ilegal",
        )

        self.assertIsNone(resultado["adjustment_id"])
        incidentes = self.service.incidents(self.tournament_id)
        self.assertEqual(1, len(incidentes))
        self.assertEqual("illegal_move", incidentes[0]["infraction"])
        acoes = {
            evento["action"]
            for evento in self.db.list_audit_events(self.tournament_id, limit=50)
        }
        self.assertIn("incident_registered", acoes)

    def test_deducao_chega_na_classificacao(self) -> None:
        """Criterio de aceite: a decisao que nao chega na tabela e um bilhete."""
        alvo = int(self.mesas[0]["white_player_id"])
        for mesa in self.mesas:
            self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        antes = {
            int(item["player_id"]): float(item["points"])
            for item in self.service.standings(self.tournament_id)
        }

        self.service.register_incident(
            self.tournament_id,
            player_id=alvo,
            infraction="conduct",
            decision=DECISION_DEDUCTION,
            round_number=1,
            deduction_points=0.5,
            notes="perturbacao do adversario",
        )

        depois = {
            int(item["player_id"]): float(item["points"])
            for item in self.service.standings(self.tournament_id)
        }
        self.assertEqual(antes[alvo] - 0.5, depois[alvo])
        incidente = self.service.incidents(self.tournament_id)[0]
        self.assertIsNotNone(incidente["adjustment_id"])

    def test_partida_perdida_lanca_o_resultado_na_mesa(self) -> None:
        mesa = self.mesas[0]
        alvo = int(mesa["white_player_id"])

        self.service.register_incident(
            self.tournament_id,
            player_id=alvo,
            infraction="mobile_phone",
            decision=DECISION_LOSS,
            pairing_id=int(mesa["id"]),
            notes="celular tocou",
        )

        self.assertEqual("0F-1F", self.db.get_pairing(int(mesa["id"]))["result"])

    def test_a_rodada_nao_fecha_com_queda_de_seta_sem_decisao(self) -> None:
        """Criterio de aceite: a seta caiu, e alguem precisa dizer o que houve."""
        self._registrar_queda_de_seta()
        for mesa in self.mesas:
            self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")

        with self.assertRaises(AppError) as contexto:
            self.service.close_round(self.tournament_id, int(self.round_data["id"]))
        self.assertIn("pendencia", str(contexto.exception).lower())

    def test_registrada_a_decisao_a_rodada_fecha(self) -> None:
        evento_id = self._registrar_queda_de_seta()
        for mesa in self.mesas:
            self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")

        self.service.register_incident(
            self.tournament_id,
            player_id=int(self.mesas[0]["white_player_id"]),
            infraction="flag_fall",
            decision=DECISION_WARNING,
            round_number=1,
            clock_event_id=evento_id,
            notes="seta caiu; reclamacao indeferida",
        )
        self.service.close_round(self.tournament_id, int(self.round_data["id"]))

        self.assertEqual(
            "closed", self.db.get_round(int(self.round_data["id"]))["status"]
        )

    def test_alerta_de_tempo_critico_continua_sem_bloquear(self) -> None:
        """So seta e ausencia exigem decisao; aviso de tempo e aviso."""
        self.db.create_clock_event(
            self.tournament_id,
            "time_warning",
            round_id=int(self.round_data["id"]),
            pairing_id=int(self.mesas[0]["id"]),
            board_number=1,
            seconds_remaining=30,
        )
        for mesa in self.mesas:
            self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")

        self.service.close_round(self.tournament_id, int(self.round_data["id"]))

        self.assertEqual("closed", self.db.get_round(int(self.round_data["id"]))["status"])

    def _registrar_queda_de_seta(self) -> int:
        self.db.create_clock_event(
            self.tournament_id,
            "flag_fall",
            round_id=int(self.round_data["id"]),
            pairing_id=int(self.mesas[0]["id"]),
            board_number=1,
            seconds_remaining=0,
        )
        evento = next(
            item
            for item in self.db.list_clock_events(tournament_id=self.tournament_id, limit=10)
            if item["event_type"] == "flag_fall"
        )
        return int(evento["id"])

    def test_jogador_de_outro_torneio_e_recusado(self) -> None:
        outro = self.tournament_service.create_tournament(
            {"name": "Outro", "rounds_count": "3", "bye_points": "1"}
        )
        with self.assertRaisesRegex(AppError, "Jogador nao encontrado"):
            self.service.register_incident(
                outro,
                player_id=self.player_ids[0],
                infraction="conduct",
                decision=DECISION_WARNING,
            )

    def test_a_ata_traz_o_anexo_disciplinar_com_reincidencia(self) -> None:
        alvo = self.player_ids[0]
        for _ in range(2):
            self.service.register_incident(
                self.tournament_id,
                player_id=alvo,
                infraction="mobile_phone",
                decision=DECISION_WARNING,
                round_number=1,
                notes="celular",
            )

        secoes = self.export_service._tournament_minutes_sections(self.tournament_id)
        titulos = [titulo for titulo, _cabecalho, _linhas in secoes]
        self.assertIn("Incidentes disciplinares", titulos)
        _titulo, cabecalho, linhas = next(
            secao for secao in secoes if secao[0] == "Incidentes disciplinares"
        )
        self.assertIn("Reincidência", cabecalho)
        self.assertTrue(any("2ª ocorrência" in str(linha) for linha in linhas))
        self.assertEqual({alvo: 2}, self.service.incident_repeat_offenders(self.tournament_id))

    def test_a_ata_nao_ganha_o_anexo_quando_nao_houve_incidente(self) -> None:
        secoes = self.export_service._tournament_minutes_sections(self.tournament_id)
        self.assertNotIn(
            "Incidentes disciplinares", [titulo for titulo, _c, _l in secoes]
        )

    def test_o_rotulo_da_decisao_sai_por_extenso(self) -> None:
        self.assertEqual("Partida perdida", decision_label(DECISION_LOSS))
        self.assertEqual("Deducao de pontos", decision_label(DECISION_DEDUCTION))


if __name__ == "__main__":
    unittest.main()
