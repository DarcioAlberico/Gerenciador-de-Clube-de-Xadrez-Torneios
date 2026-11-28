"""RG2-13 — a importação de TRF não perde jogo calada nem fecha rodada sem resultado.

**D8** (decidida pelo dono em 2026-11-28): importar TRF de torneio **em
andamento** é uso suportado — é o caminho para continuar no Albericus um
torneio começado no Swiss-Manager. Por isso a rodada pareada e ainda sem
resultado entra **aberta**, e o total de rodadas vem do 142/XXR.

Antes: a leitura da linha 001 parava na primeira célula em branco (o
entrante tardio perdia a R2), adversário inexistente ou assimétrico sumia sem
aviso, rank ilegível virava ``len(players)+1`` e colidia, e toda rodada
nascia fechada — um torneio de 5 rodadas na R2 virava "2 rodadas, encerrado".
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from src.services.constants import AppError
from src.services.federation_exporters import TRF16Exporter
from src.services.trf_import import parse_trf
from tests.support.core_service_base import CoreServiceTestCase


def _celula(adversario: int, cor: str, resultado: str) -> str:
    return f"{adversario:4d} {cor} {resultado}  "


def _linha(rank: str | int, nome: str, *celulas: str) -> str:
    rank_texto = f"{rank:>4}" if isinstance(rank, str) else f"{rank:4d}"
    base = f"001 {rank_texto} m    {nome:<33} {1800:4d} BRA {'':>11} {'2000/01/01':<10} {'0.0':>4} {rank_texto}  "
    return (base + "".join(celulas)).rstrip() + "\r\n"


EM_BRANCO = " " * 10


class LeituraDaLinhaTest(CoreServiceTestCase):
    def test_r1_em_branco_devolve_duas_celulas(self) -> None:
        conteudo = _linha(1, "Ana", EM_BRANCO, _celula(2, "w", "1")) + _linha(2, "Bia", EM_BRANCO, _celula(1, "b", "0"))
        jogadores = parse_trf(conteudo)["players"]
        self.assertEqual(2, len(jogadores[0]["rounds"]))
        self.assertEqual("", jogadores[0]["rounds"][0]["opponent_rank"])
        self.assertEqual("2", jogadores[0]["rounds"][1]["opponent_rank"])

    def test_adversario_inexistente_vira_aviso_com_rank_e_linha(self) -> None:
        conteudo = (
            "012 Aberto\r\n"
            + _linha(1, "Ana", _celula(2, "w", "1"))
            + _linha(2, "Bia", _celula(1, "b", "0"))
            + _linha(3, "Cris", _celula(9, "w", "1"))
        )
        avisos = parse_trf(conteudo)["warnings"]
        (aviso,) = [texto for texto in avisos if "rank 9" in texto]
        self.assertIn("linha 4", aviso)
        self.assertIn("Cris", aviso)

    def test_jogo_assimetrico_vira_aviso(self) -> None:
        conteudo = (
            _linha(1, "Ana", _celula(2, "w", "1"))
            + _linha(2, "Bia", _celula(3, "b", "0"))
            + _linha(3, "Cris", _celula(2, "w", "1"))
        )
        avisos = parse_trf(conteudo)["warnings"]
        self.assertTrue(any("Ana" in texto and "rank 2" in texto for texto in avisos), avisos)

    def test_letra_desconhecida_vira_aviso(self) -> None:
        conteudo = _linha(1, "Ana", _celula(2, "w", "X")) + _linha(2, "Bia", _celula(1, "b", "X"))
        avisos = parse_trf(conteudo)["warnings"]
        self.assertTrue(any('"X"' in texto for texto in avisos), avisos)

    def test_arquivo_coerente_nao_tem_aviso(self) -> None:
        conteudo = _linha(1, "Ana", _celula(2, "w", "1")) + _linha(2, "Bia", _celula(1, "b", "0"))
        self.assertEqual([], parse_trf(conteudo)["warnings"])

    def test_total_de_rodadas_vem_do_xxr(self) -> None:
        conteudo = "XXR 7\r\n" + _linha(1, "Ana", _celula(2, "w", "1")) + _linha(2, "Bia", _celula(1, "b", "0"))
        self.assertEqual(7, parse_trf(conteudo)["rounds_count"])

    def test_total_de_rodadas_vem_do_142(self) -> None:
        conteudo = "142 9\r\n" + _linha(1, "Ana", _celula(2, "w", "1")) + _linha(2, "Bia", _celula(1, "b", "0"))
        self.assertEqual(9, parse_trf(conteudo)["rounds_count"])


class ImportacaoTest(CoreServiceTestCase):
    def _arquivo(self, conteudo: str) -> Path:
        caminho = Path(self.temp_dir.name) / "entrada.trf"
        caminho.write_text(conteudo, encoding="utf-8", newline="")
        return caminho

    def test_rank_duplicado_recusa_e_nao_cria_torneio(self) -> None:
        antes = len(self.db.list_tournaments())
        conteudo = _linha(1, "Ana", _celula(2, "w", "1")) + _linha(1, "Bia", _celula(1, "b", "0"))
        with self.assertRaisesRegex(AppError, "rank 1"):
            self.import_service.import_trf(self._arquivo(conteudo))
        self.assertEqual(antes, len(self.db.list_tournaments()))

    def test_rank_ilegivel_recusa(self) -> None:
        conteudo = _linha(1, "Ana", _celula(2, "w", "1")) + _linha("ab", "Bia", _celula(1, "b", "0"))
        with self.assertRaisesRegex(AppError, "linha 2"):
            self.import_service.import_trf(self._arquivo(conteudo))

    def test_previa_mostra_os_avisos_sem_gravar(self) -> None:
        antes = len(self.db.list_tournaments())
        conteudo = _linha(1, "Ana", _celula(2, "w", "1")) + _linha(2, "Bia", _celula(9, "b", "0"))
        previa = self.import_service.preview_trf(self._arquivo(conteudo))
        self.assertEqual(2, previa["players"])
        self.assertTrue(any("rank 9" in texto for texto in previa["warnings"]))
        self.assertEqual(antes, len(self.db.list_tournaments()))

    def test_round_trip_de_torneio_em_andamento(self) -> None:
        """Cenário ``r5/t7``: 5 rodadas, R1 fechada, R2 pareada e sem resultado."""
        self._create_players(6)
        r1 = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(int(r1["id"]))
        self.service.close_round(self.tournament_id, int(r1["id"]))
        self.service.generate_next_round(self.tournament_id)
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "andamento.trf"
            TRF16Exporter(self.export_service).export(self.tournament_id, caminho)
            importado = self.import_service.import_trf(caminho)

        novo = int(importado["tournament_id"])
        self.assertEqual(5, self.db.get_tournament(novo)["rounds_count"])
        estados = {int(rodada["number"]): rodada["status"] for rodada in self.db.list_rounds(novo)}
        self.assertEqual("closed", estados[1])
        self.assertIn(2, estados, "a R2 pareada não pode sumir")
        self.assertNotEqual("closed", estados[2], "rodada sem resultado não pode nascer fechada")
        self.assertEqual([], importado["warnings"])


class TelaMostraOsAvisosTest(CoreServiceTestCase):
    """A tela pergunta antes de importar quando o TRF tem avisos."""

    def _perguntar(self, previa: dict[str, object], resposta: bool) -> tuple[bool, list[str]]:
        from types import SimpleNamespace

        from src.ui.screens.tournaments.view import TournamentListView

        mensagens: list[str] = []

        def confirmar(_titulo: str, mensagem: str, **_kw: object) -> bool:
            mensagens.append(mensagem)
            return resposta

        tela = SimpleNamespace(host=SimpleNamespace(_confirm_action=confirmar))
        return TournamentListView._confirm_trf_warnings(tela, previa), mensagens

    def test_sem_aviso_nao_pergunta(self) -> None:
        self.assertEqual((True, []), self._perguntar({"name": "Aberto", "warnings": []}, False))

    def test_com_aviso_mostra_o_texto_e_respeita_o_nao(self) -> None:
        aviso = "Cris (rank 3, linha 4), rodada 1: aponta para o rank 9"
        aceitou, mensagens = self._perguntar({"name": "Aberto", "warnings": [aviso]}, False)
        self.assertFalse(aceitou)
        self.assertIn(aviso, mensagens[0])
