"""FED-06 — normas FIDE conforme o Handbook B.01 e certificado IT3.

O assistente de normas indicava norma onde não havia. Três erros somados:

1. **CM, WCM, NM e WNM contavam como "titulado"**. CM e WCM estão fora por
   texto expresso do 1.4.5; NM e WNM nunca foram título FIDE. Com eles dentro,
   um open doméstico cheio de CMs fechava o piso de 50% de titulados — e não
   havia contagem por NÍVEL (a norma de GM exige três GMs, não três titulados
   quaisquer).
2. **A federação do próprio candidato entrava na contagem de federações.** O
   1.4.3 pede duas federações ALÉM da dele; contando a própria, um torneio
   estadual com dois convidados já "passava".
3. **Faltavam os tetos e o piso**: no máximo 3/5 dos adversários da federação do
   candidato, 2/3 de uma mesma federação, 20% sem rating — e o piso de rating
   ajustado (1.4.6), que sobe UM adversário, o mais fraco, e não todos.

Sem o IT3 nada disso chegava à FIDE: o árbitro via "norma atingida" na tela e
não tinha o formulário para submeter.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.services.constants import AppError
from src.services.norms import (
    NORM_REQUIREMENTS,
    adjusted_ratings,
    build_certificate,
    evaluate_norms,
    is_title_holder,
    limits_for,
    norm_candidates,
)
from src.services.norms.it3 import format_date, result_label
from src.services.norms.opponents import unrated_without_points
from tests.support.core_service_base import CoreServiceTestCase
from tests.support.norm_fixtures import (
    gm_norm_opponents,
    opponent,
    replace_opponent,
    weak_field_opponents,
)


def _indicator(evaluations, title: str, name_fragment: str):
    evaluation = next(item for item in evaluations if item.title == title)
    return next(item for item in evaluation.indicators if name_fragment in item.name)


class TabelaDoAnexoTest(unittest.TestCase):
    """O Anexo do B.01 publica os limites por número de rodadas.

    O motor não copia a tabela: aplica as frações do texto com o arredondamento
    de cada uma. O teste existe para provar que a derivação bate com o que a
    FIDE publicou — se divergir, é a derivação que está errada.
    """

    ANEXO = {
        #        titulados, do nível, própria fed., uma fed., sem rating
        9: (5, 3, 5, 6, 2),
        10: (5, 4, 6, 6, 2),
        11: (6, 4, 6, 7, 2),
        12: (6, 4, 7, 8, 2),
        13: (7, 5, 7, 8, 2),
    }

    def test_limites_batem_com_o_anexo_publicado(self) -> None:
        for partidas, esperado in self.ANEXO.items():
            with self.subTest(partidas=partidas):
                limites = limits_for(partidas)
                self.assertEqual(
                    (
                        limites["min_title_holders"],
                        limites["min_level_title_holders"],
                        limites["max_own_federation"],
                        limites["max_single_federation"],
                        limites["max_unrated"],
                    ),
                    esperado,
                )

    def test_minimo_de_titulados_do_nivel_nunca_cai_abaixo_de_tres(self) -> None:
        """1/3 de 7 é 2,33 — mas o regulamento diz "com mínimo de 3"."""
        self.assertEqual(3, limits_for(7)["min_level_title_holders"])

    def test_duas_federacoes_alem_da_do_candidato_em_qualquer_tamanho(self) -> None:
        for partidas in range(9, 14):
            self.assertEqual(2, limits_for(partidas)["min_other_federations"])


class TituladosTest(unittest.TestCase):
    def test_cm_wcm_nm_e_wnm_nao_sao_titulados_para_norma(self) -> None:
        for titulo in ("CM", "WCM", "NM", "WNM", "", "MF"):
            with self.subTest(titulo=titulo):
                self.assertFalse(is_title_holder(titulo))

    def test_titulos_fide_contam(self) -> None:
        for titulo in ("GM", "IM", "FM", "WGM", "WIM", "WFM"):
            with self.subTest(titulo=titulo):
                self.assertTrue(is_title_holder(titulo))

    def test_open_de_cms_nao_indica_norma(self) -> None:
        """O caso que o motor antigo dava como norma."""
        avaliacoes = evaluate_norms("BRA", "M", weak_field_opponents())
        self.assertFalse(any(item.meets for item in avaliacoes))
        titulados = _indicator(avaliacoes, "GM", "titulados (50%)")
        self.assertEqual(0, titulados.actual)

    def test_norma_de_gm_exige_gms_e_nao_titulados_quaisquer(self) -> None:
        """Nove FMs cumprem os 50% de titulados e não cumprem o 1/3 de GMs."""
        campo = [
            opponent(index + 1, title="FM", rating=2400, federation=federation, points=points)
            for index, (federation, points) in enumerate(
                zip(["BRA", "ARG", "URU"] * 3, [1.0] * 7 + [0.0, 0.0])
            )
        ]
        avaliacoes = evaluate_norms("BRA", "M", campo)
        self.assertEqual(9, _indicator(avaliacoes, "GM", "titulados (50%)").actual)
        nivel = _indicator(avaliacoes, "GM", "Adversários GM (")
        self.assertEqual(0, nivel.actual)
        self.assertEqual(3, nivel.required)
        self.assertFalse(next(item for item in avaliacoes if item.title == "GM").meets)

    def test_campo_com_tres_gms_fecha_a_norma(self) -> None:
        avaliacao = next(
            item for item in evaluate_norms("BRA", "M", gm_norm_opponents()) if item.title == "GM"
        )
        self.assertTrue(avaliacao.meets, avaliacao.missing)
        self.assertEqual(3, avaliacao.level_title_holders)
        self.assertEqual(9, avaliacao.title_holders)


class FederacoesTest(unittest.TestCase):
    def test_federacao_do_candidato_fica_fora_da_contagem(self) -> None:
        """Critério de aceite do FED-06."""
        avaliacao = next(
            item for item in evaluate_norms("BRA", "M", gm_norm_opponents()) if item.title == "GM"
        )
        # O campo tem BRA, ARG e URU; contam duas.
        self.assertEqual(2, avaliacao.other_federations)

    @staticmethod
    def _campo(federacoes: list[str]):
        """O campo de norma de GM com as federações trocadas, uma a uma."""
        campo = gm_norm_opponents()
        for posicao, federacao in enumerate(federacoes):
            campo = replace_opponent(campo, posicao, federation=federacao)
        return campo

    def test_so_uma_federacao_alem_da_do_candidato_reprova(self) -> None:
        avaliacoes = evaluate_norms("BRA", "M", self._campo(["ARG"] * 9))
        indicador = _indicator(avaliacoes, "GM", "Federações além")
        self.assertEqual(1, indicador.actual)
        self.assertFalse(indicador.ok)

    def test_teto_de_tres_quintos_da_federacao_do_candidato(self) -> None:
        campo = self._campo(["BRA"] * 6 + ["ARG", "URU", "ARG"])
        indicador = _indicator(evaluate_norms("BRA", "M", campo), "GM", "federação do candidato")
        self.assertEqual(6, indicador.actual)
        self.assertEqual(5, indicador.required)
        self.assertFalse(indicador.ok)

    def test_cinco_da_federacao_do_candidato_em_nove_ainda_cabem(self) -> None:
        campo = self._campo(["BRA"] * 5 + ["ARG", "URU", "ARG", "URU"])
        indicador = _indicator(evaluate_norms("BRA", "M", campo), "GM", "federação do candidato")
        self.assertEqual(5, indicador.actual)
        self.assertTrue(indicador.ok)

    def test_teto_de_dois_tercos_de_uma_mesma_federacao(self) -> None:
        campo = self._campo(["ARG"] * 7 + ["BRA", "URU"])
        indicador = _indicator(evaluate_norms("BRA", "M", campo), "GM", "uma mesma federação")
        self.assertEqual(7, indicador.actual)
        self.assertEqual(6, indicador.required)
        self.assertFalse(indicador.ok)


class PisoDeRatingTest(unittest.TestCase):
    """1.4.6 — o piso ajustado sobe UM adversário, o mais fraco."""

    def test_um_so_adversario_sobe_ate_o_piso(self) -> None:
        campo = replace_opponent(gm_norm_opponents(), 0, rating=1900)
        campo = replace_opponent(campo, 1, rating=2000)
        ratings = adjusted_ratings(campo, NORM_REQUIREMENTS["GM"])
        # O de 1900 (o mais fraco) sobe para 2200; o de 2000 fica onde estava.
        self.assertEqual(2200, ratings[0])
        self.assertEqual(2000, ratings[1])

    def test_piso_e_por_norma(self) -> None:
        campo = replace_opponent(gm_norm_opponents(), 0, rating=1900)
        self.assertEqual(2200, adjusted_ratings(campo, NORM_REQUIREMENTS["GM"])[0])
        self.assertEqual(2050, adjusted_ratings(campo, NORM_REQUIREMENTS["IM"])[0])
        self.assertEqual(1900, adjusted_ratings(campo, NORM_REQUIREMENTS["WIM"])[0])

    def test_sem_rating_conta_como_1400_antes_do_piso(self) -> None:
        campo = replace_opponent(gm_norm_opponents(), 0, rating=0)
        campo = replace_opponent(campo, 1, rating=1500)
        ratings = adjusted_ratings(campo, NORM_REQUIREMENTS["WIM"])
        # 1400 (o não ratado) é o mais fraco e sobe ao piso da WIM; 1500 fica.
        self.assertEqual(1850, ratings[0])
        self.assertEqual(1500, ratings[1])

    def test_campo_sem_ninguem_abaixo_do_piso_nao_muda(self) -> None:
        campo = gm_norm_opponents()
        self.assertEqual(
            [2400] * 9, adjusted_ratings(campo, NORM_REQUIREMENTS["GM"])
        )

    def test_ra_sai_inteiro_como_a_fide_calcula(self) -> None:
        """Ra é inteiro: é o campo do IT3 e é como o regulamento conta."""
        campo = replace_opponent(gm_norm_opponents(), 0, rating=2404)
        avaliacao = next(
            item for item in evaluate_norms("BRA", "M", campo) if item.title == "GM"
        )
        # Média real 2400,44 → 2400.
        self.assertEqual(2400, avaliacao.average_opponent)
        self.assertIsInstance(avaliacao.average_opponent, int)


class NaoRatadosTest(unittest.TestCase):
    def test_teto_de_vinte_por_cento_mais_um(self) -> None:
        campo = list(gm_norm_opponents())
        for posicao in range(3):
            campo = replace_opponent(campo, posicao, rating=0)
        avaliacoes = evaluate_norms("BRA", "M", campo)
        indicador = _indicator(avaliacoes, "GM", "sem rating")
        self.assertEqual(3, indicador.actual)
        self.assertEqual(2, indicador.required)
        self.assertFalse(indicador.ok)

    def test_dois_nao_ratados_em_nove_ainda_cabem(self) -> None:
        campo = list(gm_norm_opponents())
        for posicao in range(2):
            campo = replace_opponent(campo, posicao, rating=0)
        indicador = _indicator(evaluate_norms("BRA", "M", campo), "GM", "sem rating")
        self.assertTrue(indicador.ok)

    def test_nao_ratado_que_zerou_contra_ratados_e_descartavel(self) -> None:
        """1.4.2 — em round-robin, a partida contra ele não conta."""
        partidas = [
            {"white_id": 1, "black_id": 9, "white_points": 1.0, "black_points": 0.0},
            {"white_id": 9, "black_id": 2, "white_points": 0.0, "black_points": 1.0},
            {"white_id": 1, "black_id": 2, "white_points": 0.5, "black_points": 0.5},
        ]
        ratings = {1: 2400, 2: 2350, 9: 0}
        self.assertEqual({9}, unrated_without_points(partidas, ratings))

    def test_nao_ratado_que_pontuou_continua_valendo(self) -> None:
        partidas = [
            {"white_id": 1, "black_id": 9, "white_points": 0.5, "black_points": 0.5},
        ]
        self.assertEqual(set(), unrated_without_points(partidas, {1: 2400, 9: 0}))


class FormatacaoDoIT3Test(unittest.TestCase):
    def test_data_iso_vira_formato_de_formulario(self) -> None:
        self.assertEqual("04/08/2026", format_date("2026-08-04"))
        self.assertEqual("04.08.2026", format_date("04.08.2026"))
        self.assertEqual("", format_date(None))

    def test_resultado_sai_como_a_fide_escreve(self) -> None:
        self.assertEqual("1", result_label(1.0))
        self.assertEqual("½", result_label(0.5))
        self.assertEqual("0", result_label(0.0))


class CertificadoIT3Test(CoreServiceTestCase):
    """Torneio de 9 rodadas com uma norma de GM fechada e o IT3 emitido."""

    TITULOS = ["GM", "GM", "GM", "IM", "IM", "IM", "FM", "FM", "FM"]
    FEDERACOES = ["BRA", "ARG", "URU"] * 3
    RESULTADOS = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0]

    def setUp(self) -> None:
        super().setUp()
        self.tournament_id = self.db.create_tournament("Aberto Internacional", rounds_count=9)
        self.db.save_tournament_settings(
            self.tournament_id,
            {
                "federation": "BRA",
                "chief_arbiter": "Ana Souza",
                "fide_event_id": "998877",
                "pairing_method": "swiss",
            },
        )
        self.candidate_id = self.db.create_player(
            self.tournament_id,
            name="Joao Silva",
            surname="Silva",
            given_name="Joao",
            federation_id="BRA",
            fide_id="2900001",
            sex="M",
            international_rating=2500,
            rating=2500,
        )
        self.opponent_ids = [
            self.db.create_player(
                self.tournament_id,
                name=f"Adversario {index + 1}",
                surname=f"Sobrenome{index + 1}",
                given_name="Nome",
                federation_id=federation,
                title=title,
                sex="M",
                international_rating=2400,
                rating=2400,
            )
            for index, (title, federation) in enumerate(zip(self.TITULOS, self.FEDERACOES))
        ]
        for index, opponent_id in enumerate(self.opponent_ids):
            venceu = self.RESULTADOS[index] == 1.0
            round_id = self.db.create_round_with_pairings(
                self.tournament_id,
                index + 1,
                [
                    {
                        "board_number": 1,
                        "white_player_id": self.candidate_id,
                        "black_player_id": opponent_id,
                        "result": "1-0" if venceu else "0-1",
                    }
                ],
            )
            self.db.close_round(round_id)

    def _candidatos(self):
        return norm_candidates(
            self.db.list_players(self.tournament_id, active_only=False),
            self.db.get_pairings_for_tournament(self.tournament_id, closed_only=True),
            "fide",
        )

    def test_torneio_fecha_norma_de_gm(self) -> None:
        candidatos = self._candidatos()
        gm = next(item for item in candidatos if item.evaluation.title == "GM")
        self.assertEqual(self.candidate_id, int(gm.player["id"]))
        self.assertEqual(9, gm.evaluation.games)
        self.assertEqual(7.0, gm.evaluation.score)
        self.assertEqual(2400.0, gm.evaluation.average_opponent)
        self.assertGreaterEqual(gm.evaluation.performance, 2600)

    def test_certificado_traz_torneio_candidato_e_partidas(self) -> None:
        gm = next(item for item in self._candidatos() if item.evaluation.title == "GM")
        certificado = build_certificate(
            self.db.get_tournament(self.tournament_id),
            self.db.get_tournament_settings(self.tournament_id) or {},
            gm.player,
            gm.opponents,
            gm.evaluation,
            candidate_name="Silva, Joao",
            candidate_rating=2500,
            chief_arbiter="Ana Souza",
            tournament_type="Individual: Swiss-System",
            rounds=9,
        )
        self.assertEqual("Aberto Internacional", certificado.tournament_name)
        self.assertEqual("998877", certificado.event_id)
        self.assertEqual("Ana Souza", certificado.chief_arbiter)
        self.assertEqual("Silva, Joao", certificado.candidate_name)
        self.assertEqual("2900001", certificado.candidate_fide_id)
        self.assertEqual("BRA", certificado.candidate_federation)
        self.assertEqual("GM", certificado.norm_title)
        self.assertTrue(certificado.meets)
        self.assertEqual([], certificado.missing)
        self.assertEqual(9, certificado.game_count)
        self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8, 9], [jogo.round_number for jogo in certificado.games])
        self.assertEqual(
            ["1", "1", "1", "1", "1", "1", "1", "0", "0"],
            [jogo.result for jogo in certificado.games],
        )
        self.assertEqual(2400, certificado.games[0].rating_used)

    def test_export_gera_pdf_do_it3(self) -> None:
        from pypdf import PdfReader

        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "it3.pdf"
            caminho = self.export_service.export_it3_certificate(self.tournament_id, destino)
            self.assertTrue(caminho.exists())
            self.assertTrue(caminho.read_bytes().startswith(b"%PDF"))
            texto = "\n".join(page.extract_text() or "" for page in PdfReader(caminho).pages)

        self.assertIn("IT3 - TITLE NORM CERTIFICATE", texto)
        self.assertIn("Aberto Internacional", texto)
        self.assertIn("Silva, Joao", texto)
        self.assertIn("2900001", texto)  # FIDE ID do candidato
        self.assertIn("998877", texto)  # Event-ID do torneio
        self.assertIn("Ana Souza", texto)  # arbitro principal
        # A tabela de partidas leva os adversarios e o rating usado pela norma.
        self.assertIn("Sobrenome1", texto)
        self.assertIn("Sobrenome9", texto)
        self.assertIn("exclusiva da FIDE", texto)  # aviso de apoio, nao homologacao

    def test_export_sem_norma_avisa_em_vez_de_gerar_papel_vazio(self) -> None:
        vazio = self.db.create_tournament("Sem norma", rounds_count=3)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AppError) as erro:
                self.export_service.export_it3_certificate(vazio, Path(tmp) / "it3.pdf")
        self.assertIn("Nenhuma norma", str(erro.exception))

    def test_relatorio_de_normas_traz_a_norma_e_as_federacoes_sem_a_do_candidato(self) -> None:
        relatorio = self.norm_assistant_service.evaluate_tournament(self.tournament_id)
        candidato = next(
            item for item in relatorio["players"] if int(item["player_id"]) == self.candidate_id
        )
        self.assertEqual(2, candidato["federations"])
        self.assertEqual(9, candidato["titled_opponents"])
        self.assertIn("Grande Mestre (GM)", candidato["achieved"])
