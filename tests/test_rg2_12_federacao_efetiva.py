"""RG2-12 — federação vazia não escapa dos limites de federação das normas.

As normas descartavam a federação vazia: candidato e 7 dos 9 adversários sem
``federation_id`` (o cadastro local não preenche), mais 1 ARG e 1 URY, davam
"IM atingida" com **0** adversários da própria federação. O TRF, no mesmo
torneio, já punha a federação do torneio nessas linhas — duas regras para a
mesma pergunta.

Agora ``effective_federation(player, settings)`` é a única: TRF, normas e IT3.
Sem federação nem no jogador nem no torneio, a norma conta o adversário como
da federação do candidato (o lado conservador: não inventa federação estrangeira).
"""
from __future__ import annotations

import unittest

from src.domain.fide_player import effective_federation
from src.services.federation_exporters import TRF16Exporter
from src.services.norms import build_certificate, norm_candidates
from src.services.norms.report import build_norm_report
from src.services.trf_layout import FEDERATION, NAME, field
from tests.support.core_service_base import CoreServiceTestCase


def _jogador(pid: int, fed: str = "", title: str = "IM", intl: int = 2450) -> dict:
    return {
        "id": pid,
        "name": f"P{pid}",
        "surname": "",
        "given_name": "",
        "federation_id": fed,
        "title": title,
        "international_rating": intl,
        "rating": intl,
        "national_rating": 0,
        "sex": "M",
    }


_MESAS = [
    {
        "white_player_id": 1,
        "black_player_id": i,
        "result": "1/2-1/2" if i % 2 else "1-0",
        "is_bye": 0,
        "round_number": i - 1,
    }
    for i in range(2, 11)
]


def _cenario_t6_a() -> list[dict]:
    jogadores = [_jogador(1, title="", intl=2400)]
    jogadores += [_jogador(i) for i in range(2, 9)]  # 7 sem federação: brasileiros de fato
    jogadores += [_jogador(9, fed="ARG"), _jogador(10, fed="URY")]
    return jogadores


class LeitorTest(unittest.TestCase):
    def test_a_do_jogador_vence_e_a_do_torneio_completa(self) -> None:
        self.assertEqual("ARG", effective_federation({"federation_id": " arg "}, {"federation": "BRA"}))
        self.assertEqual("BRA", effective_federation({"federation_id": ""}, {"federation": "bra"}))
        self.assertEqual("", effective_federation({}, {}))


class NormaTest(unittest.TestCase):
    def _relatorio(self, **kwargs) -> dict:
        (linha,) = [r for r in build_norm_report(_cenario_t6_a(), _MESAS, **kwargs) if r["player_id"] == 1]
        return linha

    def test_cenario_t6_a_sem_federacao_no_torneio_reprova_no_1_4_4(self) -> None:
        relatorio = self._relatorio()
        im = next(t for t in relatorio["titles"] if t["title"] == "IM")
        self.assertEqual(7, im["own_federation_opponents"])
        self.assertFalse(im["meets"])
        self.assertTrue(any("1.4.4" in item for item in im["missing"]))
        self.assertFalse(relatorio["achieved"])

    def test_cenario_t6_a_com_a_federacao_do_torneio(self) -> None:
        relatorio = self._relatorio(tournament_settings={"federation": "BRA"})
        im = next(t for t in relatorio["titles"] if t["title"] == "IM")
        self.assertEqual(7, im["own_federation_opponents"])
        self.assertEqual("BRA", relatorio["federation"])
        self.assertEqual(2, relatorio["federations"])

    def test_candidato_estrangeiro_conta_os_sem_federacao_como_do_torneio(self) -> None:
        jogadores = _cenario_t6_a()
        jogadores[0]["federation_id"] = "ARG"
        candidatos = norm_candidates(
            jogadores, _MESAS, "fide", achieved_only=False, tournament_settings={"federation": "BRA"}
        )
        im = next(c for c in candidatos if c.evaluation.title == "IM")
        self.assertEqual(1, im.evaluation.own_federation_opponents)
        self.assertEqual({"BRA", "ARG", "URY"}, {o.federation for o in im.opponents})


class TrfEIt3Test(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.db.save_tournament_settings(self.tournament_id, {"federation": "BRA"})
        self.ana = self.db.create_player(
            self.tournament_id, name="Ana Souza", surname="Souza", given_name="Ana", rating=1650, sex="F"
        )
        self.db.create_player(
            self.tournament_id, name="Bia Lima", surname="Lima", given_name="Bia", rating=1600, federation_id="arg"
        )

    def test_trf_usa_a_mesma_federacao_efetiva(self) -> None:
        linhas = TRF16Exporter(self.export_service).render(self.tournament_id).splitlines()
        federacoes = {
            field(linha, NAME).split(",")[0].strip(): field(linha, FEDERATION)
            for linha in linhas
            if linha.startswith("001")
        }
        self.assertEqual({"Souza": "BRA", "Lima": "ARG"}, federacoes)

    def test_it3_traz_a_federacao_efetiva_do_candidato(self) -> None:
        jogadores = _cenario_t6_a()
        (candidato,) = norm_candidates(
            jogadores, _MESAS, "fide", achieved_only=False, player_id=1, title="IM",
            tournament_settings={"federation": "BRA"},
        )
        certificado = build_certificate(
            {"name": "Aberto"},
            {"federation": "BRA"},
            candidato.player,
            candidato.opponents,
            candidato.evaluation,
            candidate_name="P1",
            candidate_rating=2400,
        )
        self.assertEqual("BRA", certificado.candidate_federation)
        self.assertEqual("BRA", certificado.games[0].federation)


if __name__ == "__main__":
    unittest.main()
