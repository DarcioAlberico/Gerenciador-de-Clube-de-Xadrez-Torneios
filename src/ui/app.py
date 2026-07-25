from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from typing import Any, Callable
from PIL import Image, ImageTk

from .screens.admin import AdminPagesMixin
from .screens.club import ClubPagesMixin
from .screens.dashboard import DashboardPagesMixin
from .screens.free_tournament import FreeTournamentMixin
from .screens.home import HomePagesMixin
from .screens.library import LibraryMixin
from .screens.pairings import PairingPagesMixin
from .screens.referees import RefereePagesMixin
from .screens.settings import SettingsPagesMixin
from .support import *
from .components import EmptyState, show_donation_modal
from .shell import AppShell
from .screens.tournaments import TournamentPagesMixin
from .screens.reports import ReportPagesMixin
from .screens.audit import AuditPagesMixin
from .screens.communication import CommunicationPagesMixin
from .screens.integrations import IntegrationPagesMixin
from src.services.message_service import MessageService
from src.services.report_engine import ReportEngine


class AlbericusApp(
    AppShell,
    UIBuilderMixin,
    HomePagesMixin,
    ClubPagesMixin,
    DashboardPagesMixin,
    AdminPagesMixin,
    RefereePagesMixin,
    TournamentPagesMixin,
    PairingPagesMixin,
    SettingsPagesMixin,
    LibraryMixin,
    ReportPagesMixin,
    AuditPagesMixin,
    CommunicationPagesMixin,
    IntegrationPagesMixin,
    FreeTournamentMixin,
    ctk.CTk,
):
    def __init__(self, db: Database | None = None) -> None:
        super().__init__()
        configure_logging()
        logger.info("Aplicativo iniciado")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("Albericus - Emparceiramento de Xadrez v1.0")
        # Janela começa pequena e centralizada para a tela de login.
        # Apos o login bem-sucedido e maximizada automaticamente.
        _lw, _lh = 420, 400
        self.update_idletasks()
        _sw = self.winfo_screenwidth()
        _sh = self.winfo_screenheight()
        _lx = (_sw - _lw) // 2
        _ly = (_sh - _lh) // 2
        self.geometry(f"{_lw}x{_lh}+{_lx}+{_ly}")
        self.resizable(False, False)

        self.db = db or Database()
        self._arbitration_auto_refresh_enabled = True
        self._arbitration_refresh_interval_seconds = 15
        self._arbitration_inline_tables_limit = 20
        # Aplica os presets de aparencia antes de criar qualquer widget.
        try:
            _init_settings = self.db.get_app_settings()
            from src.ui.theme import apply_accent_preset, apply_bg_preset, apply_frame_bg_preset
            apply_bg_preset(str(_init_settings.get("bg_preset") or "slate"))
            apply_frame_bg_preset(str(_init_settings.get("frame_bg_preset") or "slate"))
            apply_accent_preset(str(_init_settings.get("accent_preset") or "blue"))
        except Exception:
            pass
        self._apply_app_settings()
        self._set_window_icon()
        self._load_menu_icons()
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
        self.sync_service = SyncService(self.db)
        self.clock_integration_service = ClockIntegrationService(self.db)
        self.pairing_service = PairingService(self.db)
        self.qr_result_service = QRResultService(self.db, self.pairing_service)
        self.import_service = ImportService(self.db)
        self.google_forms_service = GoogleFormsService(self.db)
        self.official_rating_service = OfficialRatingService(self.db)
        self.internal_rating_service = InternalRatingService(self.db)
        self.fide_rating_service = FideRatingService(self.db)
        self.norm_assistant_service = NormAssistantService(self.db)
        self.prize_service = PrizeService(self.db)
        self.list_layout_service = ListLayoutService(self.db)
        self.export_service = ExportService(self.db, self.pairing_service)
        self.chess_results_service = ChessResultsService(self.db, self.export_service)
        self.photo_album_service = PhotoAlbumService(self.db)
        self.batch_export_service = BatchExportService(self.export_service)
        self.certificate_service = CertificateService(self.db, self.pairing_service)
        self.communication_service = CommunicationService(self.db)
        self.calendar_service = CalendarService(self.db)
        self.library_service = LibraryService(self.db)
        self.report_engine = ReportEngine(self.db, self.finance_service, self.member_service, self.tournament_service)

        self.current_tournament_id: int | None = None
        self.current_round_id: int | None = None
        self.round_option_map: dict[str, int] = {}
        self.pairing_row_map: dict[str, int] = {}
        self.pairing_detail_map: dict[str, dict[str, Any]] = {}
        self.local_result_server: LocalResultServer | None = None
        self._scheduled_dispatch_job: str | None = None
        self._arbitration_refresh_job: str | None = None

        # Navegacao central (registro unico de destinos) — a casca monta.
        self._build_shell_navigation()

        self._configure_grid()
        self._configure_tree_style()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._build_login_screen()

    def _on_closing(self) -> None:
        try:
            self.security_service.create_backup("auto_shutdown")
        except Exception as exc:
            logger.error("Erro ao gerar backup no fechamento: %s", exc)
        if self._scheduled_dispatch_job is not None:
            try:
                self.after_cancel(self._scheduled_dispatch_job)
            except Exception:
                pass
            self._scheduled_dispatch_job = None
        if self._arbitration_refresh_job is not None:
            try:
                self.after_cancel(self._arbitration_refresh_job)
            except Exception:
                pass
            self._arbitration_refresh_job = None
        if self.local_result_server is not None:
            self.local_result_server.stop()
        self.destroy()

    # Intervalo do tick de mensagens agendadas (5 min). Num desktop offline, o
    # disparo so ocorre com o app aberto; a fila persistida garante que nada se
    # perde, mas o envio fica para a proxima vez que o app estiver rodando.
    _SCHEDULED_DISPATCH_INTERVAL_MS = 5 * 60 * 1000

    def _start_scheduled_dispatch(self) -> None:
        """Dispara as mensagens agendadas vencidas na inicializacao e reagenda um
        tick periodico enquanto o app estiver aberto."""
        self._dispatch_scheduled_messages_once()
        self._scheduled_dispatch_job = self.after(
            self._SCHEDULED_DISPATCH_INTERVAL_MS, self._scheduled_dispatch_tick
        )

    def _rebuild_ui_after_theme_change(self) -> None:
        """Aplica o tema **na hora**, reestilizando o que ja esta na tela (P0-6).

        Antes isto destruia `statusbar` e `content` e remontava tudo: a tela
        voltava ao inicio, a selecao da tabela sumia, o scroll ia ao topo e o
        foco se perdia. Agora a troca e `configure()` widget a widget — como
        nada e recriado, foco, scroll e selecao ficam onde estavam.

        O nome antigo foi mantido porque a tela de configuracoes o chama; o que
        mudou e a estrategia, nao o contrato.
        """
        from src.ui.restyle import restyle, snapshot_defaults
        from src.ui.theme import apply_accent_preset, apply_bg_preset, apply_frame_bg_preset

        settings = self.db.get_app_settings()
        # Retrato ANTES: e ele que diz quem seguia o padrao do tema e deve
        # acompanhar a troca, sem repintar quem tem cor propria (danger, etc.).
        padroes_antes = snapshot_defaults()

        apply_bg_preset(str(settings.get("bg_preset") or "slate"))
        apply_frame_bg_preset(str(settings.get("frame_bg_preset") or "slate"))
        apply_accent_preset(str(settings.get("accent_preset") or "blue"))
        self._apply_app_settings()

        restyle(self, padroes_antes)
        self._configure_tree_style(register_callback=False)
        self._refresh_statusbar()
        self._show_toast("Tema aplicado com sucesso.", kind="success")

    def _scheduled_dispatch_tick(self) -> None:
        self._dispatch_scheduled_messages_once()
        self._scheduled_dispatch_job = self.after(
            self._SCHEDULED_DISPATCH_INTERVAL_MS, self._scheduled_dispatch_tick
        )

    def _dispatch_scheduled_messages_once(self) -> None:
        """Roda o despacho da fila de mensagens agendadas. Nunca propaga erro: uma
        falha de envio nao pode derrubar a interface."""
        try:
            settings = self.db.get_app_settings()
            mailer = MessageService(
                smtp_server=settings.get("smtp_server", ""),
                smtp_port=int(settings.get("smtp_port", 587) or 587),
                smtp_user=settings.get("smtp_user", ""),
                smtp_password=settings.get("smtp_password", ""),
            )
            results = self.communication_service.dispatch_due_scheduled_messages(mailer)
            if results:
                logger.info("Mensagens agendadas despachadas: %s", len(results))
        except Exception as exc:
            logger.error("Falha no despacho de mensagens agendadas: %s", exc)

    def _build_login_screen(self) -> None:
        self.login_frame = ctk.CTkFrame(self, corner_radius=12, width=320)
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.login_frame.grid_propagate(False)

        # Logotipo de Login
        try:
            logo_path = resource_path("assets/icons/64/16-login.png")
            if logo_path.exists():
                img_pil = Image.open(logo_path)
                logo_img = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(64, 64))
                logo_label = ctk.CTkLabel(self.login_frame, image=logo_img, text="")
                logo_label.pack(pady=(20, 0))
                self._login_logo = logo_img
        except Exception as exc:
            logger.error("Erro ao carregar logotipo de login: %s", exc)

        ctk.CTkLabel(self.login_frame, text="Albericus", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(10, 10))
        ctk.CTkLabel(self.login_frame, text="Acesso Restrito", font=ctk.CTkFont(size=14)).pack(pady=(0, 20))

        self.username_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Usuário", width=200)
        self.username_entry.pack(pady=10, padx=20)

        self.password_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Senha", show="*", width=200)
        self.password_entry.pack(pady=10, padx=20)
        
        self.login_error_label = ctk.CTkLabel(self.login_frame, text="", text_color=THEME_DANGER)
        self.login_error_label.pack()

        def try_login(event=None):
            user = self.username_entry.get().strip()
            pwd = self.password_entry.get().strip()
            if not user or not pwd:
                self.login_error_label.configure(text="Preencha usuário e senha.")
                return
            if self.security_service.login(user, pwd):
                self.login_frame.destroy()
                # Maximiza a janela principal apos o login.
                self.resizable(True, True)
                self.minsize(980, 640)
                self.state("zoomed")
                self._build_menu()
                self._build_statusbar()
                self._build_content()
                self._register_shortcuts()
                # Abre nas pendencias, nao no cadastro do clube (P1-8 / F3.2).
                self.show_home()
                self._refresh_statusbar()
                self._start_scheduled_dispatch()
            else:
                self.login_error_label.configure(text="Credenciais inválidas.")

        self.password_entry.bind("<Return>", try_login)
        ctk.CTkButton(self.login_frame, text="Entrar", command=try_login, width=200).pack(pady=(10, 20), padx=20)
        self.username_entry.focus()

    def _configure_tree_style(self, register_callback: bool = True) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        scale = getattr(self, "_ui_scale_percent", 120) / 100
        body_font_size = max(10, int(10 * scale))
        style.configure(
            "Treeview",
            rowheight=max(34, int(34 * scale)),   # mais respiro entre linhas
            font=("Segoe UI", body_font_size),
            borderwidth=0,
            relief="flat",
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", max(10, int(10 * scale)), "bold"),
            relief="flat",
            padding=(6, 6),
        )
        style.map(
            "Treeview",
            background=[("selected", pick(THEME_TREE_SELECTED))],
            foreground=[("selected", pick(THEME_TREE_SELECTED_FG))],
        )
        self._update_tree_colors(style)
        if register_callback:
            ctk.AppearanceModeTracker.add(self._on_appearance_change, self)

    def _on_appearance_change(self, new_appearance_mode: str) -> None:
        style = ttk.Style(self)
        self._update_tree_colors(style)

    def _update_tree_colors(self, style: ttk.Style) -> None:
        """Cores da tabela na aparencia atual. O ttk so aceita uma cor por vez,
        entao cada token passa por pick() (ver theme.py)."""
        bg = pick(THEME_TREE_BG)
        fg = pick(THEME_TREE_FG)
        style.configure("Treeview", background=bg, fieldbackground=bg, foreground=fg)
        cabecalho = pick(THEME_TREE_HEADING)
        style.configure("Treeview.Heading", background=cabecalho, foreground=fg)
        style.map("Treeview.Heading", background=[("active", cabecalho)])
        style.map(
            "Treeview",
            background=[("selected", pick(THEME_TREE_SELECTED))],
            foreground=[("selected", pick(THEME_TREE_SELECTED_FG))],
        )


    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        def get_ico(name: str):
            return self._menu_icons.get(name)

        # 1. Clube
        club_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Clube", menu=club_menu)
        club_menu.add_command(label="Dashboard Visual", command=self.show_visual_dashboard, accelerator="Ctrl+1", image=get_ico("dashboard"), compound="left")
        club_menu.add_command(label="Perfil do Clube", command=self.show_club, image=get_ico("clube"), compound="left")
        club_menu.add_command(label="Membros", command=self.show_members, image=get_ico("membros"), compound="left")
        club_menu.add_command(label="Níveis", command=self.show_learning_levels, image=get_ico("aulas"), compound="left")
        club_menu.add_command(label="Responsáveis", command=self.show_guardians, image=get_ico("membros"), compound="left")

        # 2. Treinamento
        training_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Treinamento", menu=training_menu)
        # Aulas e Exercícios temporariamente DESATIVADOS (não excluídos):
        # itens visíveis porém acinzentados/não-clicáveis. Para reativar,
        # remover state="disabled". Métodos/telas permanecem intactos.
        # O rotulo "(em breve)" evita a leitura de "quebrado": item cinza sem
        # explicacao passa a impressao de erro, e nao de escopo (P1-12 / F3.4).
        training_menu.add_command(label="Aulas (em breve)", command=self.show_training, image=get_ico("aulas"), compound="left", state="disabled")
        training_menu.add_command(label="Exercícios (em breve)", command=self.show_exercises, image=get_ico("biblioteca"), compound="left", state="disabled")
        training_menu.add_separator()
        training_menu.add_command(label="Torneio | Livre", command=self.show_free_tournament_mode, image=get_ico("torneios"), compound="left")

        # 3. Gestão
        mgmt_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Gestão", menu=mgmt_menu)
        mgmt_menu.add_command(label="Árbitros", command=self.show_referees, image=get_ico("arbitros"), compound="left")
        mgmt_menu.add_command(label="Inventário", command=self.show_inventory, image=get_ico("integracoes"), compound="left")
        mgmt_menu.add_command(label="Financeiro", command=self.show_finance, image=get_ico("financeiro"), compound="left")
        mgmt_menu.add_command(label="Calendário", command=self.show_calendar, image=get_ico("calendario"), compound="left")
        mgmt_menu.add_command(label="Ranking Interno", command=self.show_internal_ranking, image=get_ico("dashboard"), compound="left")

        # 4. Torneio
        tourn_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Torneio", menu=tourn_menu)
        tourn_menu.add_command(label="Torneios", command=self.show_tournaments, accelerator="Ctrl+2", image=get_ico("torneios"), compound="left")
        tourn_menu.add_command(label="Central do Torneio", command=self.show_tournament_dashboard, accelerator="Ctrl+3", image=get_ico("emparceiramento"), compound="left")
        tourn_menu.add_command(label="Painel do Árbitro", command=self.show_arbitration_panel, image=get_ico("arbitros"), compound="left")
        tourn_menu.add_command(label="Config. Torneio", command=self.show_tournament_settings, image=get_ico("configuracoes"), compound="left")
        tourn_menu.add_separator()
        tourn_menu.add_command(label="Jogadores", command=self.show_players, image=get_ico("membros"), compound="left")
        tourn_menu.add_command(label="Equipes", command=self.show_teams, image=get_ico("clube"), compound="left")
        tourn_menu.add_command(label="Rodadas", command=self.show_pairings, accelerator="Ctrl+4", image=get_ico("emparceiramento"), compound="left")
        tourn_menu.add_command(label="Classificação", command=self.show_standings, accelerator="Ctrl+5", image=get_ico("dashboard"), compound="left")
        tourn_menu.add_command(label="Diplomas", command=self.show_certificates, image=get_ico("relatorios"), compound="left")

        # 5. Ferramentas
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ferramentas", menu=tools_menu)
        tools_menu.add_command(label="Exportar", command=self.show_export, image=get_ico("integracoes"), compound="left")
        tools_menu.add_command(label="Relatórios Administrativos", command=self.show_administrative_reports, image=get_ico("relatorios"), compound="left")
        tools_menu.add_command(label="DRE Financeiro", command=self.show_financial_reports, image=get_ico("financeiro"), compound="left")
        tools_menu.add_command(label="Comunicação", command=self.show_communication, image=get_ico("comunicacao"), compound="left")
        tools_menu.add_command(label="Integrações Operacionais", command=self.show_integrations, image=get_ico("integracoes"), compound="left")

        # 6. Configurações
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configurações", menu=settings_menu)
        settings_menu.add_command(label="Config. App", command=self.show_app_settings, accelerator="Ctrl+,", image=get_ico("configuracoes"), compound="left")
        settings_menu.add_command(label="Auditoria Completa", command=self.show_audit_logs, image=get_ico("auditoria"), compound="left")

        # 7. Ajuda
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ajuda", menu=help_menu)
        
        help_menu.add_command(label="Buscar ação...", command=self._show_command_palette, accelerator="Ctrl+K")
        help_menu.add_separator()
        help_menu.add_command(label="❤ Apoie o Projeto", command=lambda: show_donation_modal(self))
    def require_permission(self, action: str) -> None:
        self.security_service.require_permission(action)

    def show_administrative_reports(self) -> None:
        SettingsPagesMixin.show_reports(self)

    def show_financial_reports(self) -> None:
        ReportPagesMixin.show_reports(self)

    def show_reports(self) -> None:
        self.show_administrative_reports()

    def _page_title(self, title: str, subtitle: str = "") -> None:
        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.grid(row=0, column=0, padx=22, pady=(22, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        self._page_header = header

        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(size=SIZE_PAGE_TITLE, weight="bold"),
            text_color=THEME_TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w")
        if subtitle:
            ctk.CTkLabel(
                header,
                text=subtitle,
                text_color=THEME_TEXT_SUB,
                wraplength=760,
                justify="left",
            ).grid(row=1, column=0, pady=(2, 0), sticky="w")

    def _build_tournament_nav(self, active: str) -> None:
        if not getattr(self, "current_tournament_id", None):
            return
        tournament = self.db.get_tournament(self.current_tournament_id)
        if not tournament:
            return
        header = getattr(self, "_page_header", None)
        if header is None:
            return

        is_team_tournament = tournament.get("competition_type") == "team"
        nav = ctk.CTkFrame(header, fg_color="transparent")
        nav.grid(row=0, column=1, rowspan=2, padx=(16, 0), sticky="e")

        items: list[tuple[str, str, Callable[[], None], str | None]] = [
            ("central", "Central", self.show_tournament_dashboard, None),
            ("arbiter", "Árbitro", self.show_arbitration_panel, None),
            ("settings", "Config.", self.show_tournament_settings, "tournament_write"),
            ("players", "Jogadores", self.show_players, "tournament_write"),
            ("pairings", "Rodadas", self.show_pairings, "tournament_write"),
            ("standings", "Classificação", self.show_standings, None),
            ("export", "Exportar", self.show_export, None),
            ("certificates", "Diplomas", self.show_certificates, None),
        ]
        if is_team_tournament:
            items.insert(3, ("teams", "Equipes", self.show_teams, "tournament_write"))

        for index, (key, label, command, permission) in enumerate(items):
            is_active = key == active
            button = ctk.CTkButton(
                nav,
                text=label,
                command=command,
                width=112,
                height=32,
                fg_color=THEME_ACCENT if is_active else "transparent",
                border_width=0 if is_active else 1,
                text_color=("#FFFFFF", "#0B0F19") if is_active else THEME_TEXT_MAIN,
            )
            button.grid(row=0, column=index, padx=(6, 0), pady=(0, 6), sticky="e")
            if permission:
                self._disable_if_unauthorized(button, permission)

    def _make_panel(self, parent: ctk.CTkBaseClass | None = None) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(parent or self.content, fg_color=THEME_PANEL_BG, corner_radius=8)
        return panel

    def _section_title(
        self,
        parent: ctk.CTkBaseClass,
        text: str,
        *,
        subsection: bool = False,
    ) -> ctk.CTkLabel:
        """Rótulo padronizado de seção. Use subsection=True para sub-cabeçalhos."""
        font = font_subsection() if subsection else font_section()
        return ctk.CTkLabel(parent, text=text, font=font, text_color=THEME_TEXT_MAIN)

    def _kpi_card(
        self,
        parent: ctk.CTkBaseClass,
        label: str,
        value: Any,
        *,
        subtitle: str = "",
        command: Callable[[], None] | None = None,
    ) -> ctk.CTkFrame:
        """Card padrão de KPI: label (sub) / valor grande / subtitle opcional.

        O caller posiciona o card com .grid()/.pack() no parent.
        """
        card = self._make_panel(parent)
        ctk.CTkLabel(card, text=label, text_color=THEME_TEXT_SUB).pack(
            anchor="w", padx=14, pady=(12, 0)
        )
        ctk.CTkLabel(card, text=str(value), font=font_kpi_value()).pack(
            anchor="w", padx=14, pady=(0, 0 if subtitle else 12)
        )
        if subtitle:
            ctk.CTkLabel(card, text=subtitle, text_color=THEME_TEXT_SUB).pack(
                anchor="w", padx=14, pady=(0, 12)
            )
        if command is not None:
            # Borda sempre presente (na cor do painel, invisivel) para o realce do
            # hover nao deslocar o conteudo em 1px ao entrar/sair (P1-10).
            card.configure(border_width=1, border_color=THEME_PANEL_BG)

            def highlight(active: bool) -> None:
                try:
                    card.configure(border_color=THEME_ACCENT if active else THEME_PANEL_BG)
                except Exception:
                    pass

            def left_card(event: Any) -> None:
                # Os rotulos cobrem o card: sair do rotulo para o card ainda e
                # "dentro". Sem esta checagem o realce piscaria a cada travessia.
                try:
                    under = card.winfo_containing(event.x_root, event.y_root)
                except Exception:
                    under = None
                if under is not None and str(under).startswith(str(card)):
                    return
                highlight(False)

            def bind_click(widget: ctk.CTkBaseClass) -> None:
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda _event: command())
                widget.bind("<Enter>", lambda _event: highlight(True))
                widget.bind("<Leave>", left_card)
                for child in widget.winfo_children():
                    bind_click(child)

            bind_click(card)
        return card

    def _make_scrollable_panel(
        self,
        parent: ctk.CTkBaseClass | None = None,
        width: int = 292,
    ) -> ctk.CTkScrollableFrame:
        panel = ctk.CTkScrollableFrame(
            parent or self.content,
            fg_color=THEME_PANEL_BG,
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
        empty = EmptyState(
            self.content,
            title="Nenhum torneio selecionado",
            description="Crie um novo torneio ou abra um existente para liberar esta tela.",
            cta_text="Ir para Torneios",
            cta_command=self.show_tournaments,
        )
        empty.grid(row=1, column=0, padx=22, pady=18, sticky="nsew")
        return False

    def _set_current_tournament(self, tournament_id: int) -> None:
        self.current_tournament_id = tournament_id
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            self.tournament_label.configure(text="Nenhum torneio selecionado")
            return
        scope = self._tournament_scope_text(tournament)
        mode = "Modo Livre" if self._is_free_mode(tournament_id) else "Modo Oficial"
        self.tournament_label.configure(
            text=f"{tournament['name']} | {scope} | {tournament['rounds_count']} rodadas | {tournament['status']} | {mode}"
        )
        self._refresh_statusbar()

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
            # Sempre usa "blue" como base estrutural (formas, raios, espessuras).
            # A cor de destaque e controlada por accent_preset via ThemeManager.
            ctk.set_default_color_theme("blue")
            # Re-aplica o accent apos carregar o tema base (set_default_color_theme
            # sobrescreve o ThemeManager; o patch deve vir depois).
            try:
                accent_key = str(settings.get("accent_preset") or "blue")
                from src.ui.theme import apply_accent_preset
                apply_accent_preset(accent_key)
            except Exception:
                pass
            try:
                scale_percent = int(str(settings.get("ui_scale_percent") or "120"))
            except ValueError:
                scale_percent = 100
            scale_percent = min(160, max(80, scale_percent))
            self._ui_scale_percent = scale_percent
            scale = scale_percent / 100
            ctk.set_widget_scaling(scale)
            ctk.set_window_scaling(scale)
            self._arbitration_auto_refresh_enabled = str(
                settings.get("arbitration_auto_refresh_enabled") or "1"
            ).strip().lower() not in {"0", "false", "off", "no"}
            self._arbitration_refresh_interval_seconds = self._bounded_int_setting(
                settings,
                "arbitration_refresh_interval_seconds",
                default=15,
                minimum=10,
                maximum=120,
            )
            self._arbitration_inline_tables_limit = self._bounded_int_setting(
                settings,
                "arbitration_inline_tables_limit",
                default=20,
                minimum=10,
                maximum=50,
            )
        except Exception:
            logger.exception("Falha ao aplicar configuracoes do aplicativo")

    @staticmethod
    def _bounded_int_setting(
        settings: dict[str, Any],
        key: str,
        *,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            value = int(str(settings.get(key) or default))
        except ValueError:
            return default
        return value if minimum <= value <= maximum else default

    def _set_window_icon(self) -> None:
        icon_path = resource_path("assets/app_icon.ico")
        if not icon_path.exists():
            return
        try:
            self.iconbitmap(str(icon_path))
        except Exception:
            logger.exception("Falha ao carregar icone do aplicativo")

    def _load_menu_icons(self) -> None:
        self._menu_icons = {}
        self._ctk_menu_icons = {}
        icon_mappings = {
            "dashboard": "01-dashboard.png",
            "clube": "02-clube.png",
            "membros": "03-membros.png",
            "torneios": "04-torneios.png",
            "emparceiramento": "05-emparceiramento.png",
            "arbitros": "06-arbitros.png",
            "relatorios": "07-relatorios.png",
            "auditoria": "08-auditoria.png",
            "comunicacao": "09-comunicacao.png",
            "configuracoes": "10-configuracoes.png",
            "integracoes": "11-integracoes.png",
            "biblioteca": "12-biblioteca.png",
            "aulas": "13-aulas.png",
            "financeiro": "14-financeiro.png",
            "calendario": "15-calendario.png",
            "login": "16-login.png"
        }
        for name, filename in icon_mappings.items():
            path24 = resource_path(f"assets/icons/24/{filename}")
            if path24.exists():
                try:
                    img = Image.open(path24)
                    self._menu_icons[name] = ImageTk.PhotoImage(img)
                    self._ctk_menu_icons[name] = ctk.CTkImage(
                        light_image=img,
                        dark_image=img,
                        size=(20, 20)
                    )
                except Exception as exc:
                    logger.error(f"Erro ao carregar icone {filename}: {exc}")

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
        indicator = getattr(self, "busy_indicator", None)
        if indicator is not None:
            indicator.start()

        def run() -> None:
            try:
                result = work()
            except Exception as exc:
                self.after(0, lambda error=exc: finish(error=error))
                return
            self.after(0, lambda: finish(result=result))

        def finish(result: Any = None, error: Exception | None = None) -> None:
            if indicator is not None:
                indicator.stop()
            if busy_widget is not None:
                try:
                    busy_widget.configure(state="normal")
                except Exception:
                    logger.exception("Falha ao reabilitar widget apos tarefa em background")
            # So volta ao texto padrao quando nao ha mais nada rodando: com duas
            # tarefas simultaneas, a primeira a terminar limparia a mensagem da
            # outra e a statusbar contradiria a barra de progresso (ainda visivel).
            ocioso = indicator is None or not indicator.is_running
            if hasattr(self, "status_label") and ocioso:
                self.status_label.configure(text=self._default_status_text())
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
        required_action: str = "",
    ) -> None:
        for offset, (label, command) in enumerate(buttons):
            btn = ctk.CTkButton(parent, text=label, command=command)
            btn.grid(
                row=start_row + offset,
                column=0,
                padx=padx,
                pady=(8 if offset == 0 else 4, 0),
                sticky="ew",
            )
            if required_action:
                self._disable_if_unauthorized(btn, required_action)
