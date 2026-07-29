from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from typing import Any, Callable, Sequence
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
from .components import (
    ActionGroup,
    DangerAction,
    EmptyState,
    FormAction,
    ThemedTreeview,
    danger_button,
    menu_button,
    primary_button,
    secondary_button,
    show_donation_modal,
)
from .components.dialogs import alert_dialog
from .components.progress import overlay_of
from .form_layout import FORM_PANEL_WIDTH
from .navigation import by_group as nav_by_group
from .layout import wrap_positions
from .shell import AppShell
from .screens.tournaments import TournamentPagesMixin
from .screens.reports import ReportPagesMixin
from .screens.audit import AuditPagesMixin
from .screens.communication import CommunicationPagesMixin
from .screens.integrations import IntegrationPagesMixin
from src.core.version import APP_NAME, APP_SITE, APP_TAGLINE, app_title, version_label
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

        self.title(app_title())
        # Janela começa pequena e centralizada para a tela de login.
        # Apos o login bem-sucedido e maximizada automaticamente.
        _lw, _lh = self.LOGIN_LARGURA, self.LOGIN_ALTURA
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
        self.column_layout_service = ColumnLayoutService(self.db)
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

    # Login em duas faixas: marca a esquerda, formulario a direita (P2-6). A
    # janela antiga era 420x400 — o formulario ficava espremido e nao sobrava
    # lugar para versao nem para orientar quem entra pela primeira vez.
    LOGIN_LARGURA = 900
    LOGIN_ALTURA = 540

    def _build_login_screen(self) -> None:
        self.login_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=THEME_APP_BG)
        self.login_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.login_frame.grid_columnconfigure(0, weight=4, uniform="login")
        self.login_frame.grid_columnconfigure(1, weight=5, uniform="login")
        self.login_frame.grid_rowconfigure(0, weight=1)

        self._build_login_brand(self.login_frame)
        self._build_login_form(self.login_frame)
        self.username_entry.focus()

    def _build_login_brand(self, parent: ctk.CTkFrame) -> None:
        """Faixa de marca: logo, nome, proposito e versao."""
        marca = ctk.CTkFrame(parent, corner_radius=0, fg_color=THEME_ACCENT)
        marca.grid(row=0, column=0, sticky="nsew")
        marca.grid_columnconfigure(0, weight=1)
        marca.grid_rowconfigure(0, weight=1)
        marca.grid_rowconfigure(3, weight=1)

        try:
            logo_path = resource_path("assets/icons/64/16-login.png")
            if logo_path.exists():
                imagem = Image.open(logo_path)
                self._login_logo = ctk.CTkImage(light_image=imagem, dark_image=imagem, size=(96, 96))
                ctk.CTkLabel(marca, image=self._login_logo, text="").grid(
                    row=0, column=0, padx=SPACE_XL, pady=(SPACE_XL, 0), sticky="s"
                )
        except Exception:
            logger.exception("Falha ao carregar o logotipo do login")

        ctk.CTkLabel(
            marca,
            text=APP_NAME,
            text_color=THEME_ON_ACCENT,
            font=ctk.CTkFont(size=SIZE_PAGE_TITLE + 6, weight="bold"),
        ).grid(row=1, column=0, padx=SPACE_XL, pady=(SPACE_LG, 0))
        ctk.CTkLabel(
            marca,
            text=APP_TAGLINE,
            text_color=THEME_ON_ACCENT,
            wraplength=260,
            justify="center",
            font=ctk.CTkFont(size=SIZE_PAGE_SUBTITLE),
        ).grid(row=2, column=0, padx=SPACE_XL, pady=(SPACE_SM, 0))

        try:
            rodape = version_label(self.db.SCHEMA_VERSION)
        except Exception:
            rodape = version_label()
        ctk.CTkLabel(
            marca,
            text=f"{rodape}\n{APP_SITE}",
            text_color=THEME_ON_ACCENT,
            justify="center",
            font=ctk.CTkFont(size=SIZE_BODY),
        ).grid(row=3, column=0, padx=SPACE_XL, pady=(0, SPACE_LG), sticky="s")

    def _build_login_form(self, parent: ctk.CTkFrame) -> None:
        """Faixa do formulario: entrar, erro e ajuda de primeiro acesso."""
        area = ctk.CTkFrame(parent, corner_radius=0, fg_color="transparent")
        area.grid(row=0, column=1, sticky="nsew")
        area.grid_columnconfigure(0, weight=1)
        area.grid_rowconfigure(0, weight=1)
        area.grid_rowconfigure(7, weight=1)

        ctk.CTkLabel(
            area, text="Acesso restrito", font=ctk.CTkFont(size=SIZE_PAGE_TITLE, weight="bold")
        ).grid(row=1, column=0, padx=SPACE_XL, pady=(0, SPACE_XS), sticky="w")
        ctk.CTkLabel(
            area,
            text="Entre com as suas credenciais de operador.",
            text_color=THEME_TEXT_SUB,
        ).grid(row=2, column=0, padx=SPACE_XL, pady=(0, SPACE_LG), sticky="w")

        self.username_entry = ctk.CTkEntry(area, placeholder_text="Usuário", height=38)
        self.username_entry.grid(row=3, column=0, padx=SPACE_XL, pady=(0, SPACE_SM), sticky="ew")
        self.password_entry = ctk.CTkEntry(area, placeholder_text="Senha", show="*", height=38)
        self.password_entry.grid(row=4, column=0, padx=SPACE_XL, pady=(0, SPACE_XS), sticky="ew")

        self.login_error_label = ctk.CTkLabel(area, text="", text_color=THEME_DANGER, anchor="w")
        self.login_error_label.grid(row=5, column=0, padx=SPACE_XL, sticky="ew")

        entrar = primary_button(area, "Entrar", self._try_login, height=40)
        entrar.grid(row=6, column=0, padx=SPACE_XL, pady=(SPACE_SM, SPACE_LG), sticky="ew")

        ajuda = secondary_button(area, "Primeiro acesso?", self._show_first_access_help, height=32)
        ajuda.grid(row=7, column=0, padx=SPACE_XL, pady=(0, SPACE_XL), sticky="n")

        self.username_entry.bind("<Return>", lambda _e: self.password_entry.focus())
        self.password_entry.bind("<Return>", lambda _e: self._try_login())

    def _show_first_access_help(self) -> None:
        """Orienta sem entregar credencial: senha na tela de login seria um
        convite a nunca troca-la."""
        alert_dialog(
            self,
            "Primeiro acesso",
            "O usuário administrador é criado na instalação do Albericus.\n\n"
            "Se você ainda não tem credenciais, peça ao responsável pelo clube: "
            "ele cadastra operadores em Configurações › Segurança e dados › "
            "Gerenciar Usuários do Sistema.",
            kind="info",
        )

    def _try_login(self, event: Any = None) -> None:
        usuario = self.username_entry.get().strip()
        senha = self.password_entry.get().strip()
        if not usuario or not senha:
            self.login_error_label.configure(text="Preencha usuário e senha.")
            return
        if not self.security_service.login(usuario, senha):
            self.login_error_label.configure(text="Credenciais inválidas.")
            self.password_entry.delete(0, "end")
            self.password_entry.focus()
            return

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


    # Atalhos exibidos no menu. A MESMA tabela alimenta os bindings globais em
    # `shell._register_shortcuts`: antes o acelerador era escrito a mao no menu
    # e o binding a mao no shell, sem nada garantindo que combinassem.
    MENU_ACCELERATORS = {
        "show_visual_dashboard": "Ctrl+1",
        "show_tournaments": "Ctrl+2",
        "show_tournament_dashboard": "Ctrl+3",
        "show_pairings": "Ctrl+4",
        "show_standings": "Ctrl+5",
        "show_app_settings": "Ctrl+,",
    }

    @staticmethod
    def _menu_em_breve() -> dict[str, tuple[tuple[str, str, str], ...]]:
        """Itens do menu que NAO sao destinos navegaveis: as duas telas
        pedagogicas desativadas. Ficam explicitas porque sao excecao — o rotulo
        "(em breve)" evita a leitura de "quebrado" que um item cinza sem
        explicacao passa (P1-12 / F3.4).

        Os rotulos sao resolvidos aqui, com `t("chave")` literal: chave vinda
        de variavel e invisivel para o `test_ui_i18n`, que cobra que toda chave
        do catalogo tenha uso — e uma chave orfa hoje e um texto perdido amanha.
        """
        return {
            "training": (
                (t("menu.soon.classes"), "show_training", "aulas"),
                (t("menu.soon.exercises"), "show_exercises", "biblioteca"),
            ),
        }

    def _build_menu(self) -> None:
        """Menu nativo **gerado** do registro de destinos (F5.11 / P3-14).

        Ele era 31 itens escritos a mao, em paralelo a `DESTINATIONS` — e os
        rotulos ja tinham divergido da sidebar, que le o mesmo registro pelo
        catalogo. Duas listas da mesma coisa so ficam iguais por disciplina;
        aqui passam a ficar por construcao. O menu tambem ganhou o que faltava
        (Inicio, Biblioteca) e perdeu o risco de esquecer um destino novo.
        """
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        icone = self._menu_icons.get

        for grupo, destinos in nav_by_group().items():
            if not grupo:
                continue
            submenu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=grupo, menu=submenu)
            for destino in destinos:
                submenu.add_command(
                    label=destino.label,
                    command=lambda chave=destino.key: self.navigator.go(chave),
                    accelerator=self.MENU_ACCELERATORS.get(destino.method, ""),
                    image=icone(destino.icon) if destino.icon else None,
                    compound="left",
                )
            for rotulo, metodo, nome_icone in self._menu_em_breve().get(
                destinos[0].group_key, ()
            ):
                submenu.add_separator()
                submenu.add_command(
                    label=rotulo,
                    command=getattr(self, metodo, lambda: None),
                    image=icone(nome_icone),
                    compound="left",
                    state="disabled",
                )

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=t("menu.help"), menu=help_menu)
        help_menu.add_command(
            label=t("menu.search_action"),
            command=self._show_command_palette,
            accelerator="Ctrl+K",
        )
        help_menu.add_separator()
        help_menu.add_command(label=t("menu.donate"), command=lambda: show_donation_modal(self))

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

        botoes: list[ctk.CTkButton] = []
        for key, label, command, permission in items:
            is_active = key == active
            button = ctk.CTkButton(
                nav,
                text=label,
                command=command,
                width=self._NAV_ITEM_WIDTH,
                height=32,
                fg_color=THEME_ACCENT if is_active else "transparent",
                border_width=0 if is_active else 1,
                text_color=THEME_ON_ACCENT if is_active else THEME_TEXT_MAIN,
            )
            botoes.append(button)
            if permission:
                self._disable_if_unauthorized(button, permission)

        self._tournament_nav = nav
        self._tournament_nav_buttons = botoes
        self._layout_tournament_nav()

    # Barra de navegacao do torneio: 8 itens (9 em torneio por equipes) de 112px
    # numa linha so custam ~950px, e era ELA — nao o conteudo das telas — que
    # empurrava botao para fora da janela em todas as telas de torneio (B-8).
    # Medido: o unico widget fora da borda era sempre o ultimo item ("Diplomas").
    _NAV_ITEM_WIDTH = 112
    _NAV_ITEM_PAD = 6
    # Espaco reservado ao titulo da pagina, a esquerda da barra.
    _NAV_TITLE_RESERVE = 300

    @staticmethod
    def _requested_width(widget: ctk.CTkBaseClass) -> int:
        """Largura que o widget pede, em pixels de tela. 0 se ainda nao sabe."""
        try:
            return int(widget.winfo_reqwidth())
        except Exception:
            return 0

    def _layout_tournament_nav(self) -> None:
        """Distribui os itens em quantas linhas couberem na largura atual.

        Quebrar em duas linhas custa ~38px de altura, que sobra; insistir numa
        linha so custa um botao inacessivel, que nao tem substituto — o menu
        nativo leva as mesmas telas, mas quem esta olhando a barra nao sabe
        disso.
        """
        nav = getattr(self, "_tournament_nav", None)
        botoes = getattr(self, "_tournament_nav_buttons", None)
        if not nav or not botoes:
            return
        try:
            if not nav.winfo_exists():
                return
            # Pelo `content`, e nao pelo cabecalho: o cabecalho acabou de nascer
            # junto com a tela e ainda mede 1px, enquanto o `content` sobrevive
            # a troca de tela e ja traz a largura util (sem a sidebar).
            largura = self.content.winfo_width()
        except Exception:
            return
        # A conta esta em ui/layout.py, sem Tk: e a mesma que as faixas de
        # filtro das telas administrativas passaram a usar (continuacao da B-8).
        # Largura 1 (antes do primeiro desenho) vira linha unica la dentro, para
        # nao piscar um layout intermediario que o proximo <Configure> desfaz.
        #
        # `winfo_reqwidth` e nao `_NAV_ITEM_WIDTH`: o botao criado com width=112
        # desenha 134px, porque o CTk multiplica pela escala de UI (120% por
        # padrao). Medido: com a conta em unidades logicas, a barra so quebrava
        # tarde demais e "Diplomas" ficava fora da janela ate 1.416px.
        larguras = [max(self._NAV_ITEM_WIDTH, self._requested_width(b)) for b in botoes]
        arranjo = wrap_positions(
            larguras,
            largura,
            self._NAV_ITEM_PAD,
            self._NAV_TITLE_RESERVE,
        )
        if getattr(nav, "_arranjo_nav", None) == arranjo:
            return
        nav._arranjo_nav = arranjo  # type: ignore[attr-defined]
        for (linha, coluna), button in zip(arranjo, botoes):
            button.grid(
                row=linha,
                column=coluna,
                padx=(self._NAV_ITEM_PAD, 0),
                pady=(0, self._NAV_ITEM_PAD),
                sticky="e",
            )

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
        width: int = FORM_PANEL_WIDTH,
    ) -> ctk.CTkScrollableFrame:
        """Coluna de formulario. A largura e uma so (F5.4): antes o mesmo painel
        media 272, 280, 292, 300 ou 302 conforme a tela — cinco ajustes no olho
        para a mesma coisa (P3-12). Quem precisa de outra largura passa `width`
        de proposito (a redacao de mensagem, o editor de certificado)."""
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
        empty_title: str = "Nenhum registro",
        empty_description: str = "Os dados aparecem aqui quando houver registros.",
    ) -> ttk.Treeview:
        tree_frame = ctk.CTkFrame(parent, fg_color="transparent")
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        tree = ThemedTreeview(
            tree_frame,
            columns=columns,
            height=visible_rows,
            show="headings",
            selectmode="browse",
        )
        # A coluna mais larga (nome, em geral) absorve a sobra: sem isso toda
        # tabela vivia com barra horizontal permanente (P3-9).
        larguras = {column: widths.get(column, 100) for column in columns}
        principal = max(larguras, key=lambda c: larguras[c]) if columns else None
        for column in columns:
            tree.heading(column, text=headings.get(column, column))
            tree.column(
                column,
                width=larguras[column],
                anchor="w",
                stretch=(column == principal),
            )
        tree.enable_sorting()
        y_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        x_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        tree.attach_empty_state(
            EmptyState(tree_frame, title=empty_title, description=empty_description)
        )
        self._remember_column_widths(tree)
        return tree

    def _remember_column_widths(self, tree: ttk.Treeview) -> None:
        """Aplica a largura que o usuario escolheu e passa a guardar o arrasto (B-1).

        Recebe a tabela **pronta** e le dela tudo de que precisa: colunas,
        titulos e a largura que o codigo pediu (que e o padrao). Por isso serve
        tanto ao _make_tree quanto as tabelas montadas a mao — e foi assim que
        as tres tabelas fora do helper entraram sem virar excecao.

        A identidade da tabela sai das proprias colunas (ver column_layouts):
        sao ~59 chamadas de _make_tree, e exigir uma chave em cada uma seriam
        59 chances de errar.
        """
        columns = [str(column) for column in tree["columns"]]
        if not columns:
            return
        headings = {column: str(tree.heading(column, "text")) for column in columns}
        defaults = {column: int(tree.column(column, "width") or 0) for column in columns}
        key = ColumnLayoutService.key_for(columns, headings)
        user_id = self.security_service.current_user_id()

        for column, width in self.column_layout_service.widths_for(
            user_id, key, columns, defaults
        ).items():
            tree.column(column, width=width)

        # Grava no soltar do botao, e nao a cada pixel: o ttk nao avisa que uma
        # coluna mudou de tamanho, entao a alternativa seria vigiar o <Motion> —
        # uma escrita em banco por pixel arrastado.
        state = {"dragging": False}

        def on_press(event: Any) -> None:
            state["dragging"] = tree.identify_region(event.x, event.y) == "separator"

        def on_release(_event: Any) -> None:
            if not state["dragging"]:
                return
            state["dragging"] = False
            current = {column: int(tree.column(column, "width") or 0) for column in columns}
            self.column_layout_service.remember(user_id, key, defaults, current)

        tree.bind("<ButtonPress-1>", on_press, add="+")
        tree.bind("<ButtonRelease-1>", on_release, add="+")

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

    def _busy_target(self, busy_widget: Any | None) -> Any:
        """Painel que o veu de progresso cobre (F5.9).

        Regra: a acao disparada de dentro de um modal cobre o **modal**; as
        demais cobrem a area de conteudo. Cobrir `self.content` quando o clique
        veio de um dialogo deixaria o dialogo livre para receber o segundo
        clique — que e justamente o que o veu existe para impedir.
        """
        if busy_widget is not None:
            try:
                topo = busy_widget.winfo_toplevel()
                if topo is not self:
                    return topo
            except Exception:
                pass
        return getattr(self, "content", self)

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
        # O veu vem depois do indicador de propósito: se montar o veu falhar
        # (janela em destruicao), a statusbar ainda registra a tarefa.
        overlay = overlay_of(self._busy_target(busy_widget))
        overlay.start(busy_message)

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
            overlay.stop()
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
        buttons: Sequence[FormAction],
        start_row: int,
        padx: int = 16,
        required_action: str = "",
    ) -> None:
        """Empilha as acoes do formulario em coluna.

        Aceita ``(rotulo, comando)`` como sempre e, desde a F5.6, tambem
        ``ActionGroup`` (vira menu recolhido) e ``DangerAction`` (cor de perigo,
        posicao isolada). Chamadas antigas com lista plana seguem identicas.
        """
        autorizado = not required_action or self.security_service.has_permission(required_action)
        for offset, acao in enumerate(buttons):
            pady = (8 if offset == 0 else 4, 0)
            if isinstance(acao, ActionGroup):
                # Sem permissao, os itens do menu nascem inativos: desabilitar so
                # o gatilho esconderia a razao atras de um clique.
                itens = list(acao.items) if autorizado else [
                    (item[0], None) for item in acao.items if item is not None
                ]
                widget = menu_button(parent, acao.label, itens, tip=acao.tip or None)
                # O gatilho continua clicavel de proposito: o menu abre e mostra
                # o que existe, acinzentado. Desabilitar o gatilho esconderia a
                # razao atras de um botao morto.
                widget.grid(row=start_row + offset, column=0, padx=padx, pady=pady, sticky="ew")
                continue
            if isinstance(acao, DangerAction):
                widget = danger_button(parent, acao.label, acao.command, tip=acao.tip or None)
                pady = (SPACE_MD, 0)  # respiro extra isola a acao destrutiva
            else:
                label, command = acao
                widget = ctk.CTkButton(parent, text=label, command=command)
            widget.grid(row=start_row + offset, column=0, padx=padx, pady=pady, sticky="ew")
            if required_action:
                self._disable_if_unauthorized(widget, required_action)
