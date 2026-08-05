"""Ordem do ranking inicial — o torneio pareado é o torneio declarado.

Três lugares montavam o ranking inicial por conta própria e todos pela mesma
chave (rating FIDE na frente), **ignorando o `initial_order` do torneio**: o
exportador TRF16, o TRF25 e o `GacruxEngine` — que é o motor de pareamento
PADRÃO.

O efeito não era cosmético. O Gacrux recebe o TRF e devolve pares por NÚMERO DE
ORDEM: um torneio declarado "ordem pelo rating nacional" era pareado pela ordem
do rating FIDE, com adversário e cor diferentes na mesa 1, enquanto o motor
próprio (`_seeding`) fazia o certo. O mesmo torneio, no mesmo banco, dava dois
pareamentos conforme o motor — e os testes de `initial_order` que existiam
rodavam com o motor próprio forçado (`tests/conftest.py`), então o caminho de
produção estava descoberto.

O TRF25 sabia da divergência e apenas AVISAVA, declarando `FIDE` no registro
172. Agora a ordem é uma só e o 172 declara o método que o arquivo realmente
usa.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.services.starting_rank import (
    order_players,
    start_rank_by_player_id,
    starting_rank_rating,
    trf_starting_rank_method,
    unsupported_order_warning,
    uses_fide_rating,
)
from tests.support.core_service_base import CoreServiceTestCase


# `_trf_rating` do exportador: internacional, senão principal, senão nacional.
def _fide_rating(player: dict) -> int:
    return int(
        player.get("international_rating")
        or player.get("rating")
        or player.get("national_rating")
        or 0
    )


def _jogador(pid: int, nome: str, *, nac: int = 0, intl: int = 0, rating: int = 0) -> dict:
    return {
        "id": pid,
        "name": nome,
        "surname": "",
        "given_name": nome,
        "national_rating": nac,
        "international_rating": intl,
        "rating": rating,
    }


PLANTEL = [
    _jogador(1, "Nacional 1", nac=2400, rating=2400),
    _jogador(2, "Nacional 2", nac=2300, rating=2300),
    _jogador(3, "FIDE alto", nac=1000, intl=2500, rating=1000),
    _jogador(4, "Nacional baixo", nac=900, rating=900),
]


class OrdemPuraTest(unittest.TestCase):
    def _ordem(self, initial_order: str) -> list[str]:
        return [
            item["name"]
            for item in order_players(PLANTEL, initial_order, fide_rating=_fide_rating)
        ]

    def test_ordem_nacional_poe_o_nacional_na_frente(self) -> None:
        self.assertEqual(
            ["Nacional 1", "Nacional 2", "FIDE alto", "Nacional baixo"],
            self._ordem("national_rating"),
        )

    def test_ordem_padrao_mantem_a_convencao_do_arquivo_fide(self) -> None:
        """`rating` e o DEFAULT da coluna: quem nao escolheu nao declarou nada.

        Mudar o comportamento aqui reescreveria o TRF de todo torneio que
        existe hoje, sem que ninguem tenha pedido.
        """
        esperado = ["FIDE alto", "Nacional 1", "Nacional 2", "Nacional baixo"]
        self.assertEqual(esperado, self._ordem("rating"))
        self.assertEqual(esperado, self._ordem(""))
        self.assertEqual(esperado, self._ordem("international_rating"))

    def test_maior_rating_e_internacional_depois_nacional(self) -> None:
        self.assertEqual(
            ["FIDE alto", "Nacional 1", "Nacional 2", "Nacional baixo"],
            self._ordem("max_rating"),
        )
        self.assertEqual(
            ["FIDE alto", "Nacional 1", "Nacional 2", "Nacional baixo"],
            self._ordem("international_then_national"),
        )

    def test_manual_cai_no_rating_porque_nao_ha_onde_gravar(self) -> None:
        self.assertEqual(
            ["FIDE alto", "Nacional 1", "Nacional 2", "Nacional baixo"],
            self._ordem("manual"),
        )
        self.assertIn("manual", str(unsupported_order_warning("manual")))
        self.assertIsNone(unsupported_order_warning("national_rating"))

    def test_rating_do_ranking_por_ordem(self) -> None:
        fide_alto = PLANTEL[2]
        self.assertEqual(2500, starting_rank_rating(fide_alto, "rating", fide_rating=_fide_rating))
        self.assertEqual(
            1000, starting_rank_rating(fide_alto, "national_rating", fide_rating=_fide_rating)
        )

    def test_numero_de_ordem_por_jogador(self) -> None:
        mapa = start_rank_by_player_id(PLANTEL, "national_rating", fide_rating=_fide_rating)
        self.assertEqual(1, mapa[1])
        self.assertEqual(4, mapa[4])

    def test_desempate_estavel_por_nome(self) -> None:
        empatados = [
            _jogador(9, "Zeca", nac=1500, rating=1500),
            _jogador(8, "Ana", nac=1500, rating=1500),
        ]
        self.assertEqual(
            ["Ana", "Zeca"],
            [i["name"] for i in order_players(empatados, "national_rating", fide_rating=_fide_rating)],
        )

    def test_convencao_fide_por_ordem(self) -> None:
        self.assertTrue(uses_fide_rating(""))
        self.assertTrue(uses_fide_rating("rating"))
        self.assertFalse(uses_fide_rating("national_rating"))


class Registro172Test(unittest.TestCase):
    """O 172 passou a declarar o metodo que o arquivo usa, nao `FIDE` sempre."""

    def test_metodos_que_a_spec_permite_afirmar(self) -> None:
        self.assertEqual("FIDE", trf_starting_rank_method("rating"))
        self.assertEqual("FIDE", trf_starting_rank_method(""))
        self.assertEqual("FIDE", trf_starting_rank_method("international_rating"))
        self.assertEqual("NRO", trf_starting_rank_method("national_rating"))

    def test_ordem_sem_codigo_definido_sai_como_other(self) -> None:
        """A spec lista `FIDON`/`HBFN`/`NIDOF` e nao define o significado.

        Afirmar um codigo cujo sentido nao se conhece e o mesmo erro do "Sistema
        Hort": `OTHER` e o codigo que a propria spec oferece para isso.
        """
        self.assertEqual("OTHER", trf_starting_rank_method("international_then_national"))
        self.assertEqual("OTHER", trf_starting_rank_method("max_rating"))
        self.assertEqual("OTHER", trf_starting_rank_method("manual"))


class MotorPadraoRespeitaOrdemTest(CoreServiceTestCase):
    """O caminho de PRODUCAO: `gacrux_swiss` e o sistema padrao.

    `tests/conftest.py` forca `fide_dutch` para a suite inteira, e era por isso
    que os testes de `initial_order` nao pegavam este defeito. Aqui o sistema e
    escolhido explicitamente, nos dois motores.
    """

    def _torneio(self, sistema: str) -> tuple[int, dict[int, str]]:
        tournament_id = self.db.create_tournament("Nacional", rounds_count=3)
        self.db.save_tournament_settings(
            tournament_id, {"initial_order": "national_rating", "pairing_system": sistema}
        )
        nomes: dict[int, str] = {}
        for nome, nac, intl in (
            ("Nacional 1", 2400, 0),
            ("Nacional 2", 2300, 0),
            ("FIDE alto", 1000, 2500),
            ("Nacional baixo", 900, 0),
        ):
            pid = self.db.create_player(
                tournament_id,
                name=nome,
                national_rating=nac,
                international_rating=intl,
                rating=nac,
            )
            nomes[pid] = nome
        return tournament_id, nomes

    def _mesas(self, sistema: str) -> list[frozenset[str]]:
        """Quem joga com quem — SEM a cor, de proposito.

        A cor do tabuleiro 1 na primeira rodada e SORTEADA dentro do Gacrux
        (rodar o mesmo torneio duas vezes troca as cores), e e assim que a FIDE
        manda. O que o ranking inicial decide e o ADVERSARIO, e e isso que estes
        testes comparam — asserir cor aqui daria um teste instavel que falha uma
        vez a cada tres execucoes.
        """
        tournament_id, nomes = self._torneio(sistema)
        rodada = self.service.generate_next_round(tournament_id)
        return sorted(
            (
                frozenset({nomes[p["white_player_id"]], nomes[p["black_player_id"]]})
                for p in self.db.get_pairings_for_round(int(rodada["id"]))
                if not p.get("is_bye")
            ),
            key=lambda mesa: sorted(mesa),
        )

    def test_os_dois_motores_pareiam_o_mesmo_torneio_igual(self) -> None:
        """Era aqui que o mesmo torneio dava dois pareamentos diferentes."""
        self.assertEqual(self._mesas("fide_dutch"), self._mesas("gacrux_swiss"))

    def test_motor_padrao_usa_a_ordem_declarada(self) -> None:
        mesas = self._mesas("gacrux_swiss")
        # Pela ordem nacional o cabeca e "Nacional 1", que enfrenta o 3o da lista.
        self.assertIn(frozenset({"Nacional 1", "FIDE alto"}), mesas)
        # Pela ordem do rating FIDE (o defeito) o par seria "Nacional 2 x FIDE alto".
        self.assertNotIn(frozenset({"Nacional 2", "FIDE alto"}), mesas)


class ArquivoDaFederacaoTest(CoreServiceTestCase):
    def _trf(self, initial_order: str) -> str:
        tournament_id = self.db.create_tournament("Aberto", rounds_count=3)
        self.db.save_tournament_settings(
            tournament_id, {"federation": "BRA", "initial_order": initial_order}
        )
        for nome, nac, intl in (
            ("Nacional 1", 2400, 0),
            ("FIDE alto", 1000, 2500),
        ):
            self.db.create_player(
                tournament_id, name=nome, national_rating=nac,
                international_rating=intl, rating=nac,
            )
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "t.trf"
            self.export_service.export_chess_results_trf(tournament_id, destino)
            return destino.read_text(encoding="utf-8")

    def test_sno_do_trf_segue_a_ordem_declarada(self) -> None:
        conteudo = self._trf("national_rating")
        primeiro = [linha for linha in conteudo.splitlines() if linha.startswith("001")][0]
        self.assertIn("Nacional 1", primeiro)

    def test_ordem_padrao_mantem_o_arquivo_como_era(self) -> None:
        """Torneio que nunca escolheu ordem sai igual ao de antes da correcao."""
        conteudo = self._trf("rating")
        primeiro = [linha for linha in conteudo.splitlines() if linha.startswith("001")][0]
        self.assertIn("FIDE alto", primeiro)
