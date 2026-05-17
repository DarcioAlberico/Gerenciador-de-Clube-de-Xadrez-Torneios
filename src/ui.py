from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .ui_admin import AdminPagesMixin
from .ui_club import ClubPagesMixin
from .ui_dashboard import DashboardPagesMixin
from .ui_pairings import PairingPagesMixin
from .ui_referees import RefereePagesMixin
from .ui_settings import SettingsPagesMixin
from .ui_support import *
from .ui_tournaments import TournamentPagesMixin


class AlbericusApp(
    ClubPagesMixin,
    DashboardPagesMixin,
    AdminPagesMixin,
    RefereePagesMixin,
    TournamentPagesMixin,
    PairingPagesMixin,
    SettingsPagesMixin,
    ctk.CTk,
):
    def __init__(self, db: Database | None = None) -> None:
        super().__init__()
        configure_logging()
        logger.info("Aplicativo iniciado")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("Albericus - Emparceiramento de Xadrez")
        self.geometry("1180x760")
        self.minsize(980, 640)

        self.db = db or Database()
        self._apply_app_settings()
        self._set_window_icon()
        self.dashboard_service = DashboardService(self.db)
        self.referee_service = RefereeService(self.db)
        self.club_service = ClubService(self.db)
        self.guardian_service = GuardianService(self.db)
        self.tournament_service = TournamentService(self.db)
        self.team_service = TeamService(self.db)
        self.member_service = MemberService(self.db)
        self.learning_level_service = LearningLevelService(self.db)
        self.training_service = TrainingService(self.db)
        self.exercise_service = ExerciseService(self.db)
        self.finance_service = FinanceService(self.db)
        self.event_service = EventService(self.db)
        self.inventory_service = InventoryService(self.db)
        self.security_service = SecurityService(self.db)
        self.pairing_service = PairingService(self.db)
        self.import_service = ImportService(self.db)
        self.official_rating_service = OfficialRatingService(self.db)
        self.internal_rating_service = InternalRatingService(self.db)
        self.export_service = ExportService(self.db, self.pairing_service)
        self.certificate_service = CertificateService(self.db, self.pairing_service)

        self.current_tournament_id: int | None = None
        self.current_round_id: int | None = None
        self.round_option_map: dict[str, int] = {}
        self.pairing_row_map: dict[str, int] = {}
        self.pairing_detail_map: dict[str, dict[str, Any]] = {}

        self._configure_grid()
        self._configure_tree_style()
        self._build_menu()
        self._build_statusbar()
        self._build_content()
        self.show_club()

    def _configure_grid(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

    def _configure_tree_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Treeview",
            rowheight=28,
            font=("Segoe UI", 10),
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
        )
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # 1. Clube
        club_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Clube", menu=club_menu)
        club_menu.add_command(label="Dashboard Visual", command=self.show_visual_dashboard)
        club_menu.add_command(label="Perfil do Clube", command=self.show_club)
        club_menu.add_command(label="Membros", command=self.show_members)
        club_menu.add_command(label="Níveis", command=self.show_learning_levels)
        club_menu.add_command(label="Responsáveis", command=self.show_guardians)

        # 2. Treinamento
        training_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Treinamento", menu=training_menu)
        training_menu.add_command(label="Aulas", command=self.show_training)
        training_menu.add_command(label="Exercícios", command=self.show_exercises)

        # 3. Gestão
        mgmt_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Gestão", menu=mgmt_menu)
        mgmt_menu.add_command(label="Árbitros", command=self.show_referees)
        mgmt_menu.add_command(label="Inventário", command=self.show_inventory)
        mgmt_menu.add_command(label="Financeiro", command=self.show_finance)
        mgmt_menu.add_command(label="Calendário", command=self.show_calendar)
        mgmt_menu.add_command(label="Ranking Interno", command=self.show_internal_ranking)

        # 4. Torneio
        tourn_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Torneio", menu=tourn_menu)
        tourn_menu.add_command(label="Torneios", command=self.show_tournaments)
        tourn_menu.add_command(label="Config. Torneio", command=self.show_tournament_settings)
        tourn_menu.add_separator()
        tourn_menu.add_command(label="Jogadores", command=self.show_players)
        tourn_menu.add_command(label="Equipes", command=self.show_teams)
        tourn_menu.add_command(label="Rodadas", command=self.show_pairings)
        tourn_menu.add_command(label="Classificação", command=self.show_standings)
        tourn_menu.add_command(label="Diplomas", command=self.show_certificates)

        # 5. Ferramentas
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ferramentas", menu=tools_menu)
        tools_menu.add_command(label="Exportar", command=self.show_export)
        tools_menu.add_command(label="Relatórios", command=self.show_reports)

        # 6. Configurações
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configurações", menu=settings_menu)
        settings_menu.add_command(label="Config. App", command=self.show_app_settings)

    def _build_statusbar(self) -> None:
        self.statusbar = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color=("gray85", "gray15"))
        self.statusbar.grid(row=1, column=0, sticky="ew")
        self.statusbar.grid_columnconfigure(0, weight=1)
        self.statusbar.grid_columnconfigure(1, weight=1)
        
        self.tournament_label = ctk.CTkLabel(
            self.statusbar,
            text="Nenhum torneio selecionado",
            text_color="#64748B",
            justify="left",
            font=ctk.CTkFont(size=12)
        )
        self.tournament_label.grid(row=0, column=0, padx=10, pady=2, sticky="w")
        
        self.status_label = ctk.CTkLabel(
            self.statusbar,
            text=f"Banco: {Path(self.db.db_path).name}",
            text_color="#64748B",
            justify="right",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.grid(row=0, column=1, padx=10, pady=2, sticky="e")

    def _build_content(self) -> None:
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color="#F8FAFC")
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)

    def _clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def _page_title(self, title: str, subtitle: str = "") -> None:
        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.grid(row=0, column=0, padx=22, pady=(22, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#0F172A",
        ).grid(row=0, column=0, sticky="w")
        if subtitle:
            ctk.CTkLabel(
                header,
                text=subtitle,
                text_color="#64748B",
                wraplength=760,
                justify="left",
            ).grid(row=1, column=0, pady=(2, 0), sticky="w")

    def _make_panel(self, parent: ctk.CTkBaseClass | None = None) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(parent or self.content, fg_color="#FFFFFF", corner_radius=8)
        return panel

    def _make_scrollable_panel(
        self,
        parent: ctk.CTkBaseClass | None = None,
        width: int = 292,
    ) -> ctk.CTkScrollableFrame:
        panel = ctk.CTkScrollableFrame(
            parent or self.content,
            fg_color="#FFFFFF",
            corner_radius=8,
            width=width,
        )
        panel.grid_columnconfigure(0, weight=1)
        return panel

    def _make_tree(
        self,
        parent: ctk.CTkFrame,
        columns: list[str],
        headings: dict[str, str],
        widths: dict[str, int],
        visible_rows: int = 10,
    ) -> ttk.Treeview:
        tree_frame = ctk.CTkFrame(parent, fg_color="transparent")
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            height=visible_rows,
            show="headings",
            selectmode="browse",
        )
        for column in columns:
            tree.heading(column, text=headings.get(column, column))
            tree.column(column, width=widths.get(column, 100), anchor="w", stretch=False)
        y_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        x_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        return tree

    @staticmethod
    def _member_display_name(member: dict[str, Any]) -> str:
        name = str(member.get("name") or "").strip()
        surname = str(member.get("surname") or "").strip()
        return f"{surname}, {name}" if surname and name else surname or name

    def _require_tournament(self) -> bool:
        if self.current_tournament_id:
            return True
        self._clear_content()
        self._page_title("Selecione um torneio", "Crie ou abra um torneio antes de usar esta tela.")
        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=18, sticky="nsew")
        ctk.CTkButton(body, text="Ir para Torneios", command=self.show_tournaments).pack(anchor="w")
        return False

    def _set_current_tournament(self, tournament_id: int) -> None:
        self.current_tournament_id = tournament_id
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            self.tournament_label.configure(text="Nenhum torneio selecionado")
            return
        scope = self._tournament_scope_text(tournament)
        self.tournament_label.configure(
            text=f"{tournament['name']} | {scope} | {tournament['rounds_count']} rodadas | {tournament['status']}"
        )

    @staticmethod
    def _tournament_scope_key(tournament: dict[str, Any]) -> str:
        if tournament.get("class_id"):
            return "class"
        if tournament.get("club_id"):
            return "club"
        return "standalone"

    def _tournament_scope_text(self, tournament: dict[str, Any]) -> str:
        scope = self._tournament_scope_key(tournament)
        if scope == "class":
            return tournament.get("class_name") or TOURNAMENT_SCOPES["class"]
        if scope == "club":
            return tournament.get("club_name") or TOURNAMENT_SCOPES["club"]
        return TOURNAMENT_SCOPES["standalone"]

    def _apply_app_settings(self) -> None:
        try:
            settings = self.db.get_app_settings()
            ctk.set_appearance_mode(str(settings.get("appearance_mode") or "System"))
        except Exception:
            logger.exception("Falha ao aplicar configuracoes do aplicativo")

    def _set_window_icon(self) -> None:
        icon_path = resource_path("assets/app_icon.ico")
        if not icon_path.exists():
            return
        try:
            self.iconbitmap(str(icon_path))
        except Exception:
            logger.exception("Falha ao carregar icone do aplicativo")

    def _default_export_dir(self) -> Path:
        try:
            settings = self.db.get_app_settings()
            path = Path(str(settings.get("default_export_dir") or default_export_dir()))
            path.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            fallback = default_export_dir()
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    def _show_error(self, error: Exception) -> None:
        error_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        title, message, is_unexpected = self._error_dialog(error, error_id)
        if is_unexpected:
            logger.error(
                "Erro inesperado [%s]",
                error_id,
                exc_info=(type(error), error, error.__traceback__),
            )
        else:
            logger.warning("%s: %s", title, error)
        messagebox.showerror(title, message)

    @staticmethod
    def _error_dialog(
        error: Exception,
        error_id: str,
    ) -> tuple[str, str, bool]:
        if isinstance(error, AppError):
            return "Erro", str(error), False
        if isinstance(error, PermissionError):
            return (
                "Erro de permissao",
                f"Sem permissao para acessar o arquivo ou pasta.\n\n{error}",
                False,
            )
        if isinstance(error, FileNotFoundError):
            return (
                "Arquivo nao encontrado",
                f"O arquivo ou pasta informado nao foi encontrado.\n\n{error}",
                False,
            )
        if isinstance(error, OSError):
            return (
                "Erro de arquivo",
                f"Nao foi possivel acessar o arquivo ou pasta.\n\n{error}",
                False,
            )
        if isinstance(error, ValueError):
            return "Dados invalidos", str(error), False
        return (
            "Erro inesperado",
            "Ocorreu uma falha inesperada.\n\n"
            f"Codigo: {error_id}\n"
            f"Consulte o log em: {current_log_path()}",
            True,
        )

    def _show_info(self, message: str) -> None:
        messagebox.showinfo("Albericus", message)

    def _run_background(
        self,
        work: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
        busy_message: str = "Processando...",
        busy_widget: Any | None = None,
    ) -> None:
        if busy_widget is not None:
            try:
                busy_widget.configure(state="disabled")
            except Exception:
                logger.exception("Falha ao desabilitar widget durante tarefa em background")
        if hasattr(self, "status_label") and busy_message:
            self.status_label.configure(text=busy_message)

        def run() -> None:
            try:
                result = work()
            except Exception as exc:
                self.after(0, lambda error=exc: finish(error=error))
                return
            self.after(0, lambda: finish(result=result))

        def finish(result: Any = None, error: Exception | None = None) -> None:
            if busy_widget is not None:
                try:
                    busy_widget.configure(state="normal")
                except Exception:
                    logger.exception("Falha ao reabilitar widget apos tarefa em background")
            if hasattr(self, "status_label"):
                self.status_label.configure(text=f"Banco: {Path(self.db.db_path).name}")
            if error:
                self._show_error(error)
                return
            if on_success:
                try:
                    on_success(result)
                except Exception as exc:
                    self._show_error(exc)

        threading.Thread(target=run, daemon=True).start()

    @staticmethod
    def _safe_filename(text: str, fallback: str) -> str:
        value = "".join(
            character.lower() if character.isalnum() else "_"
            for character in text
        ).strip("_")
        return value or fallback

    def _grid_form_buttons(
        self,
        parent: ctk.CTkBaseClass,
        buttons: list[tuple[str, Callable[[], None]]],
        start_row: int,
        padx: int = 16,
    ) -> None:
        for offset, (label, command) in enumerate(buttons):
            ctk.CTkButton(parent, text=label, command=command).grid(
                row=start_row + offset,
                column=0,
                padx=padx,
                pady=(8 if offset == 0 else 4, 0),
                sticky="ew",
            )
