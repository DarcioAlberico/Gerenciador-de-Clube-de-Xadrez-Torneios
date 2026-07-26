from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from tkinter import TclError, ttk
from unittest import mock

import customtkinter as ctk
import pytest

from src.core.database import Database
from src.core.services import AppError, TeamService, TournamentService
from src.ui.app import AlbericusApp
from src.ui.support import _classify_error
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)
from tests.support.ui_input import type_into

# Esta suite abre janela: precisa de display real. Ver o marcador 'gui'
# no pyproject — o gate sem display roda com -m 'not gui'.
pytestmark = pytest.mark.gui

class UiLayoutSmokeTest(unittest.TestCase):
    PAGES = [
        "show_club",
        "show_members",
        "show_learning_levels",
        "show_guardians",
        "show_training",
        "show_exercises",
        "show_inventory",
        "show_finance",
        "show_calendar",
        "show_internal_ranking",
        "show_tournaments",
        "show_tournament_dashboard",
        "show_arbitration_panel",
        "show_tournament_settings",
        "show_players",
        "show_teams",
        "show_pairings",
        "show_standings",
        "show_certificates",
        "show_app_settings",
        "show_reports",
        "show_export",
        "show_integrations",
    ]

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base_path = Path(self.temp_dir.name)
        self.db = Database(base_path / "albericus.db", backup_dir=base_path / "backups")
        self.tournament_id = TournamentService(self.db).create_tournament(
            {"name": "Smoke", "rounds_count": "3", "bye_points": "1"}
        )
        # O torneio-base entra em Modo Livre (marca dedicada), como faria o
        # fluxo 'Torneio | Modo Livre'. Testes de Modo Oficial desmarcam.
        self.db.set_free_mode(self.tournament_id, True)
        try:
            self.app = create_tk_window(lambda: AlbericusApp(db=self.db))
        except TclError as exc:
            self.temp_dir.cleanup()
            self.skipTest(f"Tk indisponivel para teste de layout: {exc}")
        self.app.current_tournament_id = self.tournament_id
        self.messages: list[str] = []
        self.app._show_info = self.messages.append
        self.app._show_toast = lambda msg, *a, **kw: self.messages.append(msg)
        self.app._show_error = self._raise_ui_error
        self.app._run_background = self._run_background_now
        
        self.app.security_service.login("admin", "admin")
        if hasattr(self.app, "login_frame"):
            self.app.login_frame.destroy()
            self.app._build_menu()
            self.app._build_statusbar()
            self.app._build_content()
            self.app.show_club()

    def tearDown(self) -> None:
        if hasattr(self, "app"):
            self._cancel_pending_callbacks()
            self.app.destroy()
            # customtkinter nao desregistra a janela dos seus trackers globais em
            # destroy(); sem isto cada AlbericusApp vaza e a suite acumula ate
            # estourar o tempo. Ver tests/support/ctk_cleanup.py.
            release_dead_ctk_windows()
        self.temp_dir.cleanup()

    def test_main_pages_keep_controls_inside_window_at_supported_sizes(self) -> None:
        for width, height in [(1360, 720), (1180, 640)]:
            with self.subTest(size=f"{width}x{height}"):
                self.app.geometry(f"{width}x{height}+0+0")
                self.app.update()
                for page in self.PAGES:
                    with self.subTest(page=page):
                        getattr(self.app, page)()
                        self.app.update()
                        offenders = self._widgets_past_right_edge()
                        self.assertEqual([], offenders)

    def test_free_tournament_mode_mostra_aviso_e_cancela(self) -> None:
        before_tournament = self.app.current_tournament_id
        before_count = len(self.db.list_tournaments())
        dialog = self.app.show_free_tournament_mode()
        self.app.update()
        try:
            self.assertIsInstance(dialog, ctk.CTkToplevel)
            labels = [
                str(widget.cget("text"))
                for widget in self._walk(dialog)
                if isinstance(widget, ctk.CTkLabel)
            ]
            self.assertTrue(any("Modo Livre Ativado" in label for label in labels))
            self.assertTrue(any("organizada onde o importante" in label for label in labels))
            button_texts = {
                widget.cget("text")
                for widget in self._walk(dialog)
                if isinstance(widget, ctk.CTkButton)
            }
            self.assertIn("Iniciar Modo Livre", button_texts)
            self.assertIn("Cancelar", button_texts)

            for widget in self._walk(dialog):
                if isinstance(widget, ctk.CTkButton) and widget.cget("text") == "Cancelar":
                    widget.invoke()
                    break
            self.app.update()
            self.assertFalse(dialog.winfo_exists())
            # Cancelar nao cria torneio nem mexe no torneio oficial em curso.
            self.assertEqual(self.app.current_tournament_id, before_tournament)
            self.assertEqual(len(self.db.list_tournaments()), before_count)
        finally:
            if dialog.winfo_exists():
                dialog.destroy()
                self.app.update()

    def test_free_tournament_mode_nao_mostrar_novamente_persiste_e_pula_o_aviso(self) -> None:
        dialog = self.app.show_free_tournament_mode()
        self.app.update()
        try:
            self.app.free_mode_hide_checkbox.select()
            for widget in self._walk(dialog):
                if isinstance(widget, ctk.CTkButton) and widget.cget("text") == "Cancelar":
                    widget.invoke()
                    break
            self.app.update()
        finally:
            if dialog.winfo_exists():
                dialog.destroy()
                self.app.update()

        # marcar no caminho "Cancelar" tambem tem de valer
        self.assertEqual("1", self.db.get_app_settings().get("free_mode_notice_hidden"))

        # e a partir dai o menu vai direto para a criacao (que ainda pede o nome)
        pedidos: list[str] = []
        self.app._ask_string = lambda *a, **kw: pedidos.append("nome") or None
        self.assertIsNone(self.app.show_free_tournament_mode())
        self.app.update()
        self.assertEqual(["nome"], pedidos, "deveria ir direto ao prompt de nome")

    def test_free_tournament_mode_sem_marcar_continua_mostrando_o_aviso(self) -> None:
        dialog = self.app.show_free_tournament_mode()
        self.app.update()
        for widget in self._walk(dialog):
            if isinstance(widget, ctk.CTkButton) and widget.cget("text") == "Cancelar":
                widget.invoke()
                break
        self.app.update()
        self.assertEqual("0", self.db.get_app_settings().get("free_mode_notice_hidden"))

        segundo = self.app.show_free_tournament_mode()
        self.app.update()
        try:
            self.assertIsInstance(segundo, ctk.CTkToplevel)
        finally:
            if segundo is not None and segundo.winfo_exists():
                segundo.destroy()
                self.app.update()

    def test_free_tournament_mode_iniciar_marca_modo_livre(self) -> None:
        self.app._ask_string = lambda *args, **kwargs: "Festival Escolar"
        before_ids = {tournament["id"] for tournament in self.db.list_tournaments()}
        dialog = self.app.show_free_tournament_mode()
        self.app.update()
        for widget in self._walk(dialog):
            if isinstance(widget, ctk.CTkButton) and widget.cget("text") == "Iniciar Modo Livre":
                widget.invoke()
                break
        else:
            self.fail("Botao 'Iniciar Modo Livre' nao encontrado")
        self.app.update()

        self.assertFalse(dialog.winfo_exists())
        novos = [
            tournament
            for tournament in self.db.list_tournaments()
            if tournament["id"] not in before_ids and tournament["name"] == "Festival Escolar"
        ]
        self.assertEqual(len(novos), 1)
        tournament_id = novos[0]["id"]
        self.assertEqual(self.app.current_tournament_id, tournament_id)
        # O torneio criado pelo Modo Livre recebe a marca dedicada free_mode,
        # que e o que habilita o modo (o perfil segue no default e nao decide).
        settings = self.db.get_tournament_settings(tournament_id)
        self.assertEqual((settings or {}).get("free_mode"), 1)
        self.assertTrue(self.app._is_free_mode(tournament_id))

    def _set_tournament_profile(self, tournament_id: int, profile: str) -> None:
        settings = self.db.get_tournament_settings(tournament_id) or {}
        settings["tournament_profile"] = profile
        self.db.save_tournament_settings(tournament_id, settings)

    def _set_free_mode(self, tournament_id: int, enabled: bool) -> None:
        self.db.set_free_mode(tournament_id, enabled)

    def test_is_free_mode_reflete_marca_dedicada(self) -> None:
        self.assertTrue(self.app._is_free_mode(self.tournament_id))  # marcado no setUp
        self._set_free_mode(self.tournament_id, False)
        self.assertFalse(self.app._is_free_mode(self.tournament_id))
        # o perfil 'free' (default de todo torneio) nao reativa o Modo Livre
        self._set_tournament_profile(self.tournament_id, "free")
        self.assertFalse(self.app._is_free_mode(self.tournament_id))

    def test_free_mode_repair_round_limpa_e_regera(self) -> None:
        self.assertTrue(self.app._is_free_mode(self.tournament_id))
        self.app.current_round_id = 777
        chamadas = {"delete": [], "generate": []}
        self.app.pairing_service.delete_generated_round = lambda rid: chamadas["delete"].append(rid)
        self.app.pairing_service.generate_next_round = lambda tid: chamadas["generate"].append(tid)
        self.app._load_round_options = lambda: None
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=True):
            self.app.free_mode_repair_round()
        self.assertEqual(chamadas["delete"], [777])
        self.assertEqual(chamadas["generate"], [self.tournament_id])

    def test_free_mode_repair_round_bloqueia_fora_do_modo_livre(self) -> None:
        self._set_free_mode(self.tournament_id, False)
        self.app.current_round_id = 123
        chamadas = []
        self.app.pairing_service.delete_generated_round = lambda rid: chamadas.append(rid)
        erros: list[str] = []
        self.app._show_error = lambda exc: erros.append(str(exc))
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=True):
            self.app.free_mode_repair_round()
        self.assertEqual(chamadas, [])  # fora do Modo Livre nao dispara re-pair
        self.assertTrue(any("Modo Livre" in erro for erro in erros))

    def test_late_entry_sem_rodadas_encerradas_usa_padrao(self) -> None:
        with mock.patch("src.ui.components.dialogs.tri_state_dialog") as pergunta:
            proceed, points = self.app.free_mode_late_entry_starting_points(self.tournament_id)
        self.assertTrue(proceed)
        self.assertIsNone(points)
        pergunta.assert_not_called()

    def test_late_entry_meio_ponto_por_rodada_ausente(self) -> None:
        self.app.db.list_rounds = lambda _tid: [{"status": "closed"}, {"status": "closed"}]
        with mock.patch(
            "src.ui.components.dialogs.tri_state_dialog", return_value=True
        ):
            proceed, points = self.app.free_mode_late_entry_starting_points(self.tournament_id)
        self.assertTrue(proceed)
        self.assertEqual(points, 1.0)  # 0,5 x 2 rodadas encerradas

    def test_late_entry_zero_por_rodada_ausente(self) -> None:
        self.app.db.list_rounds = lambda _tid: [{"status": "closed"}, {"status": "open"}]
        with mock.patch(
            "src.ui.components.dialogs.tri_state_dialog", return_value=False
        ):
            proceed, points = self.app.free_mode_late_entry_starting_points(self.tournament_id)
        self.assertTrue(proceed)
        self.assertEqual(points, 0.0)

    def test_late_entry_cancelar_aborta_adicao(self) -> None:
        self.app.db.list_rounds = lambda _tid: [{"status": "closed"}]
        with mock.patch(
            "src.ui.components.dialogs.tri_state_dialog", return_value=None
        ):
            proceed, points = self.app.free_mode_late_entry_starting_points(self.tournament_id)
        self.assertFalse(proceed)
        self.assertIsNone(points)

    def test_late_entry_fora_do_modo_livre_nao_pergunta(self) -> None:
        self._set_free_mode(self.tournament_id, False)
        self.app.db.list_rounds = lambda _tid: [{"status": "closed"}]
        with mock.patch("src.ui.components.dialogs.tri_state_dialog") as pergunta:
            proceed, points = self.app.free_mode_late_entry_starting_points(self.tournament_id)
        self.assertTrue(proceed)
        self.assertIsNone(points)
        pergunta.assert_not_called()

    def test_create_player_persiste_starting_points_explicito(self) -> None:
        player_id = self.db.create_player(self.tournament_id, name="Tardio", starting_points=1.5)
        player = self.db.get_player(player_id)
        self.assertEqual(player["starting_points"], 1.5)

    def test_prepare_late_entry_modo_livre_delega_meio_ponto(self) -> None:
        self.app.db.list_rounds = lambda _tid: [{"status": "closed"}, {"status": "closed"}]
        with mock.patch(
            "src.ui.components.dialogs.tri_state_dialog", return_value=True
        ):
            proceed, points = self.app.prepare_late_entry(self.tournament_id)
        self.assertTrue(proceed)
        self.assertEqual(points, 1.0)

    def test_prepare_late_entry_oficial_avisa_e_confirma(self) -> None:
        self._set_free_mode(self.tournament_id, False)
        self.app.db.list_rounds = lambda _tid: [{"status": "closed"}, {"status": "closed"}]
        with mock.patch(
            "src.ui.components.dialogs.confirm_dialog", return_value=True
        ) as aviso:
            proceed, points = self.app.prepare_late_entry(self.tournament_id)
        self.assertTrue(proceed)
        self.assertIsNone(points)  # modo oficial mantem o calculo padrao de pontos
        aviso.assert_called_once()

    def test_prepare_late_entry_oficial_cancela_adicao(self) -> None:
        self._set_free_mode(self.tournament_id, False)
        self.app.db.list_rounds = lambda _tid: [{"status": "closed"}, {"status": "closed"}]
        with mock.patch(
            "src.ui.components.dialogs.confirm_dialog", return_value=False
        ):
            proceed, points = self.app.prepare_late_entry(self.tournament_id)
        self.assertFalse(proceed)
        self.assertIsNone(points)

    def test_prepare_late_entry_oficial_sem_2_rodadas_nao_avisa(self) -> None:
        self._set_free_mode(self.tournament_id, False)
        self.app.db.list_rounds = lambda _tid: [{"status": "closed"}]
        with mock.patch("src.ui.components.dialogs.confirm_dialog") as aviso:
            proceed, points = self.app.prepare_late_entry(self.tournament_id)
        self.assertTrue(proceed)
        self.assertIsNone(points)
        aviso.assert_not_called()

    def test_set_current_tournament_indica_modo_no_rotulo(self) -> None:
        self.app._set_current_tournament(self.tournament_id)
        self.assertIn("Modo Livre", self.app.tournament_label.cget("text"))
        self._set_free_mode(self.tournament_id, False)
        self.app._set_current_tournament(self.tournament_id)
        self.assertIn("Modo Oficial", self.app.tournament_label.cget("text"))

    def test_member_and_tournament_can_be_created_from_ui_forms(self) -> None:
        self.app.show_members()
        self.app.update()
        self._set_entry_after_label("Nome", "Ana")
        self._set_entry_after_label("Sobrenome", "Silva")
        self._set_entry_after_label("Rating", "1720")
        self._set_entry_after_label("Categoria", "Sub-18")
        self._click_button("Adicionar")
        self.app.update()

        members = self.db.list_members(active_only=False)
        self.assertTrue(any(member["name"] == "Ana" and member["surname"] == "Silva" for member in members))

        self.app.show_tournaments()
        self.app.update()
        self._set_entry_after_label("Nome do torneio", "Aberto UI")
        self._set_entry_after_label("Data inicial", "13/05/2026")
        self._set_entry_after_label("Data final", "14/05/2026")
        self._set_entry_after_label("Rodadas", "2")
        self._set_entry_after_label("Pontos do bye", "1")
        self._click_button("Criar torneio")
        self.app.update()

        current = self.db.get_tournament(self.app.current_tournament_id)
        self.assertIsNotNone(current)
        self.assertEqual(current["name"], "Aberto UI")
        self.assertEqual(current["rounds_count"], 2)
        self.assertEqual(current["start_date"], "2026-05-13")
        self.assertEqual(current["end_date"], "2026-05-14")

    def test_players_csv_import_flow_runs_from_ui(self) -> None:
        csv_path = Path(self.temp_dir.name) / "jogadores.csv"
        csv_path.write_text(
            "name,rating,club,category\n"
            "Carla,1810,Clube A,ABS\n"
            "Diego,1760,Clube B,ABS\n",
            encoding="utf-8",
        )

        self.app.show_players()
        self.app.update()
        with mock.patch("src.ui.screens.tournaments.filedialog.askopenfilename", return_value=str(csv_path)):
            self._click_button("Importar CSV/Excel")
        self.app.update()

        players = self.db.list_players(self.tournament_id, active_only=False)
        self.assertCountEqual([player["name"] for player in players], ["Carla", "Diego"])
        self.assertTrue(any("2 jogadores importados" in message for message in self.messages))
        self.assertTrue(
            any(
                isinstance(widget, ctk.CTkLabel)
                and widget.cget("text") == "Total: 2 | Visiveis: 2 | Presentes: 2 | Ausentes: 0 | Membros: 0 | Convidados: 2"
                for widget in self._walk(self.app.content)
            )
        )

    def test_players_official_rating_update_opens_preview_before_applying(self) -> None:
        player_id = self.db.create_player(
            self.tournament_id,
            name="Nome antigo",
            rating=1500,
            fide_id="222",
        )
        official_csv = Path(self.temp_dir.name) / "fide_preview.csv"
        official_csv.write_text(
            "name,fide,title,fide_rating\n"
            "Nome oficial,222,FM,1810\n",
            encoding="utf-8",
        )
        self.app.official_rating_service.import_official_csv(official_csv, "FIDE", "2026-05")

        self.app.show_players()
        self.app.update()
        self._click_button("Comparar ratings oficiais")
        self.app.update()

        dialogs = [
            widget
            for widget in self.app.winfo_children()
            if isinstance(widget, ctk.CTkToplevel)
        ]
        self.assertEqual(len(dialogs), 1)
        dialog = dialogs[0]
        labels = [
            str(widget.cget("text"))
            for widget in self._walk(dialog)
            if isinstance(widget, ctk.CTkLabel)
        ]
        self.assertTrue(any("Alteracoes: 1" in label for label in labels))
        self.assertTrue(any("Selecionadas para aplicar: 1" in label for label in labels))
        self.assertEqual(self.db.get_player(player_id)["name"], "Nome antigo")

        for widget in self._walk(dialog):
            if isinstance(widget, ctk.CTkButton) and widget.cget("text") == "Cancelar":
                widget.invoke()
                break
        else:
            self.fail("Botao Cancelar nao encontrado")
        self.app.update()

        self.assertEqual(self.db.get_player(player_id)["name"], "Nome antigo")

    def test_players_official_rating_preview_applies_only_selected_rows(self) -> None:
        first_player_id = self.db.create_player(
            self.tournament_id,
            name="Primeiro antigo",
            rating=1500,
            fide_id="101",
        )
        second_player_id = self.db.create_player(
            self.tournament_id,
            name="Segundo antigo",
            rating=1400,
            fide_id="202",
        )
        official_csv = Path(self.temp_dir.name) / "fide_selected.csv"
        official_csv.write_text(
            "name,fide,fide_rating\n"
            "Primeiro oficial,101,1800\n"
            "Segundo oficial,202,1700\n",
            encoding="utf-8",
        )
        self.app.official_rating_service.import_official_csv(official_csv, "FIDE", "2026-05")

        self.app.show_players()
        self.app.update()
        self._click_button("Comparar ratings oficiais")
        self.app.update()
        dialog = next(
            widget
            for widget in self.app.winfo_children()
            if isinstance(widget, ctk.CTkToplevel)
        )
        comparison_tree = next(
            widget
            for widget in self._walk(dialog)
            if isinstance(widget, ttk.Treeview)
        )
        rows = comparison_tree.get_children()
        self.assertEqual("extended", str(comparison_tree.cget("selectmode")))
        self.assertEqual(2, len(comparison_tree.selection()))
        comparison_tree.selection_set(rows[0])
        comparison_tree.event_generate("<<TreeviewSelect>>")
        self.app.update()

        for widget in self._walk(dialog):
            if isinstance(widget, ctk.CTkButton) and widget.cget("text") == "Confirmar alteracoes":
                widget.invoke()
                break
        else:
            self.fail("Botao Confirmar alteracoes nao encontrado")
        self.app.update()

        self.assertEqual(self.db.get_player(first_player_id)["name"], "Primeiro oficial")
        self.assertEqual(self.db.get_player(second_player_id)["name"], "Segundo antigo")

    def test_team_screen_creates_team_and_assigns_player(self) -> None:
        team_tournament_id = TournamentService(self.db).create_tournament(
            {
                "name": "Equipes UI",
                "competition_type": "team",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )
        self.app.current_tournament_id = team_tournament_id
        self.db.create_player(team_tournament_id, name="Primeiro Titular", rating=1800, club="Clube A")
        self.db.create_player(team_tournament_id, name="Segundo Titular", rating=1700, club="Clube A")

        self.app.show_teams()
        self.app.update()
        self._set_entry_after_label("Nome da equipe", "Equipe A")
        self._set_entry_after_label("Clube/Cidade", "Clube A")
        self._set_entry_after_label("Capitao", "Capitao A")
        self._click_button("Criar equipe")
        self.app.update()
        self._set_entry_after_label("Tabuleiro", "1")
        self._click_button("Adicionar jogador")
        self.app.update()

        teams = self.db.list_teams(team_tournament_id)
        self.assertEqual(len(teams), 1)
        self.assertEqual(teams[0]["name"], "Equipe A")
        roster = self.db.list_team_players(int(teams[0]["id"]))
        self.assertEqual(len(roster), 1)
        self.assertEqual(roster[0]["board_number"], 1)
        self.assertEqual(roster[0]["role"], "starter")

    def test_team_settings_can_be_saved_from_ui(self) -> None:
        team_tournament_id = TournamentService(self.db).create_tournament(
            {
                "name": "Equipes Regras UI",
                "competition_type": "team",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )
        self.app.current_tournament_id = team_tournament_id

        self.app.show_tournament_settings()
        self.app.update()
        self._set_entry_after_label("Tabuleiros por equipe", "5")
        self._set_entry_after_label("Pontos por vitoria da equipe", "3")
        self._set_entry_after_label("Pontos por empate da equipe", "1")
        self._set_entry_after_label("Pontos por derrota da equipe", "0")
        self._set_entry_after_label("Taxa rating FIDE por inscrito", "2,50")
        self._set_entry_after_label("Taxa rating CBX por inscrito", "3")
        self._set_entry_after_label("Taxa rating LBX por inscrito", "1,25")
        self._click_button("Salvar")
        self.app.update()

        settings = self.db.get_tournament_settings(team_tournament_id)
        self.assertEqual(settings["team_boards_count"], 5)
        self.assertEqual(settings["team_match_win_points"], 3.0)
        self.assertEqual(settings["team_standing_primary"], "match_points")
        self.assertEqual(settings["team_standing_secondary"], "game_points")
        self.assertEqual(settings["rating_fee_fide"], 2.5)
        self.assertEqual(settings["rating_fee_cbx"], 3.0)
        self.assertEqual(settings["rating_fee_lbx"], 1.25)

    def test_pairing_screen_shows_surname_first(self) -> None:
        self.db.create_player(
            self.tournament_id,
            name="Lucas",
            surname="Lima",
            given_name="Lucas",
            rating=1800,
        )
        self.db.create_player(
            self.tournament_id,
            name="Rafael",
            surname="Cruz",
            given_name="Rafael",
            rating=1700,
        )
        self.app.pairing_service.generate_next_round(self.tournament_id)

        self.app.show_pairings()
        self.app.update()

        row_values = [
            value
            for row_id in self.app.pairing_tree.get_children()
            for value in self.app.pairing_tree.item(row_id, "values")
        ]
        self.assertIn("Lima, Lucas", row_values)
        self.assertIn("Cruz, Rafael", row_values)

    def test_projector_mode_loads_and_renders_pairings(self) -> None:
        self.db.create_player(
            self.tournament_id,
            name="Lucas",
            surname="Lima",
            given_name="Lucas",
            rating=1800,
        )
        self.db.create_player(
            self.tournament_id,
            name="Rafael",
            surname="Cruz",
            given_name="Rafael",
            rating=1700,
        )
        self.app.pairing_service.generate_next_round(self.tournament_id)

        self.app.show_pairings()
        self.app.update()

        # Call projector mode
        self.app._open_projector_mode()
        self.app.update()

        dialogs = [
            widget
            for widget in self.app.winfo_children()
            if isinstance(widget, ctk.CTkToplevel)
        ]
        self.assertEqual(len(dialogs), 1)
        dialog = dialogs[0]

        # Check if players are rendered in projector window
        labels = [
            str(widget.cget("text"))
            for widget in self._walk(dialog)
            if isinstance(widget, ctk.CTkLabel)
        ]
        self.assertTrue(any("Lima, Lucas" in label for label in labels))
        self.assertTrue(any("Cruz, Rafael" in label for label in labels))

        # Close the dialog
        dialog.destroy()
        self.app.update()

    def test_team_pairing_screen_generates_team_round(self) -> None:
        tournament_service = TournamentService(self.db)
        team_service = TeamService(self.db)
        tournament_id = tournament_service.create_tournament(
            {
                "name": "Equipes Rodada UI",
                "competition_type": "team",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )
        tournament_service.save_profile(
            tournament_id,
            {
                "name": "Equipes Rodada UI",
                "competition_type": "team",
                "scope": "standalone",
                "rounds_count": "3",
                "bye_points": "1",
            },
            {
                "team_boards_count": "2",
                "team_match_win_points": "2",
                "team_match_draw_points": "1",
                "team_match_loss_points": "0",
                "team_pairing_method": "swiss",
                "team_standing_primary": "match_points",
                "team_standing_secondary": "game_points",
            },
            [],
        )
        for team_index in range(2):
            team_id = team_service.create_team(tournament_id, {"name": f"Equipe {team_index + 1}"})
            for board_number in range(1, 3):
                player_id = self.db.create_player(
                    tournament_id,
                    name=f"E{team_index + 1} J{board_number}",
                    rating=1800 - team_index * 100 - board_number,
                )
                team_service.add_player(team_id, player_id, board_number=str(board_number), role="starter")

        self.app.current_tournament_id = tournament_id
        self.app.show_pairings()
        self.app.update()
        self._click_button("Gerar proxima rodada")
        self.app.update()

        row_values = [
            value
            for row_id in self.app.pairing_tree.get_children()
            for value in self.app.pairing_tree.item(row_id, "values")
        ]
        self.assertIn("Equipe 1", row_values)
        self.assertIn("Equipe 2", row_values)
        self.assertIn("E1 J1", row_values)
        self.assertIn("E2 J2", row_values)

        first_board_row = self.app.pairing_tree.get_children()[0]
        self.app.pairing_tree.selection_set(first_board_row)
        self.app._on_pairing_select()
        self.app.result_option.set("1-0")
        self._click_button("Salvar resultado")
        self.app.update()

        match = self.db.list_team_matches_for_round(self.app.current_round_id)[0]
        board = self.db.list_team_boards(int(match["id"]))[0]
        self.assertEqual(board["result"], "1-0")

        second_board_row = self.app.pairing_tree.get_children()[1]
        self.app.pairing_tree.selection_set(second_board_row)
        self.app._on_pairing_select()
        self.app.result_option.set("0-1")
        self._click_button("Salvar resultado")
        self._invoke_menu_item("Fechar rodada")
        self.app.update()

        updated_match = self.db.list_team_matches_for_round(self.app.current_round_id)[0]
        self.assertEqual(updated_match["result"], "1-0")
        self.assertEqual(updated_match["white_game_points"], 2.0)
        self.assertIn("Rodada fechada.", self.messages)

        self.app.show_standings()
        self.app.update()
        standing_rows = [
            self.app.standings_tree.item(row_id, "values")
            for row_id in self.app.standings_tree.get_children()
        ]
        self.assertEqual(standing_rows[0][1], updated_match["white_team_name"])
        self.assertEqual(float(standing_rows[0][4]), 2.0)
        self.assertEqual(float(standing_rows[0][5]), 2.0)
        first_standing_row = self.app.standings_tree.get_children()[0]
        self.app.standings_tree.selection_set(first_standing_row)
        self._click_button("Detalhar tabuleiros")
        self.assertIn("Tabuleiro 1", self.messages[-1])
        output_path = Path(self.temp_dir.name) / "tabela_cruzada_equipes.html"
        with mock.patch("src.ui.screens.pairings.filedialog.asksaveasfilename", return_value=str(output_path)):
            self._click_button("Exportar tabela cruzada")
        self.assertIn("Tabela cruzada por equipes", output_path.read_text(encoding="utf-8"))

    def test_pairing_result_close_and_export_flow_runs_from_ui(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")

        self.app.show_pairings()
        self.app.update()
        self._click_button("Gerar proxima rodada")
        self.app.update()

        first_pairing_row = self.app.pairing_tree.get_children()[0]
        self.app.pairing_tree.selection_set(first_pairing_row)
        self.app._on_pairing_select()
        self.app.result_option.set("1-0")
        self._click_button("Salvar resultado")
        self._invoke_menu_item("Fechar rodada")
        self.app.update()

        rounds = self.db.list_rounds(self.tournament_id)
        self.assertEqual(rounds[0]["status"], "closed")
        self.assertIn("Rodada fechada.", self.messages)

        output_path = Path(self.temp_dir.name) / "exports" / "completo.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.app.show_export()
        self.app.update()
        with mock.patch("src.ui.screens.settings.filedialog.asksaveasfilename", return_value=str(output_path)):
            self._click_button("Gerar arquivo")
        self.app.update()

        self.assertTrue(output_path.exists())
        self.assertIn("Smoke", output_path.read_text(encoding="utf-8-sig"))

    def test_bye_edit_warning_and_restore_in_ui(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Daniel", rating=1600, club="Clube", category="ABS")

        self.app.show_pairings()
        self.app.update()
        self._click_button("Gerar proxima rodada")
        self.app.update()

        # The round has 2 boards: Board 1 (Bruno x Carlos), Board 2 (Daniel x BYE)
        bye_row = self.app.pairing_tree.get_children()[1]
        self.app.pairing_tree.selection_set(bye_row)
        self.app._on_pairing_select()

        # Try to change result to "1-0"
        self.app.result_option.set("1-0")

        # 1. Test "cancel" choice (should abort edit and restore OptionMenu to "BYE")
        with mock.patch.object(self.app, "_prompt_bye_edit_warning", return_value="cancel") as mock_prompt:
            self._click_button("Salvar resultado")
            self.app.update()
            mock_prompt.assert_called_once_with("BYE", "1-0")

        # Result should still be "BYE" in database
        pairings = self.db.get_pairings_for_round(self.app.current_round_id)
        self.assertEqual(pairings[1]["result"], "BYE")
        self.assertEqual(self.app.result_option.get(), "BYE")

        # 2. Test "restore" choice (should keep result as "BYE")
        self.app.result_option.set("1-0")
        with mock.patch.object(self.app, "_prompt_bye_edit_warning", return_value="restore") as mock_prompt:
            self._click_button("Salvar resultado")
            self.app.update()
            mock_prompt.assert_called_once_with("BYE", "1-0")

        pairings = self.db.get_pairings_for_round(self.app.current_round_id)
        self.assertEqual(pairings[1]["result"], "BYE")
        bye_row_new = self.app.pairing_tree.get_children()[1]
        self.app.pairing_tree.selection_set(bye_row_new)
        self.app._on_pairing_select()
        self.assertEqual(self.app.result_option.get(), "BYE")

        # 3. Test "edit" choice (should actually save the new result "1-0")
        self.app.result_option.set("1-0")
        with mock.patch.object(self.app, "_prompt_bye_edit_warning", return_value="edit") as mock_prompt:
            self._click_button("Salvar resultado")
            self.app.update()
            mock_prompt.assert_called_once_with("BYE", "1-0")

        pairings = self.db.get_pairings_for_round(self.app.current_round_id)
        self.assertEqual(pairings[1]["result"], "1-0")
        bye_row_new2 = self.app.pairing_tree.get_children()[1]
        self.app.pairing_tree.selection_set(bye_row_new2)
        self.app._on_pairing_select()
        self.assertEqual(self.app.result_option.get(), "1-0")

    def test_pairing_preview_does_not_create_round_from_ui(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")

        self.app.show_pairings()
        self.app.update()
        self._click_button("Pre-visualizar rodada")
        self.app.update()

        self.assertEqual([], self.db.list_rounds(self.tournament_id))
        self.assertIn("Previa da rodada 1", self.messages[-1])
        self.assertIn("nao gravou rodada", self.messages[-1])

    def test_export_center_generates_rating_fee_report_xlsx(self) -> None:
        self.db.save_tournament_settings(
            self.tournament_id,
            {"rating_fee_fide": "2.5"},
        )
        self.db.create_player(
            self.tournament_id,
            name="Jogador FIDE",
            fide_id="1234",
            international_rating=1800,
        )
        output_path = Path(self.temp_dir.name) / "taxas_rating.xlsx"

        self.app.show_export()
        self.app.update()
        report_option = next(
            widget
            for widget in self._walk(self.app.content)
            if isinstance(widget, ctk.CTkOptionMenu) and "Taxas de rating" in widget.cget("values")
        )
        report_option.set("Taxas de rating")
        report_option._command("Taxas de rating")
        format_option = next(
            widget
            for widget in self._walk(self.app.content)
            if isinstance(widget, ctk.CTkOptionMenu) and list(widget.cget("values")) == ["xlsx", "pdf"]
        )
        self.assertEqual("xlsx", format_option.get())
        with mock.patch("src.ui.screens.settings.filedialog.asksaveasfilename", return_value=str(output_path)):
            self._click_button("Gerar arquivo")
        self.app.update()

        self.assertTrue(output_path.exists())
        self.assertIn("Arquivo exportado", self.messages[-1])

    def test_standings_tiebreak_explanation_button_shows_components(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        round_data = self.app.pairing_service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.app.pairing_service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.app.pairing_service.close_round(self.tournament_id, int(round_data["id"]))

        self.app.show_standings()
        self.app.update()
        first_row = self.app.standings_tree.get_children()[0]
        self.app.standings_tree.selection_set(first_row)
        self._click_button("Explicar desempate")

        self.assertIn("Buchholz", self.messages[-1])

    def test_arbitration_panel_shows_pending_metrics_and_actions(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        self.app.pairing_service.generate_next_round(self.tournament_id)

        self.app.show_arbitration_panel()
        self.app.update()

        self._label("Painel do arbitro")
        self._label("Pendentes")
        self._label("1")
        self._label("Tempo rodada")
        self._label("Mesas aguardando resultado")
        self._label("Exibindo 1 de 1")
        self._click_button("Lancar 1 resultado(s) pendente(s)")
        self.app.update()
        self._label("Rodadas e resultados")
        self.app.show_arbitration_panel()
        self.app.update()
        self._click_button("Central de pendencias")
        self.app.update()
        self._label("Central de pendencias")
        self._label("Total")
        with self.assertRaisesRegex(AssertionError, "Selecione uma pendencia"):
            self._click_button("Detalhes")
        self._click_button("Voltar ao painel")
        self.app.update()
        self._label("Painel do arbitro")
        self._click_button("Abrir rodadas")
        self.app.update()
        self._label("Rodadas e resultados")

    def test_arbitration_panel_inline_result_saves_and_selects_next_pending_table(self) -> None:
        for index in range(4):
            self.db.create_player(
                self.tournament_id,
                name=f"Jogador {index + 1}",
                rating=1800 - index * 10,
                club="Clube",
                category="ABS",
            )
        round_data = self.app.pairing_service.generate_next_round(self.tournament_id)

        self.app.show_arbitration_panel()
        self.app.update()
        first_tree = self.app.arbitration_pending_tree
        self.assertEqual("1", first_tree.item(first_tree.selection()[0], "values")[0])

        self.assertEqual("break", self.app._save_arbitration_panel_result("1-0"))
        self.app.update()

        pairings = self.db.get_pairings_for_round(int(round_data["id"]))
        self.assertEqual("1-0", pairings[0]["result"])
        second_tree = self.app.arbitration_pending_tree
        self.assertEqual("2", second_tree.item(second_tree.selection()[0], "values")[0])
        self.assertEqual("break", self.app._save_arbitration_panel_result("0-1"))
        self.app.update()
        self.assertEqual("0-1", self.db.get_pairings_for_round(int(round_data["id"]))[1]["result"])
        self._label("Nenhuma mesa aguardando resultado.")

    def test_arbitration_panel_searches_table_before_inline_result(self) -> None:
        for index in range(4):
            self.db.create_player(
                self.tournament_id,
                name=f"Jogador {index + 1}",
                rating=1800 - index * 10,
                club="Clube",
                category="ABS",
            )
        round_data = self.app.pairing_service.generate_next_round(self.tournament_id)

        self.app.show_arbitration_panel()
        self.app.update()
        self.app.arbitration_pending_query_entry.insert(0, "2")
        self._click_button("Buscar mesa")
        self.app.update()

        filtered_tree = self.app.arbitration_pending_tree
        self.assertEqual("2", filtered_tree.item(filtered_tree.selection()[0], "values")[0])
        self.assertEqual("break", self.app._save_arbitration_panel_result("1-0"))
        self.app.update()
        self.assertEqual("1-0", self.db.get_pairings_for_round(int(round_data["id"]))[1]["result"])
        self._label("Nenhuma mesa aguardando resultado.")

    def test_arbitration_panel_preferences_persist_and_reload_with_safe_defaults(self) -> None:
        self.app._toggle_arbitration_auto_refresh()
        self.app._set_arbitration_refresh_interval("60")
        with mock.patch.object(self.app, "show_arbitration_panel") as show_panel:
            self.app._set_arbitration_inline_tables_limit("40")
        show_panel.assert_called_once_with()

        settings = self.db.get_app_settings()
        self.assertEqual("0", settings["arbitration_auto_refresh_enabled"])
        self.assertEqual("60", settings["arbitration_refresh_interval_seconds"])
        self.assertEqual("40", settings["arbitration_inline_tables_limit"])

        self.app._arbitration_auto_refresh_enabled = True
        self.app._arbitration_refresh_interval_seconds = 15
        self.app._arbitration_inline_tables_limit = 20
        self.app._apply_app_settings()
        self.assertFalse(self.app._arbitration_auto_refresh_enabled)
        self.assertEqual(60, self.app._arbitration_refresh_interval_seconds)
        self.assertEqual(40, self.app._arbitration_inline_tables_limit)

        self.db.save_app_settings(
            {
                "arbitration_refresh_interval_seconds": "9",
                "arbitration_inline_tables_limit": "51",
            }
        )
        self.app._apply_app_settings()
        self.assertEqual(15, self.app._arbitration_refresh_interval_seconds)
        self.assertEqual(20, self.app._arbitration_inline_tables_limit)

    def test_arbitration_panel_inline_result_respects_closed_round_block(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        round_data = self.app.pairing_service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]

        self.app.show_arbitration_panel()
        self.app.update()
        self.db.close_round(int(round_data["id"]))

        with self.assertRaisesRegex(AssertionError, "rodada fechada"):
            self.app._save_arbitration_panel_result("1-0")

        self.assertEqual("", self.db.get_pairing(int(pairing["id"]))["result"])

    def test_arbitration_issues_can_approve_qr_submission(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        round_data = self.app.pairing_service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        token_payload = self.app.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]))
        self.app.qr_result_service.submit_result(token_payload["token"], "1-0", submitter="Mesa 1")

        self.app.show_arbitration_issues()
        self.app.update()
        tree = self._first_tree()
        first_row = tree.get_children()[0]
        tree.selection_set(first_row)
        self._click_button("Aprovar QR")

        self.assertEqual("1-0", self.db.get_pairing(int(pairing["id"]))["result"])
        self.assertIn("Resultado QR aprovado", self.messages[-1])

    def test_arbitration_issues_can_reject_qr_submission(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        round_data = self.app.pairing_service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        token_payload = self.app.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]))
        submission = self.app.qr_result_service.submit_result(token_payload["token"], "0-1", submitter="Mesa 1")

        self.app.show_arbitration_issues()
        self.app.update()
        tree = self._first_tree()
        first_row = tree.get_children()[0]
        tree.selection_set(first_row)
        self._click_button("Rejeitar QR")

        self.assertEqual("", self.db.get_pairing(int(pairing["id"]))["result"])
        self.assertEqual("rejected", self.db.get_result_submission(int(submission["id"]))["status"])
        self.assertIn("Resultado QR rejeitado", self.messages[-1])
        refreshed_tree = self._first_tree()
        self.assertEqual(0, len(refreshed_tree.get_children()))

    def test_arbitration_issues_can_acknowledge_clock_issue(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        round_data = self.app.pairing_service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.app.clock_integration_service.record_manual_event(
            self.tournament_id,
            "flag_fall",
            pairing_id=int(pairing["id"]),
            side="white",
            seconds_remaining=0,
            note="Conferido pelo arbitro.",
        )

        self.app.show_arbitration_issues()
        self.app.update()
        tree = self._first_tree()
        first_row = tree.get_children()[0]
        tree.selection_set(first_row)
        self._click_button("Marcar ciencia")

        self.assertIn("Pendencia marcada como ciente", self.messages[-1])
        refreshed_tree = self._first_tree()
        self.assertEqual(0, len(refreshed_tree.get_children()))

    def test_arbitration_issues_filter_and_search_locate_table_without_mutation(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        round_data = self.app.pairing_service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        token_payload = self.app.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]))
        self.app.qr_result_service.submit_result(token_payload["token"], "1-0", submitter="Mesa 1")
        self.app.clock_integration_service.record_manual_event(
            self.tournament_id,
            "flag_fall",
            pairing_id=int(pairing["id"]),
            side="white",
            seconds_remaining=0,
            note="Conferir mesa 1.",
        )

        self.app.show_arbitration_issues()
        self.app.update()
        tree = self.app.arbitration_issues_tree
        self.assertEqual(2, len(tree.get_children()))
        self.assertEqual("Exibindo 2 de 2", self.app.arbitration_issue_count_label.cget("text"))

        self.app.arbitration_issue_filter_option.set("QR")
        self.app.arbitration_issue_filter_option._command("QR")
        self.app.update()
        self.assertEqual(1, len(tree.get_children()))
        self.assertEqual("Exibindo 1 de 2", self.app.arbitration_issue_count_label.cget("text"))

        self.app.arbitration_issue_filter_option.set("Todas")
        self.app.arbitration_issue_filter_option._command("Todas")
        self.app.update()
        self.assertEqual(2, len(tree.get_children()))

        # A busca e adiada (B-4): a tecla so agenda, quem executa e o flush.
        # O termo abaixo nao casa com nada — antes, a asercao era "mesa 1", que
        # devolvia as MESMAS 2 linhas e por isso nao provava filtro nenhum.
        # type_into porque digitar num CTkEntry tem tres armadilhas silenciosas
        # (ver tests/support/ui_input.py). A asercao antiga deste teste
        # ("mesa 1" -> 2 linhas) media a tabela NAO filtrada e chamava aquilo de
        # busca: o evento nunca chegava ao bind.
        type_into(self.app.arbitration_issue_search_entry, "termo-que-nao-existe")
        self.assertTrue(
            self.app.arbitration_issue_search_debounced.is_pending,
            "digitar agenda o refiltro em vez de rodar a cada tecla",
        )

        self.app.arbitration_issue_search_debounced.flush()
        self.app.update()
        self.assertEqual(0, len(tree.get_children()))
        self.assertEqual("Exibindo 0 de 2", self.app.arbitration_issue_count_label.cget("text"))
        # Filtrar e ler: a base continua com as duas ocorrencias.
        self.assertEqual(2, self.app.pairing_service.arbitration_issues(self.tournament_id)["metrics"]["total"])

    def test_pairing_screen_shows_result_states_for_qr_and_correction(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        round_data = self.app.pairing_service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        token_payload = self.app.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]))
        submission = self.app.qr_result_service.submit_result(token_payload["token"], "1-0", submitter="Mesa 1")

        self.app.show_pairings()
        self.app.update()
        self.assertIn("submetido QR", self._pairing_row_values())

        self.app.qr_result_service.approve_submission(int(submission["id"]), reviewer="Arbitro")
        self.app.show_pairings()
        self.app.update()
        self.assertIn("aprovado QR", self._pairing_row_values())

        self.app.pairing_service.close_round(self.tournament_id, int(round_data["id"]))
        settings = self.db.get_tournament_settings(self.tournament_id) or {}
        settings["allow_dangerous_changes"] = 1
        self.db.save_tournament_settings(self.tournament_id, settings)
        self.app.pairing_service.update_result(self.tournament_id, int(pairing["id"]), "0-1")
        self.app.show_pairings()
        self.app.update()
        self.assertIn("corrigido", self._pairing_row_values())

    def test_pairing_screen_shows_rejected_qr_state(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        round_data = self.app.pairing_service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        token_payload = self.app.qr_result_service.result_url_for_pairing(self.tournament_id, int(pairing["id"]))
        submission = self.app.qr_result_service.submit_result(token_payload["token"], "0-1", submitter="Mesa 1")
        self.app.qr_result_service.reject_submission(int(submission["id"]), reviewer="Arbitro")

        self.app.show_pairings()
        self.app.update()

        self.assertIn("rejeitado QR", self._pairing_row_values())

    def test_pairing_screen_exports_scoresheets_pdf(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        self.app.pairing_service.generate_next_round(self.tournament_id)
        output_path = Path(self.temp_dir.name) / "sumulas.pdf"

        self.app.show_pairings()
        self.app.update()
        with mock.patch("src.ui.screens.pairings.filedialog.asksaveasfilename", return_value=str(output_path)):
            self._invoke_menu_item("Exportar sumulas")

        self.assertEqual(output_path.read_bytes()[:4], b"%PDF")
        self.assertIn("Sumulas exportadas", self.messages[-1])

    def test_pairing_screen_exports_wall_pdf(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        self.app.pairing_service.generate_next_round(self.tournament_id)
        output_path = Path(self.temp_dir.name) / "mural.pdf"

        self.app.show_pairings()
        self.app.update()
        with mock.patch("src.ui.screens.pairings.filedialog.asksaveasfilename", return_value=str(output_path)):
            self._invoke_menu_item("Exportar rodada")

        from pypdf import PdfReader

        text = "\n".join(page.extract_text() or "" for page in PdfReader(output_path).pages)
        self.assertEqual(output_path.read_bytes()[:4], b"%PDF")
        self.assertIn("Rodada aberta - QR para envio de resultado", text)
        self.assertIn("Rodada exportada", self.messages[-1])

    def test_pairing_screen_exports_table_cards_pdf(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        self.app.pairing_service.generate_next_round(self.tournament_id)
        output_path = Path(self.temp_dir.name) / "cartoes.pdf"

        self.app.show_pairings()
        self.app.update()
        with (
            mock.patch.object(self.app, "_ask_string", return_value="1-4"),
            mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=False),
            mock.patch("src.ui.screens.pairings.filedialog.asksaveasfilename", return_value=str(output_path)),
        ):
            self._invoke_menu_item("Exportar cartoes de mesa")

        from pypdf import PdfReader

        text = "\n".join(page.extract_text() or "" for page in PdfReader(output_path).pages)
        self.assertEqual(1, len(PdfReader(output_path).pages))
        self.assertIn("MESA", text)
        self.assertIn("Cartoes de mesa exportados", self.messages[-1])

    def test_standings_screen_exports_crosstable_html(self) -> None:
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Carlos", rating=1700, club="Clube", category="ABS")
        round_data = self.app.pairing_service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(int(round_data["id"]))[0]
        self.app.pairing_service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.app.pairing_service.close_round(self.tournament_id, int(round_data["id"]))
        output_path = Path(self.temp_dir.name) / "tabela_cruzada.html"

        self.app.show_standings()
        self.app.update()
        with mock.patch("src.ui.screens.pairings.filedialog.asksaveasfilename", return_value=str(output_path)):
            self._click_button("Exportar tabela cruzada")

        html_content = output_path.read_text(encoding="utf-8")
        self.assertIn("Tabela cruzada", html_content)
        self.assertIn("Bruno", html_content)
        self.assertIn("Tabela cruzada exportada", self.messages[-1])

    def test_pairing_screen_result_shortcuts_save_and_advance_selection(self) -> None:
        for index in range(4):
            self.db.create_player(
                self.tournament_id,
                name=f"Jogador {index + 1}",
                rating=1800 - index * 20,
                club="Clube",
                category="ABS",
            )

        self.app.show_pairings()
        self.app.update()
        self._click_button("Gerar proxima rodada")
        self.app.update()

        rows = list(self.app.pairing_tree.get_children())
        self.assertEqual(2, len(rows))
        self.app.pairing_tree.selection_set(rows[0])

        self.assertEqual("break", self.app._quick_save_result_from_screen("1-0"))
        self.app.update()
        self.assertEqual(self.app.pairing_tree.selection()[0], self.app.pairing_tree.get_children()[1])

        self.assertEqual("break", self.app._quick_save_result_from_screen("0-1"))
        self.app.update()

        pairings = self.db.get_pairings_for_round(self.app.current_round_id)
        results_by_board = {pairing["board_number"]: pairing["result"] for pairing in pairings}
        self.assertEqual({1: "1-0", 2: "0-1"}, results_by_board)

    def test_initial_call_summary_updates_when_marking_absent(self) -> None:
        for index in range(3):
            self.db.create_player(
                self.tournament_id,
                name=f"Aluno {index + 1}",
                rating=1500 - index * 10,
                club="Escola",
                category="Sub-12",
            )

        self.app.show_pairings()
        self.app.update()
        self.assertEqual(
            "Presentes: 3 | Ausentes: 0 | Total: 3",
            self.app.initial_call_summary_label.cget("text"),
        )

        first_row = self.app.initial_players_tree.get_children()[0]
        self.app.initial_players_tree.selection_set(first_row)
        self._click_button("Ausente")
        self.app.update()

        self.assertEqual(
            "Presentes: 2 | Ausentes: 1 | Total: 3",
            self.app.initial_call_summary_label.cget("text"),
        )
        first_row_after_absence = self.app.initial_players_tree.get_children()[0]
        self.assertIn("Aluno 1", self.app.initial_players_tree.item(first_row_after_absence, "values"))

    def test_initial_call_can_filter_players_for_fast_check_in(self) -> None:
        for name in ["Ana Escola", "Bruno Clube", "Carla Clube"]:
            self.db.create_player(self.tournament_id, name=name, rating=1500, club="Clube")

        self.app.show_pairings()
        self.app.update()
        self.app.initial_player_search_entry.insert(0, "Bruno")
        self.app._load_initial_players()
        self.app.update()

        rows = self.app.initial_players_tree.get_children()
        self.assertEqual(1, len(rows))
        self.assertIn("Bruno Clube", self.app.initial_players_tree.item(rows[0], "values"))

    def test_generate_round_warns_when_configured_rounds_are_below_recommendation(self) -> None:
        for index in range(9):
            self.db.create_player(
                self.tournament_id,
                name=f"Jogador {index + 1}",
                rating=1800 - index * 10,
                club="Clube",
                category="ABS",
            )

        self.app.show_pairings()
        self.app.update()
        with mock.patch("src.ui.components.dialogs.tri_state_dialog", return_value=True) as confirm:
            self._click_button("Gerar proxima rodada")
        self.app.update()

        self.assertEqual(1, len(self.db.list_rounds(self.tournament_id)))
        confirm.assert_called_once()
        self.assertIn("mínimo recomendado é 4 rodadas", confirm.call_args.args[2])

    def test_generate_round_warning_can_open_tournament_settings(self) -> None:
        for index in range(9):
            self.db.create_player(
                self.tournament_id,
                name=f"Jogador {index + 1}",
                rating=1800 - index * 10,
                club="Clube",
                category="ABS",
            )

        self.app.show_pairings()
        self.app.update()
        with mock.patch("src.ui.components.dialogs.tri_state_dialog", return_value=False):
            self._click_button("Gerar proxima rodada")
        self.app.update()

        self.assertEqual([], self.db.list_rounds(self.tournament_id))
        self._label("Configuração do torneio")

    def test_pairing_write_handlers_require_tournament_permission(self) -> None:
        self.db.create_player(self.tournament_id, name="Jogador A", rating=1800, club="Clube", category="ABS")
        self.db.create_player(self.tournament_id, name="Jogador B", rating=1700, club="Clube", category="ABS")
        self.app.security_service._current_user = {
            "id": "2",
            "username": "consulta",
            "role": "viewer",
        }

        self.app.show_pairings()
        self.app.update()
        with self.assertRaisesRegex(AssertionError, "Permissão negada"):
            self.app._generate_round()

        self.assertEqual([], self.db.list_rounds(self.tournament_id))

    def test_print_document_opens_file_when_direct_print_command_is_unavailable(self) -> None:
        pdf_path = Path(self.temp_dir.name) / "documento.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n")

        with (
            mock.patch("src.ui.support.sys.platform", "linux"),
            mock.patch("src.ui.support.shutil.which", return_value=None),
            mock.patch("src.ui.support.webbrowser.open") as browser_open,
        ):
            self.app._print_document(pdf_path)

        browser_open.assert_called_once_with(pdf_path.resolve().as_uri())
        self.assertIn("documento foi aberto", self.messages[-1])

    def test_remover_bye_solicitado_oferece_desfazer_que_restaura(self) -> None:
        player_id = self.db.create_player(self.tournament_id, name="Bye Undo", rating=1500)
        self.db.add_requested_bye(self.tournament_id, player_id, 1, "H", reason="viagem")

        self.app.show_requested_byes()
        self.app.update()
        tree = self._first_treeview()
        linhas = tree.get_children()
        self.assertEqual(1, len(linhas), "o bye cadastrado deveria aparecer na lista")
        tree.selection_set(linhas[0])

        acoes = self._capture_toast_actions()
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=True):
            self._click_button("Remover selecionado")
        self.app.update()

        self.assertEqual([], self.db.list_requested_byes(self.tournament_id))
        self.assertTrue(acoes and acoes[-1] is not None, "exclusao deveria oferecer Desfazer")
        rotulo, desfazer = acoes[-1]
        self.assertEqual("Desfazer", rotulo)

        desfazer()
        restaurados = self.db.list_requested_byes(self.tournament_id)
        self.assertEqual(1, len(restaurados))
        self.assertEqual(player_id, restaurados[0]["player_id"])
        self.assertEqual("H", restaurados[0]["bye_type"])
        self.assertEqual("viagem", restaurados[0]["reason"], "o motivo tem de voltar junto")
        self.assertEqual(1, restaurados[0]["round_number"])

    def test_troca_de_tema_preserva_tela_selecao_scroll_e_foco(self) -> None:
        """Aceite da F1.2: aplicar tema nao pode reconstruir a UI (P0-6)."""
        for indice in range(12):
            self.db.create_player(self.tournament_id, name=f"Jogador {indice:02d}", rating=1500 + indice)
        self.app.show_players()
        self.app.update()

        tree = self._first_treeview()
        linhas = tree.get_children()
        self.assertGreaterEqual(len(linhas), 6, "precisa de linhas para testar selecao/scroll")
        alvo = linhas[4]
        tree.selection_set(alvo)
        tree.yview_moveto(0.5)
        self.app.update()
        scroll_antes = tree.yview()[0]

        entrada = next(w for w in self._walk(self.app.content) if isinstance(w, ctk.CTkEntry))
        entrada.insert(0, "rascunho")
        self.app.focus_force()
        entrada.focus_set()
        self.app.update()

        identidade_tree = id(tree)
        identidade_content = id(self.app.content)
        foco_antes = self.app.focus_get()
        # O formulario reage a selecao da tabela, entao o texto e lido aqui, ja
        # depois disso: o que importa e ele atravessar a troca de tema intacto.
        texto_antes = entrada.get()

        self.db.save_app_settings({"accent_preset": "emerald", "frame_bg_preset": "carbon"})
        self.app._rebuild_ui_after_theme_change()
        self.app.update()

        self.assertEqual("show_players", self.app.navigator.current, "a tela nao pode trocar")
        self.assertEqual(identidade_content, id(self.app.content), "content nao pode ser recriado")
        self.assertEqual(identidade_tree, id(self._first_treeview()), "a tabela nao pode ser recriada")
        self.assertEqual((alvo,), self._first_treeview().selection(), "a selecao tem de sobreviver")
        self.assertAlmostEqual(
            scroll_antes, self._first_treeview().yview()[0], places=2,
            msg="o scroll tem de ficar onde estava",
        )
        self.assertEqual(texto_antes, entrada.get(), "o que estava no campo nao pode sumir")
        self.assertIs(foco_antes, self.app.focus_get(), "o foco tem de continuar no mesmo campo")

    def test_home_lista_pendencias_do_torneio_com_deep_link(self) -> None:
        self.db.create_player(self.tournament_id, name="Ana", rating=1900)
        self.db.create_player(self.tournament_id, name="Bruno", rating=1800)
        self.app.pairing_service.generate_next_round(self.tournament_id)

        self.app.show_home()
        self.app.update()
        rotulos = [
            str(w.cget("text"))
            for w in self._walk(self.app.content)
            if isinstance(w, ctk.CTkLabel)
        ]
        self.assertTrue(
            any("resultado" in texto and "lancar" in texto for texto in rotulos),
            f"esperava pendencia de resultado; veio {rotulos}",
        )

        # o botao da pendencia leva para a tela onde ela se resolve
        self._click_button("Lancar")
        self.app.update()
        self.assertEqual("show_pairings", self.app.navigator.current)

    def test_home_sem_pendencia_mostra_tudo_em_dia(self) -> None:
        self.app.current_tournament_id = None
        self.app._home_snapshot = lambda: __import__(
            "src.ui.home", fromlist=["HomeSnapshot"]
        ).HomeSnapshot(has_tournament=True, rounds_count=1, generated_rounds=1, closed_rounds=0)
        self.app.show_home()
        self.app.update()
        rotulos = [
            str(w.cget("text"))
            for w in self._walk(self.app.content)
            if isinstance(w, ctk.CTkLabel)
        ]
        self.assertTrue(any("Tudo em dia" in texto for texto in rotulos), rotulos)

    def test_home_e_a_tela_de_entrada_registrada(self) -> None:
        """A entrada pos-login deixou de ser o cadastro do clube (P1-8).

        Aqui so o registro: que o login REALMENTE abre nela e verificado por
        comportamento em test_ui_login.test_login_valido_entra_e_abre_a_tela_inicial
        — inspecionar o codigo-fonte do login quebrava a cada refatoracao dele.
        """
        from src.ui.navigation import find

        destino = find("home")
        self.assertIsNotNone(destino)
        self.assertEqual("show_home", destino.method)
        self.assertTrue(hasattr(self.app, "show_home"))

    def test_kpi_card_clicavel_realca_no_hover(self) -> None:
        from src.ui.support import THEME_ACCENT, THEME_PANEL_BG

        card = self.app._kpi_card(self.app.content, "Torneios", 3, command=lambda: None)
        card.grid(row=9, column=0)  # content e gerenciado por grid
        self.app.update()
        self.assertEqual(1, card.cget("border_width"), "borda constante evita deslocar o layout")
        self.assertEqual(THEME_PANEL_BG, card.cget("border_color"))

        # when="now" despacha na hora. Um update() aqui processaria tambem os
        # eventos reais de mouse — o ponteiro nao esta sobre o card durante o
        # teste, e um <Leave> verdadeiro desfaria o realce antes da asercao.
        alvo = self._hover_target(card)
        alvo.event_generate("<Enter>", when="now")
        self.assertEqual(THEME_ACCENT, card.cget("border_color"))

        # Sair do canvas para um rotulo do proprio card ainda e "dentro": o
        # realce nao pode piscar na travessia. Quem esta sob o ponteiro vem de
        # winfo_containing, que depende do empilhamento real de janelas — aqui
        # ele e forcado, para o teste nao depender do gerenciador de janelas.
        rotulo = next(w for w in self._walk(card) if isinstance(w, ctk.CTkLabel))
        card.winfo_containing = lambda _x, _y: rotulo
        alvo.event_generate("<Leave>", when="now")
        self.assertEqual(THEME_ACCENT, card.cget("border_color"))

        # ponteiro fora do card: o realce sai
        card.winfo_containing = lambda _x, _y: None
        alvo.event_generate("<Leave>", when="now")
        self.assertEqual(THEME_PANEL_BG, card.cget("border_color"))

    def test_kpi_card_sem_command_nao_ganha_borda(self) -> None:
        card = self.app._kpi_card(self.app.content, "Somente leitura", 7)
        card.grid(row=9, column=0)
        self.app.update()
        self.assertEqual(0, card.cget("border_width"))

    def test_tabela_grande_continua_rapida_de_preencher(self) -> None:
        """B-4/P2-13: o guarda que diz QUANDO a tabela vira problema.

        O achado da tarefa foi que ela ainda nao e: com 6.000 jogadores, encher
        a Treeview custou 42 ms de 677 ms de tela (6%) — o resto e a montagem
        dos widgets do formulario, que nao depende do numero de linhas. Este
        teste existe para a afirmacao nao envelhecer sozinha: se um dia
        preencher 5.000 linhas passar do orcamento, ele reprova e a
        virtualizacao volta a pauta com numero, nao com suposicao.

        Orcamento folgado de proposito (10x o medido): o que se guarda aqui e a
        ORDEM DE GRANDEZA, e a maquina do CI nao e a do desenvolvedor.
        """
        import time

        colunas = ("id", "nome", "rating", "clube", "categoria")
        tree = ttk.Treeview(self.app, columns=colunas, show="headings", height=20)
        for coluna in colunas:
            tree.column(coluna, width=120)
        linhas = [(i, f"Jogador {i}", 1500 + i % 400, "Clube", "ABS") for i in range(5000)]

        inicio = time.perf_counter()
        for linha in linhas:
            tree.insert("", "end", values=linha)
        decorrido_ms = (time.perf_counter() - inicio) * 1000
        try:
            self.assertEqual(5000, len(tree.get_children()))
            self.assertLess(
                decorrido_ms,
                2000,
                f"encher 5.000 linhas levou {decorrido_ms:.0f} ms — a tabela virou "
                "o gargalo e a virtualizacao (P2-13) deixou de ser dispensavel",
            )
        finally:
            tree.destroy()

    def _arrastar_separador(self, tree: ttk.Treeview, coluna: str, largura: int) -> None:
        """Simula o fim de um arrasto no separador da coluna.

        O ttk nao expoe "coluna redimensionada": quem observa e o proprio
        _make_tree, no par ButtonPress (estava no separador?) / ButtonRelease.
        identify_region depende de coordenada real dentro do cabecalho, que num
        teste headless nao e confiavel — entao ela e forcada, e o que se testa e
        a reacao, nao a leitura do mouse.
        """
        tree.column(coluna, width=largura)
        original = tree.identify_region
        tree.identify_region = lambda _x, _y: "separator"  # type: ignore[method-assign]
        try:
            tree.event_generate("<ButtonPress-1>", x=5, y=5, when="now")
            tree.event_generate("<ButtonRelease-1>", x=5, y=5, when="now")
        finally:
            tree.identify_region = original  # type: ignore[method-assign]

    def test_largura_de_coluna_arrastada_volta_na_proxima_visita(self) -> None:
        """B-1/P2-9: o arrasto fica guardado por usuario e sobrevive a navegacao."""
        self.app.show_members()
        self.app.update()
        tree = next(w for w in self._walk(self.app.content) if isinstance(w, ttk.Treeview))
        coluna = tree["columns"][1]
        padrao = int(tree.column(coluna, "width"))

        self._arrastar_separador(tree, coluna, padrao + 90)

        self.app.show_club()
        self.app.update()
        self.app.show_members()
        self.app.update()
        tree2 = next(w for w in self._walk(self.app.content) if isinstance(w, ttk.Treeview))
        self.assertEqual(padrao + 90, int(tree2.column(coluna, "width")))

    def test_largura_de_coluna_e_por_usuario(self) -> None:
        self.app.show_members()
        self.app.update()
        tree = next(w for w in self._walk(self.app.content) if isinstance(w, ttk.Treeview))
        coluna = tree["columns"][1]
        padrao = int(tree.column(coluna, "width"))
        self._arrastar_separador(tree, coluna, padrao + 90)

        # Outro operador na mesma maquina abre a mesma tela.
        self.app.security_service._current_user = {"id": "999", "username": "outro", "role": "arbiter"}
        self.app.show_members()
        self.app.update()
        outra = next(w for w in self._walk(self.app.content) if isinstance(w, ttk.Treeview))
        self.assertEqual(padrao, int(outra.column(coluna, "width")))

    def test_restaurar_largura_padrao_limpa_o_que_foi_arrastado(self) -> None:
        self.app.show_members()
        self.app.update()
        tree = next(w for w in self._walk(self.app.content) if isinstance(w, ttk.Treeview))
        coluna = tree["columns"][1]
        padrao = int(tree.column(coluna, "width"))
        self._arrastar_separador(tree, coluna, padrao + 90)

        self.app._reset_column_widths()

        self.app.show_members()
        self.app.update()
        tree2 = next(w for w in self._walk(self.app.content) if isinstance(w, ttk.Treeview))
        self.assertEqual(padrao, int(tree2.column(coluna, "width")))
        self.assertIn("padrão restaurada", self.messages[-1])

    def test_clique_fora_do_separador_nao_guarda_largura(self) -> None:
        """Selecionar uma linha nao pode ser confundido com redimensionar."""
        self.app.show_members()
        self.app.update()
        tree = next(w for w in self._walk(self.app.content) if isinstance(w, ttk.Treeview))
        coluna = tree["columns"][1]
        tree.column(coluna, width=int(tree.column(coluna, "width")) + 70)
        tree.identify_region = lambda _x, _y: "cell"  # type: ignore[method-assign]
        tree.event_generate("<ButtonPress-1>", x=5, y=30, when="now")
        tree.event_generate("<ButtonRelease-1>", x=5, y=30, when="now")

        usuario = self.app.security_service.current_user_id()
        chave = self.app.column_layout_service.key_for(
            list(tree["columns"]), {c: tree.heading(c, "text") for c in tree["columns"]}
        )
        self.assertEqual("", self.db.get_column_layout(usuario, chave))

    def _dashboard_fixo(self, total: int = 10, ativos: int = 8) -> dict:
        return {
            "summary": {"total_members": total, "active_members": ativos},
            "defaulters_count": 0,
            "finance_summary": {"paid_amount": 100, "pending_amount": 0, "late_amount": 0},
            "active_announcements": [],
            "upcoming_events": [],
        }

    def test_dashboard_visual_reaproveita_a_figura_na_segunda_visita(self) -> None:
        """B-5/P2-14: sem mudanca de dado, a segunda visita nao remonta nada.

        O que este teste garante e o que o teste puro NAO alcanca: que a figura
        cacheada sobrevive a **troca de canvas**. Cada visita destroi o conteudo
        e cria um FigureCanvasTkAgg novo em cima da mesma figura — se isso nao
        funcionasse, o cache seria uma otimizacao que quebra a tela.
        """
        from src.ui.screens.dashboard import DASHBOARD_FIGURES

        self.app.dashboard_service.overview = lambda: self._dashboard_fixo()
        DASHBOARD_FIGURES.clear()
        DASHBOARD_FIGURES.reset_stats()

        self.app.show_visual_dashboard()
        self.app.update()
        self.assertEqual((0, 2), (DASHBOARD_FIGURES.hits, DASHBOARD_FIGURES.misses))

        self.app.show_visual_dashboard()
        self.app.update()
        self.assertEqual((2, 2), (DASHBOARD_FIGURES.hits, DASHBOARD_FIGURES.misses))

        # A tela continua de pe: os dois graficos desenhados, nao um frame vazio.
        telas = [w for w in self._walk(self.app.content) if w.winfo_class() == "Canvas"]
        self.assertGreaterEqual(len(telas), 2)

    def test_dashboard_visual_remonta_quando_o_numero_muda(self) -> None:
        from src.ui.screens.dashboard import DASHBOARD_FIGURES

        self.app.dashboard_service.overview = lambda: self._dashboard_fixo()
        DASHBOARD_FIGURES.clear()
        DASHBOARD_FIGURES.reset_stats()
        self.app.show_visual_dashboard()
        self.app.update()

        self.app.dashboard_service.overview = lambda: self._dashboard_fixo(total=11, ativos=9)
        self.app.show_visual_dashboard()
        self.app.update()

        # O financeiro nao mudou (acerto); a pizza de membros sim (nova montagem).
        self.assertEqual(1, DASHBOARD_FIGURES.hits)
        self.assertEqual(3, DASHBOARD_FIGURES.misses)

    def test_exclusao_em_cascata_nao_oferece_desfazer(self) -> None:
        """ESPEC §5.1: cascata fica só com confirmação explícita, sem undo."""
        acoes = self._capture_toast_actions()
        chamadas: list[str] = []
        self.app._delete_with_undo(
            lambda: chamadas.append("delete"),
            None,
            "Torneio excluido.",
            lambda: chamadas.append("refresh"),
        )
        self.assertEqual(["delete", "refresh"], chamadas)
        self.assertEqual([None], acoes, "sem restore, o toast nao pode ter acao")

    def test_error_dialogs_separate_expected_file_and_unexpected_errors(self) -> None:
        # mensagem pronta (str) e tratada como recuperavel -> vira toast, nao modal
        title, message, is_unexpected = _classify_error("Nome e obrigatorio.", "ERR-0")
        self.assertEqual("Erro", title)
        self.assertEqual("Nome e obrigatorio.", message)
        self.assertFalse(is_unexpected)

        title, message, is_unexpected = _classify_error(
            AppError("Informe o nome do jogador."),
            "ERR-1",
        )
        self.assertEqual("Erro", title)
        self.assertEqual("Informe o nome do jogador.", message)
        self.assertFalse(is_unexpected)

        title, message, is_unexpected = _classify_error(
            PermissionError(13, "Acesso negado", "torneio.csv"),
            "ERR-2",
        )
        self.assertEqual("Erro de permissao", title)
        self.assertIn("Sem permissao", message)
        self.assertIn("torneio.csv", message)
        self.assertFalse(is_unexpected)

        title, message, is_unexpected = _classify_error(
            RuntimeError("detalhe interno sensivel"),
            "ERR-3",
        )
        self.assertEqual("Erro inesperado", title)
        self.assertIn("ERR-3", message)
        self.assertIn("app.log", message)
        self.assertNotIn("detalhe interno sensivel", message)
        self.assertTrue(is_unexpected)

    def _widgets_past_right_edge(self) -> list[str]:
        root_left = self.app.winfo_rootx()
        root_right = root_left + self.app.winfo_width()
        offenders = []
        for widget in self._walk(self.app):
            if not isinstance(widget, (ctk.CTkButton, ctk.CTkOptionMenu, ctk.CTkEntry, ttk.Entry)):
                continue
            if not widget.winfo_ismapped():
                continue
            right = widget.winfo_rootx() + widget.winfo_width()
            if right > root_right - 2:
                offenders.append(f"{widget.winfo_class()}:{right - root_right}px")
        return offenders

    def _cancel_pending_callbacks(self) -> None:
        cancel_pending_callbacks(self.app)

    @staticmethod
    def _raise_ui_error(error: Exception) -> None:
        raise AssertionError(str(error)) from error

    @staticmethod
    def _run_background_now(work, on_success=None, busy_message: str = "", busy_widget=None) -> None:
        result = work()
        if on_success:
            on_success(result)

    def _set_entry_after_label(self, label_text: str, value: str) -> None:
        label = self._label(label_text)
        label_grid = label.grid_info()
        target_row = int(label_grid["row"]) + 1
        target_column = int(label_grid["column"])
        for widget in label.master.winfo_children():
            if not isinstance(widget, (ctk.CTkEntry, ttk.Entry, ctk.CTkOptionMenu)):
                continue
            grid = widget.grid_info()
            if int(grid.get("row", -1)) == target_row and int(grid.get("column", -1)) == target_column:
                if isinstance(widget, ctk.CTkOptionMenu):
                    widget.set(value)
                else:
                    widget.delete(0, "end")
                    widget.insert(0, value)
                return
        self.fail(f"Entrada nao encontrada para o campo {label_text!r}")

    def _click_button(self, text: str) -> None:
        for widget in reversed(list(self._walk(self.app.content))):
            if isinstance(widget, ctk.CTkButton) and widget.cget("text") == text:
                widget.invoke()
                return
        self.fail(f"Botao {text!r} nao encontrado")

    @staticmethod
    def _hover_target(widget: object) -> object:
        """Onde o evento de mouse realmente chega num widget CTk.

        ``CTkFrame.bind()`` encaminha para o canvas interno, e ``winfo_children()``
        do CTkFrame **esconde** esse canvas — daí a busca pelo caminho Tk cru.
        Um evento sintético no frame não dispararia o binding.
        """
        caminhos = widget.tk.splitlist(widget.tk.call("winfo", "children", str(widget)))
        for caminho in caminhos:
            child = widget.nametowidget(caminho)
            if type(child).__name__ == "CTkCanvas":
                return child
        return widget

    def _first_treeview(self) -> ttk.Treeview:
        for widget in self._walk(self.app.content):
            if isinstance(widget, ttk.Treeview):
                return widget
        self.fail("Nenhuma Treeview na tela atual")

    def _capture_toast_actions(self) -> list:
        """Substitui o stub de toast por um que guarda a acao (ex.: Desfazer)."""
        acoes: list = []

        def fake_toast(message, *args, action=None, **kwargs) -> None:
            self.messages.append(message)
            acoes.append(action)

        self.app._show_toast = fake_toast
        return acoes

    def _invoke_menu_item(self, label: str) -> None:
        """Aciona um item recolhido em um menu_button (ex.: 'Exportar'/'Mais') pelo
        rotulo, invocando o mesmo comando que o tk.Menu dispararia no clique."""
        for widget in reversed(list(self._walk(self.app.content))):
            for item in getattr(widget, "_menu_items", None) or ():
                if item and item[0] == label and item[1] is not None:
                    item[1]()
                    return
        self.fail(f"Item de menu {label!r} nao encontrado")

    def _first_tree(self) -> ttk.Treeview:
        for widget in self._walk(self.app.content):
            if isinstance(widget, ttk.Treeview):
                return widget
        self.fail("Tabela nao encontrada")

    def _pairing_row_values(self) -> list[str]:
        return [
            str(value)
            for row_id in self.app.pairing_tree.get_children()
            for value in self.app.pairing_tree.item(row_id, "values")
        ]

    def _label(self, text: str) -> ctk.CTkLabel:
        for widget in self._walk(self.app.content):
            if isinstance(widget, ctk.CTkLabel) and widget.cget("text") == text:
                return widget
        self.fail(f"Rotulo {text!r} nao encontrado")

    @classmethod
    def _walk(cls, widget: object):
        yield widget
        for child in widget.winfo_children():
            yield from cls._walk(child)
