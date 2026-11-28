"""RG2-43 — a auditoria registra quem está logado, não "Administrador".

Havia duas fontes de "quem é o operador": ``SecurityService`` guardava o
usuário logado só na memória dele, e a auditoria do banco lia
``operator_name``/``operator_role`` de ``app_settings`` (padrão
"Administrador"/admin). Logado como árbitro, a correção de resultado saía como
feita pelo administrador — numa apelação, isso importa.

Agora o operador mora num lugar só: o ``Database``, definido pelo login.
"""
from __future__ import annotations

import unittest

from src.core.operator import Operator
from tests.support.core_service_base import CoreServiceTestCase


class OperadorUnicoTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.security_service.create_user("arb", "senha-arb", "arbiter")
        self.jogadores = self._create_players(4)
        self.rodada = self.service.generate_next_round(self.tournament_id)
        self.mesa = next(p for p in self.db.get_pairings_for_round(self.rodada["id"]) if not p["is_bye"])

    def test_resultado_lancado_pelo_arbitro_sai_com_o_arbitro(self) -> None:
        self.assertTrue(self.security_service.login("arb", "senha-arb"))
        self.service.update_result(self.tournament_id, int(self.mesa["id"]), "1-0")
        (evento,) = self.db.list_audit_events(self.tournament_id, action="result_updated")
        self.assertEqual(("arb", "arbiter"), (evento["actor"], evento["role"]))

    def test_o_login_define_o_operador_do_banco(self) -> None:
        self.security_service.login("arb", "senha-arb")
        operador = self.db.current_operator()
        self.assertEqual(("arb", "arbiter"), (operador.name, operador.role))
        self.assertGreater(operador.user_id, 0)
        self.assertEqual(operador.user_id, self.security_service.current_user_id())

    def test_app_settings_nao_e_mais_fonte_do_operador(self) -> None:
        self.db.save_app_settings({"operator_name": "Fulano", "operator_role": "admin"})
        self.security_service.login("arb", "senha-arb")
        self.service.update_result(self.tournament_id, int(self.mesa["id"]), "1-0")
        (evento,) = self.db.list_audit_events(self.tournament_id, action="result_updated")
        self.assertEqual("arb", evento["actor"])

    def test_sem_login_e_o_sistema(self) -> None:
        self.assertIsNone(self.db.current_operator())
        self.service.update_result(self.tournament_id, int(self.mesa["id"]), "1-0")
        (evento,) = self.db.list_audit_events(self.tournament_id, action="result_updated")
        self.assertEqual(("sistema", ""), (evento["actor"], evento["role"]))

    def test_outro_servico_montado_depois_nao_desloga(self) -> None:
        from src.services.security_service import SecurityService

        self.security_service.login("arb", "senha-arb")
        SecurityService(self.db)
        self.assertEqual("arb", self.db.current_operator().name)


class AvancoDaEliminatoriaTest(CoreServiceTestCase):
    def _fechar_rodada(self, resultados: dict[int, str]) -> int:
        rodada = self.service.generate_next_round(self.tournament_id)
        for pairing in self.db.get_pairings_for_round(int(rodada["id"])):
            if resultados.get(int(pairing["board_number"])):
                self.service.update_result(self.tournament_id, int(pairing["id"]), resultados[int(pairing["board_number"])])
        self.service.close_round(self.tournament_id, int(rodada["id"]))
        return int(rodada["id"])

    def test_avanco_grava_o_nome_do_operador(self) -> None:
        self._set_individual_pairing_method("knockout")
        self._create_players(4)
        round_id = self._fechar_rodada({1: "1/2-1/2", 2: "1-0"})
        mesa = next(p for p in self.db.get_pairings_for_round(round_id) if int(p["board_number"]) == 1)
        self.db.set_operator(Operator(user_id=7, name="arb", role="arbiter"))
        self.service.register_knockout_advancement(
            self.tournament_id, int(mesa["id"]), int(mesa["black_player_id"]), "armageddon", "armagedom"
        )
        (avanco,) = self.db.list_knockout_advancements(self.tournament_id)
        self.assertEqual("arb", avanco["actor"])


if __name__ == "__main__":
    unittest.main()
