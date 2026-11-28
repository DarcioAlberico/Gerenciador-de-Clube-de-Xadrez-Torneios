"""RG2-07b — o motor único proíbe a repetição e trata o bye como mais um nó.

O suíço por equipes repetia confronto quando havia pareamento sem repetição
(sementes 0, 2 e 7 do ``r3/team_stress.py``), repetia sem alternativa em vez de
recusar (semente 5) e dava três cores iguais seguidas (3, 4 e 6). A guarda do
RG2-07a passou a recusar essas rodadas; agora o motor acha a alternativa — e,
quando ela não existe, diz a regra.

O oráculo é força bruta: existe pareamento perfeito sem confronto repetido e
com o bye em quem ainda não teve?
"""
from __future__ import annotations

import random
import unittest
from typing import Any

from src.services.pairing.round_search import NoLegalPairingError, legal_round
from tests.support.core_service_base import CoreServiceTestCase


def _ha_pareamento_legal(ids: list[int], jogados: set[frozenset[int]], com_bye: set[int]) -> bool:
    def fecha(resto: list[int]) -> bool:
        if not resto:
            return True
        primeiro = resto[0]
        return any(
            frozenset((primeiro, outro)) not in jogados and fecha([x for x in resto[1:] if x != outro])
            for outro in resto[1:]
        )

    if len(ids) % 2 == 0:
        return fecha(ids)
    return any(fecha([x for x in ids if x != bye]) for bye in ids if bye not in com_bye)


def _fere_a_cor(sequencia: str, cor: str) -> bool:
    """Terceira cor igual seguida ou diferença de cores acima de 2 (byes não contam)."""
    if sequencia[-2:] == cor * 2:
        return True
    return abs(sequencia.count("W") + (cor == "W") - sequencia.count("B") - (cor == "B")) > 2


def _violacoes(pares: list[tuple[int, int]], cores: dict[int, str]) -> int:
    """Cor absoluta ferida na rodada, com as brancas como saíram."""
    return sum(_fere_a_cor(cores.get(b, ""), "W") + _fere_a_cor(cores.get(p, ""), "B") for b, p in pares)


def _menor_violacao_possivel(ids: list[int], jogados: set[frozenset[int]], com_bye: set[int], cores: dict[int, str]) -> int:
    """Menor número de cores absolutas feridas entre todos os pareamentos legais."""

    def melhor_orientacao(a: int, b: int) -> int:
        return min(_violacoes([(a, b)], cores), _violacoes([(b, a)], cores))

    def melhor(resto: list[int]) -> int | None:
        if not resto:
            return 0
        primeiro, achado = resto[0], None
        for outro in resto[1:]:
            if frozenset((primeiro, outro)) in jogados:
                continue
            cauda = melhor([x for x in resto[1:] if x != outro])
            if cauda is not None:
                total = melhor_orientacao(primeiro, outro) + cauda
                achado = total if achado is None else min(achado, total)
        return achado

    opcoes = [ids] if len(ids) % 2 == 0 else [[x for x in ids if x != bye] for bye in ids if bye not in com_bye]
    valores = [v for v in (melhor(o) for o in opcoes) if v is not None]
    return min(valores)


def _c(ident: int) -> dict[str, Any]:
    return {"id": ident, "name": f"E{ident}"}


class BuscaExataTest(unittest.TestCase):
    def test_confronto_jogado_nao_e_aresta(self) -> None:
        jogados = {frozenset((1, 2)), frozenset((3, 4))}
        pares, bye = legal_round([_c(i) for i in (1, 2, 3, 4)], jogados, set(), pair_cost=lambda a, b: 0, bye_cost=lambda a: 0)
        self.assertIsNone(bye)
        self.assertTrue(all(frozenset((a["id"], b["id"])) not in jogados for a, b in pares))

    def test_bye_so_para_quem_nao_teve(self) -> None:
        resultado = legal_round([_c(i) for i in (1, 2, 3)], set(), {1, 2}, pair_cost=lambda a, b: 0, bye_cost=lambda a: 0)
        assert resultado is not None
        self.assertEqual(3, resultado[1]["id"])

    def test_sem_pareamento_legal_devolve_none(self) -> None:
        todos = {frozenset(p) for p in ((1, 2), (1, 3), (2, 3))}
        self.assertIsNone(
            legal_round([_c(i) for i in (1, 2, 3)], todos, {1, 2, 3}, pair_cost=lambda a, b: 0, bye_cost=lambda a: 0)
        )

    def test_custo_menor_vence(self) -> None:
        custo = {frozenset((1, 2)): 0, frozenset((3, 4)): 0, frozenset((1, 3)): 9, frozenset((2, 4)): 9}
        pares, _bye = legal_round(
            [_c(i) for i in (1, 2, 3, 4)],
            {frozenset((1, 4)), frozenset((2, 3))},
            set(),
            pair_cost=lambda a, b: custo[frozenset((a["id"], b["id"]))],
            bye_cost=lambda a: 0,
        )
        self.assertEqual({frozenset((1, 2)), frozenset((3, 4))}, {frozenset((a["id"], b["id"])) for a, b in pares})


class SuicoPorEquipesTest(CoreServiceTestCase):
    """7 equipes × 6 rodadas, sementes fixas: o aceite do RG2-07b."""

    def _torneio(self, equipes: int, rodadas: int) -> tuple[int, list[int]]:
        torneio, ids = self._create_team_tournament(teams_count=equipes, boards_count=2)
        with self.db.connect() as conexao:
            conexao.execute("UPDATE tournaments SET rounds_count=? WHERE id=?", (rodadas, torneio))
        return torneio, ids

    def _historia(self, torneio: int) -> tuple[set[frozenset[int]], dict[int, int], dict[int, str]]:
        jogados: set[frozenset[int]] = set()
        byes: dict[int, int] = {}
        cores: dict[int, str] = {}
        for rodada in sorted(self.db.list_rounds(torneio), key=lambda r: r["number"]):
            for m in self.db.list_team_matches_for_round(int(rodada["id"])):
                brancas, pretas = m["white_team_id"], m["black_team_id"]
                if m.get("is_bye") or not pretas:
                    byes[brancas] = byes.get(brancas, 0) + 1
                    continue
                jogados.add(frozenset((brancas, pretas)))
                cores[brancas] = cores.get(brancas, "") + "W"
                cores[pretas] = cores.get(pretas, "") + "B"
        return jogados, byes, cores

    def _jogar(self, torneio: int, rodada_id: int, sorteio: random.Random) -> None:
        for m in self.db.list_team_matches_for_round(rodada_id):
            if m.get("is_bye"):
                continue
            for tabuleiro in self.db.list_team_boards(int(m["id"])):
                self.service.update_result(
                    torneio, int(tabuleiro["id"]), sorteio.choice(["1-0", "0-1", "1/2-1/2", "1-0", "0-1"])
                )
        self.service.close_round(torneio, rodada_id)

    def test_sete_equipes_seis_rodadas_sem_repeticao_evitavel(self) -> None:
        for semente in range(10):
            with self.subTest(semente=semente):
                self._uma_semente(semente)

    def _uma_semente(self, semente: int) -> None:
        sorteio = random.Random(semente)
        torneio, ids = self._torneio(7, 6)
        for numero in range(1, 7):
            jogados, byes, cores = self._historia(torneio)
            try:
                rodada = self.service.generate_next_round(torneio)
            except NoLegalPairingError as recusa:
                self.assertFalse(
                    _ha_pareamento_legal(ids, jogados, set(byes)),
                    f"R{numero}: recusou, mas havia pareamento legal",
                )
                self.assertIn("C.04.1", str(recusa))
                return
            confrontos = self.db.list_team_matches_for_round(int(rodada["id"]))
            repetidos = [
                (m["white_team_id"], m["black_team_id"])
                for m in confrontos
                if m["black_team_id"] and frozenset((m["white_team_id"], m["black_team_id"])) in jogados
            ]
            self.assertEqual([], repetidos, f"R{numero}")
            segundo_pab = [m["white_team_id"] for m in confrontos if m.get("is_bye") and m["white_team_id"] in byes]
            self.assertEqual([], segundo_pab, f"R{numero}")
            # Três cores iguais seguidas só quando nenhum pareamento legal evita.
            pares = [(m["white_team_id"], m["black_team_id"]) for m in confrontos if m["black_team_id"]]
            self.assertEqual(
                _menor_violacao_possivel(ids, jogados, set(byes), cores), _violacoes(pares, cores), f"R{numero}"
            )
            self._jogar(torneio, int(rodada["id"]), sorteio)

    def test_tres_equipes_quatro_rodadas_termina_em_erro_claro(self) -> None:
        sorteio = random.Random(0)
        torneio, _ids = self._torneio(3, 4)
        for _ in range(3):
            rodada = self.service.generate_next_round(torneio)
            self._jogar(torneio, int(rodada["id"]), sorteio)
        with self.assertRaises(NoLegalPairingError) as recusa:
            self.service.generate_next_round(torneio)
        self.assertIn("C.04.1", str(recusa.exception))
        self.assertNotIn("Traceback", str(recusa.exception))
        self.assertEqual(3, len(self.db.list_rounds(torneio)))


class SuicoIndividualTest(CoreServiceTestCase):
    """O motor próprio de jogadores (o reserva) também não repete mais."""

    def test_dois_jogadores_na_r2_recusa_em_vez_de_repetir(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"pairing_system": "fide_dutch"})
        self._create_players(2)
        rodada = self.service.generate_next_round(self.tournament_id)
        (mesa,) = self.db.get_pairings_for_round(int(rodada["id"]))
        self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(rodada["id"]))
        with self.assertRaises(NoLegalPairingError):
            self.service.generate_next_round(self.tournament_id)
        self.assertEqual(1, len(self.db.list_rounds(self.tournament_id)))


class OfertaNaTelaTest(unittest.TestCase):
    def test_sem_pareamento_legal_oferece_encerrar(self) -> None:
        from unittest import mock

        from src.ui.screens.pairing_results.view import PairingResultsMixin

        class Tela(PairingResultsMixin):
            pairing_service = mock.Mock()

            def show_pairings(self) -> None:
                pass

        tela = Tela()
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=True) as dialogo:
            self.assertTrue(tela._offer_round_way_out(7, NoLegalPairingError(None, "as equipes")))
        self.assertEqual("Encerrar o torneio aqui", dialogo.call_args.kwargs["confirm_text"])
        tela.pairing_service.end_tournament_early.assert_called_once()


if __name__ == "__main__":
    unittest.main()
