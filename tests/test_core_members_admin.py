from __future__ import annotations

import sqlite3
import unittest
from datetime import date
from pathlib import Path

from src.core.database import Database
from src.core.services import (
    AppError,
)
from tests.support.core_service_base import CoreServiceTestCase


class RolePermissionMatrixTest(unittest.TestCase):
    """Spec §14.1 — perfis capitao/jogador e matriz de permissões."""

    def test_new_roles_exist_in_operator_roles(self) -> None:
        from src.services.constants import OPERATOR_ROLES
        self.assertIn("capitao", OPERATOR_ROLES)
        self.assertIn("jogador", OPERATOR_ROLES)
        # 'publico' propositalmente NÃO é login role (portal anônimo).
        self.assertNotIn("publico", OPERATOR_ROLES)

    def test_capitao_can_submit_lineup_and_request_substitution(self) -> None:
        from src.config.permissions import get_permissions_for_role
        perms = get_permissions_for_role("capitao")
        self.assertIn("team_lineup_submit", perms)
        self.assertIn("team_substitution_request", perms)
        self.assertIn("own_data_read", perms)
        # NÃO pode mexer em config nem em outros membros
        self.assertNotIn("settings_write", perms)
        self.assertNotIn("member_write", perms)
        self.assertNotIn("tournament_write", perms)

    def test_jogador_has_only_read_own_and_presence(self) -> None:
        from src.config.permissions import get_permissions_for_role
        perms = get_permissions_for_role("jogador")
        self.assertEqual({"own_data_read", "presence_confirm"}, set(perms))

    def test_admin_inherits_all_new_permissions(self) -> None:
        from src.config.permissions import get_permissions_for_role
        perms = set(get_permissions_for_role("admin"))
        for action in (
            "team_lineup_submit",
            "team_substitution_request",
            "own_data_read",
            "presence_confirm",
        ):
            self.assertIn(action, perms)

    def test_arbiter_can_act_on_lineups_and_substitutions(self) -> None:
        from src.config.permissions import get_permissions_for_role
        perms = get_permissions_for_role("arbiter")
        self.assertIn("team_lineup_submit", perms)
        self.assertIn("team_substitution_request", perms)


class MembersAdminTest(CoreServiceTestCase):
    def test_member_registration_recalculates_age_category_for_tournament_year(self) -> None:
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Sub",
                "birth_date": "2008-01-01",
                "rating": "1500",
                "member_type": "socio",
                "status": "active",
            }
        )
        tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Torneio Sub",
                "scope": "club",
                "club_id": "1",
                "start_date": "2024-06-01",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )

        player_id = self.member_service.register_member_in_tournament(tournament_id, member_id)
        player = self.db.get_player(player_id)

        self.assertIsNotNone(player)
        self.assertEqual(player["category"], "Sub-16")
        self.assertEqual(player["age_category"], "Sub-16")
        self.assertEqual(player["rating_category"], "Sub-1800")
        self.assertEqual(player["prize_tags"], "Socio do Clube")

    def test_learning_levels_can_be_assigned_to_members(self) -> None:
        default_levels = self.db.list_learning_levels(active_only=True)
        self.assertGreaterEqual(len(default_levels), 5)
        self.assertEqual(default_levels[0]["name"], "Iniciante")

        level_id = self.learning_level_service.create_level(
            {
                "name": "Pre-competitivo",
                "description": "Pronto para torneios internos.",
                "display_order": "45",
            }
        )
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Nivel",
                "member_type": "aluno",
                "status": "active",
                "learning_level_id": str(level_id),
            }
        )

        member = self.db.get_member(member_id)
        levels = self.db.list_learning_levels(active_only=False)
        custom_level = self.db.get_learning_level(level_id)

        self.assertIsNotNone(member)
        self.assertEqual(member["learning_level_id"], level_id)
        self.assertEqual(member["learning_level_name"], "Pre-competitivo")
        self.assertEqual(custom_level["members_count"], 1)
        self.assertIn("Pre-competitivo", {level["name"] for level in levels})

        self.member_service.update_member(
            member_id,
            {
                "name": "Aluno Nivel",
                "member_type": "aluno",
                "status": "active",
                "learning_level_id": "",
            },
        )
        self.assertIsNone(self.db.get_member(member_id)["learning_level_id"])

        with self.assertRaisesRegex(AppError, "Nivel de aprendizagem"):
            self.member_service.update_member(
                member_id,
                {
                    "name": "Aluno Nivel",
                    "member_type": "aluno",
                    "status": "active",
                    "learning_level_id": "99999",
                },
            )

    def test_close_round_creates_backup_and_updates_standings(self) -> None:
        self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(round_data["id"])

        self.service.close_round(self.tournament_id, round_data["id"])

        backups = list(self.backup_dir.glob("*.db"))
        standings = self.service.standings(self.tournament_id)
        closed_round = self.db.get_round(round_data["id"])

        self.assertEqual(closed_round["status"], "closed")
        self.assertGreaterEqual(len(backups), 2)
        self.assertTrue(any("before_close_round" in backup.name for backup in backups))
        self.assertEqual(standings[0]["points"], 1.0)

    def test_member_registration_creates_linked_tournament_player(self) -> None:
        self.db.save_club("Clube Teste", city="Curitiba")
        member_id = self.member_service.create_member(
            {
                "name": "Ana Membro",
                "rating": "1800",
                "category": "Sub-18",
                "member_type": "aluno",
                "status": "active",
            }
        )

        player_id = self.member_service.register_member_in_tournament(self.tournament_id, member_id)
        player = self.db.get_player(player_id)

        self.assertEqual(player["member_id"], member_id)
        self.assertEqual(player["name"], "Ana Membro")
        self.assertEqual(player["club"], "Clube Teste")

    def test_member_surname_formats_tournament_player_name(self) -> None:
        member_id = self.member_service.create_member(
            {
                "name": "Lucas",
                "surname": "Costa",
                "rating": "1700",
                "member_type": "aluno",
                "status": "active",
            }
        )

        player_id = self.member_service.register_member_in_tournament(self.tournament_id, member_id)
        member = self.db.get_member(member_id)
        player = self.db.get_player(player_id)

        self.assertEqual(member["surname"], "Costa")
        self.assertEqual(player["name"], "Lucas Costa")
        self.assertEqual(player["surname"], "Costa")
        self.assertEqual(player["given_name"], "Lucas")

    def test_delete_unpaired_player_removes_registration(self) -> None:
        player_id = self.db.create_player(
            self.tournament_id,
            name="Cadastro errado",
            rating=1200,
        )

        self.service.delete_player_if_unpaired(self.tournament_id, player_id)

        self.assertIsNone(self.db.get_player(player_id))

    def test_delete_paired_player_is_blocked_to_preserve_history(self) -> None:
        player_ids = self._create_players(2)
        self.service.generate_next_round(self.tournament_id)

        with self.assertRaises(AppError):
            self.service.delete_player_if_unpaired(self.tournament_id, player_ids[0])

        self.assertIsNotNone(self.db.get_player(player_ids[0]))

    def test_member_statuses_control_tournament_registration_eligibility(self) -> None:
        active_id = self.member_service.create_member(
            {
                "name": "Ativo",
                "member_type": "socio",
                "status": "active",
            }
        )
        visitor_id = self.member_service.create_member(
            {
                "name": "Visitante",
                "member_type": "visitante",
                "status": "visitor",
            }
        )
        guest_id = self.member_service.create_member(
            {
                "name": "Convidado",
                "member_type": "convidado",
                "status": "guest",
            }
        )
        withdrawn_id = self.member_service.create_member(
            {
                "name": "Desistente",
                "member_type": "aluno",
                "status": "withdrawn",
            }
        )

        eligible = self.db.list_members_for_tournament(self.tournament_id, active_only=True)
        eligible_ids = {member["id"] for member in eligible}

        self.assertIn(active_id, eligible_ids)
        self.assertNotIn(visitor_id, eligible_ids)
        self.assertNotIn(guest_id, eligible_ids)
        self.assertNotIn(withdrawn_id, eligible_ids)

        with self.assertRaises(AppError):
            self.member_service.register_member_in_tournament(self.tournament_id, visitor_id)

    def test_school_classes_filter_members_for_tournament_registration(self) -> None:
        school_id = self.club_service.save_profile(
            {
                "name": "Escola Alpha",
                "kind": "school",
                "city": "Teresina",
                "active": 1,
            },
            club_id=None,
        )
        other_club_id = self.club_service.save_profile(
            {
                "name": "Clube Beta",
                "kind": "club",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": school_id,
                "name": "Turma A",
                "teacher": "Professora",
                "weekday": "Segunda",
                "time": "14:00",
                "active": 1,
            }
        )
        school_member_id = self.member_service.create_member(
            {
                "name": "Aluno Escola",
                "rating": "1500",
                "club_id": school_id,
                "class_id": class_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        other_member_id = self.member_service.create_member(
            {
                "name": "Aluno Outro Clube",
                "rating": "1450",
                "club_id": other_club_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        school_tournament_id = self.db.create_tournament(
            "Interclasse",
            club_id=school_id,
            rounds_count=3,
        )

        eligible = self.db.list_members_for_tournament(school_tournament_id, active_only=True)
        eligible_ids = {member["id"] for member in eligible}
        player_id = self.member_service.register_member_in_tournament(
            school_tournament_id,
            school_member_id,
        )
        player = self.db.get_player(player_id)
        tournament_players = self.db.list_players(school_tournament_id, active_only=False)
        member = self.db.get_member(school_member_id)
        class_data = self.db.list_classes(club_id=school_id)[0]

        self.assertIn(school_member_id, eligible_ids)
        self.assertNotIn(other_member_id, eligible_ids)
        self.assertEqual(player["club"], "Escola Alpha")
        self.assertEqual(player["active_class_name"], "Turma A")
        self.assertEqual(tournament_players[0]["active_class_name"], "Turma A")
        self.assertEqual(member["club_name"], "Escola Alpha")
        self.assertEqual(member["active_class_name"], "Turma A")
        self.assertEqual(class_data["active_members_count"], 1)

    def test_standalone_tournament_accepts_members_from_any_club(self) -> None:
        club_a_id = self.club_service.save_profile(
            {
                "name": "Clube A",
                "kind": "club",
                "active": 1,
            },
            club_id=None,
        )
        club_b_id = self.club_service.save_profile(
            {
                "name": "Clube B",
                "kind": "club",
                "active": 1,
            },
            club_id=None,
        )
        member_a_id = self.member_service.create_member(
            {
                "name": "Jogador A",
                "club_id": club_a_id,
                "status": "active",
            }
        )
        member_b_id = self.member_service.create_member(
            {
                "name": "Jogador B",
                "club_id": club_b_id,
                "status": "active",
            }
        )
        standalone_id = self.db.create_tournament(
            "Avulso",
            club_id=None,
            class_id=None,
            rounds_count=3,
        )

        eligible = self.db.list_members_for_tournament(standalone_id, active_only=True)
        eligible_ids = {member["id"] for member in eligible}
        player_id = self.member_service.register_member_in_tournament(standalone_id, member_b_id)

        self.assertIn(member_a_id, eligible_ids)
        self.assertIn(member_b_id, eligible_ids)
        self.assertIsNotNone(self.db.get_player(player_id))
        self.assertIsNone(self.db.get_tournament(standalone_id)["club_id"])

    def test_class_tournament_filters_members_by_class(self) -> None:
        school_id = self.club_service.save_profile(
            {
                "name": "Escola Gamma",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_a_id = self.club_service.save_class(
            {
                "club_id": school_id,
                "name": "Turma A",
                "active": 1,
            }
        )
        class_b_id = self.club_service.save_class(
            {
                "club_id": school_id,
                "name": "Turma B",
                "active": 1,
            }
        )
        class_member_id = self.member_service.create_member(
            {
                "name": "Aluno Turma A",
                "club_id": school_id,
                "class_id": class_a_id,
                "status": "active",
            }
        )
        other_class_member_id = self.member_service.create_member(
            {
                "name": "Aluno Turma B",
                "club_id": school_id,
                "class_id": class_b_id,
                "status": "active",
            }
        )
        no_class_member_id = self.member_service.create_member(
            {
                "name": "Aluno Sem Turma",
                "club_id": school_id,
                "status": "active",
            }
        )
        class_tournament_id = self.db.create_tournament(
            "Interturma A",
            club_id=school_id,
            class_id=class_a_id,
            rounds_count=3,
        )

        eligible = self.db.list_members_for_tournament(class_tournament_id, active_only=True)
        eligible_ids = {member["id"] for member in eligible}
        player_id = self.member_service.register_member_in_tournament(
            class_tournament_id,
            class_member_id,
        )

        self.assertEqual(eligible_ids, {class_member_id})
        self.assertIsNotNone(self.db.get_player(player_id))
        self.assertEqual(self.db.get_tournament(class_tournament_id)["class_name"], "Turma A")
        self.assertNotIn(other_class_member_id, eligible_ids)
        self.assertNotIn(no_class_member_id, eligible_ids)
        with self.assertRaises(AppError):
            self.member_service.register_member_in_tournament(class_tournament_id, other_class_member_id)

    def test_class_tournament_can_import_members_from_other_classes_when_allowed(self) -> None:
        school_id = self.club_service.save_profile(
            {
                "name": "Escola Delta",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_a_id = self.club_service.save_class(
            {
                "club_id": school_id,
                "name": "Turma A",
                "active": 1,
            }
        )
        class_b_id = self.club_service.save_class(
            {
                "club_id": school_id,
                "name": "Turma B",
                "active": 1,
            }
        )
        class_member_id = self.member_service.create_member(
            {
                "name": "Aluno Turma A",
                "club_id": school_id,
                "class_id": class_a_id,
                "status": "active",
            }
        )
        other_class_member_id = self.member_service.create_member(
            {
                "name": "Aluno Turma B",
                "club_id": school_id,
                "class_id": class_b_id,
                "status": "active",
            }
        )
        class_tournament_id = self.db.create_tournament(
            "Interturma com convidados",
            club_id=school_id,
            class_id=class_a_id,
            rounds_count=3,
        )

        scoped = self.db.list_members_for_tournament(class_tournament_id, active_only=True)
        all_available = self.db.list_members_for_tournament(
            class_tournament_id,
            active_only=True,
            include_out_of_scope=True,
        )
        imported_player_id = self.member_service.register_member_in_tournament(
            class_tournament_id,
            other_class_member_id,
            allow_out_of_scope=True,
        )
        result = self.member_service.register_active_members_in_tournament(
            class_tournament_id,
            include_out_of_scope=True,
        )

        self.assertEqual({member["id"] for member in scoped}, {class_member_id})
        self.assertEqual({member["id"] for member in all_available}, {class_member_id, other_class_member_id})
        self.assertEqual(self.db.get_player(imported_player_id)["member_id"], other_class_member_id)
        self.assertEqual(result["registered"], 1)
        self.assertEqual(result["skipped"], 1)

    def test_guardian_links_multiple_members_and_keeps_one_primary_contact(self) -> None:
        member_id = self.member_service.create_member(
            {
                "name": "Aluno menor",
                "birth_date": f"{date.today().year - 12}-01-01",
                "member_type": "aluno",
                "status": "active",
            }
        )
        sibling_id = self.member_service.create_member(
            {
                "name": "Irmao menor",
                "birth_date": f"{date.today().year - 10}-01-01",
                "member_type": "aluno",
                "status": "active",
            }
        )
        mother_id = self.guardian_service.create_guardian(
            {"name": "Maria Responsavel", "phone": "1111", "email": "maria@example.com"}
        )
        father_id = self.guardian_service.create_guardian(
            {"name": "Jose Responsavel", "phone": "2222"}
        )

        self.guardian_service.link_guardian_to_member(
            {
                "member_id": member_id,
                "guardian_id": mother_id,
                "relationship": "Mae",
                "primary_contact": 1,
                "emergency_contact": 1,
            }
        )
        self.guardian_service.link_guardian_to_member(
            {
                "member_id": member_id,
                "guardian_id": father_id,
                "relationship": "Pai",
                "primary_contact": 1,
            }
        )
        self.guardian_service.link_guardian_to_member(
            {
                "member_id": sibling_id,
                "guardian_id": mother_id,
                "relationship": "Mae",
                "primary_contact": 1,
            }
        )

        member_guardians = self.db.list_member_guardians(member_id)
        mother_members = self.db.list_guardian_members(mother_id)

        self.assertEqual(len(member_guardians), 2)
        self.assertEqual(member_guardians[0]["guardian_id"], father_id)
        self.assertEqual(member_guardians[0]["primary_contact"], 1)
        self.assertEqual(member_guardians[1]["primary_contact"], 0)
        self.assertCountEqual(
            [item["member_id"] for item in mother_members],
            [member_id, sibling_id],
        )

    def test_minor_members_without_guardians_filters_only_active_minors(self) -> None:
        minor_id = self.member_service.create_member(
            {
                "name": "Menor sem responsavel",
                "birth_date": f"{date.today().year - 9}-01-01",
                "member_type": "aluno",
                "status": "active",
            }
        )
        adult_id = self.member_service.create_member(
            {
                "name": "Adulto",
                "birth_date": f"{date.today().year - 30}-01-01",
                "member_type": "socio",
                "status": "active",
            }
        )
        inactive_minor_id = self.member_service.create_member(
            {
                "name": "Menor inativo",
                "birth_date": f"{date.today().year - 11}-01-01",
                "member_type": "aluno",
                "status": "inactive",
            }
        )
        guardian_id = self.guardian_service.create_guardian({"name": "Responsavel"})

        missing_before = self.guardian_service.minor_members_without_guardians()
        self.guardian_service.link_guardian_to_member(
            {
                "member_id": minor_id,
                "guardian_id": guardian_id,
                "relationship": "Responsavel",
                "primary_contact": 1,
            }
        )
        missing_after = self.guardian_service.minor_members_without_guardians()

        self.assertIn(minor_id, {member["id"] for member in missing_before})
        self.assertNotIn(adult_id, {member["id"] for member in missing_before})
        self.assertNotIn(inactive_minor_id, {member["id"] for member in missing_before})
        self.assertNotIn(minor_id, {member["id"] for member in missing_after})

    def test_training_session_records_attendance_and_exports_report(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Escola de Xadrez",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": club_id,
                "name": "Turma Iniciantes",
                "teacher": "Instrutora",
                "weekday": "Quarta",
                "time": "15:00",
                "active": 1,
            }
        )
        present_member_id = self.member_service.create_member(
            {
                "name": "Aluno Presente",
                "club_id": club_id,
                "class_id": class_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        absent_member_id = self.member_service.create_member(
            {
                "name": "Aluno Ausente",
                "club_id": club_id,
                "class_id": class_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        outside_member_id = self.member_service.create_member(
            {
                "name": "Aluno Outra Turma",
                "club_id": club_id,
                "member_type": "aluno",
                "status": "active",
            }
        )

        session_id = self.training_service.save_session(
            {
                "club_id": club_id,
                "class_id": class_id,
                "title": "Aula de finais",
                "session_type": "aula",
                "session_date": "2026-05-20",
                "start_time": "15:00",
                "end_time": "16:30",
                "instructor": "Instrutora",
                "location": "Sala 1",
                "status": "planned",
            }
        )
        session_members = self.db.list_session_members_for_attendance(session_id)

        result = self.training_service.record_attendance(
            session_id,
            [
                {"member_id": present_member_id, "status": "present"},
                {"member_id": absent_member_id, "status": "absent", "notes": "Avisado"},
            ],
        )
        summary = self.training_service.member_attendance_summary(present_member_id)
        sessions = self.db.list_training_sessions()
        report_rows = self.training_service.attendance_report("2026-05-01", "2026-05-31")
        output_path = Path(self.temp_dir.name) / "presencas.csv"
        self.export_service.export_attendance_report(
            output_path,
            start_date="2026-05-01",
            end_date="2026-05-31",
        )
        content = output_path.read_text(encoding="utf-8-sig")

        self.assertCountEqual(
            [member["id"] for member in session_members],
            [present_member_id, absent_member_id],
        )
        self.assertNotIn(outside_member_id, {member["id"] for member in session_members})
        self.assertEqual(result["saved"], 2)
        self.assertEqual(summary["present"], 1)
        self.assertEqual(summary["attendance_rate"], 100.0)
        self.assertEqual(sessions[0]["present_count"], 1)
        self.assertEqual(sessions[0]["absent_count"], 1)
        self.assertEqual(len(report_rows), 2)
        self.assertIn("Aula de finais", content)
        self.assertIn("Aluno Presente", content)
        self.assertIn("Aluno Ausente", content)

    def test_training_sessions_store_pedagogical_plan_fields(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Escola Pedagogica",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": club_id,
                "name": "Turma Estrategia",
                "teacher": "Instrutora",
                "active": 1,
            }
        )
        level_id = self.learning_level_service.create_level(
            {
                "name": "Plano Tatico",
                "description": "Reconhece cravadas, garfos e ataques duplos.",
                "display_order": 42,
                "active": 1,
            }
        )

        session_id = self.training_service.save_session(
            {
                "club_id": club_id,
                "class_id": class_id,
                "learning_level_id": level_id,
                "title": "Taticas de ataque duplo",
                "session_type": "aula",
                "session_date": "2026-05-21",
                "start_time": "14:00",
                "end_time": "15:30",
                "instructor": "Instrutora",
                "location": "Sala 3",
                "objective": "Identificar garfos em posicoes simples.",
                "content": "Exercicios de ataque duplo com dama, cavalo e torre.",
                "homework": "Resolver 10 diagramas de garfo.",
                "status": "planned",
                "notes": "Usar tabuleiro mural.",
            }
        )

        session = self.db.get_training_session(session_id)
        sessions = self.db.list_training_sessions(class_id=class_id)

        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session["learning_level_id"], level_id)
        self.assertEqual(session["learning_level_name"], "Plano Tatico")
        self.assertEqual(session["objective"], "Identificar garfos em posicoes simples.")
        self.assertEqual(session["content"], "Exercicios de ataque duplo com dama, cavalo e torre.")
        self.assertEqual(session["homework"], "Resolver 10 diagramas de garfo.")
        self.assertEqual(sessions[0]["learning_level_name"], "Plano Tatico")

        self.training_service.save_session(
            {
                **session,
                "objective": "Aplicar garfos em partidas de treino.",
                "homework": "Anotar dois exemplos encontrados em casa.",
            },
            session_id=session_id,
        )
        updated = self.db.get_training_session(session_id)

        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["objective"], "Aplicar garfos em partidas de treino.")
        self.assertEqual(updated["homework"], "Anotar dois exemplos encontrados em casa.")
        with self.assertRaisesRegex(AppError, "Nivel pedagogico"):
            self.training_service.save_session(
                {
                    "club_id": club_id,
                    "class_id": class_id,
                    "learning_level_id": 99999,
                    "title": "Aula invalida",
                    "session_type": "aula",
                    "status": "planned",
                }
            )

    def test_exercise_library_lists_attempts_and_training_session_link(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Escola Taticas",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": club_id,
                "name": "Turma Taticas",
                "teacher": "Instrutor",
                "active": 1,
            }
        )
        level_id = self.learning_level_service.create_level(
            {
                "name": "Tatica Basica",
                "description": "Garfos, cravadas e mates simples.",
                "display_order": 50,
                "active": 1,
            }
        )
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Tatico",
                "club_id": club_id,
                "class_id": class_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        exercise_id = self.exercise_service.save_exercise(
            {
                "club_id": club_id,
                "learning_level_id": level_id,
                "title": "Mate em 1 com dama",
                "theme": "Mate em 1",
                "difficulty": "easy",
                "fen": "6k1/5ppp/8/8/8/8/5PPP/5QK1 w - - 0 1",
                "solution": "Df7#",
                "objective": "Reconhecer mate direto.",
                "tags": "mate,dama",
            }
        )
        second_exercise_id = self.exercise_service.save_exercise(
            {
                "club_id": club_id,
                "learning_level_id": level_id,
                "title": "Garfo de cavalo",
                "theme": "Garfo",
                "difficulty": "basic",
            }
        )
        list_id = self.exercise_service.save_training_list(
            {
                "club_id": club_id,
                "class_id": class_id,
                "learning_level_id": level_id,
                "name": "Lista de mates e garfos",
                "target_date": "2026-05-22",
                "status": "ready",
                "description": "Treino tatico da turma.",
            }
        )
        self.exercise_service.set_training_list_exercises(list_id, [exercise_id, second_exercise_id])
        session_id = self.training_service.save_session(
            {
                "club_id": club_id,
                "class_id": class_id,
                "learning_level_id": level_id,
                "training_list_id": list_id,
                "title": "Treino tatico guiado",
                "session_type": "treino",
                "session_date": "2026-05-22",
                "status": "planned",
            }
        )
        attempt_id = self.exercise_service.record_attempt(
            {
                "exercise_id": exercise_id,
                "member_id": member_id,
                "list_id": list_id,
                "session_id": session_id,
                "attempt_date": "2026-05-22",
                "result": "correct",
            }
        )

        exercise = self.db.get_exercise(exercise_id)
        training_list = self.db.get_training_list(list_id)
        list_items = self.db.list_training_list_exercises(list_id)
        session = self.db.get_training_session(session_id)
        attempts = self.db.list_exercise_attempts(member_id=member_id)

        self.assertIsNotNone(exercise)
        self.assertIsNotNone(training_list)
        self.assertIsNotNone(session)
        assert exercise is not None
        assert training_list is not None
        assert session is not None
        self.assertEqual(exercise["learning_level_name"], "Tatica Basica")
        self.assertEqual(training_list["exercise_count"], 2)
        self.assertEqual([item["exercise_id"] for item in list_items], [exercise_id, second_exercise_id])
        self.assertEqual(session["training_list_id"], list_id)
        self.assertEqual(session["training_list_name"], "Lista de mates e garfos")
        self.assertEqual(attempts[0]["id"], attempt_id)
        self.assertEqual(attempts[0]["score"], 1.0)
        self.assertEqual(attempts[0]["exercise_title"], "Mate em 1 com dama")

        self.exercise_service.remove_exercise_from_training_list(list_id, exercise_id)
        remaining = self.db.list_training_list_exercises(list_id)

        self.assertEqual([item["exercise_id"] for item in remaining], [second_exercise_id])
        with self.assertRaisesRegex(AppError, "Dificuldade"):
            self.exercise_service.save_exercise({"title": "Invalido", "difficulty": "impossivel"})

    def test_inventory_tracks_items_loans_and_maintenance(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Clube Material",
                "kind": "club",
                "active": 1,
            },
            club_id=None,
        )
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Emprestimo",
                "club_id": club_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        item_id = self.inventory_service.save_item(
            {
                "club_id": club_id,
                "code": "REL-001",
                "name": "Relogio digital",
                "item_type": "clocks",
                "quantity_total": "2",
                "condition_status": "good",
                "storage_location": "Armario 1",
                "acquisition_date": "2026-05-01",
                "acquisition_value": "150,50",
            }
        )
        loan_id = self.inventory_service.save_loan(
            {
                "item_id": item_id,
                "member_id": member_id,
                "quantity": "1",
                "loan_date": "2026-05-10",
                "due_date": "2026-05-20",
                "status": "open",
                "notes": "Treino em casa",
            }
        )

        item = self.db.get_inventory_item(item_id)
        loans = self.db.list_inventory_loans(item_id=item_id)
        summary = self.inventory_service.inventory_summary()

        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item["borrowed_quantity"], 1)
        self.assertEqual(item["available_quantity"], 1)
        self.assertEqual(loans[0]["member_name"], "Aluno Emprestimo")
        self.assertEqual(summary["borrowed_quantity"], 1)
        self.assertEqual(summary["open_loans"], 1)

        with self.assertRaisesRegex(AppError, "Quantidade indisponivel"):
            self.inventory_service.save_loan(
                {
                    "item_id": item_id,
                    "member_id": member_id,
                    "quantity": "2",
                    "status": "open",
                }
            )
        with self.assertRaisesRegex(AppError, "emprestimos em aberto"):
            self.inventory_service.toggle_item_active(item_id)

        self.inventory_service.return_loan(loan_id, return_date="2026-05-18")
        returned = self.db.get_inventory_loan(loan_id)
        item_after_return = self.db.get_inventory_item(item_id)

        self.assertIsNotNone(returned)
        self.assertIsNotNone(item_after_return)
        assert returned is not None
        assert item_after_return is not None
        self.assertEqual(returned["status"], "returned")
        self.assertEqual(returned["return_date"], "2026-05-18")
        self.assertEqual(item_after_return["available_quantity"], 2)

        maintenance_id = self.inventory_service.save_maintenance(
            {
                "item_id": item_id,
                "opened_date": "2026-05-19",
                "description": "Trocar pilha",
                "cost": "12,75",
                "vendor": "Loja local",
                "status": "open",
            }
        )
        maintenance_open = self.db.get_inventory_maintenance(maintenance_id)
        self.inventory_service.close_maintenance(maintenance_id, resolved_date="2026-05-20")
        maintenance_closed = self.db.get_inventory_maintenance(maintenance_id)

        self.assertIsNotNone(maintenance_open)
        self.assertIsNotNone(maintenance_closed)
        assert maintenance_open is not None
        assert maintenance_closed is not None
        self.assertEqual(maintenance_open["cost"], 12.75)
        self.assertEqual(maintenance_closed["status"], "done")
        self.assertEqual(maintenance_closed["resolved_date"], "2026-05-20")

    def test_financial_plans_payments_status_and_export_report(self) -> None:
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Financeiro",
                "member_type": "aluno",
                "status": "active",
            }
        )
        plan_id = self.finance_service.save_plan(
            {
                "name": "Mensalidade",
                "amount": "120,50",
                "billing_cycle": "monthly",
                "active": 1,
            }
        )

        overdue_payment_id = self.finance_service.save_payment(
            {
                "member_id": member_id,
                "plan_id": plan_id,
                "reference_period": "2000-01",
                "due_date": "2000-01-10",
                "status": "pending",
            }
        )
        paid_payment_id = self.finance_service.save_payment(
            {
                "member_id": member_id,
                "description": "Aula avulsa",
                "reference_period": "2999-01",
                "due_date": "2999-01-10",
                "payment_date": "2999-01-09",
                "amount": "50",
                "status": "paid",
                "method": "Pix",
            }
        )

        payments = self.finance_service.payments_report()
        status = self.finance_service.member_financial_status(member_id)
        summary = self.finance_service.finance_summary()
        output_path = Path(self.temp_dir.name) / "financeiro.csv"
        self.export_service.export_financial_report(output_path)
        content = output_path.read_text(encoding="utf-8-sig")

        overdue_payment = next(payment for payment in payments if payment["id"] == overdue_payment_id)
        paid_payment = next(payment for payment in payments if payment["id"] == paid_payment_id)
        self.assertEqual(overdue_payment["amount"], 120.5)
        self.assertEqual(overdue_payment["effective_status"], "late")
        self.assertEqual(paid_payment["effective_status"], "paid")
        self.assertEqual(status["status"], "late")
        self.assertEqual(status["open_amount"], 120.5)
        self.assertEqual(summary["late"], 1)
        self.assertEqual(summary["paid"], 1)
        self.assertEqual(summary["paid_amount"], 50.0)
        self.assertIn("Aluno Financeiro", content)
        self.assertIn("Mensalidade", content)
        self.assertIn("Atrasado", content)

    def test_finance_generates_recurring_payments_and_receipts(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Escola Financeira",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        billable_member_id = self.member_service.create_member(
            {
                "name": "Aluno Mensalidade",
                "club_id": club_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        second_billable_member_id = self.member_service.create_member(
            {
                "name": "Socio Mensalidade",
                "club_id": club_id,
                "member_type": "socio",
                "status": "active",
            }
        )
        visitor_id = self.member_service.create_member(
            {
                "name": "Visitante Sem Cobranca",
                "club_id": club_id,
                "member_type": "visitante",
                "status": "active",
            }
        )
        plan_id = self.finance_service.save_plan(
            {
                "name": "Mensalidade recorrente",
                "amount": "95",
                "billing_cycle": "monthly",
                "active": 1,
            }
        )

        result = self.finance_service.generate_recurring_payments(
            plan_id,
            "2999-06",
            "2999-06-10",
            club_id=club_id,
        )
        duplicate_result = self.finance_service.generate_recurring_payments(
            plan_id,
            "2999-06",
            "2999-06-10",
            club_id=club_id,
        )
        payments = self.finance_service.payments_report(
            start_date="2999-06-01",
            end_date="2999-06-30",
        )
        generated_member_ids = {int(payment["member_id"]) for payment in payments}

        self.assertEqual(result["created"], 2)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(duplicate_result["created"], 0)
        self.assertEqual(duplicate_result["skipped"], 2)
        self.assertIn(billable_member_id, generated_member_ids)
        self.assertIn(second_billable_member_id, generated_member_ids)
        self.assertNotIn(visitor_id, generated_member_ids)
        for payment in payments:
            self.assertEqual(payment["description"], "Mensalidade recorrente - 2999-06")
            self.assertEqual(payment["reference_period"], "2999-06")
            self.assertEqual(payment["due_date"], "2999-06-10")
            self.assertEqual(payment["amount"], 95.0)

        first_payment_id = int(result["payment_ids"][0])
        receipt_path = Path(self.temp_dir.name) / "recibo.pdf"
        with self.assertRaisesRegex(AppError, "Recibo"):
            self.export_service.export_payment_receipt(first_payment_id, receipt_path)

        self.finance_service.mark_payment_paid(first_payment_id, payment_date="2999-06-09", method="Pix")
        exported_receipt = self.export_service.export_payment_receipt(first_payment_id, receipt_path)

        self.assertEqual(exported_receipt, receipt_path)
        self.assertTrue(receipt_path.exists())
        self.assertEqual(receipt_path.read_bytes()[:4], b"%PDF")

    def test_calendar_events_sync_tournament_and_export_report(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Clube Calendario",
                "kind": "club",
                "active": 1,
            },
            club_id=None,
        )
        tournament_id = self.db.create_tournament(
            "Aberto do Clube",
            club_id=club_id,
            location="Salao",
            start_date="2999-01-10",
            rounds_count=3,
        )

        tournament_event_id = self.event_service.sync_tournament_event(tournament_id)
        meeting_event_id = self.event_service.save_event(
            {
                "club_id": club_id,
                "title": "Reuniao de pais",
                "event_type": "meeting",
                "event_date": "2999-01-05",
                "start_time": "19:00",
                "location": "Sala 2",
                "status": "confirmed",
            }
        )
        canceled_event_id = self.event_service.save_event(
            {
                "club_id": club_id,
                "title": "Evento cancelado",
                "event_type": "social",
                "event_date": "2999-01-03",
                "status": "canceled",
            }
        )

        tournament_event = self.db.get_club_event(tournament_event_id)
        events = self.event_service.events_report("2999-01-01", "2999-01-31")
        upcoming = self.event_service.upcoming_events(limit=10)
        output_path = Path(self.temp_dir.name) / "eventos.csv"
        self.export_service.export_events_report(
            output_path,
            start_date="2999-01-01",
            end_date="2999-01-31",
        )
        content = output_path.read_text(encoding="utf-8-sig")

        self.assertEqual(tournament_event["title"], "Aberto do Clube")
        self.assertEqual(tournament_event["event_type"], "tournament")
        self.assertEqual(tournament_event["tournament_id"], tournament_id)
        self.assertCountEqual([event["id"] for event in events], [tournament_event_id, meeting_event_id, canceled_event_id])
        self.assertNotIn("Evento cancelado", [event["title"] for event in upcoming])
        self.assertIn("Aberto do Clube", content)
        self.assertIn("Reuniao de pais", content)
        self.assertIn("Torneio", content)

    def test_register_active_members_in_tournament_skips_existing_and_ineligible(self) -> None:
        active_id = self.member_service.create_member(
            {
                "name": "Ativo 1",
                "member_type": "socio",
                "status": "active",
            }
        )
        second_active_id = self.member_service.create_member(
            {
                "name": "Ativo 2",
                "member_type": "aluno",
                "status": "active",
            }
        )
        visitor_id = self.member_service.create_member(
            {
                "name": "Visitante",
                "member_type": "visitante",
                "status": "visitor",
            }
        )
        self.member_service.register_member_in_tournament(self.tournament_id, active_id)

        result = self.member_service.register_active_members_in_tournament(self.tournament_id)
        players = self.db.list_players(self.tournament_id, active_only=False)
        registered_member_ids = {player["member_id"] for player in players}

        self.assertEqual(result["registered"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertIn(active_id, registered_member_ids)
        self.assertIn(second_active_id, registered_member_ids)
        self.assertNotIn(visitor_id, registered_member_ids)

    def test_member_tournament_history_summarizes_results(self) -> None:
        member_id = self.member_service.create_member(
            {
                "name": "Ana Membro",
                "rating": "1800",
                "member_type": "aluno",
                "status": "active",
            }
        )
        member_player_id = self.member_service.register_member_in_tournament(
            self.tournament_id,
            member_id,
        )
        self.db.create_player(
            self.tournament_id,
            name="Oponente",
            rating=1500,
            club="Clube",
            category="Absoluto",
        )
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(round_data["id"])[0]
        result = "1-0" if pairing["white_player_id"] == member_player_id else "0-1"
        self.db.update_pairing_result(pairing["id"], result)
        self.service.close_round(self.tournament_id, round_data["id"])

        history = self.member_service.tournament_history(member_id)
        results = self.member_service.tournament_results(member_id, self.tournament_id)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["name"], "Torneio teste")
        self.assertEqual(history[0]["points"], 1.0)
        self.assertEqual(history[0]["wins"], 1)
        self.assertEqual(history[0]["rounds_played"], 1)
        self.assertEqual(history[0]["last_result"], "Vitoria")
        self.assertEqual(results[0]["opponent"], "Oponente")
        self.assertEqual(results[0]["outcome"], "Vitoria")
        self.assertEqual(results[0]["points"], 1.0)
        self.assertNotEqual(self.service.standings(self.tournament_id)[0]["performance"], "")

    def test_internal_rating_update_creates_history_and_updates_member_rating(self) -> None:
        member_id, _member_player_id = self._create_member_win(rating=1600)

        result = self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        member = self.db.get_member(member_id)
        history = self.internal_rating_service.member_rating_history(member_id)

        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["duplicates"], 0)
        self.assertEqual(result["external"], 1)
        self.assertGreater(member["rating"], 1600)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["old_rating"], 1600)
        self.assertEqual(history[0]["new_rating"], member["rating"])
        self.assertEqual(history[0]["games"], 1)
        self.assertEqual(history[0]["performance"], 2300)

    def test_internal_rating_update_is_idempotent(self) -> None:
        member_id, _member_player_id = self._create_member_win(rating=1600)

        first = self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        rating_after_first = self.db.get_member(member_id)["rating"]
        second = self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        rating_after_second = self.db.get_member(member_id)["rating"]
        history = self.internal_rating_service.member_rating_history(member_id)

        self.assertEqual(first["updated"], 1)
        self.assertEqual(second["updated"], 0)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(rating_after_second, rating_after_first)
        self.assertEqual(len(history), 1)

    def test_next_tournament_registration_uses_updated_internal_rating(self) -> None:
        member_id, _member_player_id = self._create_member_win(rating=1600)
        self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        updated_rating = self.db.get_member(member_id)["rating"]
        next_tournament_id = self.db.create_tournament("Torneio seguinte", rounds_count=3)

        next_player_id = self.member_service.register_member_in_tournament(
            next_tournament_id,
            member_id,
        )
        next_player = self.db.get_player(next_player_id)

        self.assertEqual(next_player["rating"], updated_rating)

    def test_internal_ranking_summarizes_rating_results_and_exports(self) -> None:
        member_id, _member_player_id = self._create_member_win(rating=1600)
        self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        self.member_service.update_member(
            member_id,
            {
                "name": "Aluno Rating",
                "rating": str(self.db.get_member(member_id)["rating"]),
                "category": "Sub-18",
                "member_type": "aluno",
                "status": "active",
            },
        )
        self.member_service.create_member(
            {
                "name": "Aluno Sem Jogos",
                "rating": "1200",
                "category": "Sub-18",
                "member_type": "aluno",
                "status": "active",
            }
        )
        output_path = Path(self.temp_dir.name) / "ranking.csv"

        ranking = self.internal_rating_service.ranking(category="Sub-18")
        self.export_service.export_internal_ranking_report(output_path, category="Sub-18")
        content = output_path.read_text(encoding="utf-8-sig")

        self.assertEqual(ranking[0]["member_id"], member_id)
        self.assertEqual(ranking[0]["games"], 1)
        self.assertEqual(ranking[0]["wins"], 1)
        self.assertEqual(ranking[0]["score_rate"], 100.0)
        self.assertGreater(ranking[0]["last_delta"], 0)
        self.assertIn("Ranking interno", content)
        self.assertIn("Aluno Rating", content)
        self.assertIn("Aproveitamento", content)

    def test_internal_ranking_filters_by_season_club_and_class(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Escola Ranking",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": club_id,
                "name": "Turma Ranking",
                "teacher": "Professor",
                "active": 1,
            }
        )
        member_id, _member_player_id = self._create_member_win(rating=1600)
        self.db.update_tournament_details(
            self.tournament_id,
            name="Torneio temporada",
            club_id=club_id,
            class_id=class_id,
            location="Sala 1",
            rounds_count=5,
            start_date="2026-05-10",
        )
        self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        updated_rating = self.db.get_member(member_id)["rating"]
        self.member_service.update_member(
            member_id,
            {
                "name": "Aluno Temporada",
                "club_id": club_id,
                "class_id": class_id,
                "rating": str(updated_rating),
                "category": "Sub-18",
                "member_type": "aluno",
                "status": "active",
            },
        )
        outside_member_id = self.member_service.create_member(
            {
                "name": "Aluno Fora",
                "rating": "1900",
                "category": "Sub-18",
                "member_type": "aluno",
                "status": "active",
            }
        )
        output_path = Path(self.temp_dir.name) / "ranking_temporada.csv"

        ranking = self.internal_rating_service.ranking(
            category="Sub-18",
            club_id=club_id,
            class_id=class_id,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        empty_season = self.internal_rating_service.ranking(
            category="Sub-18",
            club_id=club_id,
            class_id=class_id,
            start_date="2027-01-01",
            end_date="2027-12-31",
        )
        self.export_service.export_internal_ranking_report(
            output_path,
            category="Sub-18",
            club_id=club_id,
            class_id=class_id,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        content = output_path.read_text(encoding="utf-8-sig")

        self.assertEqual([item["member_id"] for item in ranking], [member_id])
        self.assertNotIn(outside_member_id, {item["member_id"] for item in ranking})
        self.assertEqual(ranking[0]["games"], 1)
        self.assertGreater(ranking[0]["season_delta"], 0)
        self.assertGreater(ranking[0]["last_delta"], 0)
        self.assertEqual(empty_season[0]["games"], 0)
        self.assertEqual(empty_season[0]["last_delta"], 0)
        self.assertIn("Escola Ranking", content)
        self.assertIn("Turma Ranking", content)
        self.assertIn("Temporada inicial", content)
        self.assertIn("2026-01-01", content)

        with self.assertRaisesRegex(AppError, "temporada"):
            self.internal_rating_service.ranking(start_date="2026-13-01")

    def test_export_member_evolution_report_includes_rating_and_results(self) -> None:
        member_id, _member_player_id = self._create_member_win(rating=1600)
        self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        guardian_id = self.guardian_service.create_guardian(
            {"name": "Maria Responsavel", "phone": "1111"}
        )
        self.guardian_service.link_guardian_to_member(
            {
                "member_id": member_id,
                "guardian_id": guardian_id,
                "relationship": "Mae",
                "primary_contact": 1,
            }
        )
        output_path = Path(self.temp_dir.name) / "evolucao.csv"

        self.export_service.export_member_evolution(member_id, output_path)
        content = output_path.read_text(encoding="utf-8-sig")

        self.assertIn("Aluno Rating", content)
        self.assertIn("Maria Responsavel", content)
        self.assertIn("Mae", content)
        self.assertIn("Evolucao por torneio", content)
        self.assertIn("Rating interno", content)
        self.assertIn("Resultados", content)
        self.assertIn("Torneio teste", content)
        self.assertIn("2300", content)
        self.assertIn("Vitoria", content)

    def test_app_settings_and_backup_restore_roundtrip(self) -> None:
        export_dir = Path(self.temp_dir.name) / "exports"
        self.db.save_app_settings(
            {
                "appearance_mode": "Dark",
                "default_export_dir": str(export_dir),
                "backup_dir": str(self.backup_dir),
                "arbitration_auto_refresh_enabled": "0",
                "arbitration_refresh_interval_seconds": "60",
                "arbitration_inline_tables_limit": "40",
            }
        )
        before_member_id = self.member_service.create_member(
            {
                "name": "Antes do backup",
                "rating": "1500",
                "member_type": "aluno",
                "status": "active",
            }
        )
        backup_path = self.db.backup("roundtrip")
        self.member_service.create_member(
            {
                "name": "Depois do backup",
                "rating": "1600",
                "member_type": "aluno",
                "status": "active",
            }
        )

        safety_backup = self.db.restore_backup(backup_path)
        settings = self.db.get_app_settings()
        members = self.db.list_members(active_only=False)
        member_names = {member["name"] for member in members}
        backups = self.db.list_backups()

        self.assertEqual(settings["appearance_mode"], "Dark")
        self.assertEqual(settings["default_export_dir"], str(export_dir))
        self.assertEqual(settings["arbitration_auto_refresh_enabled"], "0")
        self.assertEqual(settings["arbitration_refresh_interval_seconds"], "60")
        self.assertEqual(settings["arbitration_inline_tables_limit"], "40")
        self.assertTrue(safety_backup.exists())
        self.assertTrue(any(backup["name"] == backup_path.name for backup in backups))
        self.assertIn("Antes do backup", member_names)
        self.assertNotIn("Depois do backup", member_names)
        self.assertIsNotNone(self.db.get_member(before_member_id))

    def test_backup_copies_to_configured_cloud_dir(self) -> None:
        cloud_dir = Path(self.temp_dir.name) / "nuvem"
        cloud_dir.mkdir()
        self.db.save_app_settings({"cloud_sync_dir": str(cloud_dir)})

        backup_path = self.db.backup("com_nuvem")

        self.assertEqual(self.db.last_cloud_backup["status"], "success")
        self.assertTrue((cloud_dir / backup_path.name).exists())
        self.assertEqual(self.db.last_cloud_backup["path"], str(cloud_dir / backup_path.name))

    def test_backup_without_cloud_dir_reports_not_configured(self) -> None:
        self.db.save_app_settings({"cloud_sync_dir": ""})

        self.db.backup("sem_nuvem")

        self.assertEqual(self.db.last_cloud_backup["status"], "not_configured")

    def test_backup_with_invalid_cloud_dir_does_not_raise(self) -> None:
        missing = Path(self.temp_dir.name) / "nao_existe"
        self.db.save_app_settings({"cloud_sync_dir": str(missing)})

        # Falha de nuvem nao pode derrubar o backup local.
        backup_path = self.db.backup("nuvem_invalida")

        self.assertTrue(backup_path.exists())
        self.assertEqual(self.db.last_cloud_backup["status"], "invalid_directory")

    def test_create_backup_reports_cloud_status_from_db(self) -> None:
        cloud_dir = Path(self.temp_dir.name) / "nuvem2"
        cloud_dir.mkdir()
        self.db.save_app_settings({"cloud_sync_dir": str(cloud_dir)})

        result = self.security_service.create_backup("manual")

        self.assertEqual(result["cloud_status"], "success")

    def test_send_bulk_email_collects_per_recipient_results(self) -> None:
        from src.services.message_service import MessageService

        class _RecordingMailer(MessageService):
            def __init__(self, fail=()):
                super().__init__()
                self.fail = set(fail)
                self.sent: list[str] = []

            def send_email(self, to_email, subject, body):
                if to_email in self.fail:
                    raise RuntimeError("smtp down")
                self.sent.append(to_email)
                return True

        mailer = _RecordingMailer(fail={"erro@x.com"})
        recipients = [
            {"member_id": 1, "email": "ok@x.com"},
            {"member_id": 2, "email": "erro@x.com"},
            {"member_id": 3, "email": ""},  # sem e-mail -> falha sem tentar enviar
        ]

        summary = mailer.send_bulk_email(recipients, "Assunto", "Corpo")

        self.assertEqual(summary["sent_count"], 1)
        self.assertEqual(summary["failed_count"], 2)
        self.assertEqual(mailer.sent, ["ok@x.com"])
        self.assertEqual(summary["total"], 3)

    def test_bulk_email_members_targets_audience_and_logs(self) -> None:
        from src.services.dashboard_service import CommunicationService

        class _FakeMailer:
            def __init__(self):
                self.calls: list[tuple[str, str, str]] = []

            def send_bulk_email(self, recipients, subject, body):
                sent = []
                for r in recipients:
                    self.calls.append((r["email"], subject, body))
                    sent.append(r)
                return {"total": len(recipients), "sent": sent, "failed": [],
                        "sent_count": len(sent), "failed_count": 0}

        ana = self.member_service.create_member(
            {"name": "Ana", "rating": "1500", "member_type": "aluno",
             "status": "active", "email": "ana@x.com"}
        )
        self.member_service.create_member(
            {"name": "Beto", "rating": "1600", "member_type": "socio",
             "status": "active", "email": "beto@x.com"}
        )
        self.member_service.create_member(
            {"name": "Carla", "rating": "1400", "member_type": "aluno",
             "status": "active", "email": ""}  # sem e-mail -> ignorada
        )

        comm = CommunicationService(self.db)
        mailer = _FakeMailer()

        summary = comm.bulk_email_members(
            mailer, "Aviso", "Corpo do aviso", active_only=True, member_type="aluno"
        )

        # So Ana (aluno com e-mail). Beto e socio; Carla nao tem e-mail.
        self.assertEqual(summary["sent_count"], 1)
        self.assertEqual(summary["recipients_total"], 1)
        self.assertEqual(summary["skipped_no_email"], 1)
        self.assertEqual(summary["failed_count"], 0)
        self.assertEqual([call[0] for call in mailer.calls], ["ana@x.com"])
        # Envio bem-sucedido foi registrado em communication_logs.
        logs = comm.list_member_communications(ana)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["subject"], "Aviso")

    def test_bulk_email_members_requires_subject_and_body(self) -> None:
        from src.services.dashboard_service import CommunicationService

        comm = CommunicationService(self.db)
        with self.assertRaises(ValueError):
            comm.bulk_email_members(object(), "", "Corpo")

    def test_schedule_email_rejects_bad_datetime(self) -> None:
        from src.services.dashboard_service import CommunicationService

        comm = CommunicationService(self.db)
        with self.assertRaises(ValueError):
            comm.schedule_email("A", "B", "amanha de manha")

    def test_dispatch_sends_due_and_skips_future(self) -> None:
        from src.services.dashboard_service import CommunicationService

        class _FakeMailer:
            def __init__(self):
                self.calls: list[str] = []

            def send_bulk_email(self, recipients, subject, body):
                for r in recipients:
                    self.calls.append(r["email"])
                return {"total": len(recipients), "sent": list(recipients), "failed": [],
                        "sent_count": len(recipients), "failed_count": 0}

        self.member_service.create_member(
            {"name": "Ana", "rating": "1500", "member_type": "aluno",
             "status": "active", "email": "ana@x.com"}
        )
        comm = CommunicationService(self.db)
        due_id = comm.schedule_email("Vencida", "Corpo", "2000-01-01 00:00")
        comm.schedule_email("Futura", "Corpo", "2999-01-01 00:00")

        mailer = _FakeMailer()
        dispatched = comm.dispatch_due_scheduled_messages(mailer)

        self.assertEqual(len(dispatched), 1)
        self.assertEqual(dispatched[0]["id"], due_id)
        self.assertEqual(dispatched[0]["status"], "sent")
        self.assertEqual(mailer.calls, ["ana@x.com"])
        pending = comm.list_scheduled_messages(status="pending")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["subject"], "Futura")

    def test_cancel_scheduled_message_prevents_dispatch(self) -> None:
        from src.services.dashboard_service import CommunicationService

        class _FakeMailer:
            def send_bulk_email(self, recipients, subject, body):
                raise AssertionError("nao deveria enviar uma mensagem cancelada")

        comm = CommunicationService(self.db)
        msg_id = comm.schedule_email("X", "Y", "2000-01-01 00:00")
        comm.cancel_scheduled_message(msg_id)

        dispatched = comm.dispatch_due_scheduled_messages(_FakeMailer())

        self.assertEqual(dispatched, [])
        self.assertEqual(comm.list_scheduled_messages(status="pending"), [])

    def test_security_settings_audit_and_backup_retention(self) -> None:
        self.security_service.save_security_settings(
            {
                "backup_retention_count": "2",
            }
        )
        first = self.security_service.create_backup("seguranca_1")
        second = self.security_service.create_backup("seguranca_2")
        third = self.security_service.create_backup("seguranca_3")

        settings = self.db.get_app_settings()
        audit_rows = self.security_service.list_audit_logs(limit=20)
        backups = self.db.list_backups()
        backup_names = {backup["name"] for backup in backups}

        self.assertEqual(settings["backup_retention_count"], "2")
        self.assertTrue(first["path"].exists() or first["path"].name not in backup_names)
        self.assertTrue(second["path"].exists() or second["path"].name not in backup_names)
        self.assertTrue(third["path"].exists() or third["path"].name not in backup_names)
        self.assertLessEqual(len(backups), 2)
        self.assertTrue(any(row["action"] == "settings_saved" for row in audit_rows))
        self.assertTrue(any(row["action"] == "backup_created" for row in audit_rows))
        self.assertTrue(any(row["action"] == "backup_retention_applied" for row in audit_rows))

    def test_restore_corrupted_backup_keeps_current_database_usable(self) -> None:
        before_member_id = self.member_service.create_member(
            {
                "name": "Antes da falha",
                "rating": "1500",
                "member_type": "aluno",
                "status": "active",
            }
        )
        corrupted_backup = self.backup_dir / "corrompido.db"
        corrupted_backup.parent.mkdir(parents=True, exist_ok=True)
        corrupted_backup.write_text("nao e um sqlite valido", encoding="utf-8")

        with self.assertRaises(sqlite3.DatabaseError):
            self.db.restore_backup(corrupted_backup)
        after_member_id = self.member_service.create_member(
            {
                "name": "Depois da falha",
                "rating": "1510",
                "member_type": "aluno",
                "status": "active",
            }
        )
        member_names = {member["name"] for member in self.db.list_members(active_only=False)}

        self.assertIsNotNone(self.db.get_member(before_member_id))
        self.assertIsNotNone(self.db.get_member(after_member_id))
        self.assertIn("Antes da falha", member_names)
        self.assertIn("Depois da falha", member_names)

    def test_restore_legacy_backup_migrates_restored_database(self) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        legacy_path = self.backup_dir / "legacy_restore.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE tournaments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    location TEXT DEFAULT '',
                    start_date TEXT DEFAULT '',
                    end_date TEXT DEFAULT '',
                    system TEXT NOT NULL DEFAULT 'Suico',
                    rounds_count INTEGER NOT NULL DEFAULT 5,
                    time_control TEXT DEFAULT '',
                    bye_points REAL NOT NULL DEFAULT 1.0,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tournament_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    club TEXT DEFAULT '',
                    federation_id TEXT DEFAULT '',
                    fide_id TEXT DEFAULT '',
                    rating INTEGER NOT NULL DEFAULT 0,
                    category TEXT DEFAULT '',
                    birth_date TEXT DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                """
            )
            connection.commit()
        finally:
            connection.close()

        safety_backup = self.db.restore_backup(legacy_path)
        with self.db.connect() as restored_connection:
            user_version = restored_connection.execute("PRAGMA user_version").fetchone()[0]
            issuance_table = restored_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'certificate_issuances'
                """
            ).fetchone()
            template_count = restored_connection.execute(
                "SELECT COUNT(*) FROM certificate_templates"
            ).fetchone()[0]

        self.assertTrue(safety_backup.exists())
        self.assertEqual(Database.SCHEMA_VERSION, user_version)
        self.assertIsNotNone(issuance_table)
        self.assertGreaterEqual(template_count, 7)
        self.assertEqual([], self.db.list_certificate_issuances(limit=1))

    def test_certificate_service_exports_member_training_event_and_ranking_pdfs(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Escola Diplomas",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": club_id,
                "name": "Turma Diplomas",
                "teacher": "Professora",
                "active": 1,
            }
        )
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Diploma",
                "club_id": club_id,
                "class_id": class_id,
                "category": "Sub-14",
                "rating": "1500",
                "member_type": "aluno",
                "status": "active",
            }
        )
        absent_member_id = self.member_service.create_member(
            {
                "name": "Aluno Ausente",
                "club_id": club_id,
                "class_id": class_id,
                "category": "Sub-14",
                "rating": "1200",
                "member_type": "aluno",
                "status": "active",
            }
        )
        ranking_member_id = self.member_service.create_member(
            {
                "name": "Aluno Ranking",
                "club_id": club_id,
                "category": "Sub-14",
                "rating": "2200",
                "member_type": "aluno",
                "status": "active",
            }
        )
        session_id = self.training_service.save_session(
            {
                "club_id": club_id,
                "class_id": class_id,
                "title": "Aula de calculo",
                "session_type": "aula",
                "session_date": "2026-05-20",
                "instructor": "Professora",
                "location": "Sala 2",
                "status": "done",
            }
        )
        self.training_service.record_attendance(
            session_id,
            [
                {"member_id": member_id, "status": "present"},
                {"member_id": absent_member_id, "status": "absent"},
            ],
        )
        event_id = self.event_service.save_event(
            {
                "club_id": club_id,
                "title": "Festival Escolar",
                "event_type": "social",
                "event_date": "2026-05-21",
                "location": "Auditorio",
                "status": "done",
            }
        )

        member_path = Path(self.temp_dir.name) / "membro.pdf"
        training_path = Path(self.temp_dir.name) / "aula.pdf"
        event_path = Path(self.temp_dir.name) / "evento.pdf"
        ranking_path = Path(self.temp_dir.name) / "ranking.pdf"
        member_result = self.certificate_service.export_member_certificates(
            member_path,
            member_ids=[member_id],
        )
        training_result = self.certificate_service.export_training_certificates(
            session_id,
            training_path,
            present_only=False,
            member_ids=[member_id, absent_member_id],
        )
        event_result = self.certificate_service.export_event_certificates(
            event_id,
            event_path,
            member_ids=[member_id],
        )
        ranking_result = self.certificate_service.export_ranking_certificates(
            ranking_path,
            category="Sub-14",
            top_n=1,
        )
        member_recipient = self.certificate_service.member_recipients(member_ids=[member_id])[0]
        training_recipients = self.certificate_service.training_recipients(
            session_id,
            present_only=False,
        )
        event_recipient = self.certificate_service.event_recipients(event_id, member_ids=[member_id])[0]
        ranking_recipient = self.certificate_service.ranking_recipients(category="Sub-14", top_n=1)[0]

        self.assertEqual(member_result["exported"], 1)
        self.assertEqual(training_result["exported"], 2)
        self.assertEqual(event_result["exported"], 1)
        self.assertEqual(ranking_result["exported"], 1)
        all_codes = (
            member_result["verification_codes"]
            + training_result["verification_codes"]
            + event_result["verification_codes"]
            + ranking_result["verification_codes"]
        )
        issued_records = self.certificate_service.list_issuances(limit=10)
        verified_member = self.certificate_service.verify_issuance(member_result["verification_codes"][0])
        self.assertEqual(len(all_codes), 5)
        self.assertEqual(len(set(all_codes)), 5)
        self.assertEqual(len(issued_records), 5)
        self.assertEqual(verified_member["context_type"], "members")
        self.assertEqual(verified_member["recipient_name"], "Aluno Diploma")
        self.assertEqual(member_recipient["class_name"], "Turma Diplomas")
        self.assertEqual({item["status"] for item in training_recipients}, {"Presente", "Falta"})
        self.assertEqual(event_recipient["event"], "Festival Escolar")
        self.assertEqual(ranking_recipient["member_id"], ranking_member_id)
        for path in (member_path, training_path, event_path, ranking_path):
            self.assertTrue(path.exists())
            self.assertEqual(path.read_bytes()[:4], b"%PDF")

if __name__ == "__main__":
    unittest.main()
