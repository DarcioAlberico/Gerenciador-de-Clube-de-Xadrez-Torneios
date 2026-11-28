"""RGS-10 — correção de resultado atômica, reconciliação em segundo plano e
retrato N só com dados até N.

Três camadas:

1. **A correção** (`update_result` em rodada fechada): resultado, auditoria,
   cascata e a marca `reconcile_pending=1` dos retratos numa transação, com
   backup antes — e SEM recalcular classificação nenhuma (0 chamadas a
   `_standings`), porque é isso que travava a tela.
2. **O trabalhador** (`SnapshotReconciler`): reconcilia os pendentes numa
   thread, fala com a tela só pelo `after()` que recebe, é idempotente e
   retomável — o app, ao abrir, termina o que ficou pela metade.
3. **O corte do retrato N**: só ajustes com `round_number <= N`, só quem
   estava inscrito até N e o status vigente na rodada N (histórico ARB-05).
"""

from __future__ import annotations

import json
import threading
import unittest
from unittest import mock

from src.core.database import Database
from src.core.services import PairingService
from src.services.constants import AppError
from tests.support.core_service_base import CoreServiceTestCase

_MOTIVO = "Sumula trocada pelo arbitro"


class _TresRodadasFechadas(CoreServiceTestCase):
    """4 jogadores (``JOGADORES``), 3 rodadas fechadas com vitória das brancas."""

    RODADAS = 3
    JOGADORES = 4

    def setUp(self) -> None:
        super().setUp()
        self.player_ids = self._create_players(self.JOGADORES)
        self.round_ids: list[int] = []
        for _ in range(self.RODADAS):
            round_data = self.service.generate_next_round(self.tournament_id)
            round_id = int(round_data["id"])
            self.round_ids.append(round_id)
            for pairing in self.db.get_pairings_for_round(round_id):
                self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
            self.service.close_round(self.tournament_id, round_id)
        self.mesa_r1 = self.db.get_pairings_for_round(self.round_ids[0])[0]

    def _corrigir_r1(self, result: str = "0-1") -> None:
        self.service.unlock_round_for_correction(
            self.tournament_id, self.round_ids[0], "Reclamacao do jogador"
        )
        self.service.update_result(
            self.tournament_id, int(self.mesa_r1["id"]), result, _MOTIVO
        )

    def _pendencias(self, db: Database | None = None) -> dict[int, int]:
        with (db or self.db).connect() as connection:
            rows = connection.execute(
                "SELECT round_number, reconcile_pending FROM standings_snapshots "
                "WHERE tournament_id = ? ORDER BY round_number",
                (self.tournament_id,),
            ).fetchall()
        return {int(row[0]): int(row[1]) for row in rows}

    def _retrato(self, round_number: int, db: Database | None = None) -> list[dict]:
        for item in (db or self.db).list_standings_snapshots(self.tournament_id):
            if int(item["round_number"]) == round_number:
                return json.loads(item["standings_json"])
        self.fail(f"sem retrato da rodada {round_number}")

    def _eventos(self, action: str) -> list[dict]:
        return self.db.list_audit_events(self.tournament_id, action=action, limit=50)


# --------------------------------------------------------------------------- #
# 1. A correção
# --------------------------------------------------------------------------- #


class CorrecaoAtomicaTest(_TresRodadasFechadas):
    def test_correcao_em_rodada_fechada_nao_calcula_classificacao(self) -> None:
        """Aceite: `_standings` instrumentado, 0 chamadas no `update_result`."""
        with mock.patch.object(
            self.service, "_standings", wraps=self.service._standings
        ) as standings:
            self._corrigir_r1()
        self.assertEqual(0, standings.call_count)
        self.assertEqual("0-1", self.db.get_pairing(int(self.mesa_r1["id"]))["result"])

    def test_correcao_marca_os_retratos_da_rodada_corrigida_em_diante(self) -> None:
        self._corrigir_r1()
        self.assertEqual({1: 1, 2: 1, 3: 1}, self._pendencias())
        self.assertEqual([], self.db.list_superseded_standings_snapshots(self.tournament_id))

    def test_correcao_na_r2_nao_marca_o_retrato_da_r1(self) -> None:
        self.service.unlock_round_for_correction(
            self.tournament_id, self.round_ids[1], "Reclamacao do jogador"
        )
        mesa = self.db.get_pairings_for_round(self.round_ids[1])[0]
        self.service.update_result(self.tournament_id, int(mesa["id"]), "0-1", _MOTIVO)
        self.assertEqual({1: 0, 2: 1, 3: 1}, self._pendencias())

    def test_backup_antes_da_correcao(self) -> None:
        antes = len(self._eventos("backup_created"))
        self._corrigir_r1()
        backups = self._eventos("backup_created")
        self.assertEqual(antes + 1, len(backups))
        self.assertIn("result_correction", backups[0]["after_json"])

    def test_falha_na_cascata_desfaz_resultado_e_auditoria(self) -> None:
        """Resultado, auditoria, cascata e marca entram juntos ou nada entra."""
        original = self.db.create_audit_event

        def falha_na_cascata(*args, **kwargs):
            if kwargs.get("action") == "result_correction_cascade":
                raise RuntimeError("falha injetada na cascata")
            return original(*args, **kwargs)

        with mock.patch.object(self.db, "create_audit_event", side_effect=falha_na_cascata):
            with self.assertRaises(RuntimeError):
                self._corrigir_r1()

        self.assertEqual("1-0", self.db.get_pairing(int(self.mesa_r1["id"]))["result"])
        self.assertEqual([], self._eventos("result_corrected"))
        self.assertEqual({1: 0, 2: 0, 3: 0}, self._pendencias())

    def test_falha_ao_marcar_retratos_desfaz_a_correcao(self) -> None:
        with mock.patch.object(
            self.db,
            "mark_standings_snapshots_pending",
            side_effect=RuntimeError("falha injetada na marca"),
        ):
            with self.assertRaises(RuntimeError):
                self._corrigir_r1()
        self.assertEqual("1-0", self.db.get_pairing(int(self.mesa_r1["id"]))["result"])
        self.assertEqual([], self._eventos("result_corrected"))
        self.assertEqual([], self._eventos("result_correction_cascade"))

    def test_correcao_avisa_quem_escuta_depois_de_gravar(self) -> None:
        """O gancho da tela: chamado com o torneio, e só depois do commit."""
        vistos: list[tuple[int, dict[int, int]]] = []
        self.service.on_snapshots_pending = lambda tid: vistos.append(
            (tid, self._pendencias())
        )
        self._corrigir_r1()
        self.assertEqual([(self.tournament_id, {1: 1, 2: 1, 3: 1})], vistos)



# --------------------------------------------------------------------------- #
# 2. A reconciliação e o trabalhador
# --------------------------------------------------------------------------- #


class LancamentoEmRodadaAbertaTest(_TresRodadasFechadas):
    """Precisa de uma R4. Com 4 jogadores (ou 6, com estes resultados) não há R4
    sem repetir confronto: o motor antigo repetia; desde o RG2-07b ele recusa."""

    JOGADORES = 8

    def test_lancamento_em_rodada_aberta_nao_marca_nem_avisa(self) -> None:
        vistos: list[int] = []
        self.service.on_snapshots_pending = vistos.append
        round_data = self.service.generate_next_round(self.tournament_id)
        mesa = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.assertEqual([], vistos)
        self.assertEqual({1: 0, 2: 0, 3: 0}, self._pendencias())


class ReconciliacaoTest(_TresRodadasFechadas):
    def test_reconciliar_grava_os_n_retratos_e_zera_a_pendencia(self) -> None:
        self._corrigir_r1()
        gravados = self.service.reconcile_pending_snapshots()
        self.assertEqual(3, gravados)
        self.assertEqual({1: 0, 2: 0, 3: 0}, self._pendencias())
        self.assertEqual(3, len(self.db.list_superseded_standings_snapshots(self.tournament_id)))
        self.assertEqual(3, len(self._eventos("standings_snapshot_reconciled")))
        pontos_r1 = sum(float(linha["points"]) for linha in self._retrato(1))
        self.assertEqual(2.0, pontos_r1)

    def test_reconciliar_de_novo_nao_faz_nada(self) -> None:
        self._corrigir_r1()
        self.service.reconcile_pending_snapshots()
        self.assertEqual(0, self.service.reconcile_pending_snapshots())
        self.assertEqual(3, len(self.db.list_superseded_standings_snapshots(self.tournament_id)))

    def test_nova_correcao_durante_o_calculo_nao_e_perdida(self) -> None:
        """Marca nova entre o cálculo e a gravação: o retrato é refeito."""
        self._corrigir_r1()
        original = self.service._standings
        disparou = []

        def com_correcao_no_meio(*args, **kwargs):
            resultado = original(*args, **kwargs)
            if not disparou:
                disparou.append(True)
                self.db.update_pairing_result(int(self.mesa_r1["id"]), "1/2-1/2")
                self.db.mark_standings_snapshots_pending(self.tournament_id, 1, _MOTIVO)
            return resultado

        with mock.patch.object(self.service, "_standings", side_effect=com_correcao_no_meio):
            self.service.reconcile_pending_snapshots()

        self.assertEqual({1: 0, 2: 0, 3: 0}, self._pendencias())
        pontos_r1 = sorted(float(linha["points"]) for linha in self._retrato(1))
        self.assertIn(0.5, pontos_r1, "o retrato da R1 traz o empate gravado no meio")

    def test_falha_no_terceiro_retrato_e_terminada_ao_reabrir(self) -> None:
        """Aceite: falha injetada no 3º retrato -> reabrir o app termina."""
        from src.services.snapshot_reconciler import SnapshotReconciler

        self._corrigir_r1()
        original = self.db.create_standings_snapshot
        chamadas = []

        def falha_no_terceiro(*args, **kwargs):
            chamadas.append(1)
            if len(chamadas) == 3:
                raise RuntimeError("falha injetada no 3o retrato")
            return original(*args, **kwargs)

        with mock.patch.object(self.db, "create_standings_snapshot", side_effect=falha_no_terceiro):
            with self.assertRaises(RuntimeError):
                self.service.reconcile_pending_snapshots()
        self.assertEqual({1: 0, 2: 0, 3: 1}, self._pendencias())

        # "Reabrir o app": banco e serviço novos sobre o mesmo arquivo.
        reaberto = Database(self.db.db_path, backup_dir=self.backup_dir)
        trabalhador = SnapshotReconciler(PairingService(reaberto), notify=lambda fn: fn())
        trabalhador.start()
        self.assertTrue(trabalhador.wait(30))
        self.assertEqual({1: 0, 2: 0, 3: 0}, self._pendencias(reaberto))
        self.assertEqual(3, len(reaberto.list_superseded_standings_snapshots(self.tournament_id)))


class TrabalhadorTest(_TresRodadasFechadas):
    def test_fala_com_a_tela_so_pelo_after(self) -> None:
        from src.services.snapshot_reconciler import SnapshotReconciler

        self._corrigir_r1()
        fila: list = []
        concluidos: list[int] = []
        trabalhador = SnapshotReconciler(
            self.service,
            notify=fila.append,
            on_done=concluidos.append,
        )
        trabalhador.start()
        self.assertTrue(trabalhador.wait(30))
        self.assertEqual([], concluidos, "nada chega a tela fora do after()")
        self.assertEqual({1: 0, 2: 0, 3: 0}, self._pendencias())
        for callback in fila:
            callback()
        self.assertEqual([3], concluidos)

    def test_trabalho_roda_fora_da_thread_que_chamou(self) -> None:
        from src.services.snapshot_reconciler import SnapshotReconciler

        self._corrigir_r1()
        threads: list[threading.Thread] = []
        original = self.service.reconcile_pending_snapshots

        def registra(*args, **kwargs):
            threads.append(threading.current_thread())
            return original(*args, **kwargs)

        with mock.patch.object(self.service, "reconcile_pending_snapshots", side_effect=registra):
            trabalhador = SnapshotReconciler(self.service, notify=lambda fn: fn())
            trabalhador.start()
            self.assertTrue(trabalhador.wait(30))
        self.assertTrue(threads)
        self.assertNotIn(threading.main_thread(), threads)

    def test_erro_chega_a_tela_pelo_after_e_a_pendencia_fica(self) -> None:
        from src.services.snapshot_reconciler import SnapshotReconciler

        self._corrigir_r1()
        fila: list = []
        erros: list[Exception] = []
        with mock.patch.object(
            self.service, "_standings", side_effect=AppError("motor caiu")
        ):
            trabalhador = SnapshotReconciler(
                self.service, notify=fila.append, on_error=erros.append
            )
            trabalhador.start()
            self.assertTrue(trabalhador.wait(30))
        self.assertEqual([], erros)
        for callback in fila:
            callback()
        self.assertEqual(1, len(erros))
        self.assertEqual({1: 1, 2: 1, 3: 1}, self._pendencias())


# --------------------------------------------------------------------------- #
# 3. O retrato N só com dados até N
# --------------------------------------------------------------------------- #


class RetratoSoComDadosAteNTest(_TresRodadasFechadas):
    def _ids(self, linhas: list[dict]) -> set[int]:
        return {int(linha["player_id"]) for linha in linhas}

    def test_inscrito_na_r4_nao_entra_no_corte_da_r3(self) -> None:
        tardio = self.db.create_player(self.tournament_id, name="Tardio", rating=1500)
        corte = self.service._standings(self.tournament_id, up_to_round=3)
        self.assertNotIn(tardio, self._ids(corte))
        self.assertIn(tardio, self._ids(self.service._standings(self.tournament_id)))

    def test_inscrito_na_r4_nao_aparece_no_retrato_reconciliado_da_r3(self) -> None:
        """Aceite: jogador inscrito na R4 não aparece no retrato da R3."""
        tardio = self.db.create_player(self.tournament_id, name="Tardio", rating=1500)
        self._corrigir_r1()
        self.service.reconcile_pending_snapshots()
        self.assertNotIn(tardio, self._ids(self._retrato(3)))
        self.assertEqual(set(self.player_ids), self._ids(self._retrato(3)))

    def test_ajuste_da_r5_nao_altera_o_corte_da_r3(self) -> None:
        alvo = self.player_ids[0]
        antes = {
            int(linha["player_id"]): float(linha["points"])
            for linha in self.service._standings(self.tournament_id, up_to_round=3)
        }
        self.db.add_point_adjustment(
            self.tournament_id, round_number=5, player_id=alvo, game_points=1.0, reason="Ajuste R5"
        )
        depois = {
            int(linha["player_id"]): float(linha["points"])
            for linha in self.service._standings(self.tournament_id, up_to_round=3)
        }
        self.assertEqual(antes, depois)

    def test_ajuste_ate_a_r3_continua_valendo_no_corte_da_r3(self) -> None:
        alvo = self.player_ids[0]
        antes = {
            int(linha["player_id"]): float(linha["points"])
            for linha in self.service._standings(self.tournament_id, up_to_round=3)
        }
        self.db.add_point_adjustment(
            self.tournament_id, round_number=2, player_id=alvo, game_points=1.0, reason="Ajuste R2"
        )
        depois = {
            int(linha["player_id"]): float(linha["points"])
            for linha in self.service._standings(self.tournament_id, up_to_round=3)
        }
        self.assertEqual(antes[alvo] + 1.0, depois[alvo])

    def test_ajuste_da_r5_nao_altera_o_retrato_reconciliado_da_r3(self) -> None:
        """Aceite: ajuste da R5 não altera o retrato da R3."""
        self._corrigir_r1()
        self.service.reconcile_pending_snapshots()
        sem_ajuste = self._retrato(3)

        self.db.add_point_adjustment(
            self.tournament_id,
            round_number=5,
            player_id=self.player_ids[0],
            game_points=1.0,
            reason="Ajuste R5",
        )
        self._corrigir_r1("0-1")  # mesma correção: reconcilia de novo, agora com o ajuste no banco
        self.service.reconcile_pending_snapshots()
        self.assertEqual(
            [(linha["player_id"], linha["points"]) for linha in sem_ajuste],
            [(linha["player_id"], linha["points"]) for linha in self._retrato(3)],
        )

    def test_status_e_o_vigente_na_rodada_do_corte(self) -> None:
        alvo = self.player_ids[1]
        rodada = self.service.set_player_participation(
            self.tournament_id, alvo, "withdrawn", reason="Viagem"
        )
        self.assertEqual(4, rodada)
        linha_r3 = next(
            linha
            for linha in self.service._standings(self.tournament_id, up_to_round=3)
            if int(linha["player_id"]) == alvo
        )
        self.assertEqual("active", linha_r3["player_status"])
        self.assertEqual(1, int(linha_r3["active"]))
        linha_hoje = next(
            linha
            for linha in self.service._standings(self.tournament_id)
            if int(linha["player_id"]) == alvo
        )
        self.assertEqual("withdrawn", linha_hoje["player_status"])


class InscricaoPorRodadaTest(_TresRodadasFechadas):
    def test_inscricao_guarda_a_rodada_de_entrada(self) -> None:
        tardio = self.db.create_player(self.tournament_id, name="Tardio", rating=1500)
        self.assertEqual(4, int(self.db.get_player(tardio)["entry_round"]))
        self.assertEqual(1, int(self.db.get_player(self.player_ids[0])["entry_round"]))


class MigracaoV56Test(unittest.TestCase):
    """v56: `reconcile_pending` (e companhia) nos retratos e `entry_round` no jogador."""

    def setUp(self) -> None:
        import tempfile
        from pathlib import Path

        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base = Path(self.temp_dir.name)
        self.path = base / "v55.db"
        self.backup_dir = base / "backups"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _banco_v55(self) -> None:
        import sqlite3

        Database(self.path, backup_dir=self.backup_dir)
        connection = sqlite3.connect(self.path)
        try:
            colunas = {
                tabela: {row[1] for row in connection.execute(f"PRAGMA table_info({tabela})")}
                for tabela in ("standings_snapshots", "players")
            }
            for coluna in ("reconcile_pending", "reconcile_reason", "reconcile_generation"):
                if coluna in colunas["standings_snapshots"]:
                    connection.execute(f"ALTER TABLE standings_snapshots DROP COLUMN {coluna}")
            if "entry_round" in colunas["players"]:
                connection.execute("ALTER TABLE players DROP COLUMN entry_round")
            connection.executescript(
                """
                INSERT INTO tournaments (id, name, created_at) VALUES (1, 'Legado', '2026-05-01 08:00:00');
                INSERT INTO rounds (id, tournament_id, number, status, created_at)
                VALUES (1, 1, 1, 'closed', '2026-05-01 10:00:00'),
                       (2, 1, 2, 'closed', '2026-05-01 12:00:00'),
                       (3, 1, 3, 'closed', '2026-05-01 14:00:00');
                INSERT INTO players (id, tournament_id, name, created_at)
                VALUES (1, 1, 'Do inicio', '2026-05-01 09:00:00'),
                       (2, 1, 'Mesmo segundo da R1', '2026-05-01 10:00:00'),
                       (3, 1, 'Depois da R3', '2026-05-01 14:30:00');
                INSERT INTO standings_snapshots
                    (tournament_id, round_id, round_number, standings_json, snapshot_hash, created_at)
                VALUES (1, 1, 1, '[]', 'h1', '2026-05-01 11:00:00');
                PRAGMA user_version = 55;
                """
            )
            connection.commit()
        finally:
            connection.close()

    def test_migracao_cria_as_colunas_e_preenche_a_rodada_de_entrada(self) -> None:
        self._banco_v55()
        migrado = Database(self.path, backup_dir=self.backup_dir)
        with migrado.connect() as connection:
            versao = connection.execute("PRAGMA user_version").fetchone()[0]
            retrato = connection.execute(
                "SELECT reconcile_pending, reconcile_reason, reconcile_generation "
                "FROM standings_snapshots"
            ).fetchone()
            entradas = {
                int(row["id"]): int(row["entry_round"])
                for row in connection.execute("SELECT id, entry_round FROM players")
            }
        self.assertEqual(Database.SCHEMA_VERSION, versao)
        self.assertEqual((0, "", 0), tuple(retrato))
        # Mesmo segundo que a R1: na dúvida, entra (como era antes).
        self.assertEqual({1: 1, 2: 1, 3: 4}, entradas)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
