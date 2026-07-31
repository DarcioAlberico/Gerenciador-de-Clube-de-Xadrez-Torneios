"""ARB-05 — retirada e reentrada com histórico por rodada.

`players.player_status` é um campo ÚNICO: guarda o estado de agora e apaga o
anterior. `withdrawn` e `absent` produziam o mesmo efeito (`active = 0`) e não
sobrava rastro de "saiu na rodada 3, voltou na 5" — nem para a ata, nem para
explicar por que um jogador some do pareamento no meio do evento.

Sobre o TRF: ele não tem código para separar "desistiu" de "faltou". As duas
viram `0000 - Z` (não pareado, zero ponto), e isso está certo — o que a FIDE
distingue é `Z` de `-` (pareado e não compareceu, que é forfeit e exige mesa).
A diferença entre desistência e ausência é do regulamento, e por isso ela vive
na ata. Há teste para as duas afirmações.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from src.services.constants import AppError
from src.services.pairing.participation import (
    STATUS_ABSENT,
    STATUS_ACTIVE,
    STATUS_WITHDRAWN,
    absence_rounds,
    change_error,
    effective_round,
    history_lines,
    is_out,
    status_at_round,
    summarize,
)
from tests.support.core_service_base import CoreServiceTestCase


def _evento(rodada: int, status: str, motivo: str = "", ident: int = 0) -> dict:
    return {"id": ident or rodada, "round_number": rodada, "status": status, "reason": motivo}


class HistoricoPuroTest(unittest.TestCase):
    """O que o histórico responde, sem banco."""

    def test_sem_evento_o_jogador_sempre_jogou(self) -> None:
        self.assertEqual(STATUS_ACTIVE, status_at_round([], 5))
        self.assertEqual([], absence_rounds([], 5))

    def test_saiu_na_3_e_voltou_na_5(self) -> None:
        """O caso que a espec descreve, e que o campo unico nao guardava."""
        historico = [_evento(3, STATUS_WITHDRAWN), _evento(5, STATUS_ACTIVE)]

        self.assertEqual(STATUS_ACTIVE, status_at_round(historico, 2))
        self.assertEqual(STATUS_WITHDRAWN, status_at_round(historico, 3))
        self.assertEqual(STATUS_WITHDRAWN, status_at_round(historico, 4))
        self.assertEqual(STATUS_ACTIVE, status_at_round(historico, 5))
        self.assertEqual([3, 4], absence_rounds(historico, 7))

    def test_ausencia_e_desistencia_tiram_do_pareamento_igual(self) -> None:
        """O efeito e o mesmo; o que muda e o que a ata diz."""
        self.assertTrue(is_out(STATUS_WITHDRAWN))
        self.assertTrue(is_out(STATUS_ABSENT))
        self.assertFalse(is_out(STATUS_ACTIVE))

    def test_a_mudanca_vale_da_PROXIMA_rodada(self) -> None:
        """A rodada em andamento ja foi pareada: tirar alguem agora nao desfaz a mesa."""
        self.assertEqual(1, effective_round(None))
        self.assertEqual(4, effective_round({"number": 3, "status": "generated"}))
        self.assertEqual(4, effective_round({"number": 3, "status": "closed"}))

    def test_repetir_o_estado_atual_e_recusado(self) -> None:
        erro = change_error(new_status=STATUS_ABSENT, current_status=STATUS_ABSENT, reason="")
        self.assertIn("ja esta como", erro)

    def test_reentrada_de_desistente_exige_motivo(self) -> None:
        """Voltar quem DESISTIU e decisao arbitral, e vai para a ata."""
        erro = change_error(
            new_status=STATUS_ACTIVE, current_status=STATUS_WITHDRAWN, reason=""
        )
        self.assertIn("decisao arbitral", erro)
        self.assertEqual(
            "",
            change_error(
                new_status=STATUS_ACTIVE, current_status=STATUS_WITHDRAWN, reason="apelacao deferida"
            ),
        )

    def test_volta_de_quem_so_faltou_nao_exige_motivo(self) -> None:
        self.assertEqual(
            "", change_error(new_status=STATUS_ACTIVE, current_status=STATUS_ABSENT, reason="")
        )

    def test_estado_inventado_nao_entra_no_historico(self) -> None:
        self.assertIn(
            "invalido", change_error(new_status="ferias", current_status=STATUS_ACTIVE, reason="")
        )

    def test_as_linhas_do_historico_saem_em_ordem(self) -> None:
        historico = [_evento(5, STATUS_ACTIVE, "voltou"), _evento(3, STATUS_WITHDRAWN, "viagem")]
        self.assertEqual(
            ["R3 — Desistente: viagem", "R5 — Ativo: voltou"], history_lines(historico)
        )

    def test_o_resumo_agrupa_as_rodadas_de_fora(self) -> None:
        historico = [_evento(3, STATUS_WITHDRAWN), _evento(6, STATUS_ACTIVE)]
        resumo = summarize(historico, 7)
        self.assertIn("Fora R3-R5", resumo)
        self.assertIn("R3 — Desistente", resumo)

    def test_o_resumo_separa_faixas_descontinuas(self) -> None:
        historico = [
            _evento(2, STATUS_ABSENT),
            _evento(3, STATUS_ACTIVE),
            _evento(5, STATUS_ABSENT),
            _evento(6, STATUS_ACTIVE),
        ]
        self.assertIn("Fora R2, R5", summarize(historico, 8))

    def test_sem_evento_nao_ha_resumo(self) -> None:
        self.assertEqual("", summarize([], 5))


class ParticipacaoNoServicoTest(CoreServiceTestCase):
    """O caminho inteiro: sair, ser excluído do pareamento, voltar."""

    def setUp(self) -> None:
        super().setUp()
        self.player_ids = self._create_players(6)

    def test_retirada_registra_estado_historico_e_auditoria(self) -> None:
        rodada = self.service.set_player_participation(
            self.tournament_id, self.player_ids[0], STATUS_WITHDRAWN, "viagem"
        )

        self.assertEqual(1, rodada, "sem rodada gerada, vale da primeira")
        jogador = self.db.get_player(self.player_ids[0])
        self.assertEqual(STATUS_WITHDRAWN, jogador["player_status"])
        self.assertEqual(0, int(jogador["active"]))
        historico = self.service.participation_history(self.tournament_id, self.player_ids[0])
        self.assertEqual(1, len(historico))
        self.assertEqual("viagem", historico[0]["reason"])
        acoes = {
            evento["action"]
            for evento in self.db.list_audit_events(self.tournament_id, limit=50)
        }
        self.assertIn("player_participation_changed", acoes)

    def test_a_mudanca_vale_da_rodada_seguinte_a_gerada(self) -> None:
        self.service.generate_next_round(self.tournament_id)

        rodada = self.service.set_player_participation(
            self.tournament_id, self.player_ids[0], STATUS_WITHDRAWN, "desistiu"
        )

        self.assertEqual(2, rodada)

    def test_quem_saiu_nao_e_pareado_e_quem_volta_e(self) -> None:
        """Criterio de aceite: sai, volta, e o pareamento acompanha."""
        self.service.set_player_participation(
            self.tournament_id, self.player_ids[0], STATUS_WITHDRAWN, "viagem"
        )
        primeira = self.service.generate_next_round(self.tournament_id)
        pareados_r1 = self._pareados(primeira)
        for mesa in self.db.get_pairings_for_round(int(primeira["id"])):
            if not mesa["is_bye"]:
                self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(primeira["id"]))

        self.service.set_player_participation(
            self.tournament_id, self.player_ids[0], STATUS_ACTIVE, "apelacao deferida"
        )
        segunda = self.service.generate_next_round(self.tournament_id)

        self.assertNotIn(self.player_ids[0], pareados_r1)
        self.assertIn(self.player_ids[0], self._pareados(segunda))

    def _pareados(self, round_data: dict) -> set[int]:
        ids: set[int] = set()
        for mesa in self.db.get_pairings_for_round(int(round_data["id"])):
            ids.add(int(mesa["white_player_id"]))
            if mesa.get("black_player_id"):
                ids.add(int(mesa["black_player_id"]))
        return ids

    def test_o_historico_mostra_as_rodadas_de_ausencia(self) -> None:
        self.service.generate_next_round(self.tournament_id)
        self.service.set_player_participation(
            self.tournament_id, self.player_ids[0], STATUS_ABSENT, "sem aviso"
        )

        resumo = {
            item["player_id"]: item
            for item in self.service.participation_summary(self.tournament_id)
        }

        self.assertIn(self.player_ids[0], resumo)
        self.assertIn("Fora R2", resumo[self.player_ids[0]]["summary"])
        self.assertEqual(STATUS_ABSENT, resumo[self.player_ids[0]]["final_status"])

    def test_reentrada_de_desistente_sem_motivo_e_recusada(self) -> None:
        self.service.set_player_participation(
            self.tournament_id, self.player_ids[0], STATUS_WITHDRAWN, "viagem"
        )

        with self.assertRaisesRegex(AppError, "decisao arbitral"):
            self.service.set_player_participation(
                self.tournament_id, self.player_ids[0], STATUS_ACTIVE
            )

    def test_jogador_de_outro_torneio_e_recusado(self) -> None:
        outro = self.tournament_service.create_tournament(
            {"name": "Outro", "rounds_count": "3", "bye_points": "1"}
        )
        with self.assertRaisesRegex(AppError, "Jogador nao encontrado"):
            self.service.set_player_participation(outro, self.player_ids[0], STATUS_ABSENT)

    def test_torneio_sem_mudanca_nao_tem_resumo(self) -> None:
        self.assertEqual([], self.service.participation_summary(self.tournament_id))


class AtaEArquivoTest(CoreServiceTestCase):
    """Onde a distinção aparece: na ata (texto) e no TRF (código)."""

    def setUp(self) -> None:
        super().setUp()
        self.player_ids = self._create_players(5)

    def test_a_ata_lista_desistencias_com_a_rodada(self) -> None:
        self.service.set_player_participation(
            self.tournament_id, self.player_ids[0], STATUS_WITHDRAWN, "viagem de trabalho"
        )

        secoes = self.export_service._tournament_minutes_sections(self.tournament_id)
        titulos = [titulo for titulo, _cabecalho, _linhas in secoes]
        self.assertIn("Desistências, ausências e reentradas", titulos)
        _titulo, cabecalho, linhas = next(
            secao for secao in secoes if secao[0] == "Desistências, ausências e reentradas"
        )
        self.assertIn("Rodadas fora", cabecalho)
        self.assertTrue(any("viagem de trabalho" in str(linha) for linha in linhas))

    def test_a_ata_nao_ganha_a_secao_quando_ninguem_saiu(self) -> None:
        secoes = self.export_service._tournament_minutes_sections(self.tournament_id)
        titulos = [titulo for titulo, _cabecalho, _linhas in secoes]
        self.assertNotIn("Desistências, ausências e reentradas", titulos)

    def test_o_trf_separa_nao_pareado_de_forfait(self) -> None:
        """`Z` = nao pareado (zero ponto); `-` = pareado e nao compareceu.

        E a distincao que a FIDE faz — e a unica que o arquivo tem. "Desistiu"
        x "faltou" e do regulamento, e sai na ata.
        """
        from src.services.federation_exporters import TRF16Exporter

        round_data = self.service.generate_next_round(self.tournament_id)
        mesas = [
            item
            for item in self.db.get_pairings_for_round(int(round_data["id"]))
            if not item["is_bye"]
        ]
        self.service.update_result(self.tournament_id, int(mesas[0]["id"]), "1F-0F")
        self.service.update_result(self.tournament_id, int(mesas[1]["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(round_data["id"]))
        # Um jogador desiste depois da rodada 1: as rodadas seguintes ficam sem
        # mesa, e o TRF as escreve como `0000 - Z`.
        self.service.set_player_participation(
            self.tournament_id, self.player_ids[0], STATUS_WITHDRAWN, "desistiu"
        )

        # A rodada 2 e gerada SEM o desistente: e ali que o TRF escreve
        # `0000 - Z` para ele — o exportador so emite celula de rodada que
        # existe, entao rodada futura nao vira `Z` nenhum.
        segunda = self.service.generate_next_round(self.tournament_id)
        for mesa in self.db.get_pairings_for_round(int(segunda["id"])):
            if not mesa["is_bye"]:
                self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(segunda["id"]))

        destino = Path(self.temp_dir.name) / "participacao.trf"
        TRF16Exporter(self.export_service).export(self.tournament_id, destino)
        conteudo = destino.read_text(encoding="utf-8")
        linhas = [linha for linha in conteudo.splitlines() if linha.startswith("001 ")]

        self.assertTrue(any(" +  " in linha or linha.rstrip().endswith("+") for linha in linhas))
        self.assertTrue(any("-" in linha for linha in linhas))
        self.assertIn("0000 - Z", conteudo)


if __name__ == "__main__":
    unittest.main()
