"""Smoke tests da God Class Database (src/core/database.py).

Rede de seguranca para a extracao incremental de mixins por dominio: exercita
o CRUD basico de cada dominio num banco temporario e congela a interface
publica num snapshot (tests/fixtures/database_public_api.txt). Se a refatoracao
perder/renomear um metodo da fachada Database ou quebrar um fluxo, estes testes
pegam.

Complementa (nao substitui) os testes de comportamento em test_core_services.py,
que exercitam a Database indiretamente via os servicos.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.core.database import Database

_API_SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "database_public_api.txt"


def _public_methods(cls: type) -> set[str]:
    return {n for n in dir(cls) if not n.startswith("_") and callable(getattr(cls, n))}


class DatabaseTestCase(unittest.TestCase):
    """Base: banco temporario isolado por teste."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base = Path(self._tmp.name)
        self.db = Database(db_path=base / "test.db", backup_dir=base / "backups")

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestDatabasePublicInterface(DatabaseTestCase):
    """Snapshot da API publica — rede contra perda de metodo na extracao de mixins.

    Para regenerar o snapshot apos uma mudanca INTENCIONAL de interface::

        from src.core.database import Database
        pub = sorted(n for n in dir(Database)
                     if not n.startswith("_") and callable(getattr(Database, n)))
        Path("tests/fixtures/database_public_api.txt").write_text(
            "\\n".join(pub) + "\\n", encoding="utf-8")
    """

    def _snapshot(self) -> set[str]:
        names = set()
        for line in _API_SNAPSHOT.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                names.add(stripped)
        return names

    def test_snapshot_is_substantial(self) -> None:
        # guarda contra snapshot vazio/corrompido mascarar a verificacao abaixo
        self.assertGreaterEqual(len(self._snapshot()), 250)

    def test_public_api_matches_snapshot(self) -> None:
        expected = self._snapshot()
        actual = _public_methods(Database)
        missing = expected - actual
        extra = actual - expected
        self.assertEqual(
            missing,
            set(),
            f"Metodos publicos sumiram da Database (regressao de refatoracao?): {sorted(missing)}",
        )
        self.assertEqual(
            extra,
            set(),
            "Metodos publicos novos nao registrados no snapshot. Se intencional, "
            f"regenere tests/fixtures/database_public_api.txt. Novos: {sorted(extra)}",
        )


class TestDatabaseSchema(DatabaseTestCase):
    def test_schema_version(self) -> None:
        self.assertEqual(Database.SCHEMA_VERSION, 47)

    def test_core_tables_exist(self) -> None:
        with self.db.connect() as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in (
            "clubs", "members", "tournaments", "players", "teams", "referees",
            "payments", "membership_plans", "inventory_items", "sponsors",
            "training_sessions", "audit_log", "learning_levels", "classes",
        ):
            self.assertIn(table, tables)

    def test_now_format(self) -> None:
        self.assertRegex(self.db.now(), r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


class TestClubAndPeopleDomain(DatabaseTestCase):
    def test_club_crud(self) -> None:
        club_id = self.db.save_club("Clube Teste", city="Sao Paulo")
        club = self.db.get_club(club_id)
        self.assertIsNotNone(club)
        assert club is not None
        self.assertEqual(club["name"], "Clube Teste")
        self.assertIn(club_id, [c["id"] for c in self.db.list_clubs()])

    def test_learning_level_crud(self) -> None:
        # niveis padrao (Iniciante, Basico, ...) sao semeados; usar nome unico
        level_id = self.db.create_learning_level("Nivel Smoke", description="nivel 1")
        level = self.db.get_learning_level(level_id)
        assert level is not None
        self.assertEqual(level["name"], "Nivel Smoke")
        self.db.update_learning_level(level_id, name="Nivel Smoke 2", description="nivel 1")
        updated = self.db.get_learning_level(level_id)
        assert updated is not None
        self.assertEqual(updated["name"], "Nivel Smoke 2")
        self.assertIn(level_id, [lv["id"] for lv in self.db.list_learning_levels()])

    def test_class_crud(self) -> None:
        class_id = self.db.create_class(1, "Turma A", teacher="Prof")
        self.assertIsNotNone(self.db.get_class(class_id))
        self.assertIn(class_id, [c["id"] for c in self.db.list_classes()])

    def test_member_crud(self) -> None:
        member_id = self.db.create_member("Ana", surname="Silva", email="ana@x.com")
        member = self.db.get_member(member_id)
        assert member is not None
        self.assertEqual(member["name"], "Ana")
        self.db.update_member(member_id, name="Ana Maria", surname="Silva")
        updated = self.db.get_member(member_id)
        assert updated is not None
        self.assertEqual(updated["name"], "Ana Maria")
        self.assertIn(member_id, [m["id"] for m in self.db.list_members()])

    def test_guardian_link(self) -> None:
        member_id = self.db.create_member("Crianca")
        guardian_id = self.db.create_guardian("Mae", phone="999")
        self.assertIsNotNone(self.db.get_guardian(guardian_id))
        self.db.link_guardian_to_member(member_id, guardian_id, relationship="mae")
        self.assertTrue(any(g["id"] == guardian_id for g in self.db.list_member_guardians(member_id)))


class TestTournamentDomain(DatabaseTestCase):
    def test_tournament_crud(self) -> None:
        tid = self.db.create_tournament("Copa", rounds_count=5)
        tournament = self.db.get_tournament(tid)
        assert tournament is not None
        self.assertEqual(tournament["name"], "Copa")
        self.db.update_tournament_status(tid, "active")
        updated = self.db.get_tournament(tid)
        assert updated is not None
        self.assertEqual(updated["status"], "active")
        self.assertIn(tid, [t["id"] for t in self.db.list_tournaments()])
        self.db.delete_tournament(tid)
        self.assertIsNone(self.db.get_tournament(tid))

    def test_player_crud(self) -> None:
        tid = self.db.create_tournament("Copa")
        pid = self.db.create_player(tid, "Joao", rating=1500, club="CX")
        player = self.db.get_player(pid)
        assert player is not None
        self.assertEqual(player["name"], "Joao")
        self.db.update_player(pid, "Joao P", "CX", 1600, "Absoluto", 1)
        updated = self.db.get_player(pid)
        assert updated is not None
        self.assertEqual(updated["rating"], 1600)
        self.assertIn(pid, [p["id"] for p in self.db.list_players(tid)])
        self.db.delete_player(pid)
        self.assertEqual(self.db.list_players(tid), [])

    def test_team_crud(self) -> None:
        tid = self.db.create_tournament("Copa Equipes", competition_type="team")
        team_id = self.db.create_team(tid, "Equipe A", captain="Capitao")
        pid = self.db.create_player(tid, "Jogador")
        self.db.add_player_to_team(team_id, pid, board_number=1)
        self.assertIn(team_id, [t["id"] for t in self.db.list_teams(tid)])
        self.assertEqual(len(self.db.list_team_players(team_id)), 1)
        self.db.update_team(team_id, name="Equipe Alfa")
        team = self.db.get_team(team_id)
        assert team is not None
        self.assertEqual(team["name"], "Equipe Alfa")


class TestFinanceDomain(DatabaseTestCase):
    def test_membership_plan_and_payment(self) -> None:
        member_id = self.db.create_member("Pagador")
        plan_id = self.db.create_membership_plan("Mensal", amount=50.0)
        self.assertIn(plan_id, [p["id"] for p in self.db.list_membership_plans()])
        pay_id = self.db.create_payment(member_id, plan_id=plan_id, amount=50.0, status="pending")
        payment = self.db.get_payment(pay_id)
        assert payment is not None
        self.assertEqual(payment["amount"], 50.0)
        self.db.update_payment(pay_id, member_id, plan_id=plan_id, amount=50.0, status="paid")
        updated = self.db.get_payment(pay_id)
        assert updated is not None
        self.assertEqual(updated["status"], "paid")
        self.assertIn(pay_id, [p["id"] for p in self.db.list_payments()])

    def test_financial_transaction(self) -> None:
        tx_id = self.db.create_financial_transaction(
            type="income", amount=200.0, transaction_date="2026-06-05",
            description="Inscricoes", category="tournament",
        )
        self.assertGreater(tx_id, 0)


class TestRefereeDomain(DatabaseTestCase):
    def test_referee_crud_and_assignment(self) -> None:
        ref_id = self.db.insert_referee({"name": "Arbitro", "category": "FA"})
        referee = self.db.get_referee(ref_id)
        assert referee is not None
        self.assertEqual(referee["name"], "Arbitro")
        self.db.update_referee(ref_id, {"name": "Arbitro Chefe"})
        updated = self.db.get_referee(ref_id)
        assert updated is not None
        self.assertEqual(updated["name"], "Arbitro Chefe")
        self.assertIn(ref_id, [r["id"] for r in self.db.list_referees()])
        tid = self.db.create_tournament("Copa")
        self.db.assign_tournament_referee(tid, ref_id, "chief")
        self.assertEqual(len(self.db.list_tournament_referees(tid)), 1)


class TestInventoryAndSponsorDomain(DatabaseTestCase):
    def test_inventory_item(self) -> None:
        item_id = self.db.create_inventory_item(name="Tabuleiro", item_type="board", quantity_total=10)
        item = self.db.get_inventory_item(item_id)
        assert item is not None
        self.assertEqual(item["name"], "Tabuleiro")
        self.assertIn(item_id, [i["id"] for i in self.db.list_inventory_items()])

    def test_sponsor_crud(self) -> None:
        sp_id = self.db.create_sponsor(name="Patrocinador", sponsor_type="ouro", contribution_amount=1000.0)
        sponsor = self.db.get_sponsor(sp_id)
        assert sponsor is not None
        self.assertEqual(sponsor["name"], "Patrocinador")
        self.assertIn(sp_id, [s["id"] for s in self.db.list_sponsors()])
        self.db.delete_sponsor(sp_id)
        self.assertNotIn(sp_id, [s["id"] for s in self.db.list_sponsors()])


class TestTrainingDomain(DatabaseTestCase):
    def test_training_session(self) -> None:
        sid = self.db.create_training_session(title="Aula 1", session_type="aula")
        session = self.db.get_training_session(sid)
        assert session is not None
        self.assertEqual(session["title"], "Aula 1")
        self.assertIn(sid, [s["id"] for s in self.db.list_training_sessions()])


class TestAppSettingsAndAudit(DatabaseTestCase):
    def test_app_settings_roundtrip(self) -> None:
        settings = self.db.get_app_settings()
        self.assertIsInstance(settings, dict)
        # round-trip nao deve falhar nem perder o tipo
        self.db.save_app_settings(settings)
        self.assertIsInstance(self.db.get_app_settings(), dict)

    def test_audit_log(self) -> None:
        log_id = self.db.create_audit_log("test_action", actor="tester", description="smoke")
        self.assertGreater(log_id, 0)
        logs = self.db.list_audit_logs()
        self.assertTrue(any(entry["action"] == "test_action" for entry in logs))


if __name__ == "__main__":
    unittest.main()
