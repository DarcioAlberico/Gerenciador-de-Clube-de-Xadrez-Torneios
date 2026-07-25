"""Testes das pendências da tela inicial (``src/ui/home.py``).

As regras são puras: nenhum teste aqui abre janela nem toca banco. É o ponto da
separação — o que conta como pendência, e em que ordem, dá para verificar sem
montar um torneio de verdade.
"""
from __future__ import annotations

import unittest

from src.ui.home import (
    ATTENTION,
    INFO,
    URGENT,
    HomeSnapshot,
    Pendency,
    build_pendencies,
)
from src.ui.navigation import find


def chaves(pendencias: list[Pendency]) -> list[str]:
    return [p.key for p in pendencias]


class SemTorneioTest(unittest.TestCase):
    def test_estado_vazio_pede_um_torneio(self) -> None:
        itens = build_pendencies(HomeSnapshot())
        self.assertEqual(["sem_torneio"], chaves(itens))
        self.assertEqual("tournaments", itens[0].destination)

    def test_pendencia_do_clube_aparece_mesmo_sem_torneio(self) -> None:
        itens = build_pendencies(HomeSnapshot(defaulters=3))
        self.assertIn("financeiro", chaves(itens))


class TorneioTest(unittest.TestCase):
    def base(self, **kwargs) -> HomeSnapshot:
        dados = dict(has_tournament=True, tournament_name="Aberto", rounds_count=5,
                     generated_rounds=2, closed_rounds=1, players_count=8)
        dados.update(kwargs)
        return HomeSnapshot(**dados)

    def test_torneio_em_dia_nao_gera_pendencia(self) -> None:
        self.assertEqual([], build_pendencies(self.base()))

    def test_resultados_pendentes(self) -> None:
        itens = build_pendencies(self.base(pending_results=4))
        self.assertEqual(["resultados"], chaves(itens))
        self.assertIn("4 resultados", itens[0].title)
        self.assertEqual("pairings", itens[0].destination)
        self.assertEqual(URGENT, itens[0].severity)

    def test_singular_no_titulo(self) -> None:
        itens = build_pendencies(self.base(pending_results=1))
        self.assertIn("1 resultado a lancar", itens[0].title)

    def test_bloqueio_de_arbitragem_e_urgente(self) -> None:
        itens = build_pendencies(self.base(blocking_issues=2))
        self.assertEqual("arbitration_panel", itens[0].destination)
        self.assertEqual(URGENT, itens[0].severity)

    def test_qr_aguardando_aprovacao(self) -> None:
        itens = build_pendencies(self.base(qr_pending=3))
        self.assertEqual(["qr"], chaves(itens))
        self.assertEqual("arbitration_panel", itens[0].destination)

    def test_sem_rodadas_com_jogadores_manda_gerar(self) -> None:
        itens = build_pendencies(self.base(generated_rounds=0, players_count=8))
        self.assertEqual(["sem_rodadas"], chaves(itens))
        self.assertEqual("pairings", itens[0].destination)
        self.assertEqual("Gerar rodada", itens[0].action_label)

    def test_sem_rodadas_e_sem_jogadores_manda_inscrever(self) -> None:
        """A ação tem de ser a que destrava: sem jogador, gerar rodada não adianta."""
        itens = build_pendencies(self.base(generated_rounds=0, players_count=0))
        self.assertEqual("players", itens[0].destination)
        self.assertEqual("Inscrever", itens[0].action_label)

    def test_torneio_concluido_sugere_diplomas(self) -> None:
        itens = build_pendencies(self.base(rounds_count=5, closed_rounds=5, generated_rounds=5))
        self.assertEqual(["torneio_concluido"], chaves(itens))
        self.assertEqual("certificates", itens[0].destination)
        self.assertEqual(INFO, itens[0].severity)

    def test_concluido_nao_aparece_com_rodada_pendente(self) -> None:
        itens = build_pendencies(
            self.base(rounds_count=5, closed_rounds=5, generated_rounds=5, pending_results=2)
        )
        self.assertIn("resultados", chaves(itens))
        self.assertIn("torneio_concluido", chaves(itens))
        self.assertLess(
            chaves(itens).index("resultados"), chaves(itens).index("torneio_concluido"),
            "o que trava o trabalho vem antes do que e so sugestao",
        )


class ClubeTest(unittest.TestCase):
    def test_inadimplencia(self) -> None:
        itens = build_pendencies(HomeSnapshot(has_tournament=True, defaulters=1))
        financeiro = [p for p in itens if p.key == "financeiro"][0]
        self.assertIn("1 mensalidade em atraso", financeiro.title)
        self.assertEqual("finance", financeiro.destination)

    def test_proximo_evento_com_contagem_dos_demais(self) -> None:
        itens = build_pendencies(
            HomeSnapshot(
                has_tournament=True,
                upcoming_events=(("2026-08-01", "Festival"), ("2026-08-09", "Rapid")),
            )
        )
        evento = [p for p in itens if p.key == "eventos"][0]
        self.assertIn("Festival", evento.detail)
        self.assertIn("+1", evento.detail)
        self.assertEqual("calendar", evento.destination)


class OrdemEIntegridadeTest(unittest.TestCase):
    def test_urgente_vem_antes_de_atencao_e_de_info(self) -> None:
        itens = build_pendencies(
            HomeSnapshot(
                has_tournament=True, tournament_name="X", rounds_count=3, generated_rounds=1,
                pending_results=2, defaulters=5, upcoming_events=(("2026-08-01", "Festival"),),
            )
        )
        severidades = [p.severity for p in itens]
        self.assertEqual([URGENT, ATTENTION, INFO], severidades)

    def test_todo_destino_existe_no_registro_de_navegacao(self) -> None:
        """Deep link quebrado é pior que pendência nenhuma."""
        cenarios = [
            HomeSnapshot(),
            HomeSnapshot(has_tournament=True, generated_rounds=0, players_count=0),
            HomeSnapshot(has_tournament=True, generated_rounds=0, players_count=5),
            HomeSnapshot(has_tournament=True, generated_rounds=1, pending_results=2,
                         blocking_issues=1, qr_pending=1),
            HomeSnapshot(has_tournament=True, rounds_count=2, generated_rounds=2, closed_rounds=2),
            HomeSnapshot(defaulters=2, upcoming_events=(("2026-08-01", "Festival"),)),
        ]
        for snapshot in cenarios:
            for pendencia in build_pendencies(snapshot):
                self.assertIsNotNone(
                    find(pendencia.destination),
                    f"destino '{pendencia.destination}' da pendencia '{pendencia.key}' nao existe",
                )

    def test_chaves_nao_se_repetem(self) -> None:
        itens = build_pendencies(
            HomeSnapshot(has_tournament=True, generated_rounds=1, pending_results=1,
                         qr_pending=1, blocking_issues=1, defaulters=1,
                         upcoming_events=(("2026-08-01", "X"),))
        )
        self.assertEqual(len(itens), len(set(chaves(itens))))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
