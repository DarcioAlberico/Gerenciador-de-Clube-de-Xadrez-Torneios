"""RG2-15 — a categoria do jogador acompanha o edital e as datas (com a D3).

A categoria era calculada só ao criar/editar o jogador e gravada; regravar o
edital ou mudar a data de referência não mexia em quem já estava inscrito. E a
inscrição a partir do cadastro repassava a categoria do membro (calculada no
ano corrente, com as faixas padrão), que o cálculo tratava como manual.

D3 (decidida pelo dono em 2026-11-28): depois da 1ª rodada fechada, recalcula
com confirmação e auditoria; recusa se houver certificado emitido do torneio ou
se o torneio estiver encerrado. Os retratos por rodada ficam com a categoria da
época.
"""
from __future__ import annotations

import unittest

from src.services.constants import AppError
from src.services.tournament_configuration import TIPO_RECALCULO_CATEGORIAS
from tests.support.core_service_base import CoreServiceTestCase

EDITAL = [
    {"name": "Sub-11", "kind": "age", "max_value": 11, "position": 0},
    {"name": "Sub-13", "kind": "age", "max_value": 13, "position": 1},
    {"name": "Feminino", "kind": "sex", "sex": "F", "position": 2},
]


class CategoriaDerivadaTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.db.update_tournament_details(
            self.tournament_id, name="Torneio teste", rounds_count=5, start_date="2026-03-01"
        )

    def test_inscrita_antes_do_edital_acompanha_o_edital(self) -> None:
        ana = self.db.create_player(self.tournament_id, name="Ana", birth_date="2015-03-01", sex="F", rating=1350)
        self.tournament_service.replace_categories(self.tournament_id, EDITAL)
        self.assertEqual("Sub-11; Feminino", self.db.get_player(ana)["categories"])
        self.assertEqual("Sub-11", self.db.get_player(ana)["category"])

    def test_inscrita_do_cadastro_cai_na_categoria_do_edital(self) -> None:
        self.tournament_service.replace_categories(self.tournament_id, EDITAL[1:])
        membro = self.member_service.create_member(
            {"name": "Bia", "member_type": "aluno", "status": "active", "birth_date": "2014-05-01", "sex": "F"}
        )
        bia = self.member_service.register_member_in_tournament(self.tournament_id, membro, allow_out_of_scope=True)
        self.assertEqual("Sub-13", self.db.get_player(bia)["category"])
        self.assertIn("Feminino", self.db.get_player(bia)["categories"])

    def test_categoria_escrita_a_mao_fica(self) -> None:
        caio = self.db.create_player(self.tournament_id, name="Caio", birth_date="2015-01-01", category="Convidado")
        self.tournament_service.replace_categories(self.tournament_id, EDITAL)
        self.assertEqual("Convidado", self.db.get_player(caio)["category"])

    def test_mudar_a_data_de_referencia_recalcula(self) -> None:
        self.tournament_service.replace_categories(self.tournament_id, EDITAL)
        dani = self.db.create_player(self.tournament_id, name="Dani", birth_date="2014-12-31")
        self.assertEqual("Sub-13", self.db.get_player(dani)["category"])
        torneio = self.db.get_tournament(self.tournament_id)
        self.tournament_service.save_profile(
            self.tournament_id,
            {"name": torneio["name"], "rounds_count": 5, "start_date": "2026-03-01"},
            {"category_reference_date": "2025-12-31"},
            [],
        )
        self.assertEqual("Sub-11", self.db.get_player(dani)["category"])


class GanchoDaD3Test(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.jogadores = []
        for indice, nascimento in enumerate(("2015-03-01", "2014-03-01", "2013-03-01", "2012-03-01")):
            self.jogadores.append(
                self.db.create_player(self.tournament_id, name=f"J{indice}", birth_date=nascimento, rating=1500 + indice)
            )
        rodada = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(rodada["id"])
        self.service.close_round(self.tournament_id, rodada["id"])

    def test_com_rodada_fechada_pede_confirmacao(self) -> None:
        with self.assertRaisesRegex(AppError, "rodada"):
            self.tournament_service.replace_categories(self.tournament_id, EDITAL)
        self.assertEqual([], self.db.list_tournament_categories(self.tournament_id))

    def test_confirmado_recalcula_audita_e_nao_mexe_no_retrato(self) -> None:
        retratos_antes = self.db.list_standings_snapshots(self.tournament_id)
        self.tournament_service.replace_categories(self.tournament_id, EDITAL, confirmed=True)
        self.assertEqual("Sub-11", self.db.get_player(self.jogadores[0])["category"])
        (evento,) = self.db.list_audit_events(self.tournament_id, action="player_categories_recalculated")
        self.assertIn("players", evento["after_json"])
        self.assertEqual(retratos_antes, self.db.list_standings_snapshots(self.tournament_id))

    def test_o_plano_da_tela_traz_a_confirmacao(self) -> None:
        tipos = self.tournament_service.plan_category_change(self.tournament_id, EDITAL)
        self.assertEqual([TIPO_RECALCULO_CATEGORIAS], [c.tipo for c in tipos])

    def test_regravar_o_mesmo_edital_nao_pede_nada(self) -> None:
        self.assertEqual([], self.tournament_service.plan_category_change(self.tournament_id, []))
        self.tournament_service.replace_categories(self.tournament_id, [])

    def test_com_certificado_emitido_recusa(self) -> None:
        self.db.create_certificate_issuances(
            [{"verification_code": "ABC123", "context_type": "tournament", "source_id": self.tournament_id,
              "recipient_name": "J0", "certificate_type": "participation"}]
        )
        with self.assertRaisesRegex(AppError, "certificado"):
            self.tournament_service.replace_categories(self.tournament_id, EDITAL, confirmed=True)

    def test_torneio_encerrado_recusa(self) -> None:
        self.db.update_tournament_status(self.tournament_id, "finished")
        with self.assertRaisesRegex(AppError, "encerrado"):
            self.tournament_service.replace_categories(self.tournament_id, EDITAL, confirmed=True)


if __name__ == "__main__":
    unittest.main()
