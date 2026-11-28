"""RG2-11 — o rating do clube não sai como rating FIDE (TRF, normas, IT3).

O TRF, o registro 072, o aviso "sem rating FIDE", as normas e o IT3 liam
``international_rating or rating or national_rating``: uma jogadora sem FIDE e
com 1650 do clube saía com 1650 na coluna FIDE, contava como ratada no 072 e,
reimportada, ganhava ``international_rating=1650`` — o dado falso virava
permanente. Nas normas, 9 "GM" sem FIDE com 2500 local davam norma de GM.

Agora ``fide_rating`` (``src/domain/fide_player.py``) é o único leitor do
campo FIDE; o atalho para o rating local fica só na ordem inicial.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.domain.fide_player import fide_rating
from src.services.federation_exporters import TRF16Exporter, TRF25Exporter
from src.services.norms.report import build_norm_report, norm_candidates
from src.services.trf_layout import NAME, RATING, field
from tests.support.core_service_base import CoreServiceTestCase


class LeitorTest(unittest.TestCase):
    def test_so_o_rating_internacional_e_rating_fide(self) -> None:
        self.assertEqual(0, fide_rating({"rating": 1650, "national_rating": 1700}))
        self.assertEqual(2100, fide_rating({"international_rating": 2100, "rating": 1650}))
        self.assertEqual(0, fide_rating({"international_rating": None}))


class ColunaFideDoTrfTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ana = self.db.create_player(
            self.tournament_id, name="Ana Souza", surname="Souza", given_name="Ana", rating=1650, sex="F"
        )
        self.db.create_player(
            self.tournament_id,
            name="Bruno Lima",
            surname="Lima",
            given_name="Bruno",
            rating=2100,
            international_rating=2100,
            fide_id="123",
            sex="M",
        )
        self.db.create_player(
            self.tournament_id, name="Caio Reis", surname="Reis", given_name="Caio", rating=1500, sex="M"
        )
        self.db.create_player(
            self.tournament_id,
            name="Davi Melo",
            surname="Melo",
            given_name="Davi",
            rating=1800,
            international_rating=1800,
            sex="M",
        )
        rodada = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(int(rodada["id"]))
        self.service.close_round(self.tournament_id, int(rodada["id"]))

    def _trf16(self) -> list[str]:
        return TRF16Exporter(self.export_service).render(self.tournament_id).splitlines()

    def _trf25(self) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "t.trf"
            TRF25Exporter(self.export_service).export(self.tournament_id, destino)
            return destino.read_text(encoding="utf-8").splitlines()

    def _linha_de(self, linhas: list[str], sobrenome: str) -> str:
        return next(linha for linha in linhas if linha.startswith("001") and sobrenome in field(linha, NAME))

    def test_rating_do_clube_deixa_a_coluna_fide_vazia(self) -> None:
        linhas = self._trf16()
        self.assertEqual("", field(self._linha_de(linhas, "Souza"), RATING).strip())
        self.assertEqual("2100", field(self._linha_de(linhas, "Lima"), RATING).strip())

    def test_072_conta_so_quem_tem_rating_fide(self) -> None:
        for nome, linhas in (("TRF16", self._trf16()), ("TRF25", self._trf25())):
            with self.subTest(formato=nome):
                (registro,) = [linha for linha in linhas if linha.startswith("072")]
                self.assertEqual("2", registro[4:].strip())

    def test_aviso_de_rating_fide_cita_quem_so_tem_o_do_clube(self) -> None:
        avisos = TRF16Exporter(self.export_service).validate(self.tournament_id)
        (aviso,) = [item for item in avisos if "rating FIDE" in item]
        self.assertIn("Souza", aviso)
        self.assertNotIn("Lima", aviso)

    def test_reimportar_nao_transforma_o_rating_do_clube_em_fide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "t.trf"
            TRF16Exporter(self.export_service).export(self.tournament_id, destino)
            novo = self.import_service.import_trf(destino)["tournament_id"]
        ana = next(p for p in self.db.list_players(novo, active_only=False) if "Souza" in p["name"])
        self.assertEqual(0, int(ana["international_rating"] or 0))


def _jogador(pid: int, fed: str = "", title: str = "IM", intl: int = 2450, rating: int | None = None) -> dict:
    return {
        "id": pid,
        "name": f"P{pid}",
        "surname": "",
        "given_name": "",
        "federation_id": fed,
        "title": title,
        "international_rating": intl,
        "rating": intl if rating is None else rating,
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


class NormaComRatingLocalTest(unittest.TestCase):
    def test_cenario_t6_b_nove_gm_sem_fide_nao_dao_norma(self) -> None:
        jogadores = [_jogador(1, fed="BRA", title="", intl=2400)]
        jogadores += [
            _jogador(i, fed=["ARG", "URY", "CHI", "BRA"][i % 4], title="GM", intl=0, rating=2500)
            for i in range(2, 11)
        ]
        (relatorio,) = [r for r in build_norm_report(jogadores, _MESAS) if r["player_id"] == 1]
        self.assertEqual(9, relatorio["unrated_opponents"])
        self.assertFalse(relatorio["achieved"])


class RatingDoCandidatoNoIt3Test(CoreServiceTestCase):
    """O IT3 leva o rating FIDE do candidato, não o do clube."""

    def setUp(self) -> None:
        super().setUp()
        self.tournament_id = self.db.create_tournament("Aberto", rounds_count=9)
        self.db.save_tournament_settings(
            self.tournament_id, {"federation": "BRA", "chief_arbiter": "Ana", "pairing_method": "swiss"}
        )
        self.candidato = self.db.create_player(
            self.tournament_id,
            name="Joao Silva",
            surname="Silva",
            given_name="Joao",
            federation_id="BRA",
            fide_id="2900001",
            sex="M",
            international_rating=0,
            rating=2500,
        )
        titulos = ["GM", "GM", "GM", "IM", "IM", "IM", "FM", "FM", "FM"]
        for indice, (titulo, fed) in enumerate(zip(titulos, ["BRA", "ARG", "URU"] * 3)):
            adversario = self.db.create_player(
                self.tournament_id,
                name=f"Adv {indice}",
                surname=f"Sobrenome{indice}",
                given_name="Nome",
                federation_id=fed,
                title=titulo,
                sex="M",
                international_rating=2400,
                rating=2400,
            )
            round_id = self.db.create_round_with_pairings(
                self.tournament_id,
                indice + 1,
                [
                    {
                        "board_number": 1,
                        "white_player_id": self.candidato,
                        "black_player_id": adversario,
                        "result": "1-0" if indice < 7 else "0-1",
                    }
                ],
            )
            self.db.close_round(round_id)

    def test_candidato_sem_fide_sai_sem_rating(self) -> None:
        candidatos = norm_candidates(
            self.db.list_players(self.tournament_id, active_only=False),
            self.db.get_pairings_for_tournament(self.tournament_id, closed_only=True),
            "fide",
        )
        self.assertTrue(candidatos, "o cenário precisa fechar uma norma")
        capturados: list = []
        with mock.patch(
            "src.services.export_federation.write_it3_pdf",
            side_effect=lambda certificados, caminho: capturados.extend(certificados) or Path(caminho),
        ):
            self.export_service.export_it3_certificate(self.tournament_id, Path("ignorado.pdf"))
        self.assertTrue(capturados)
        self.assertEqual({0}, {c.candidate_rating for c in capturados})


if __name__ == "__main__":
    unittest.main()
