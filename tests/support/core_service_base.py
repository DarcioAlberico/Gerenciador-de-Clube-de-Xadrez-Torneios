from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.core.services import (
    CertificateService,
    ClockIntegrationService,
    ClubService,
    DashboardService,
    EventService,
    ExerciseService,
    ExportService,
    FinanceService,
    GuardianService,
    ImportService,
    InternalRatingService,
    InventoryService,
    LearningLevelService,
    ListLayoutService,
    MemberService,
    NormAssistantService,
    OfficialRatingService,
    PairingService,
    PrizeService,
    QRResultService,
    SecurityService,
    SyncService,
    TeamService,
    TournamentService,
    TrainingService,
)


class CoreServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base_path = Path(self.temp_dir.name)
        self.backup_dir = base_path / "backups"
        self.db = Database(base_path / "albericus.db", backup_dir=self.backup_dir)
        self.service = PairingService(self.db)
        self.club_service = ClubService(self.db)
        self.clock_integration_service = ClockIntegrationService(self.db)
        self.dashboard_service = DashboardService(self.db)
        self.guardian_service = GuardianService(self.db)
        self.member_service = MemberService(self.db)
        self.learning_level_service = LearningLevelService(self.db)
        self.training_service = TrainingService(self.db)
        self.exercise_service = ExerciseService(self.db)
        self.tournament_service = TournamentService(self.db)
        self.team_service = TeamService(self.db)
        self.event_service = EventService(self.db)
        self.import_service = ImportService(self.db)
        self.official_rating_service = OfficialRatingService(self.db)
        self.internal_rating_service = InternalRatingService(self.db)
        self.inventory_service = InventoryService(self.db)
        self.security_service = SecurityService(self.db)
        self.sync_service = SyncService(self.db)
        self.qr_result_service = QRResultService(self.db, self.service)
        self.export_service = ExportService(self.db, self.service)
        self.certificate_service = CertificateService(self.db, self.service)
        self.finance_service = FinanceService(self.db)
        self.prize_service = PrizeService(self.db)
        self.norm_assistant_service = NormAssistantService(self.db)
        self.list_layout_service = ListLayoutService(self.db)
        self.tournament_id = self.db.create_tournament("Torneio teste", rounds_count=5)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_players(self, total: int) -> list[int]:
        player_ids = []
        for index in range(total):
            player_ids.append(
                self.db.create_player(
                    self.tournament_id,
                    name=f"Jogador {index + 1}",
                    rating=2000 - index * 50,
                    club="Clube",
                    category="Absoluto",
                )
            )
        return player_ids

    def _create_team_tournament(
        self,
        teams_count: int = 4,
        boards_count: int = 2,
    ) -> tuple[int, list[int]]:
        tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Torneio por equipes",
                "competition_type": "team",
                "rounds_count": "5",
                "bye_points": "1",
            }
        )
        self.tournament_service.save_profile(
            tournament_id,
            {
                "name": "Torneio por equipes",
                "competition_type": "team",
                "scope": "standalone",
                "rounds_count": "5",
                "bye_points": "1",
            },
            {
                "team_boards_count": str(boards_count),
                "team_match_win_points": "2",
                "team_match_draw_points": "1",
                "team_match_loss_points": "0",
                "team_pairing_method": "swiss",
                "team_standing_primary": "match_points",
                "team_standing_secondary": "game_points",
            },
            [],
        )
        team_ids = []
        for team_index in range(teams_count):
            team_id = self.team_service.create_team(
                tournament_id,
                {
                    "name": f"Equipe {team_index + 1}",
                    "club": f"Clube {team_index + 1}",
                    "captain": f"Capitao {team_index + 1}",
                },
            )
            team_ids.append(team_id)
            for board_number in range(1, boards_count + 1):
                player_id = self.db.create_player(
                    tournament_id,
                    name=f"Equipe {team_index + 1} Jogador {board_number}",
                    rating=2200 - team_index * 100 - board_number * 10,
                    club=f"Clube {team_index + 1}",
                )
                self.team_service.add_player(team_id, player_id, board_number=str(board_number), role="starter")
        return tournament_id, team_ids

    def _fill_decisive_results(self, round_id: int) -> None:
        for pairing in self.db.get_pairings_for_round(round_id):
            if not pairing["is_bye"]:
                self.db.update_pairing_result(pairing["id"], "1-0")

    def _create_member_win(self, rating: int = 1600) -> tuple[int, int]:
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Rating",
                "rating": str(rating),
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
        return member_id, member_player_id

    def _close_team_round_with_decisive_boards(self, tournament_id: int, round_id: int) -> None:
        for match in self.db.list_team_matches_for_round(int(round_id)):
            if match["is_bye"]:
                continue
            for board in self.db.list_team_boards(int(match["id"])):
                self.service.update_result(tournament_id, int(board["id"]), "1-0")
        self.service.close_round(tournament_id, int(round_id))

    def _enable_disable_bye(self) -> None:
        self.tournament_service.save_profile(
            self.tournament_id,
            {"name": "Torneio teste", "rounds_count": "5", "bye_points": "1"},
            {"initial_order": "rating", "tournament_type": "real", "disable_bye": 1},
            [],
        )

    def _set_individual_pairing_method(self, method: str) -> None:
        self.db.get_tournament_settings(self.tournament_id)  # garante a linha
        with self.db.connect() as connection:
            connection.execute(
                "UPDATE tournament_settings SET pairing_method = ? WHERE tournament_id = ?",
                (method, self.tournament_id),
            )

    def _phase_a_fixture(self) -> tuple[dict, list[dict], list[int]]:
        """Cenario deterministico de 4 jogadores e 3 rodadas.

        R1: 1>4, 2>3 ; R2: 1>2, 3>4 ; R3: 1=3, 2>4.
        Pontos finais: P1=2.5, P2=2.0, P3=1.5, P4=0.0.
        """
        ids = self._create_players(4)  # ratings 2000,1950,1900,1850
        tournament = self.db.get_tournament(self.tournament_id)
        closed = [
            {"white_player_id": ids[0], "black_player_id": ids[3], "result": "1-0", "is_bye": 0, "round_number": 1},
            {"white_player_id": ids[1], "black_player_id": ids[2], "result": "1-0", "is_bye": 0, "round_number": 1},
            {"white_player_id": ids[0], "black_player_id": ids[1], "result": "1-0", "is_bye": 0, "round_number": 2},
            {"white_player_id": ids[2], "black_player_id": ids[3], "result": "1-0", "is_bye": 0, "round_number": 2},
            {"white_player_id": ids[0], "black_player_id": ids[2], "result": "1/2-1/2", "is_bye": 0, "round_number": 3},
            {"white_player_id": ids[1], "black_player_id": ids[3], "result": "1-0", "is_bye": 0, "round_number": 3},
        ]
        return tournament, closed, ids

    @staticmethod
    def _fide_player(pid: int, rating: int, *, intl: int | None = None, birth: str = "") -> dict:
        return {
            "id": pid, "name": f"P{pid}", "surname": "", "given_name": "",
            "international_rating": rating if intl is None else intl,
            "national_rating": 0, "rating": rating, "birth_date": birth, "k_factor": None,
        }

    @staticmethod
    def _prize_standings() -> list[dict]:
        # P1 e P2 empatados em pontos (3.0) ocupam as posicoes 1-2.
        return [
            {"player_id": 1, "name": "P1", "position": 1, "points": 3.0, "category": "A"},
            {"player_id": 2, "name": "P2", "position": 2, "points": 3.0, "category": "B"},
            {"player_id": 3, "name": "P3", "position": 3, "points": 2.0, "category": "A"},
            {"player_id": 4, "name": "P4", "position": 4, "points": 1.0, "category": "B"},
        ]

    @staticmethod
    def _prize_rows() -> list[dict]:
        return [
            {"kind": "overall", "label": "1o", "rank_from": 1, "rank_to": 1, "amount": 1000},
            {"kind": "overall", "label": "2o", "rank_from": 2, "rank_to": 2, "amount": 600},
            {"kind": "overall", "label": "3o", "rank_from": 3, "rank_to": 3, "amount": 200},
            {"kind": "category", "label": "Cat A 1o", "category": "A", "rank_from": 1, "rank_to": 1, "amount": 300},
            {"kind": "category", "label": "Cat B 1o", "category": "B", "rank_from": 1, "rank_to": 1, "amount": 300},
        ]

    def _play_first_round(self, results: list[str]) -> None:
        round_data = self.service.generate_next_round(self.tournament_id)
        round_id = int(round_data["id"])
        pairings = self.db.get_pairings_for_round(round_id)
        for pairing, result in zip(pairings, results):
            self.service.update_result(self.tournament_id, int(pairing["id"]), result)
        self.service.close_round(self.tournament_id, round_id)
