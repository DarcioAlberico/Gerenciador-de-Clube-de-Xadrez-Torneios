"""TBK-02 — a troca de motor de desempate deixa de ser silenciosa.

Três camadas, e a do meio é a que importa:

- o retrato puro (`EngineReport`) e os textos que as três portas compartilham;
- o `PairingService` diante de um motor que falha — fallback com trilha, modo
  estrito que barra, e a falha cacheada que impede a enxurrada de subprocessos;
- a pendência que aparece no painel do árbitro.

O motor é substituído por um dublê que levanta `AppError`: o que está sob teste
não é o Gacrux, é o que o Albericus faz quando ele não responde.
"""

from __future__ import annotations

import unittest
from unittest import mock

import src.services.pairing_service as ps
from src.services.constants import AppError
from src.services.pairing.tiebreak_engine import (
    ENGINE_ALBERICUS,
    ENGINE_GACRUX,
    EngineReport,
    engine_badge,
    engine_label,
    fallback_audit_reason,
    report_engine_blocked,
    report_engine_fallback,
    report_engine_ok,
    strict_block_message,
)
from tests.support.core_service_base import CoreServiceTestCase


class RetratoTest(unittest.TestCase):
    def test_tres_estados_e_nenhum_se_confunde(self) -> None:
        saudavel = report_engine_ok(ENGINE_GACRUX)
        degradado = report_engine_fallback(ENGINE_GACRUX, "subprocesso morreu")
        bloqueado = report_engine_blocked(ENGINE_GACRUX, "subprocesso morreu")

        self.assertTrue(saudavel.healthy)
        self.assertFalse(saudavel.fallback)
        self.assertFalse(saudavel.blocked)

        self.assertTrue(degradado.fallback)
        self.assertFalse(degradado.blocked)
        self.assertEqual(ENGINE_ALBERICUS, degradado.used)

        self.assertTrue(bloqueado.blocked)
        self.assertFalse(bloqueado.fallback, "bloqueado nao e fallback: nada foi publicado")

    def test_motor_proprio_configurado_nao_e_fallback(self) -> None:
        """Quem escolheu o motor próprio recebeu o que pediu."""
        self.assertTrue(report_engine_ok(ENGINE_ALBERICUS).healthy)

    def test_rotulo_desconhecido_volta_cru(self) -> None:
        self.assertEqual("FIDE (Gacrux)", engine_label(ENGINE_GACRUX))
        self.assertEqual("motor_novo", engine_label("motor_novo"))


class FaixaTest(unittest.TestCase):
    def test_estado_normal_ainda_diz_qual_motor_assinou(self) -> None:
        """A faixa é permanente — só aparecer no erro ensina a não olhar."""
        faixa = engine_badge(report_engine_ok(ENGINE_GACRUX))
        self.assertEqual("ok", faixa["tone"])
        self.assertIn("FIDE (Gacrux)", faixa["label"])
        self.assertEqual("", faixa["detail"])

    def test_fallback_diz_o_que_muda_na_pratica(self) -> None:
        faixa = engine_badge(report_engine_fallback(ENGINE_GACRUX, "timeout"))
        self.assertEqual("warning", faixa["tone"])
        self.assertIn("Albericus", faixa["label"])
        self.assertIn("FIDE (Gacrux)", faixa["label"])
        self.assertIn("adversário virtual", faixa["detail"])
        self.assertIn("timeout", faixa["detail"])

    def test_bloqueio_aponta_a_saida(self) -> None:
        faixa = engine_badge(report_engine_blocked(ENGINE_GACRUX, "timeout"))
        self.assertEqual("danger", faixa["tone"])
        self.assertIn("bloqueada", faixa["label"].casefold())
        self.assertIn("modo estrito", faixa["detail"])

    def test_falha_sem_mensagem_ainda_produz_texto_util(self) -> None:
        for texto in (
            engine_badge(report_engine_fallback(ENGINE_GACRUX, ""))["detail"],
            fallback_audit_reason(report_engine_fallback(ENGINE_GACRUX, "")),
            strict_block_message(ENGINE_GACRUX, ""),
        ):
            self.assertIn("sem mensagem do motor", texto)


class _MotorQueFalha:
    """Dublê do GacruxTiebreakEngine: sempre levanta, e conta as tentativas."""

    tentativas = 0

    def __init__(self, db: object) -> None:
        self.db = db

    def compute(self, *args: object, **kwargs: object) -> dict:
        type(self).tentativas += 1
        raise AppError("Erro no calculo de desempates do Gacrux: subprocesso morreu")

    compute_teams = compute


class MotorQueFalhaTest(CoreServiceTestCase):
    """O que o serviço faz quando o motor FIDE não responde."""

    def setUp(self) -> None:
        super().setUp()
        ps._GACRUX_TIEBREAK_CACHE.clear()
        ps._LAST_TIEBREAK_ENGINE.clear()
        _MotorQueFalha.tentativas = 0
        self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        for pairing in self.db.get_pairings_for_round(int(round_data["id"])):
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(round_data["id"]))
        self.db.save_tournament_settings(self.tournament_id, {"tiebreak_engine": ENGINE_GACRUX})

    def _com_motor_quebrado(self):
        return mock.patch(
            "src.services.pairing.gacrux_tiebreak_engine.GacruxTiebreakEngine",
            _MotorQueFalha,
        )

    def _estrito(self, ligado: bool) -> None:
        self.db.save_tournament_settings(
            self.tournament_id, {"tiebreak_strict": 1 if ligado else 0}
        )

    # -- Fallback ---------------------------------------------------------- #

    def test_fallback_publica_a_classificacao_e_registra_a_troca(self) -> None:
        with self._com_motor_quebrado():
            standings = self.service.standings(self.tournament_id)

        self.assertEqual(4, len(standings), "a classificacao sai pelo motor proprio")
        self.assertFalse(any("_gacrux_rank" in item for item in standings))

        report = self.service.tiebreak_engine_report(self.tournament_id)
        self.assertTrue(report.fallback)
        self.assertEqual(ENGINE_ALBERICUS, report.used)
        self.assertIn("subprocesso morreu", report.error)

    def test_fallback_deixa_evento_de_auditoria_com_o_motivo(self) -> None:
        with self._com_motor_quebrado():
            self.service.standings(self.tournament_id)

        eventos = self.db.list_audit_events(
            self.tournament_id, action="tiebreak_engine_fallback", limit=10
        )
        self.assertEqual(1, len(eventos))
        self.assertIn("FIDE (Gacrux) falhou", eventos[0]["reason"])
        self.assertIn("Albericus", eventos[0]["reason"])

    def test_motor_quebrado_roda_uma_vez_por_estado_do_torneio(self) -> None:
        """Falha cacheada: antes eram dezenas de subprocessos por tela aberta.

        E é o mesmo mecanismo que impede a enxurrada de eventos de auditoria —
        um por estado, não um por chamada.
        """
        with self._com_motor_quebrado():
            for _ in range(5):
                self.service.standings(self.tournament_id)

        self.assertEqual(1, _MotorQueFalha.tentativas)
        self.assertEqual(
            1,
            len(self.db.list_audit_events(
                self.tournament_id, action="tiebreak_engine_fallback", limit=10
            )),
        )

    def test_recalcular_devolve_a_chance_ao_motor(self) -> None:
        """Falha cacheada não pode prender o torneio numa falha passageira."""
        with self._com_motor_quebrado():
            self.service.standings(self.tournament_id)
            self.service.reset_tiebreak_engine(self.tournament_id)
            self.service.standings(self.tournament_id)

        self.assertEqual(2, _MotorQueFalha.tentativas)

    def test_pendencia_do_fallback_aparece_no_painel(self) -> None:
        with self._com_motor_quebrado():
            self.service.standings(self.tournament_id)
            issues = self.service.arbitration_issues(self.tournament_id)

        pendencias = [item for item in issues["issues"] if item["source"] == "tiebreak"]
        self.assertEqual(1, len(pendencias))
        self.assertEqual("engine_fallback", pendencias[0]["kind"])
        self.assertIn("FIDE (Gacrux) falhou", pendencias[0]["detail"])
        self.assertEqual(1, issues["metrics"]["tiebreak_alerts"])
        # "attention", nao "decision": o aviso nao pode barrar o fechamento da
        # rodada — quem segura a publicacao e o modo estrito, em standings().
        self.assertEqual("attention", pendencias[0]["severity"])
        self.assertEqual(0, issues["metrics"]["decision_required"])

    # -- Modo estrito ------------------------------------------------------ #

    def test_modo_estrito_barra_a_publicacao_em_vez_de_trocar_de_motor(self) -> None:
        self._estrito(True)
        with self._com_motor_quebrado():
            with self.assertRaises(AppError) as erro:
                self.service.standings(self.tournament_id)

        self.assertIn("modo estrito", str(erro.exception))
        report = self.service.tiebreak_engine_report(self.tournament_id)
        self.assertTrue(report.blocked)

    def test_modo_estrito_barra_tambem_nas_chamadas_seguintes(self) -> None:
        """A falha cacheada continua barrando: nada escapa pela segunda porta."""
        self._estrito(True)
        with self._com_motor_quebrado():
            with self.assertRaises(AppError):
                self.service.standings(self.tournament_id)
            with self.assertRaises(AppError):
                self.service.standings(self.tournament_id)
        self.assertEqual(1, _MotorQueFalha.tentativas)

    def test_modo_estrito_registra_bloqueio_e_avisa_no_painel(self) -> None:
        self._estrito(True)
        with self._com_motor_quebrado():
            with self.assertRaises(AppError):
                self.service.standings(self.tournament_id)
            issues = self.service.arbitration_issues(self.tournament_id)

        eventos = self.db.list_audit_events(
            self.tournament_id, action="tiebreak_engine_blocked", limit=10
        )
        self.assertEqual(1, len(eventos))
        pendencias = [item for item in issues["issues"] if item["kind"] == "engine_blocked"]
        self.assertEqual(1, len(pendencias))

    def test_painel_nao_cai_quando_a_classificacao_esta_bloqueada(self) -> None:
        """O diagnóstico de pareamento lê a classificação; o painel tem de abrir.

        Derrubar a Central de pendências aqui esconderia justamente a pendência
        que explica o bloqueio.
        """
        self._estrito(True)
        self.service.generate_next_round(self.tournament_id)  # rodada aberta -> diagnostico roda
        with self._com_motor_quebrado():
            issues = self.service.arbitration_issues(self.tournament_id)
        self.assertIn("metrics", issues)

    # -- O modo estrito barra a PUBLICACAO, nao o torneio ------------------- #

    def test_modo_estrito_nao_impede_gerar_a_proxima_rodada(self) -> None:
        """Pareamento só precisa da ordem por pontos, que os dois motores dão igual.

        Barrar aqui pararia o torneio por causa de um problema de relatório —
        trocaria um risco de publicação por um risco de operação, que é maior.
        """
        self._estrito(True)
        with self._com_motor_quebrado():
            round_data = self.service.generate_next_round(self.tournament_id)
        self.assertEqual(2, int(round_data["number"]))
        self.assertTrue(self.db.get_pairings_for_round(int(round_data["id"])))

    def test_modo_estrito_nao_impede_fechar_a_rodada(self) -> None:
        self._estrito(True)
        with self._com_motor_quebrado():
            round_data = self.service.generate_next_round(self.tournament_id)
            for pairing in self.db.get_pairings_for_round(int(round_data["id"])):
                self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
            self.service.close_round(self.tournament_id, int(round_data["id"]))

        fechada = self.db.get_round(int(round_data["id"]))
        self.assertEqual("closed", fechada["status"])
        self.assertTrue(self.db.list_standings_snapshots(self.tournament_id))

    def test_bloqueio_registra_mesmo_quando_o_uso_interno_degrada(self) -> None:
        """Quem falha é o motor; o modo estrito do torneio é que diz se bloqueia.

        Um uso interno pode ser o primeiro a bater na falha — e ainda assim o
        retrato tem de dizer "bloqueado", senão a publicação seguinte leria o
        cache e degradaria em silêncio, que é o bug que a TBK-02 fecha.
        """
        self._estrito(True)
        with self._com_motor_quebrado():
            self.service.generate_next_round(self.tournament_id)  # uso interno primeiro
            self.assertTrue(self.service.tiebreak_engine_report(self.tournament_id).blocked)
            with self.assertRaises(AppError):
                self.service.standings(self.tournament_id)

        self.assertEqual(
            1,
            len(self.db.list_audit_events(
                self.tournament_id, action="tiebreak_engine_blocked", limit=10
            )),
        )

    # -- Motor saudável ---------------------------------------------------- #

    def test_motor_proprio_configurado_nao_gera_alerta_nenhum(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"tiebreak_engine": ENGINE_ALBERICUS})
        standings = self.service.standings(self.tournament_id)

        self.assertEqual(4, len(standings))
        report = self.service.tiebreak_engine_report(self.tournament_id)
        self.assertTrue(report.healthy)
        self.assertEqual(ENGINE_ALBERICUS, report.used)
        self.assertEqual(
            [], self.db.list_audit_events(self.tournament_id, action="tiebreak_engine_fallback")
        )

    def test_faixa_pronta_para_a_tela_sai_do_servico(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"tiebreak_engine": ENGINE_ALBERICUS})
        faixa = self.service.tiebreak_engine_badge(self.tournament_id)
        self.assertEqual("ok", faixa["tone"])
        self.assertIn("Albericus", faixa["label"])

    def test_sem_calculo_a_faixa_mostra_o_motor_configurado(self) -> None:
        """Tela aberta antes de qualquer cálculo já diz quem vai assinar."""
        ps._LAST_TIEBREAK_ENGINE.clear()
        report = self.service.tiebreak_engine_report(self.tournament_id)
        self.assertEqual(ENGINE_GACRUX, report.configured)
        self.assertTrue(report.healthy)


class EquipesTest(CoreServiceTestCase):
    """O caminho de equipes espelha o individual, inclusive no registro."""

    def setUp(self) -> None:
        super().setUp()
        ps._GACRUX_TIEBREAK_CACHE.clear()
        ps._LAST_TIEBREAK_ENGINE.clear()
        _MotorQueFalha.tentativas = 0
        self.team_tournament_id, self.team_ids = self._create_team_tournament(
            teams_count=2, boards_count=2
        )
        round_data = self.service.generate_next_round(self.team_tournament_id)
        for match in self.db.list_team_matches_for_round(int(round_data["id"])):
            if match["is_bye"]:
                continue
            for board in self.db.list_team_boards(int(match["id"])):
                self.service.update_result(self.team_tournament_id, int(board["id"]), "1-0")
        self.service.close_round(self.team_tournament_id, int(round_data["id"]))
        self.db.save_tournament_settings(
            self.team_tournament_id, {"tiebreak_engine": ENGINE_GACRUX}
        )

    def test_fallback_de_equipes_tambem_registra_e_publica(self) -> None:
        with mock.patch(
            "src.services.pairing.gacrux_tiebreak_engine.GacruxTiebreakEngine", _MotorQueFalha
        ):
            standings = self.service.team_standings(self.team_tournament_id)

        self.assertEqual(2, len(standings))
        self.assertTrue(self.service.tiebreak_engine_report(self.team_tournament_id).fallback)
        self.assertEqual(
            1,
            len(self.db.list_audit_events(
                self.team_tournament_id, action="tiebreak_engine_fallback", limit=10
            )),
        )

    def test_modo_estrito_de_equipes_barra_a_classificacao(self) -> None:
        self.db.save_tournament_settings(self.team_tournament_id, {"tiebreak_strict": 1})
        with mock.patch(
            "src.services.pairing.gacrux_tiebreak_engine.GacruxTiebreakEngine", _MotorQueFalha
        ):
            with self.assertRaises(AppError):
                self.service.team_standings(self.team_tournament_id)


class EstadoDaConfiguracaoTest(CoreServiceTestCase):
    def test_modo_estrito_persiste_e_nasce_desligado(self) -> None:
        settings = self.db.get_tournament_settings(self.tournament_id) or {}
        self.assertEqual(0, int(settings.get("tiebreak_strict") or 0))

        self.db.save_tournament_settings(self.tournament_id, {"tiebreak_strict": 1})
        recarregado = self.db.get_tournament_settings(self.tournament_id) or {}
        self.assertEqual(1, int(recarregado["tiebreak_strict"]))

    def test_salvar_outra_configuracao_nao_apaga_o_modo_estrito(self) -> None:
        """O UPDATE reescreve a linha inteira: sem merge, a marca se perderia."""
        self.db.save_tournament_settings(self.tournament_id, {"tiebreak_strict": 1})
        self.db.save_tournament_settings(self.tournament_id, {"organizer": "Clube"})
        settings = self.db.get_tournament_settings(self.tournament_id) or {}
        self.assertEqual(1, int(settings["tiebreak_strict"]))


class ReportDataclassTest(unittest.TestCase):
    def test_retrato_e_imutavel(self) -> None:
        """Imutável de propósito: é um retrato do passado, não um estado vivo."""
        report = EngineReport(configured=ENGINE_GACRUX, used=ENGINE_GACRUX)
        with self.assertRaises(Exception):
            report.used = ENGINE_ALBERICUS  # type: ignore[misc]


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
