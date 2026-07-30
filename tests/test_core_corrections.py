"""ARB-01 — correção em rodada fechada: motivo, desbloqueio, cascata, retratos.

Três camadas: as regras puras (motivo, expiração, cascata), o serviço diante de
uma correção real, e o que a correção deixa atrás — pendência no painel e
retratos de classificação reconciliados sem apagar o que foi publicado.
"""

from __future__ import annotations

import unittest

from src.services.constants import AppError
from src.services.pairing.corrections import (
    DEFAULT_UNLOCK_MINUTES,
    MIN_REASON_LENGTH,
    active_unlock,
    cascade_message,
    cascade_rounds,
    clean_reason,
    correction_reason_error,
    expiry_from,
    reconcilable_rounds,
    unlock_is_live,
    unlock_minutes,
    unlock_reason_error,
    unlock_state,
)
from tests.support.core_service_base import CoreServiceTestCase

_AGORA = "2026-07-30 14:00:00"


class MotivoTest(unittest.TestCase):
    def test_vazio_e_recusado_com_recado_que_explica(self) -> None:
        erro = correction_reason_error("")
        self.assertIn("motivo", erro.casefold())
        self.assertIn("prova documental", erro)

    def test_so_espaco_conta_como_vazio(self) -> None:
        self.assertNotEqual("", correction_reason_error("   \n\t "))

    def test_motivo_curto_nao_e_motivo(self) -> None:
        """"ok" numa ata de apelação vale tanto quanto o campo vazio."""
        self.assertNotEqual("", correction_reason_error("ok"))
        self.assertIn(str(MIN_REASON_LENGTH), correction_reason_error("ok"))

    def test_motivo_descritivo_passa(self) -> None:
        self.assertEqual("", correction_reason_error("Arbitro anotou 1-0 no lugar de 0-1"))

    def test_limpeza_normaliza_espacos_e_quebras(self) -> None:
        self.assertEqual("erro de digitacao", clean_reason("  erro   de\n digitacao  "))

    def test_desbloqueio_usa_o_mesmo_criterio(self) -> None:
        self.assertNotEqual("", unlock_reason_error(""))
        self.assertNotEqual("", unlock_reason_error("x"))
        self.assertEqual("", unlock_reason_error("Reclamacao do jogador da mesa 4"))


class ExpiracaoTest(unittest.TestCase):
    def test_janela_padrao_e_curta(self) -> None:
        """O desbloqueio existe para a correção de agora, não para deixar aberta."""
        self.assertEqual("2026-07-30 14:15:00", expiry_from(_AGORA, DEFAULT_UNLOCK_MINUTES))

    def test_janela_fora_da_faixa_volta_ao_padrao(self) -> None:
        for pedido in (0, -5, 10_000, "muitos", None):
            self.assertEqual(DEFAULT_UNLOCK_MINUTES, unlock_minutes(pedido))

    def test_timestamp_quebrado_nasce_expirado(self) -> None:
        """Desbloqueio que nasce expirado é mais seguro do que um eterno."""
        self.assertEqual("ontem", expiry_from("ontem", 15))

    def test_vigente_expirado_e_revogado(self) -> None:
        vigente = {"expires_at": "2026-07-30 14:10:00", "revoked_at": ""}
        expirado = {"expires_at": "2026-07-30 13:59:00", "revoked_at": ""}
        revogado = {"expires_at": "2026-07-30 14:10:00", "revoked_at": "2026-07-30 14:01:00"}
        self.assertTrue(unlock_is_live(vigente, _AGORA))
        self.assertFalse(unlock_is_live(expirado, _AGORA))
        self.assertFalse(unlock_is_live(revogado, _AGORA))
        self.assertFalse(unlock_is_live({"expires_at": ""}, _AGORA))

    def test_vigente_e_o_de_prazo_mais_longo(self) -> None:
        curto = {"expires_at": "2026-07-30 14:05:00", "revoked_at": ""}
        longo = {"expires_at": "2026-07-30 14:30:00", "revoked_at": ""}
        self.assertEqual(longo, active_unlock([curto, longo], _AGORA))
        self.assertIsNone(active_unlock([], _AGORA))


class PermissaoTest(unittest.TestCase):
    def test_desbloqueio_pontual_vem_antes_do_interruptor_global(self) -> None:
        estado = unlock_state(
            [{"expires_at": "2026-07-30 14:10:00", "revoked_at": "", "reason": "mesa 4"}],
            _AGORA,
            dangerous_changes=True,
        )
        self.assertTrue(estado.allowed)
        self.assertEqual("unlock", estado.source)
        self.assertIn("mesa 4", estado.label())

    def test_interruptor_global_ainda_vale(self) -> None:
        """Não se tira um caminho que torneios em andamento já usam."""
        estado = unlock_state([], _AGORA, dangerous_changes=True)
        self.assertTrue(estado.allowed)
        self.assertEqual("dangerous_changes", estado.source)
        self.assertIn("qualquer rodada", estado.label())

    def test_sem_nenhum_dos_dois_a_rodada_fica_fechada(self) -> None:
        estado = unlock_state([], _AGORA, dangerous_changes=False)
        self.assertFalse(estado.allowed)
        self.assertIn("Desbloqueie", estado.label())


class CascataTest(unittest.TestCase):
    _RODADAS = [
        {"number": 1, "status": "closed"},
        {"number": 2, "status": "closed"},
        {"number": 3, "status": "closed"},
        {"number": 4, "status": "generated"},
        {"number": 5, "status": "pending"},
    ]

    def test_rodada_apenas_gerada_conta(self) -> None:
        """O pareamento da 4 nasceu do placar antigo — é aí que ainda se repareia."""
        self.assertEqual([3, 4], cascade_rounds(self._RODADAS, 2))

    def test_rodada_futura_sem_pareamento_nao_conta(self) -> None:
        self.assertNotIn(5, cascade_rounds(self._RODADAS, 2))

    def test_corrigir_a_ultima_nao_tem_cascata(self) -> None:
        self.assertEqual([], cascade_rounds(self._RODADAS, 4))

    def test_recado_diz_o_que_fazer(self) -> None:
        texto = cascade_message(2, [3, 4])
        self.assertIn("rodada 2", texto)
        self.assertIn("3, 4", texto)
        self.assertIn("reparear", texto)
        self.assertEqual("", cascade_message(2, []))

    def test_reconciliaveis_sao_as_fechadas_a_partir_da_corrigida(self) -> None:
        numeros = [
            int(item["number"]) for item in reconcilable_rounds(self._RODADAS, 2)
        ]
        self.assertEqual([2, 3], numeros, "a 4 esta apenas gerada: nao tem retrato")


class CorrecaoNoServicoTest(CoreServiceTestCase):
    """Correção real: duas rodadas fechadas, correção na primeira."""

    def setUp(self) -> None:
        super().setUp()
        self.player_ids = self._create_players(4)
        self.round_ids: list[int] = []
        for _ in range(2):
            round_data = self.service.generate_next_round(self.tournament_id)
            round_id = int(round_data["id"])
            self.round_ids.append(round_id)
            for pairing in self.db.get_pairings_for_round(round_id):
                self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
            self.service.close_round(self.tournament_id, round_id)
        self.first_round_id = self.round_ids[0]
        self.first_pairing = self.db.get_pairings_for_round(self.first_round_id)[0]

    def _corrigir(self, reason: str) -> None:
        self.service.update_result(
            self.tournament_id, int(self.first_pairing["id"]), "0-1", reason
        )

    def _desbloquear(self, reason: str = "Reclamacao do jogador") -> dict:
        return self.service.unlock_round_for_correction(
            self.tournament_id, self.first_round_id, reason
        )

    # -- Motivo obrigatório ------------------------------------------------ #

    def test_correcao_sem_motivo_e_rejeitada(self) -> None:
        self._desbloquear()
        with self.assertRaises(AppError) as erro:
            self._corrigir("")
        self.assertIn("motivo", str(erro.exception).casefold())

    def test_motivo_e_checado_antes_da_permissao(self) -> None:
        """Sem isso, quem esquece o motivo com a rodada travada ouve outra coisa."""
        with self.assertRaises(AppError) as erro:
            self._corrigir("")
        self.assertIn("motivo", str(erro.exception).casefold())

    def test_resultado_nao_muda_quando_o_motivo_falta(self) -> None:
        self._desbloquear()
        with self.assertRaises(AppError):
            self._corrigir("")
        self.assertEqual(
            self.first_pairing["result"],
            self.db.get_pairing(int(self.first_pairing["id"]))["result"],
        )

    def test_motivo_do_arbitro_vai_para_a_trilha(self) -> None:
        self._desbloquear()
        self._corrigir("Sumula trocada: o placar correto e 0-1")

        eventos = self.db.list_audit_events(
            self.tournament_id, action="result_corrected", limit=10
        )
        self.assertEqual(1, len(eventos))
        self.assertEqual("Sumula trocada: o placar correto e 0-1", eventos[0]["reason"])

    # -- Desbloqueio pontual ----------------------------------------------- #

    def test_rodada_fechada_recusa_correcao_sem_desbloqueio(self) -> None:
        with self.assertRaises(AppError) as erro:
            self._corrigir("Sumula trocada pelo arbitro")
        self.assertIn("Desbloqueie", str(erro.exception))

    def test_desbloqueio_permite_a_correcao_e_fica_registrado(self) -> None:
        aberta = self._desbloquear("Reclamacao do jogador da mesa 1")
        self.assertEqual(DEFAULT_UNLOCK_MINUTES, aberta["minutes"])
        self._corrigir("Sumula trocada pelo arbitro")

        self.assertEqual("0-1", self.db.get_pairing(int(self.first_pairing["id"]))["result"])
        eventos = self.db.list_audit_events(
            self.tournament_id, action="round_correction_unlocked", limit=5
        )
        self.assertEqual(1, len(eventos))
        self.assertIn("Reclamacao do jogador", eventos[0]["reason"])

    def test_desbloqueio_sem_justificativa_e_recusado(self) -> None:
        with self.assertRaises(AppError):
            self._desbloquear("")

    def test_desbloqueio_vale_para_UMA_rodada(self) -> None:
        """É o que substitui ligar `allow_dangerous_changes` e esquecer."""
        self._desbloquear()
        outra = self.db.get_pairings_for_round(self.round_ids[1])[0]
        with self.assertRaises(AppError):
            self.service.update_result(
                self.tournament_id, int(outra["id"]), "0-1", "Motivo suficiente aqui"
            )

    def test_desbloqueio_expirado_nao_autoriza(self) -> None:
        self.db.create_correction_unlock(
            self.tournament_id,
            self.first_round_id,
            reason="Desbloqueio antigo",
            expires_at="2000-01-01 00:00:00",
        )
        with self.assertRaises(AppError):
            self._corrigir("Sumula trocada pelo arbitro")

    def test_revogar_fecha_a_rodada_antes_do_prazo(self) -> None:
        self._desbloquear()
        self.assertTrue(
            self.service.correction_unlock_state(self.tournament_id, self.first_round_id).allowed
        )

        revogados = self.service.revoke_round_correction_unlock(
            self.tournament_id, self.first_round_id
        )
        self.assertEqual(1, revogados)
        self.assertFalse(
            self.service.correction_unlock_state(self.tournament_id, self.first_round_id).allowed
        )

    def test_interruptor_global_continua_abrindo_caminho(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"allow_dangerous_changes": 1})
        self._corrigir("Sumula trocada pelo arbitro")
        self.assertEqual("0-1", self.db.get_pairing(int(self.first_pairing["id"]))["result"])

    def test_desbloqueio_de_rodada_inexistente_e_recusado(self) -> None:
        with self.assertRaises(AppError):
            self.service.unlock_round_for_correction(
                self.tournament_id, 99999, "Motivo suficiente aqui"
            )

    # -- Cascata ------------------------------------------------------------ #

    def test_correcao_com_rodada_posterior_gera_alerta_de_cascata(self) -> None:
        self._desbloquear()
        self._corrigir("Sumula trocada pelo arbitro")

        eventos = self.db.list_audit_events(
            self.tournament_id, action="result_correction_cascade", limit=5
        )
        self.assertEqual(1, len(eventos))
        self.assertIn("reparear", eventos[0]["reason"])

    def test_alerta_de_cascata_aparece_no_painel_sem_travar_a_rodada(self) -> None:
        self._desbloquear()
        self._corrigir("Sumula trocada pelo arbitro")

        issues = self.service.arbitration_issues(self.tournament_id)
        pendencias = [item for item in issues["issues"] if item["source"] == "correction"]
        self.assertEqual(1, len(pendencias))
        self.assertEqual("cascade", pendencias[0]["kind"])
        self.assertEqual(1, issues["metrics"]["correction_alerts"])
        # `attention`: quem decide se repareia e o arbitro; travar nao ajudaria.
        self.assertEqual("attention", pendencias[0]["severity"])

    def test_corrigir_a_ultima_rodada_nao_gera_cascata(self) -> None:
        ultima_id = self.round_ids[1]
        self.service.unlock_round_for_correction(
            self.tournament_id, ultima_id, "Reclamacao na ultima rodada"
        )
        mesa = self.db.get_pairings_for_round(ultima_id)[0]
        self.service.update_result(
            self.tournament_id, int(mesa["id"]), "0-1", "Sumula trocada pelo arbitro"
        )
        self.assertEqual(
            [],
            self.db.list_audit_events(
                self.tournament_id, action="result_correction_cascade", limit=5
            ),
        )

    # -- Retratos de classificação ----------------------------------------- #

    def test_retrato_divergente_e_arquivado_e_o_novo_e_gravado(self) -> None:
        antes = {
            int(item["round_number"]): str(item["snapshot_hash"])
            for item in self.db.list_standings_snapshots(self.tournament_id)
        }
        self.assertEqual({1, 2}, set(antes))

        self._desbloquear()
        self._corrigir("Sumula trocada pelo arbitro")

        superados = self.db.list_superseded_standings_snapshots(self.tournament_id)
        self.assertEqual([1, 2], [int(item["round_number"]) for item in superados])
        for item in superados:
            self.assertEqual(antes[int(item["round_number"])], str(item["snapshot_hash"]))
            self.assertIn("Sumula trocada", str(item["superseded_reason"]))
            self.assertTrue(str(item["superseded_at"]))

        depois = {
            int(item["round_number"]): str(item["snapshot_hash"])
            for item in self.db.list_standings_snapshots(self.tournament_id)
        }
        self.assertEqual({1, 2}, set(depois), "continua um retrato vivo por rodada")
        self.assertNotEqual(antes[1], depois[1], "o retrato da rodada corrigida mudou")

    def test_reconciliacao_deixa_evento_com_os_dois_hashes(self) -> None:
        self._desbloquear()
        self._corrigir("Sumula trocada pelo arbitro")

        eventos = self.db.list_audit_events(
            self.tournament_id, action="standings_snapshot_reconciled", limit=10
        )
        self.assertEqual(2, len(eventos), "uma rodada corrigida + uma posterior fechada")
        for evento in eventos:
            self.assertTrue(str(evento["before_hash"]))
            self.assertTrue(str(evento["after_hash"]))
            self.assertNotEqual(evento["before_hash"], evento["after_hash"])

    def test_retrato_da_rodada_1_nao_recebe_a_classificacao_de_hoje(self) -> None:
        """O corte por rodada é o que separa reconciliar de plantar outro erro."""
        import json

        self._desbloquear()
        self._corrigir("Sumula trocada pelo arbitro")

        por_rodada = {
            int(item["round_number"]): json.loads(item["standings_json"])
            for item in self.db.list_standings_snapshots(self.tournament_id)
        }
        pontos_r1 = sum(float(linha["points"]) for linha in por_rodada[1])
        pontos_r2 = sum(float(linha["points"]) for linha in por_rodada[2])
        self.assertEqual(2.0, pontos_r1, "2 mesas na rodada 1 => 2 pontos distribuidos")
        self.assertEqual(4.0, pontos_r2, "duas rodadas => 4 pontos")

    def test_ata_registra_a_correcao_com_motivo(self) -> None:
        """Quem revisa uma apelação lê a ata, não a tela de auditoria."""
        self._desbloquear()
        self._corrigir("Sumula trocada: o placar correto e 0-1")

        secoes = self.export_service._tournament_minutes_sections(self.tournament_id)
        titulos = [titulo for titulo, _headers, _rows in secoes]
        self.assertIn("Correções em rodada fechada", titulos)

        _titulo, headers, rows = next(
            secao for secao in secoes if secao[0] == "Correções em rodada fechada"
        )
        self.assertIn("Motivo", headers)
        self.assertEqual(1, len(rows))
        self.assertIn("Sumula trocada: o placar correto e 0-1", rows[0])
        self.assertIn("1-0 → 0-1", rows[0])
        self.assertIn(1, rows[0], "a rodada corrigida aparece pelo numero")

    def test_ata_sem_correcao_nao_ganha_secao_vazia(self) -> None:
        titulos = [
            titulo
            for titulo, _headers, _rows in self.export_service._tournament_minutes_sections(
                self.tournament_id
            )
        ]
        self.assertNotIn("Correções em rodada fechada", titulos)

    def test_lancamento_em_rodada_aberta_nao_exige_motivo_nem_reconcilia(self) -> None:
        """O caminho comum não pode ficar mais caro por causa da correção."""
        round_data = self.service.generate_next_round(self.tournament_id)
        mesa = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")

        self.assertEqual(
            [], self.db.list_superseded_standings_snapshots(self.tournament_id)
        )
        eventos = self.db.list_audit_events(
            self.tournament_id, action="result_updated", limit=20
        )
        self.assertTrue(eventos)
        self.assertEqual("", eventos[0]["reason"])


class CorrecaoPorEquipesTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.team_tournament_id, self.team_ids = self._create_team_tournament(
            teams_count=2, boards_count=2
        )
        round_data = self.service.generate_next_round(self.team_tournament_id)
        self.round_id = int(round_data["id"])
        for match in self.db.list_team_matches_for_round(self.round_id):
            if match["is_bye"]:
                continue
            for board in self.db.list_team_boards(int(match["id"])):
                self.service.update_result(self.team_tournament_id, int(board["id"]), "1-0")
        self.service.close_round(self.team_tournament_id, self.round_id)
        self.board = self.db.list_team_boards(
            int(self.db.list_team_matches_for_round(self.round_id)[0]["id"])
        )[0]

    def test_correcao_de_tabuleiro_exige_motivo_e_desbloqueio(self) -> None:
        with self.assertRaises(AppError) as erro:
            self.service.update_result(
                self.team_tournament_id, int(self.board["id"]), "0-1", ""
            )
        self.assertIn("motivo", str(erro.exception).casefold())

        with self.assertRaises(AppError) as erro:
            self.service.update_result(
                self.team_tournament_id, int(self.board["id"]), "0-1", "Sumula trocada"
            )
        self.assertIn("Desbloqueie", str(erro.exception))

    def test_correcao_de_equipes_registra_motivo_e_reconcilia(self) -> None:
        self.service.unlock_round_for_correction(
            self.team_tournament_id, self.round_id, "Reclamacao do capitao"
        )
        self.service.update_result(
            self.team_tournament_id, int(self.board["id"]), "0-1", "Sumula trocada no tabuleiro 1"
        )

        eventos = self.db.list_audit_events(
            self.team_tournament_id, action="team_result_corrected", limit=5
        )
        self.assertEqual(1, len(eventos))
        self.assertEqual("Sumula trocada no tabuleiro 1", eventos[0]["reason"])
        superados = self.db.list_superseded_standings_snapshots(self.team_tournament_id)
        self.assertEqual(1, len(superados))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
