"""ARB-04 — política de byes solicitados.

O bye solicitado era gravado direto da tela no banco (`db.add_requested_bye`),
sem passar por serviço nenhum: o que se validava era o FORMATO do formulário
(tem alvo? tem rodada? o tipo é F/H/Z?). Não havia onde uma política morar, e
por isso quatro coisas davam errado em silêncio — pedido para rodada já gerada
nunca era aplicado, pedido de jogador inativo sumia na hora de parear, não havia
limite por jogador e não havia última rodada permitida.
"""

from __future__ import annotations

import unittest

from src.services.constants import AppError
from src.services.pairing.bye_policy import (
    ByePolicy,
    count_limited,
    discarded_warning,
    request_error,
)
from tests.support.core_service_base import CoreServiceTestCase


def _erro(**campos) -> str:
    base = dict(
        policy=ByePolicy(),
        bye_type="H",
        round_number=2,
        rounds_count=5,
        round_status=None,
        player_active=True,
        existing_byes=(),
    )
    base.update(campos)
    return request_error(**base)


class PoliticaDeByesTest(unittest.TestCase):
    """As regras, sem banco."""

    def test_pedido_normal_passa(self) -> None:
        self.assertEqual("", _erro())

    def test_rodada_ja_gerada_e_recusada(self) -> None:
        """Era aceito e nunca aplicado: o pareamento daquela rodada ja esta feito."""
        erro = _erro(round_status="generated")
        self.assertIn("ja foi gerada", erro)
        self.assertIn("nunca aplicado", erro)

    def test_rodada_fechada_e_recusada(self) -> None:
        erro = _erro(round_status="closed")
        self.assertIn("ja foi fechada", erro)

    def test_jogador_inativo_e_recusado_com_o_motivo(self) -> None:
        """O descarte silencioso vira recusa explicada, na hora do pedido."""
        erro = _erro(player_active=False)
        self.assertIn("inativo", erro)
        self.assertIn("descartado", erro)

    def test_rodada_alem_do_torneio_e_recusada(self) -> None:
        self.assertIn("nao existe rodada 9", _erro(round_number=9, rounds_count=5))

    def test_tipo_invalido_e_recusado(self) -> None:
        self.assertIn("Tipo de bye invalido", _erro(bye_type="X"))

    def test_rodada_zero_e_recusada(self) -> None:
        self.assertIn("Informe a rodada", _erro(round_number=0))

    def test_sem_configuracao_nao_ha_limite(self) -> None:
        """Padrao = comportamento historico: torneio antigo nao muda de regra."""
        muitos = [{"bye_type": "H", "round_number": r} for r in range(1, 6)]
        self.assertEqual("", _erro(existing_byes=muitos))

    def test_limite_por_jogador(self) -> None:
        politica = ByePolicy(max_requested_byes=2)
        dois = [{"bye_type": "H", "round_number": 1}, {"bye_type": "F", "round_number": 3}]
        erro = _erro(policy=politica, existing_byes=dois)
        self.assertIn("ja usou 2 de 2", erro)
        self.assertEqual("", _erro(policy=politica, existing_byes=dois[:1]))

    def test_o_bye_de_zero_ponto_nao_conta_para_o_limite(self) -> None:
        """Limitar o `Z` puniria quem AVISOU que faltaria, em vez de sumir."""
        politica = ByePolicy(max_requested_byes=1)
        zeros = [{"bye_type": "Z", "round_number": 1}, {"bye_type": "Z", "round_number": 2}]
        self.assertEqual("", _erro(policy=politica, existing_byes=zeros))
        self.assertEqual(0, count_limited(zeros))

    def test_corrigir_o_bye_da_propria_rodada_nao_esbarra_no_limite(self) -> None:
        politica = ByePolicy(max_requested_byes=1)
        mesmo = [{"bye_type": "H", "round_number": 2}]
        self.assertIn("ja usou", _erro(policy=politica, existing_byes=mesmo))
        self.assertEqual(
            "",
            _erro(policy=politica, existing_byes=mesmo, editing_existing=True),
        )

    def test_ultima_rodada_permitida(self) -> None:
        """O meio-ponto na rodada final decide classificacao sem jogo."""
        politica = ByePolicy(last_requested_bye_round=3)
        self.assertEqual("", _erro(policy=politica, round_number=3))
        self.assertIn("ate a rodada 3", _erro(policy=politica, round_number=4))

    def test_a_politica_se_descreve(self) -> None:
        self.assertEqual("", ByePolicy().describe())
        self.assertEqual(
            "maximo de 2 byes por jogador; ultima rodada permitida: 7",
            ByePolicy(max_requested_byes=2, last_requested_bye_round=7).describe(),
        )
        self.assertEqual("maximo de 1 bye por jogador", ByePolicy(max_requested_byes=1).describe())

    def test_configuracao_invalida_vira_sem_limite(self) -> None:
        politica = ByePolicy.from_settings({"max_requested_byes": "abc", "last_requested_bye_round": -3})
        self.assertFalse(politica.has_limits)

    def test_o_aviso_do_descarte_nomeia_quem_ficou_de_fora(self) -> None:
        self.assertEqual("", discarded_warning([]))
        aviso = discarded_warning([{"player_name": "Ana"}, {"player_name": "Bruno"}])
        self.assertIn("2 byes solicitados foram descartados", aviso)
        self.assertIn("Ana", aviso)
        self.assertIn("Bruno", aviso)


class ByeNoServicoTest(CoreServiceTestCase):
    """O caminho inteiro, com banco: pedir, recusar, gerar e avisar."""

    def setUp(self) -> None:
        super().setUp()
        self.player_ids = self._create_players(6)

    def test_pedido_valido_e_registrado_com_auditoria(self) -> None:
        self.service.request_bye(self.tournament_id, self.player_ids[0], 1, "H", "viagem")

        byes = self.db.list_requested_byes(self.tournament_id)
        self.assertEqual(1, len(byes))
        self.assertEqual("H", byes[0]["bye_type"])
        acoes = {
            evento["action"]
            for evento in self.db.list_audit_events(self.tournament_id, limit=50)
        }
        self.assertIn("requested_bye_registered", acoes)

    def test_pedido_para_rodada_ja_gerada_e_recusado(self) -> None:
        self.service.generate_next_round(self.tournament_id)

        with self.assertRaisesRegex(AppError, "ja foi gerada"):
            self.service.request_bye(self.tournament_id, self.player_ids[0], 1)

    def test_pedido_de_jogador_inativo_e_recusado(self) -> None:
        self.db.set_player_active(self.player_ids[0], False)

        with self.assertRaisesRegex(AppError, "inativo"):
            self.service.request_bye(self.tournament_id, self.player_ids[0], 1)

    def test_limite_configurado_e_aplicado(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"max_requested_byes": 1})
        self.service.request_bye(self.tournament_id, self.player_ids[0], 1)

        with self.assertRaisesRegex(AppError, "ja usou 1 de 1"):
            self.service.request_bye(self.tournament_id, self.player_ids[0], 2)

    def test_ultima_rodada_configurada_e_aplicada(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"last_requested_bye_round": 2})

        self.service.request_bye(self.tournament_id, self.player_ids[0], 2)
        with self.assertRaisesRegex(AppError, "ate a rodada 2"):
            self.service.request_bye(self.tournament_id, self.player_ids[1], 3)

    def test_jogador_de_outro_torneio_e_recusado(self) -> None:
        outro = self.tournament_service.create_tournament(
            {"name": "Outro", "rounds_count": "3", "bye_points": "1"}
        )
        with self.assertRaisesRegex(AppError, "Jogador nao encontrado"):
            self.service.request_bye(outro, self.player_ids[0], 1)

    def test_o_resumo_da_politica_sai_para_a_tela(self) -> None:
        self.assertEqual("", self.service.bye_policy_summary(self.tournament_id))
        self.db.save_tournament_settings(
            self.tournament_id, {"max_requested_byes": 2, "last_requested_bye_round": 4}
        )
        self.assertEqual(
            "maximo de 2 byes por jogador; ultima rodada permitida: 4",
            self.service.bye_policy_summary(self.tournament_id),
        )

    def test_o_bye_solicitado_continua_valendo_na_geracao(self) -> None:
        """Guarda: a politica nao pode ter quebrado o que ja funcionava."""
        self.service.request_bye(self.tournament_id, self.player_ids[0], 1, "H")

        round_data = self.service.generate_next_round(self.tournament_id)
        mesas = self.db.get_pairings_for_round(int(round_data["id"]))
        # Com 6 jogadores e 1 bye solicitado sobram 5 para parear, entao ha
        # tambem um bye ALOCADO — o que importa aqui e o solicitado, com o tipo
        # que o jogador pediu.
        solicitado = [
            item
            for item in mesas
            if item["is_bye"] and int(item["white_player_id"]) == self.player_ids[0]
        ]

        self.assertEqual(1, len(solicitado))
        self.assertEqual("H", solicitado[0]["result"])

    def test_bye_de_jogador_desativado_depois_do_pedido_avisa(self) -> None:
        """O pedido era valido quando entrou; o jogador saiu depois.

        E o unico caminho que ainda descarta — e agora ele avisa, em vez de
        sumir. A rodada continua sendo gerada: barrar por um pedido que ficou
        para tras seria trocar um silencio ruim por uma parada pior.
        """
        self.service.request_bye(self.tournament_id, self.player_ids[0], 1, "H")
        self.db.set_player_active(self.player_ids[0], False)

        round_data = self.service.generate_next_round(self.tournament_id)

        self.assertTrue(self.db.get_pairings_for_round(int(round_data["id"])))
        eventos = [
            evento
            for evento in self.db.list_audit_events(self.tournament_id, limit=50)
            if evento["action"] == "requested_bye_discarded"
        ]
        self.assertEqual(1, len(eventos))
        chaves = {
            item["issue_key"]
            for item in self.service.arbitration_issues(self.tournament_id)["issues"]
        }
        self.assertTrue(
            any(chave.startswith("bye:discarded:") for chave in chaves),
            f"pendencia de bye descartado nao apareceu: {chaves}",
        )


if __name__ == "__main__":
    unittest.main()
