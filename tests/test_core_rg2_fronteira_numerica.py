"""F1.1 — fronteira numérica nos serviços (RG2-46, RG2-14, RG2-27, RG2-10).

Cada teste chama o serviço como a tela chama e confere o que fica gravado.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from src.services.constants import AppError
from src.services.prize_service import validated_prizes
from tests.support.core_service_base import CoreServiceTestCase


class DinheiroTest(CoreServiceTestCase):
    """RG2-46 — o ponto de milhar não vira decimal."""

    def test_premio_1000_nao_vira_um_real(self) -> None:
        (premio,) = validated_prizes([{"kind": "overall", "label": "1º lugar", "rank_from": 1, "amount": "1.000"}])
        self.assertEqual(1000.0, premio["amount"])

    def test_plano_de_mensalidade(self) -> None:
        for texto, esperado in (("1.500", 1500.0), ("1.500,50", 1500.5), ("1,5", 1.5), ("120,50", 120.5)):
            with self.subTest(texto=texto):
                plano = self.finance_service.save_plan({"name": f"Plano {texto}", "amount": texto})
                self.assertEqual(esperado, self.db.get_membership_plan(plano)["amount"])

    def test_valor_de_aquisicao_do_inventario(self) -> None:
        clube = self.club_service.save_profile({"name": "Clube", "kind": "club", "active": 1}, club_id=None)
        item = self.inventory_service.save_item(
            {"club_id": clube, "code": "T-1", "name": "Tabuleiro", "item_type": "boards",
             "quantity_total": "1", "condition_status": "good", "acquisition_value": "1.500,50"}
        )
        self.assertEqual(1500.5, self.db.get_inventory_item(item)["acquisition_value"])

    def test_nan_inf_e_ambiguo_recusados(self) -> None:
        for texto in ("nan", "inf", "1.5000"):
            with self.subTest(texto=texto):
                with self.assertRaises(AppError):
                    validated_prizes([{"kind": "overall", "label": "1º lugar", "rank_from": 1, "amount": texto}])
                with self.assertRaises(AppError):
                    self.finance_service.save_plan({"name": "P", "amount": texto})
        with self.assertRaisesRegex(AppError, r'"1,5" ou "1\.500"'):
            self.finance_service.save_plan({"name": "P", "amount": "1.5000"})

    def test_salvar_de_novo_o_valor_que_a_tela_mostra(self) -> None:
        plano = self.finance_service.save_plan({"name": "Mensal", "amount": "1.500"})
        mostrado = str(self.db.get_membership_plan(plano)["amount"])
        self.finance_service.save_plan({"name": "Mensal", "amount": mostrado}, plan_id=plano)
        self.assertEqual(1500.0, self.db.get_membership_plan(plano)["amount"])

    def test_taxa_de_rating_com_milhar(self) -> None:
        torneio = self.tournament_service.create_tournament_from_profile(
            {"name": "Com taxa", "rounds_count": 5}, {"rating_fee_fide": "1.200"}, []
        )
        self.assertEqual(1200.0, self.db.get_tournament_settings(torneio)["rating_fee_fide"])


class RatingImportadoTest(CoreServiceTestCase):
    """RG2-14 — "1.850" importa 1850; texto inválido é erro da linha, não 0."""

    def _importar(self, conteudo: str) -> dict:
        caminho = Path(self.temp_dir.name) / "jogadores.csv"
        caminho.write_text(conteudo, encoding="utf-8")
        return self.import_service.import_players_csv(self.tournament_id, caminho)

    def _jogador(self, nome: str) -> dict | None:
        return next((p for p in self.db.list_players(self.tournament_id) if p["name"] == nome), None)

    def test_milhar_com_ponto_e_espaco(self) -> None:
        resultado = self._importar(
            "nome;rating_nacional;rating_internacional\nAna;1.850;1 790\n"
        )
        self.assertEqual(1, resultado["imported"], resultado["errors"])
        ana = self._jogador("Ana")
        self.assertEqual(1850, ana["national_rating"])
        self.assertEqual(1790, ana["international_rating"])
        self.assertEqual(1850, ana["rating"])

    def test_coluna_rating_tambem(self) -> None:
        self._importar("nome;rating\nBia;2.010\n")
        self.assertEqual(2010, self._jogador("Bia")["rating"])

    def test_texto_invalido_e_erro_da_linha_e_o_jogador_nao_entra_com_zero(self) -> None:
        for coluna in ("rating_nacional", "rating_internacional", "rating"):
            with self.subTest(coluna=coluna):
                nome = f"Caio {coluna}"
                resultado = self._importar(f"nome;{coluna}\n{nome};abc\n")
                self.assertEqual(0, resultado["imported"])
                self.assertTrue(any("abc" in erro and "Linha 2" in erro for erro in resultado["errors"]), resultado)
                self.assertIsNone(self._jogador(nome))

    def test_vazio_continua_sem_rating(self) -> None:
        resultado = self._importar("nome;rating_nacional\nDani;\n")
        self.assertEqual(1, resultado["imported"])
        self.assertEqual(0, self._jogador("Dani")["rating"])


class PontosTest(CoreServiceTestCase):
    """RG2-27 — bye e entrada tardia só na faixa {0; 0,5; 1}."""

    def test_bye_fora_da_faixa_recusado_com_a_faixa_na_mensagem(self) -> None:
        for texto in ("inf", "0,3", "7", "nan"):
            with self.subTest(texto=texto), self.assertRaisesRegex(AppError, "0; 0,5; 1"):
                self.tournament_service.create_tournament({"name": "B", "rounds_count": 5, "bye_points": texto})

    def test_entrada_tardia_fora_da_faixa_recusada(self) -> None:
        for texto in ("-1", "inf", "0,25", "nan"):
            with self.subTest(texto=texto), self.assertRaisesRegex(AppError, "0; 0,5; 1"):
                self.tournament_service.create_tournament_from_profile(
                    {"name": "T", "rounds_count": 5}, {"late_entry_points": texto}, []
                )

    def test_valores_validos_com_ponto_ou_virgula(self) -> None:
        for texto, esperado in (("0,5", 0.5), ("0.5", 0.5), ("1", 1.0), ("0", 0.0)):
            with self.subTest(texto=texto):
                torneio = self.tournament_service.create_tournament(
                    {"name": f"V {texto}", "rounds_count": 5, "bye_points": texto}
                )
                self.assertEqual(esperado, self.db.get_tournament(torneio)["bye_points"])

    def test_pontos_de_equipe_multiplo_de_meio(self) -> None:
        with self.assertRaises(AppError):
            self.tournament_service.create_tournament_from_profile(
                {"name": "E", "rounds_count": 5}, {"team_match_win_points": "inf"}, []
            )


class ZeroNaoViraUmTest(CoreServiceTestCase):
    """RG2-10 — o 0 gravado é 0; a divisão é atômica e copia os ratings rápidos."""

    def test_empate_de_equipe_salvo_como_zero_e_lido_zero(self) -> None:
        self.db.save_tournament_settings(
            self.tournament_id, {"team_match_win_points": 0, "team_match_draw_points": 0}
        )
        ajustes = self.db.get_tournament_settings(self.tournament_id)
        self.assertEqual(0.0, ajustes["team_match_draw_points"])
        self.assertEqual(0.0, ajustes["team_match_win_points"])

    def _mae_com_bye_zero(self) -> int:
        mae = self.db.create_tournament("Mãe", rounds_count=5, bye_points=0.0)
        for indice in range(4):
            self.db.create_player(
                mae, name=f"J{indice}", rating=1500 + indice,
                rapid_rating=1400 + indice, blitz_rating=1300 + indice, games_played=10 + indice,
            )
        return mae

    def test_dividir_com_bye_zero_mantem_zero_e_copia_ratings_rapidos(self) -> None:
        filhos = self.tournament_service.split_tournament(self._mae_com_bye_zero(), 2)
        for filho in filhos:
            self.assertEqual(0.0, self.db.get_tournament(filho)["bye_points"])
            for jogador in self.db.list_players(filho, active_only=False):
                indice = int(jogador["name"][1:])
                self.assertEqual(1400 + indice, jogador["rapid_rating"])
                self.assertEqual(1300 + indice, jogador["blitz_rating"])
                self.assertEqual(10 + indice, jogador["games_played"])

    def test_falha_no_segundo_grupo_nao_deixa_filho_nenhum(self) -> None:
        mae = self._mae_com_bye_zero()
        antes = {t["id"] for t in self.db.list_tournaments()}
        original = self.db.create_tournament
        chamadas = {"n": 0}

        def falha_no_segundo(*args, **kwargs):
            chamadas["n"] += 1
            if chamadas["n"] == 2:
                raise RuntimeError("falha injetada")
            return original(*args, **kwargs)

        with mock.patch.object(self.db, "create_tournament", side_effect=falha_no_segundo):
            with self.assertRaises(RuntimeError):
                self.tournament_service.split_tournament(mae, 2)
        self.assertEqual(antes, {t["id"] for t in self.db.list_tournaments()})


if __name__ == "__main__":
    unittest.main()
