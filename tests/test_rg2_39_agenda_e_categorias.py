"""RG2-39 — agenda e categorias recusam o impossível. Um teste por linha do item.

1. Categoria de idade "15 a 12", de sexo sem sexo e de marca sem marca eram
   aceitas — e nunca casavam com ninguém, caladas.
2. A "Folga" da agenda só existia no banco e na tela: o gerador de agenda a
   ignorava.
3. A agenda aceitava a R3 antes da R2.
4. ``update_tournament_details`` apagava a agenda acima do novo total sem
   perguntar — a proteção morava só no serviço, e só olhava a agenda que a
   tela mandou.
5. Sem data de início, o ano de referência da idade cai na data de criação: o
   torneio criado em dezembro para janeiro calcula a idade do ano errado.
"""
from __future__ import annotations

from src.services.constants import AppError
from src.services.tournament_service import TournamentService
from tests.support.core_service_base import CoreServiceTestCase


class CategoriasImpossiveisTest(CoreServiceTestCase):
    def _recusa(self, categoria: dict, trecho: str) -> None:
        with self.assertRaisesRegex(AppError, trecho):
            self.tournament_service.replace_categories(self.tournament_id, [categoria])
        self.assertEqual([], self.db.list_tournament_categories(self.tournament_id))

    def test_idade_invertida(self) -> None:
        self._recusa({"name": "Juvenil", "kind": "age", "min_value": 15, "max_value": 12}, "Juvenil")

    def test_rating_invertido(self) -> None:
        self._recusa({"name": "Faixa B", "kind": "rating", "min_value": 1800, "max_value": 1400}, "Faixa B")

    def test_sexo_em_branco(self) -> None:
        self._recusa({"name": "Damas", "kind": "sex", "sex": ""}, "Damas")

    def test_marca_vazia(self) -> None:
        self._recusa({"name": "Sócios", "kind": "tag", "tag": ""}, "Sócios")

    def test_faixa_aberta_de_um_lado_continua_valendo(self) -> None:
        self.tournament_service.replace_categories(
            self.tournament_id, [{"name": "S50+", "kind": "age", "min_value": 50}]
        )
        self.assertEqual(1, len(self.db.list_tournament_categories(self.tournament_id)))


class GeradorRespeitaAFolgaTest(CoreServiceTestCase):
    ARGS = dict(rounds_count=4, start_date="2026-03-01", first_time="09:00",
                round_duration_minutes=60, break_minutes=0, rounds_per_day=2)

    def test_folga_depois_da_r2_pula_um_dia(self) -> None:
        agenda = TournamentService.generate_round_schedule(**self.ARGS, rest_after_rounds={2})
        self.assertEqual(
            ["2026-03-01", "2026-03-01", "2026-03-03", "2026-03-03"], [item["date"] for item in agenda]
        )
        self.assertEqual(["09:00", "10:00", "09:00", "10:00"], [item["time"] for item in agenda])

    def test_folga_no_meio_do_dia_comeca_o_dia_seguinte_a_folga(self) -> None:
        agenda = TournamentService.generate_round_schedule(**self.ARGS, rest_after_rounds={1})
        self.assertEqual(
            ["2026-03-01", "2026-03-03", "2026-03-03", "2026-03-04"], [item["date"] for item in agenda]
        )

    def test_sem_folga_como_antes(self) -> None:
        agenda = TournamentService.generate_round_schedule(**self.ARGS)
        self.assertEqual(
            ["2026-03-01", "2026-03-01", "2026-03-02", "2026-03-02"], [item["date"] for item in agenda]
        )


class AgendaEmOrdemTest(CoreServiceTestCase):
    def _salvar(self, agenda: list[dict]) -> None:
        torneio = self.db.get_tournament(self.tournament_id)
        self.tournament_service.save_profile(
            self.tournament_id,
            {"name": torneio["name"], "rounds_count": 3, "competition_type": "individual"},
            {},
            agenda,
        )

    def test_r3_antes_da_r2_e_recusada(self) -> None:
        with self.assertRaisesRegex(AppError, "3"):
            self._salvar([
                {"round_number": 1, "date": "2026-03-01"},
                {"round_number": 2, "date": "2026-03-03"},
                {"round_number": 3, "date": "2026-03-02"},
            ])

    def test_no_mesmo_dia_a_hora_tambem_conta(self) -> None:
        with self.assertRaisesRegex(AppError, "3"):
            self._salvar([
                {"round_number": 2, "date": "2026-03-01", "time": "14:00"},
                {"round_number": 3, "date": "2026-03-01", "time": "09:00"},
            ])

    def test_mesma_data_e_rodada_sem_data_passam(self) -> None:
        self._salvar([
            {"round_number": 1, "date": "2026-03-01", "time": "09:00"},
            {"round_number": 2, "date": "2026-03-01", "time": "14:00"},
            {"round_number": 3, "date": ""},
        ])
        self.assertEqual(
            ["2026-03-01", "2026-03-01", ""],
            [item["date"] for item in self.db.list_round_schedule(self.tournament_id)],
        )


class AgendaAcimaDoTotalTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.db.update_tournament_details(self.tournament_id, name="Torneio teste", rounds_count=5)
        self.db.save_round_schedule(
            self.tournament_id, [{"round_number": 5, "date": "2026-03-05", "time": "09:00"}]
        )

    def _datas(self) -> dict[int, str]:
        with self.db.connect() as conexao:
            linhas = conexao.execute(
                "SELECT round_number, date FROM round_schedule WHERE tournament_id = ?", (self.tournament_id,)
            ).fetchall()
        return {int(linha["round_number"]): str(linha["date"]) for linha in linhas}

    def test_o_banco_nao_apaga_data_marcada_sem_ordem_explicita(self) -> None:
        with self.assertRaises(ValueError):
            self.db.update_tournament_details(self.tournament_id, name="Torneio teste", rounds_count=3)
        self.assertEqual("2026-03-05", self._datas()[5])
        self.assertEqual(5, self.db.get_tournament(self.tournament_id)["rounds_count"])

    def test_com_ordem_explicita_apaga(self) -> None:
        self.db.update_tournament_details(
            self.tournament_id, name="Torneio teste", rounds_count=3, discard_schedule_above=True
        )
        self.assertNotIn(5, self._datas())

    def test_o_servico_pergunta_mesmo_que_a_tela_nao_mande_a_rodada_5(self) -> None:
        with self.assertRaisesRegex(AppError, "5"):
            self.tournament_service.save_profile(
                self.tournament_id,
                {"name": "Torneio teste", "rounds_count": 3, "competition_type": "individual"},
                {},
                [{"round_number": 1, "date": ""}],
            )
        self.assertEqual("2026-03-05", self._datas()[5])


class AnoDeReferenciaTest(CoreServiceTestCase):
    def test_sem_inicio_nem_data_de_referencia_avisa(self) -> None:
        aviso = self.tournament_service.category_reference_warning(self.tournament_id)
        self.assertIn("data de início", aviso)

    def test_com_inicio_nao_avisa(self) -> None:
        with self.db.connect() as conexao:
            conexao.execute("UPDATE tournaments SET start_date = '2027-01-10' WHERE id = ?", (self.tournament_id,))
        self.assertEqual("", self.tournament_service.category_reference_warning(self.tournament_id))

    def test_com_data_de_referencia_nao_avisa(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"category_reference_date": "2027"})
        self.assertEqual("", self.tournament_service.category_reference_warning(self.tournament_id))
