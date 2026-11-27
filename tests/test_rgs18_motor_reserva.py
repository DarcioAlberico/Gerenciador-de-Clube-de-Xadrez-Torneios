"""RGS-18 (F3.7) — motor reserva (``fide_dutch``): três defeitos de regra e o rótulo.

O motor próprio é RESERVA: não segue o holandês completo (C.04.3) e não é
homologado pela FIDE. Não se reescreve aqui — corrigem-se três desvios de regra
que ele tinha mesmo no que já faz, e ele passa a se apresentar como reserva.

1. **PAB da R1** (C.04.3, A.? / C.04.1 c): o bye vai ao ÚLTIMO da ordem
   inicial. Com ratings empatados ia ao primeiro do alfabeto — o cabeça de
   chave.
2. **W.O. impede o PAB** (C.04.1 (d)): quem já marcou, sem jogar, o ponto de
   uma vitória — PAB, bye de ponto inteiro (F) ou vitória por W.O. — não
   recebe o PAB. O W.O. a favor não contava.
3. **Cor por E.3–E.5** (C.04.3 E): no empate das preferências, alterna-se a
   partir da última rodada em que tiveram cores diferentes (E.3); senão,
   vale a preferência do MAIS BEM CLASSIFICADO — pontos, depois número de
   pareamento (E.4); senão, número ímpar recebe a cor inicial (E.5). O motor
   dava brancas ao maior rating.

Antes de mexer: caracterização do que a seção 8 da ESPEC manda preservar
(byes F/H/Z/U, W.O. fora de confronto e de cor, preferências de cor).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.services.constants import PAIRING_SYSTEMS, RESERVE_ENGINE_LABEL
from src.services.pairing.constraints import choose_colors, color_preference, is_color_valid_fide
from src.services.pairing.fide_dutch import first_round_pairings, swiss_pairings
from src.services.pairing.histories import bye_player_ids, color_histories, played_pairs
from src.services.pairing_service import PairingService


def _p(pid: int, nome: str, rating: int = 1500) -> dict:
    return {"id": pid, "name": nome, "rating": rating, "title": ""}


def _mesa(branco: int, preto: int | None, resultado: str, bye: bool = False) -> dict:
    return {"white_player_id": branco, "black_player_id": preto, "result": resultado, "is_bye": int(bye)}


class CaracterizacaoSecao8Test(unittest.TestCase):
    """O que já estava certo e não pode mudar (ESPEC §8, itens 3, 4 e 6)."""

    def test_byes_que_impedem_e_que_nao_impedem_o_pab(self) -> None:
        historico = [
            _mesa(1, None, "BYE", bye=True),
            _mesa(2, None, "U", bye=True),
            _mesa(3, None, "F", bye=True),
            _mesa(4, None, "H", bye=True),
            _mesa(5, None, "Z", bye=True),
        ]
        self.assertEqual({1, 2, 3}, bye_player_ids(historico))

    def test_wo_nao_conta_como_confronto_nem_como_cor(self) -> None:
        historico = [_mesa(1, 2, "1F-0F"), _mesa(3, 4, "1-0")]
        self.assertEqual({frozenset((3, 4))}, played_pairs(historico))
        cores = color_histories(historico)
        self.assertEqual([], cores[1])
        self.assertEqual(["W"], cores[3])

    def test_preferencias_de_cor(self) -> None:
        cores = {1: ["W", "B"], 2: ["W", "W", "B"], 3: ["W", "B", "B"], 4: ["W", "W"], 5: []}
        self.assertEqual(("W", "mild"), (color_preference(1, cores).due_color, color_preference(1, cores).strength))
        self.assertEqual(("B", "strong"), (color_preference(2, cores).due_color, color_preference(2, cores).strength))
        self.assertEqual(("W", "absolute"), (color_preference(3, cores).due_color, color_preference(3, cores).strength))
        self.assertEqual(("B", "absolute"), (color_preference(4, cores).due_color, color_preference(4, cores).strength))
        self.assertEqual((None, "none"), (color_preference(5, cores).due_color, color_preference(5, cores).strength))
        self.assertFalse(is_color_valid_fide(4, "W", cores))  # três iguais seguidas
        self.assertFalse(is_color_valid_fide(2, "W", {2: ["W", "W", "B", "W"]}))  # diferença +2... e mais

    def test_preferencia_diferente_resolve_sem_desempate(self) -> None:
        cores = {1: ["W", "W"], 2: ["B", "B"]}
        self.assertEqual((2, 1), choose_colors(_p(1, "A", 2000), _p(2, "B", 1000), cores))


class PabDaPrimeiraRodadaTest(unittest.TestCase):
    def test_ratings_empatados_o_bye_vai_ao_ultimo_da_ordem_inicial(self) -> None:
        jogadores = [_p(1, "Alves"), _p(2, "Barros"), _p(3, "Costa")]
        (bye,) = [m for m in first_round_pairings(jogadores) if m["is_bye"]]
        self.assertEqual(3, bye["white_player_id"])

    def test_com_ratings_diferentes_continua_o_menor_rating(self) -> None:
        jogadores = [_p(1, "Alves", 1400), _p(2, "Barros", 1600), _p(3, "Costa", 1500)]
        (bye,) = [m for m in first_round_pairings(jogadores) if m["is_bye"]]
        self.assertEqual(1, bye["white_player_id"])


class WoImpedePabTest(unittest.TestCase):
    def test_vitoria_por_wo_impede_o_pab(self) -> None:
        historico = [_mesa(1, 2, "1F-0F"), _mesa(3, 4, "0F-1F"), _mesa(5, 6, "0F-0F")]
        self.assertEqual({1, 4}, bye_player_ids(historico))

    def test_vencedor_por_wo_nao_recebe_o_pab_no_pareamento(self) -> None:
        """Três com 1,0; o de menor rating venceu por W.O. e seria o PAB natural.

        A venceu de pretas e B de brancas: A-B atende as duas preferências e
        empata em qualidade com B-C, então o desempate pelo menor rating
        mandava o PAB para C — que já tinha o ponto do W.O.
        """
        jogadores = [_p(1, "A", 2000), _p(2, "B", 1900), _p(3, "C", 1800)]
        historico = [_mesa(4, 1, "0-1"), _mesa(2, 5, "1-0"), _mesa(3, 6, "1F-0F")]
        classificacao = {
            pid: {"points": 1.0, "position": posicao}
            for posicao, pid in enumerate((1, 2, 3), start=1)
        }
        mesas = swiss_pairings(
            jogadores,
            classificacao,
            color_histories(historico),
            {},
            played_pairs(historico),
            bye_player_ids(historico),
            max_exhaustive_pairing_players=16,
            repeat_pairing_penalty=1_000_000,
            score_group_float_penalty=10_000,
            score_diff_penalty=1_000,
        )
        (pab,) = [m for m in mesas if m["is_bye"]]
        self.assertNotEqual(3, pab["white_player_id"])


class CorE3E5Test(unittest.TestCase):
    """Empate das preferências: E.3, depois E.4, depois E.5 — nunca o rating."""

    def test_e4_preferencia_do_mais_bem_classificado(self) -> None:
        # Os dois querem brancas (leve); o mais bem classificado (mais pontos)
        # tem o MENOR rating.
        cores = {1: ["W", "B"], 2: ["W", "B"]}
        ranking = {1: (-2.0, 3), 2: (-1.5, 1)}
        self.assertEqual((1, 2), choose_colors(_p(1, "A", 1900), _p(2, "B", 2000), cores, ranking))

    def test_e3_alterna_a_partir_da_ultima_rodada_com_cores_diferentes(self) -> None:
        # Ambos devem brancas (leve). Na R2 o 1 teve pretas e o 2 brancas: o 1
        # recebe brancas, mesmo o 2 sendo o mais bem classificado e o de maior
        # rating.
        cores = {1: ["W", "B", "W", "B"], 2: ["B", "W", "W", "B"]}
        ranking = {1: (-2.0, 4), 2: (-2.0, 1)}
        self.assertEqual((1, 2), choose_colors(_p(1, "A", 1800), _p(2, "B", 2000), cores, ranking))

    def test_e5_sem_preferencia_numero_par_recebe_a_cor_oposta_a_inicial(self) -> None:
        # Sem histórico de cor nenhum. O mais bem classificado tem o nº 2 (par):
        # recebe pretas, embora tenha o maior rating.
        ranking = {1: (-1.0, 2), 2: (-1.0, 5)}
        self.assertEqual((2, 1), choose_colors(_p(1, "A", 2000), _p(2, "B", 1900), {}, ranking))

    def test_e5_numero_impar_recebe_a_cor_inicial(self) -> None:
        ranking = {1: (-1.0, 3), 2: (-1.0, 4)}
        self.assertEqual((1, 2), choose_colors(_p(1, "A", 1900), _p(2, "B", 2000), {}, ranking))


class RotuloTest(unittest.TestCase):
    def test_seletor_rotula_o_motor_proprio_como_reserva(self) -> None:
        self.assertEqual("motor reserva — não homologado FIDE", RESERVE_ENGINE_LABEL)
        for chave in ("fide_dutch", "dubov", "burstein", "lim", "custom_authorized"):
            self.assertIn(RESERVE_ENGINE_LABEL, PAIRING_SYSTEMS[chave])
        self.assertNotIn("reserva", PAIRING_SYSTEMS["gacrux_swiss"])


class AvisoPersistenteTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Database(db_path=Path(self._tmp.name) / "t.db", backup_dir=Path(self._tmp.name) / "bk")
        self.service = PairingService(self.db)
        self.tid = self.db.create_tournament("RGS-18 aviso", rounds_count=3, bye_points=1.0)
        for i in range(4):
            self.db.create_player(self.tid, f"J{i}", rating=2000 - 100 * i)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_rodada_do_motor_reserva_tem_aviso_permanente(self) -> None:
        self.db.save_tournament_settings(self.tid, {"pairing_system": "fide_dutch", "pairing_method": "swiss"})
        rodada = self.service.generate_next_round(self.tid)
        aviso = self.service.round_engine_notice(self.tid, int(rodada["id"]))
        self.assertIn(RESERVE_ENGINE_LABEL, aviso)
        self.assertIn("Rodada 1", aviso)
        # Marcar as pendências como cientes não apaga o aviso da rodada.
        for item in self.service.arbitration_issues(self.tid)["issues"]:
            self.service.acknowledge_arbitration_issue(self.tid, item["issue_key"], "visto")
        self.assertEqual(aviso, self.service.round_engine_notice(self.tid, int(rodada["id"])))

    def test_rodada_de_calendario_nao_tem_aviso(self) -> None:
        self.db.save_tournament_settings(self.tid, {"pairing_method": "round_robin"})
        rodada = self.service.generate_next_round(self.tid)
        self.assertEqual("", self.service.round_engine_notice(self.tid, int(rodada["id"])))


if __name__ == "__main__":
    unittest.main()
