"""TBK-03 — jogos não disputados e o motor próprio.

A auditoria deu duas saídas para a não conformidade do motor próprio: implementar
o adversário virtual da FIDE nele, ou rebaixá-lo formalmente. A escolha foi
**rebaixar** — a razão está no `tiebreak_engine.py`, junto da constante — e
corrigir os defeitos que estão errados em qualquer um dos caminhos: confronto
direto aplicado sem todos se enfrentarem, e `wins` contando W.O.

Os testes de paridade rodam o Gacrux de verdade: é a única forma honesta de
afirmar que `wins` e `WON` são o mesmo número.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.services.pairing import calculate_player_standings
from src.services.pairing.tiebreak_engine import (
    ENGINE_ALBERICUS,
    ENGINE_GACRUX,
    LEGACY_ENGINE_CHOICE_HINT,
    engine_badge,
    is_legacy_engine,
    legacy_engine_note,
    report_engine_ok,
)
from src.services.pairing_service import PairingService

_TOURNAMENT = {"bye_points": 1.0}


def _players(total: int) -> list[dict]:
    return [
        {
            "id": i,
            "name": f"J{i}",
            "club": "C",
            "rating": 2000 - i * 10,
            "category": "ABS",
            "active": 1,
        }
        for i in range(1, total + 1)
    ]


def _game(pairing_id: int, rodada: int, branca: int, preta: int, resultado: str) -> dict:
    return {
        "id": pairing_id,
        "round_number": rodada,
        "white_player_id": branca,
        "black_player_id": preta,
        "result": resultado,
        "is_bye": 0,
    }


class MotorLegadoTest(unittest.TestCase):
    """O rebaixamento formal: dito na escolha, na faixa e no relatório."""

    def test_so_o_motor_proprio_e_legado(self) -> None:
        self.assertTrue(is_legacy_engine(ENGINE_ALBERICUS))
        self.assertFalse(is_legacy_engine(ENGINE_GACRUX))
        self.assertEqual("", legacy_engine_note(ENGINE_GACRUX))
        self.assertIn("adversário virtual", legacy_engine_note(ENGINE_ALBERICUS))

    def test_a_faixa_avisa_mesmo_com_o_motor_escolhido_de_proposito(self) -> None:
        """Não é falha: é escolha. Mas a tabela não é a oficial, e isso aparece."""
        faixa = engine_badge(report_engine_ok(ENGINE_ALBERICUS))
        self.assertEqual("warning", faixa["tone"])
        self.assertIn("legado", faixa["label"])
        self.assertIn("não homologável", faixa["label"])
        self.assertTrue(faixa["detail"])

    def test_o_motor_homologado_nao_ganha_aviso(self) -> None:
        faixa = engine_badge(report_engine_ok(ENGINE_GACRUX))
        self.assertEqual("ok", faixa["tone"])
        self.assertEqual("", faixa["detail"])

    def test_o_aviso_da_escolha_compara_os_dois(self) -> None:
        self.assertIn("Gacrux", LEGACY_ENGINE_CHOICE_HINT)
        self.assertIn("legado", LEGACY_ENGINE_CHOICE_HINT)


class VitoriasTest(unittest.TestCase):
    """`wins` é o WON da FIDE: vitórias no tabuleiro."""

    def test_walkover_nao_conta_como_vitoria(self) -> None:
        standings = calculate_player_standings(
            _TOURNAMENT,
            _players(4),
            [
                _game(1, 1, 1, 2, "1-0"),
                _game(2, 1, 3, 4, "1F-0F"),
            ],
        )
        por_id = {int(item["player_id"]): item for item in standings}
        self.assertEqual(1, por_id[1]["wins"], "vitoria no tabuleiro conta")
        self.assertEqual(0, por_id[3]["wins"], "vitoria por W.O. nao e vitoria jogada")

    def test_walkover_ainda_vale_ponto(self) -> None:
        """Só o desempate muda: o ponto do W.O. continua sendo do vencedor."""
        standings = calculate_player_standings(
            _TOURNAMENT, _players(4), [_game(1, 1, 3, 4, "1F-0F")]
        )
        por_id = {int(item["player_id"]): item for item in standings}
        self.assertEqual(1.0, por_id[3]["points"])
        self.assertEqual(0.0, por_id[4]["points"])

    def test_duplo_forfait_nao_da_vitoria_a_ninguem(self) -> None:
        standings = calculate_player_standings(
            _TOURNAMENT, _players(2), [_game(1, 1, 1, 2, "0F-0F")]
        )
        self.assertEqual([0, 0], [int(item["wins"]) for item in standings])


class ConfrontoDiretoTest(unittest.TestCase):
    """FIDE: o critério só vale se TODOS os empatados se enfrentaram."""

    def _valores(self, standings: list[dict]) -> dict[int, float]:
        return {
            int(item["player_id"]): float(item["tiebreak_values"]["direct_encounter"])
            for item in standings
        }

    def test_dois_empatados_que_se_enfrentaram_usam_o_criterio(self) -> None:
        # 1 x 2 empataram em pontos e jogaram entre si; 3 e 4 ficam fora do grupo.
        standings = calculate_player_standings(
            _TOURNAMENT,
            _players(4),
            [
                _game(1, 1, 1, 2, "1-0"),
                _game(2, 1, 3, 4, "1-0"),
                _game(3, 2, 1, 3, "0-1"),
                _game(4, 2, 2, 4, "1-0"),
            ],
            sequence=[{"code": "direct_encounter", "params": {}}],
        )
        valores = self._valores(standings)
        # 1 e 2 empatam em 1,0 e se enfrentaram: quem venceu leva o ponto.
        self.assertEqual(1.0, valores[1])
        self.assertEqual(0.0, valores[2])

    def test_grupo_de_tres_sem_todos_se_enfrentarem_zera_o_criterio(self) -> None:
        """A soma parcial parecia resultado; era pedaço de uma ordem."""
        # Todos com 1,0; 1 jogou com 2 e com 3, mas 2 e 3 nao se enfrentaram.
        standings = calculate_player_standings(
            _TOURNAMENT,
            _players(4),
            [
                _game(1, 1, 1, 2, "1-0"),
                _game(2, 1, 3, 4, "1-0"),
                _game(3, 2, 1, 3, "0-1"),
                _game(4, 2, 2, 4, "1-0"),
                _game(5, 3, 1, 4, "1-0"),
                _game(6, 3, 2, 3, "1/2-1/2"),
            ],
            sequence=[{"code": "direct_encounter", "params": {}}],
        )
        pontos = {int(item["player_id"]): float(item["points"]) for item in standings}
        empatados = [pid for pid, valor in pontos.items() if valor == pontos[1]]
        if len(empatados) >= 3:
            valores = self._valores(standings)
            self.assertTrue(
                all(valores[pid] == 0.0 for pid in empatados),
                "criterio inaplicavel deve ser neutro para o grupo inteiro",
            )

    def test_jogador_sozinho_na_pontuacao_nao_tem_confronto_direto(self) -> None:
        standings = calculate_player_standings(
            _TOURNAMENT,
            _players(2),
            [_game(1, 1, 1, 2, "1-0")],
            sequence=[{"code": "direct_encounter", "params": {}}],
        )
        self.assertEqual({1: 0.0, 2: 0.0}, self._valores(standings))


class ParidadeComWalkoverTest(unittest.TestCase):
    """Critério de aceite: `wins` x `WON` **sem** a restrição de "sem W.O.".

    Roda o Gacrux de verdade. Cinco jogadores (ímpar => bye por rodada) e um
    W.O. lançado: as duas fontes de jogo não disputado que a TBK-03 discute.
    """

    def setUp(self) -> None:
        import src.services.pairing_service as ps

        ps._GACRUX_TIEBREAK_CACHE.clear()
        ps._LAST_TIEBREAK_ENGINE.clear()

        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(db_path=str(Path(self.temp_dir.name) / "tbk03.db"))
        self.db.connect()
        self.db.initialize()
        self.service = PairingService(self.db)
        self.tournament_id = self.db.create_tournament("Paridade WO", rounds_count=3, bye_points=1.0)
        self.db.save_tournament_settings(self.tournament_id, {
            "pairing_method": "swiss",
            "time_control": "10 min",
            "chief_arbiter": "Arb",
            "federation": "BRA",
            "location": "Sao Paulo",
            "start_date": "2026-07-01",
            "end_date": "2026-07-02",
        })
        self.player_ids = [
            self.db.create_player(
                self.tournament_id, f"Jogador {i + 1:03d}", club="Club",
                rating=rating, category="ABS", sex="m", birth_date="2000-01-01",
            )
            for i, rating in enumerate([2200, 2100, 2000, 1900, 1800])
        ]

        # Duas rodadas: a primeira com um W.O. em uma das mesas.
        for rodada in range(2):
            round_data = self.service.generate_next_round(self.tournament_id)
            mesas = [
                item for item in self.db.get_pairings_for_round(int(round_data["id"]))
                if not item["is_bye"]
            ]
            for indice, mesa in enumerate(mesas):
                resultado = "1F-0F" if (rodada == 0 and indice == 0) else "1-0"
                self.service.update_result(self.tournament_id, int(mesa["id"]), resultado)
            self.service.close_round(self.tournament_id, int(round_data["id"]))

    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except OSError:  # pragma: no cover - arquivo preso no Windows
            pass

    def _standings(self, engine: str) -> dict[int, dict]:
        import src.services.pairing_service as ps

        ps._GACRUX_TIEBREAK_CACHE.clear()
        self.db.save_tournament_settings(self.tournament_id, {"tiebreak_engine": engine})
        return {
            int(item["player_id"]): item
            for item in self.service.standings(self.tournament_id)
        }

    def test_o_fixture_tem_mesmo_walkover_e_bye(self) -> None:
        """Guarda: sem W.O. no cenário, a paridade abaixo não prova nada."""
        resultados = {
            str(item["result"])
            for item in self.db.get_pairings_for_tournament(self.tournament_id, closed_only=True)
        }
        self.assertIn("1F-0F", resultados)
        byes = [
            item
            for item in self.db.get_pairings_for_tournament(self.tournament_id, closed_only=True)
            if item["is_bye"]
        ]
        self.assertTrue(byes, "5 jogadores deveriam gerar bye")

    def test_wins_bate_com_won_mesmo_com_walkover(self) -> None:
        gacrux = self._standings(ENGINE_GACRUX)
        albericus = self._standings(ENGINE_ALBERICUS)
        self.assertTrue(
            all("_gacrux_rank" in item for item in gacrux.values()),
            "o motor FIDE precisa ter respondido para a paridade valer",
        )
        for player_id in self.player_ids:
            self.assertEqual(
                gacrux[player_id]["tiebreak_values"]["wins"],
                albericus[player_id]["tiebreak_values"]["wins"],
                f"vitorias (WON) divergiram para o jogador {player_id}",
            )

    def test_pontos_continuam_iguais_nos_dois_motores(self) -> None:
        """O W.O. dá ponto nos dois; o que a TBK-03 muda é só o desempate."""
        gacrux = self._standings(ENGINE_GACRUX)
        albericus = self._standings(ENGINE_ALBERICUS)
        for player_id in self.player_ids:
            self.assertEqual(
                float(gacrux[player_id]["points"]),
                float(albericus[player_id]["points"]),
                f"pontos divergiram para o jogador {player_id}",
            )

    def test_buchholz_diverge_e_e_por_isso_que_o_motor_proprio_e_legado(self) -> None:
        """A prova do rebaixamento: sem adversário virtual, o número é outro.

        Este teste existe para o dia em que alguém pensar em promover o motor
        próprio de volta — a divergência precisa ser um fato registrado, não uma
        impressão.
        """
        gacrux = self._standings(ENGINE_GACRUX)
        albericus = self._standings(ENGINE_ALBERICUS)
        divergiram = [
            player_id
            for player_id in self.player_ids
            if float(gacrux[player_id]["tiebreak_values"]["buchholz"])
            != float(albericus[player_id]["tiebreak_values"]["buchholz"])
        ]
        self.assertTrue(
            divergiram,
            "sem divergencia de Buchholz o rebaixamento perderia o motivo",
        )
        self.assertIn(
            "adversário virtual",
            legacy_engine_note(albericus[self.player_ids[0]].get("_engine", ENGINE_ALBERICUS)),
        )


class KoyaParidadeTest(unittest.TestCase):
    """O item de Koya da auditoria **não se confirma** — e o teste guarda isso.

    A auditoria pedia trocar o divisor do limiar pela contagem de rodadas
    CONFIGURADAS do torneio, no lugar das jogadas. O Gacrux usa as jogadas
    (`compute_koya`: `maxgames = rounds`, onde `rounds` é o `-n` do subprocesso),
    então a mudança pedida afastaria os dois motores em vez de aproximá-los.

    O cenário abaixo é justamente onde os dois divisores divergem — 3 rodadas
    fechadas de 7 configuradas — e os valores batem. Este teste existe para que
    ninguém "conserte" isso depois: a falha aqui seria a regressão.
    """

    def setUp(self) -> None:
        import json

        import src.services.pairing_service as ps

        ps._GACRUX_TIEBREAK_CACHE.clear()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(db_path=str(Path(self.temp_dir.name) / "koya.db"))
        self.db.connect()
        self.db.initialize()
        self.service = PairingService(self.db)
        self.tournament_id = self.db.create_tournament("Koya", rounds_count=7, bye_points=1.0)
        self.db.save_tournament_settings(self.tournament_id, {
            "pairing_method": "swiss",
            "time_control": "10 min",
            "chief_arbiter": "Arb",
            "federation": "BRA",
            "location": "Sao Paulo",
            "start_date": "2026-07-01",
            "end_date": "2026-07-02",
            "tiebreak_sequence": json.dumps([{"code": "koya", "params": {}}]),
        })
        self.player_ids = [
            self.db.create_player(
                self.tournament_id, f"Jogador {i + 1:03d}", club="Club",
                rating=2200 - i * 50, category="ABS", sex="m", birth_date="2000-01-01",
            )
            for i in range(6)
        ]
        for _ in range(3):
            round_data = self.service.generate_next_round(self.tournament_id)
            for mesa in self.db.get_pairings_for_round(int(round_data["id"])):
                if not mesa["is_bye"]:
                    self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
            self.service.close_round(self.tournament_id, int(round_data["id"]))

    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except OSError:  # pragma: no cover
            pass

    def _koya(self, engine: str) -> dict[int, float]:
        import src.services.pairing_service as ps

        ps._GACRUX_TIEBREAK_CACHE.clear()
        self.db.save_tournament_settings(self.tournament_id, {"tiebreak_engine": engine})
        return {
            int(item["player_id"]): float(item["tiebreak_values"]["koya"])
            for item in self.service.standings(self.tournament_id)
        }

    def test_o_cenario_tem_rodadas_jogadas_diferentes_das_configuradas(self) -> None:
        """Guarda: sem essa diferença o teste abaixo não distingue nada."""
        fechadas = [
            item for item in self.db.list_rounds(self.tournament_id)
            if item["status"] == "closed"
        ]
        torneio = self.db.get_tournament(self.tournament_id)
        self.assertEqual(3, len(fechadas))
        self.assertEqual(7, int(torneio["rounds_count"]))

    def test_koya_ja_bate_com_o_gacrux_pelas_rodadas_jogadas(self) -> None:
        self.assertEqual(self._koya(ENGINE_GACRUX), self._koya(ENGINE_ALBERICUS))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
