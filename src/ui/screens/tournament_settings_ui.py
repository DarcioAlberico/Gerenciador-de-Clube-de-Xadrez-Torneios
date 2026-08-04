from __future__ import annotations

from datetime import datetime

from ..support import *
from ..components import (
    FormStack,
    clear_field_error,
    form_of,
    set_field_error,
    set_field_warning,
)

from src.services.pairing.acceleration import acceleration_spec
from src.services.pairing.tiebreak_engine import LEGACY_ENGINE_CHOICE_HINT
from src.services.constants import PAIRING_SYSTEMS, TIEBREAK_ENGINES
from src.services.pairing import (
    DEFAULT_PLAYER_TIEBREAKS,
    DEFAULT_TEAM_TIEBREAKS,
    PLAYER_TIEBREAKS,
    TEAM_TIEBREAKS,
    parse_player_tiebreak_sequence,
    parse_team_tiebreak_sequence,
    serialize_tiebreak_sequence,
)
from src.services.prizes import PRIZE_POLICIES
from src.services.list_layouts import DEFAULT_STANDINGS_COLUMNS, STANDINGS_COLUMNS
from src.services.chess_results import normalize_results_url
from src.services.rating import parse_regulation_overrides
from .tournament_widgets import (
    CategoryEditor,
    ColumnLayoutEditor,
    PrizeEditor,
    TiebreakSequenceEditor,
)

# Ritmo para efeito de rating. Vazio = deduzir do campo "Ritmo" do torneio.
RATING_SPEED_LABELS = {
    "": "Automático (pelo ritmo de jogo)",
    "standard": "Standard (clássico)",
    "rapid": "Rápido",
    "blitz": "Blitz",
}

# Parâmetros do regulamento de rating que o árbitro pode ajustar. Deixar em
# branco mantém o valor do perfil publicado.
RATING_REGULATION_FIELDS = [
    ("k_new", "K de jogador novo", "Ex.: 40"),
    ("k_new_games", "Partidas até deixar de ser novo", "Ex.: 30"),
    ("k_youth", "K de sub-18", "Ex.: 40"),
    ("k_youth_max_rating", "Rating máximo para o K de sub-18", "Ex.: 2300"),
    ("k_top", "K de rating alto", "Ex.: 10"),
    ("k_top_rating", "Rating a partir do qual vale o K alto", "Ex.: 2300"),
    ("k_default", "K padrão", "Ex.: 20"),
    ("rating_floor", "Piso de rating", "Ex.: 1400"),
    ("initial_min_games", "Partidas mínimas para rating inicial", "Ex.: 5"),
    ("initial_max_rating", "Teto do rating inicial", "Ex.: 2200"),
]


class TournamentSettingsMixin:
    @staticmethod
    def _settings_tab(tabview: ctk.CTkTabview, name: str) -> ctk.CTkScrollableFrame:
        """Cria uma aba rolavel no tabview e devolve o painel de conteudo.

        A pilha de formulario da aba nasce junto (``FormStack``): quem tem o
        painel na mao alcanca a mesma pilha por ``form_of`` — dois contadores
        de linha sobre o mesmo grid e como o formulario se desalinha calado.
        """
        tab = tabview.add(name)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        panel = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        panel.grid(row=0, column=0, sticky="nsew")
        FormStack(panel)
        return panel

    @staticmethod
    def _settings_stack(
        panel: ctk.CTkScrollableFrame,
        widget: Any,
        *,
        label: str = "",
        section: bool = False,
        help_text: str = "",
    ) -> Any:
        """Empilha (rotulo + ajuda + widget) numa coluna — hoje via ``FormStack``.

        A F5.4 promoveu este metodo a componente
        ([`components/form.py`](../components/form.py)); o que sobrou aqui e a
        ponte para os call-sites que empilham editores proprios (sequencia de
        desempates, premiacao, colunas), que nao sao campos de entrada.
        """
        pilha = form_of(panel)
        if section:
            pilha.section(label, help_text=help_text)
            return pilha.place(widget, "widget")
        return pilha.widget(widget, label=label, help_text=help_text)

    def show_tournament_settings(self) -> None:
        if not self._require_tournament():
            return

        tournament = self.db.get_tournament(self.current_tournament_id)
        if not tournament:
            self._show_error(AppError("Selecione um torneio valido."))
            return
        settings = self.db.get_tournament_settings(self.current_tournament_id) or {}

        self._clear_content()
        self._page_title(
            "Configuração do torneio",
            f"Torneio: {tournament['name']} - {self._tournament_scope_text(tournament)}",
        )
        self._build_tournament_nav("settings")

        container = ctk.CTkFrame(self.content, fg_color="transparent")
        container.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        tabview = ctk.CTkTabview(container)
        tabview.grid(row=0, column=0, sticky="nsew")
        tab_general = self._settings_tab(tabview, "Dados gerais")
        tab_official = self._settings_tab(tabview, "Dados oficiais")
        tab_rules = self._settings_tab(tabview, "Regras e desempates")
        tab_prizes = self._settings_tab(tabview, "Premiação")
        tab_reports = self._settings_tab(tabview, "Classificação e agenda")

        stack = self._settings_stack
        form_general = form_of(tab_general)
        form_official = form_of(tab_official)
        form_rules = form_of(tab_rules)

        # ------------------------------------------------------------------ #
        # Aba 1 - Dados gerais
        # ------------------------------------------------------------------ #
        # Onze campos seguidos viravam uma coluna corrida de rotulos, sem onde
        # o olho descansar (P3-12). Sao tres perguntas diferentes — que torneio
        # e este, quando acontece, quem ele alcanca — e agora sao tres secoes.
        tournament_entries: dict[str, Any] = {}
        general_sections: list[tuple[str, list[tuple[str, str, str]]]] = [
            (
                "Identificação",
                [
                    ("name", "Nome do torneio", "Ex.: Aberto de Verão 2026"),
                    ("location", "Local", "Ex.: Clube Municipal de Xadrez"),
                ],
            ),
            (
                "Calendário e ritmo",
                [
                    ("start_date", "Data inicial", ""),
                    ("end_date", "Data final", ""),
                    ("rounds_count", "Rodadas", "Ex.: 7"),
                    ("time_control", "Ritmo", ""),
                    ("bye_points", "Pontos do bye", "Ex.: 0,5"),
                ],
            ),
        ]
        for titulo, campos in general_sections:
            form_general.section(titulo)
            for key, label, dica in campos:
                if key in ("start_date", "end_date"):
                    entry = form_general.date(label)
                elif key == "time_control":
                    entry = form_general.field(label, self._make_time_control_menu)
                else:
                    entry = form_general.text(label, placeholder=dica)
                entry.insert(0, str(tournament.get(key) or ""))
                tournament_entries[key] = entry

        form_general.section("Abrangência")
        scope_option = form_general.select("Escopo", list(TOURNAMENT_SCOPE_VALUES.keys()))
        scope_option.set(TOURNAMENT_SCOPES[self._tournament_scope_key(tournament)])

        competition_by_label = {label: value for value, label in COMPETITION_TYPES.items()}
        competition_option = form_general.select("Formato", list(competition_by_label.keys()))
        competition_option.set(
            COMPETITION_TYPES.get(tournament.get("competition_type", "individual"), COMPETITION_TYPES["individual"])
        )

        tournament_club_map: dict[str, int] = {}
        tournament_club_values = []
        for club in self.db.list_clubs(active_only=True):
            kind = CLUB_KIND_LABELS.get(club.get("kind", "club"), club.get("kind", ""))
            label = f"{club['id']} - {club['name'] or 'Clube padrao'} ({kind})"
            tournament_club_values.append(label)
            tournament_club_map[label] = int(club["id"])
        if not tournament_club_values:
            tournament_club_values = ["1 - Clube padrao (Clube)"]
            tournament_club_map[tournament_club_values[0]] = 1
        tournament_club_option = form_general.select("Clube/Escola", tournament_club_values)
        selected_tournament_club = next(
            (
                label
                for label, club_id in tournament_club_map.items()
                if club_id == int(tournament.get("club_id") or 1)
            ),
            tournament_club_values[0],
        )
        tournament_club_option.set(selected_tournament_club)

        tournament_class_map: dict[str, int | None] = {"Sem turma": None}
        tournament_class_option = form_general.select("Turma", ["Sem turma"])

        def load_tournament_class_options(club_id: int | None, selected_id: int | None = None) -> None:
            tournament_class_map.clear()
            tournament_class_map["Sem turma"] = None
            values = ["Sem turma"]
            if club_id:
                for class_data in self.db.list_classes(club_id=club_id, active_only=True):
                    label = f"{class_data['id']} - {class_data['name']}"
                    values.append(label)
                    tournament_class_map[label] = int(class_data["id"])
            tournament_class_option.configure(values=values)
            chosen = next(
                (label for label, class_id in tournament_class_map.items() if class_id == selected_id),
                "Sem turma",
            )
            tournament_class_option.set(chosen)

        def refresh_tournament_scope_state(_value: str | None = None) -> None:
            scope = TOURNAMENT_SCOPE_VALUES[scope_option.get()]
            club_state = "normal" if scope in {"club", "class"} else "disabled"
            class_state = "normal" if scope == "class" else "disabled"
            tournament_club_option.configure(state=club_state)
            tournament_class_option.configure(state=class_state)

        def on_tournament_club_change(_value: str) -> None:
            load_tournament_class_options(tournament_club_map.get(tournament_club_option.get()), None)

        scope_option.configure(command=refresh_tournament_scope_state)
        tournament_club_option.configure(command=on_tournament_club_change)
        load_tournament_class_options(
            tournament_club_map.get(tournament_club_option.get()),
            tournament.get("class_id"),
        )
        refresh_tournament_scope_state()

        # ------------------------------------------------------------------ #
        # Aba 2 - Dados oficiais (campos para exportacao/identificacao + taxas)
        # ------------------------------------------------------------------ #
        # Dezesseis campos numa coluna so: quatro secoes, porque quem preenche
        # "Taxa rating CBX" nao esta na mesma tarefa de quem preenche "FIDE
        # Event-ID" — e a exportacao oficial cobra os tres primeiros grupos.
        setting_entries: dict[str, Any] = {}
        official_sections: list[tuple[str, list[tuple[str, str, str]]]] = [
            (
                "Identificação oficial",
                [
                    ("fide_event_id", "FIDE Event-ID", "Ex.: 123456"),
                    ("federation", "Federação", "Ex.: BRA"),
                    ("state", "Estado", "Ex.: SP"),
                    ("categories", "Categorias", "Ex.: Absoluto, Sub-18"),
                ],
            ),
            (
                "Organização",
                [
                    ("organizer", "Organizador", "Ex.: Federação Paulista"),
                    ("director", "Diretor do torneio", "Nome do diretor"),
                    ("chief_arbiter", "Árbitro principal", "Nome do árbitro"),
                    ("arbiters", "Árbitros auxiliares", "Nomes separados por vírgula"),
                ],
            ),
            (
                "Contato e divulgação",
                [
                    ("website", "Página web", "https://..."),
                    ("contact_email", "E-mail", "contato@exemplo.com"),
                    ("comments", "Comentários", "Observações do torneio"),
                ],
            ),
            (
                "Prazos e taxas",
                [
                    ("cutoff_date", "Data de corte", "aaaa-mm-dd"),
                    ("late_entry_points", "Pontos por adesão tardia", "Ex.: 0"),
                    ("rating_fee_fide", "Taxa rating FIDE por inscrito", "Ex.: 2,50"),
                    ("rating_fee_cbx", "Taxa rating CBX por inscrito", "Ex.: 3,00"),
                    ("rating_fee_lbx", "Taxa rating LBX por inscrito", "Ex.: 1,25"),
                ],
            ),
        ]
        for titulo, campos in official_sections:
            form_official.section(titulo)
            for key, label, dica in campos:
                entry = form_official.text(label, placeholder=dica)
                value = settings.get(key)
                entry.insert(0, "" if value is None else str(value))
                setting_entries[key] = entry

        # ------------------------------------------------------------------ #
        # Regulamento de rating (FED-07)
        # ------------------------------------------------------------------ #
        # O ritmo decide a LISTA de rating usada (standard, rápido ou blitz) e o
        # perfil do regulamento. Vazio = deduzir do campo Ritmo da aba anterior.
        form_official.section("Rating")
        rating_speed_option = form_official.select(
            "Ritmo para rating", list(RATING_SPEED_LABELS.values())
        )
        rating_speed_option.set(
            RATING_SPEED_LABELS.get(
                str(settings.get("rating_speed") or ""), RATING_SPEED_LABELS[""]
            )
        )

        # O regulamento da CBX não está publicado em formato que o programa
        # consiga ler. Em vez de fingir que sabe, o perfil sai editável: o que o
        # árbitro preencher aqui vale, e o relatório diz que veio daqui.
        rating_regulation_entries: dict[str, Any] = {}
        saved_overrides = parse_regulation_overrides(settings.get("rating_regulation")).get("cbx", {})
        form_official.section("Regulamento CBX (conferir no texto vigente)")
        for key, label, dica in RATING_REGULATION_FIELDS:
            entry = form_official.text(label, placeholder=dica)
            value = saved_overrides.get(key)
            entry.insert(0, "" if value in (None, "") else str(value))
            rating_regulation_entries[key] = entry

        # ------------------------------------------------------------------ #
        # Aba 3 - Regras e desempates
        # ------------------------------------------------------------------ #
        initial_order_by_label = {label: value for value, label in INITIAL_ORDER_OPTIONS.items()}
        profile_by_label = {label: value for value, label in TOURNAMENT_PROFILES.items()}
        type_by_label = {label: value for value, label in TOURNAMENT_TYPES.items()}
        pairing_by_label = {label: value for value, label in PAIRING_METHODS.items()}
        system_by_label = {label: value for value, label in PAIRING_SYSTEMS.items()}
        tiebreak_engine_by_label = {label: value for value, label in TIEBREAK_ENGINES.items()}
        team_pairing_by_label = {label: value for value, label in TEAM_PAIRING_METHODS.items()}
        team_criterion_by_label = {label: value for value, label in TEAM_STANDING_CRITERIA.items()}
        acceleration_by_label = {label: value for value, label in ACCELERATION_METHODS.items()}

        form_rules.section("Emparceiramento")
        initial_order_option = form_rules.select("Ordem inicial", list(initial_order_by_label.keys()))
        initial_order_option.set(
            INITIAL_ORDER_OPTIONS.get(settings.get("initial_order", "rating"), INITIAL_ORDER_OPTIONS["rating"])
        )

        tournament_profile_option = form_rules.select("Perfil do torneio", list(profile_by_label.keys()))
        tournament_profile_option.set(
            TOURNAMENT_PROFILES.get(settings.get("tournament_profile", "free"), TOURNAMENT_PROFILES["free"])
        )

        tournament_type_option = form_rules.select("Tipo de torneio", list(type_by_label.keys()))
        tournament_type_option.set(
            TOURNAMENT_TYPES.get(settings.get("tournament_type", "real"), TOURNAMENT_TYPES["real"])
        )

        pairing_option = form_rules.select(
            "Sistema de emparceiramento", list(pairing_by_label.keys())
        )
        pairing_option.set(PAIRING_METHODS.get(settings.get("pairing_method", "swiss"), PAIRING_METHODS["swiss"]))

        system_option = form_rules.select(
            "Motor/Regra de emparceiramento", list(system_by_label.keys())
        )
        system_option.set(
            PAIRING_SYSTEMS.get(
                settings.get("pairing_system", "gacrux_swiss"),
                PAIRING_SYSTEMS["gacrux_swiss"],
            )
        )

        tiebreak_engine_option = form_rules.select(
            "Motor de desempate (classificação)",
            list(tiebreak_engine_by_label.keys()),
            help_text=LEGACY_ENGINE_CHOICE_HINT,
        )
        tiebreak_engine_option.set(
            TIEBREAK_ENGINES.get(
                settings.get("tiebreak_engine", "gacrux"),
                TIEBREAK_ENGINES["gacrux"],
            )
        )

        # Pontuacao/criterios por equipes (campos textuais + menus). A secao
        # inteira so vale para o formato "Equipes" — e por isso ela e uma
        # secao, e nao um bloco de campos perdido no meio das regras gerais.
        form_rules.section(
            "Por equipes",
            help_text="Vale apenas quando o Formato (aba “Dados gerais”) é “Equipes”.",
        )
        # Politica de bye SOLICITADO (ARB-04). Vazio ou 0 = sem limite, que e o
        # comportamento de sempre. Fica antes da secao de equipes porque vale
        # para o individual, que e onde o bye solicitado existe.
        # A linha de apoio quebra à mão: `note()` monta um CTkLabel sem
        # `wraplength`, então um texto longo numa linha só alarga o painel e
        # empurra os controles para fora da janela nos tamanhos suportados —
        # o teste de layout pega exatamente isso.
        form_rules.section(
            "Byes solicitados",
            help_text=(
                "Limites do regulamento para o bye que o jogador PEDE (0 = sem limite).\n"
                "Não confunda com “Desativar bye alocado (PAB)”, que é o bye\n"
                "dado a quem sobra num número ímpar."
            ),
        )
        for key, label, dica in (
            ("max_requested_byes", "Máximo de byes por jogador", "0 = sem limite"),
            ("last_requested_bye_round", "Última rodada com bye permitido", "0 = sem limite"),
        ):
            entry = form_rules.text(label, placeholder=dica)
            entry.insert(0, str(settings.get(key, 0) or 0))
            setting_entries[key] = entry

        team_setting_fields = [
            ("team_boards_count", "Tabuleiros por equipe", "Ex.: 4"),
            ("team_match_win_points", "Pontos por vitória da equipe", "Ex.: 2"),
            ("team_match_draw_points", "Pontos por empate da equipe", "Ex.: 1"),
            ("team_match_loss_points", "Pontos por derrota da equipe", "Ex.: 0"),
        ]
        for key, label, dica in team_setting_fields:
            entry = form_rules.text(label, placeholder=dica)
            value = settings.get(key)
            entry.insert(0, "" if value is None else str(value))
            setting_entries[key] = entry

        team_pairing_option = form_rules.select("Método por equipes", list(team_pairing_by_label.keys()))
        team_pairing_option.set(
            TEAM_PAIRING_METHODS.get(settings.get("team_pairing_method", "swiss"), TEAM_PAIRING_METHODS["swiss"])
        )

        team_primary_option = form_rules.select(
            "Critério principal por equipes", list(team_criterion_by_label.keys())
        )
        team_primary_option.set(
            TEAM_STANDING_CRITERIA.get(
                settings.get("team_standing_primary", "match_points"),
                TEAM_STANDING_CRITERIA["match_points"],
            )
        )

        team_secondary_option = form_rules.select(
            "Critério secundário por equipes", list(team_criterion_by_label.keys())
        )
        team_secondary_option.set(
            TEAM_STANDING_CRITERIA.get(
                settings.get("team_standing_secondary", "game_points"),
                TEAM_STANDING_CRITERIA["game_points"],
            )
        )

        team_fixed_board_order_check = ctk.CTkCheckBox(tab_rules, text="Manter ordem fixa dos tabuleiros")
        form_rules.widget(team_fixed_board_order_check)
        if settings.get("team_fixed_board_order", 1):
            team_fixed_board_order_check.select()

        flag_labels = {
            "allow_public_registration": "Permitir inscricao publica",
            "allow_player_result_edit": "Jogador pode alterar resultado",
            "allow_dangerous_changes": "Permitir mudancas perigosas",
            # `disable_bye` desativa o bye ALOCADO (o PAB de quem sobra num numero
            # impar). O bye SOLICITADO — o jogador avisando que faltaria — tem
            # politica propria (ARB-04) e nao passa por aqui.
            "disable_bye": "Desativar bye alocado (PAB)",
            # So tem efeito no formato "Schuring (Todos contra todos)": o
            # calendario roda duas vezes, com as cores invertidas na volta.
            "round_robin_double": "Returno no todos contra todos (turno e returno)",
            # So tem efeito no formato "Mata-mata": os dois perdedores da
            # semifinal jogam pelo 3o lugar, na mesma rodada da final.
            "knockout_third_place": "Disputa de 3o lugar no mata-mata",
            "accelerated_system": "Sistema acelerado",
            "hide_standings": "Ocultar classificacao",
            "calculate_performance": "Calcular desempenho do jogador",
            "hide_color_names": "Ocultar nomes de cores",
            "show_opponents_in_standings": "Mostrar adversarios na classificacao",
            "tiebreak_strict": "Falhar em vez de degradar (motor de desempate)",
            "archived": "Arquivado",
        }
        flag_checks: dict[str, ctk.CTkCheckBox] = {}
        form_rules.section("Permissões e visibilidade")
        for key in sorted(TOURNAMENT_FLAG_FIELDS):
            checkbox = ctk.CTkCheckBox(tab_rules, text=flag_labels.get(key, key))
            form_rules.widget(checkbox)
            if settings.get(key):
                checkbox.select()
            flag_checks[key] = checkbox

        current_spec = acceleration_spec(settings.get("acceleration_method", "none"))
        scheme_to_key = {"none": "none", "classic": "accelerated", "custom": "custom", "baku": "baku"}
        current_accel_key = scheme_to_key.get(current_spec.get("scheme", "none"), "none")

        form_rules.section("Aceleração (TRF25 reg. 250)")
        acceleration_option = form_rules.select("Método", list(acceleration_by_label.keys()))
        acceleration_option.set(ACCELERATION_METHODS.get(current_accel_key, ACCELERATION_METHODS["none"]))

        custom_frame = ctk.CTkFrame(tab_rules, fg_color="transparent")
        form_rules.widget(custom_frame)
        accel_custom_entries: dict[str, ctk.CTkEntry] = {}
        custom_defaults = {
            "rounds": str(int(current_spec.get("round_count", 2) or 2)),
            "bonus": str(float(current_spec.get("bonus", 1.0) or 1.0)),
            "upper": str(float(current_spec.get("upper_fraction", 0.5) or 0.5)),
        }
        custom_labels = [
            ("rounds", "Rodadas aceleradas"),
            ("bonus", "Bônus por jogador"),
            ("upper", "Fracao do topo (0-1)"),
        ]
        for column, (key, label) in enumerate(custom_labels):
            custom_frame.grid_columnconfigure(column, weight=1)
            ctk.CTkLabel(custom_frame, text=label).grid(
                row=0, column=column, padx=(0 if column == 0 else 8, 0), pady=(0, 2), sticky="w"
            )
            entry = ctk.CTkEntry(custom_frame, width=110)
            entry.grid(row=1, column=column, padx=(0 if column == 0 else 8, 0), pady=(0, 4), sticky="ew")
            entry.insert(0, custom_defaults[key])
            accel_custom_entries[key] = entry

        def refresh_accel_state() -> None:
            is_custom = acceleration_by_label.get(acceleration_option.get()) == "custom"
            for entry in accel_custom_entries.values():
                entry.configure(state="normal" if is_custom else "disabled")

        acceleration_option.configure(command=lambda _value: refresh_accel_state())
        refresh_accel_state()

        # Sequencia salva -> codigos + parametros por criterio (TBK-04). Antes so
        # os codigos chegavam ao editor, e por isso o corte configurado sumia ao
        # reabrir a tela.
        sequencia_individual = parse_player_tiebreak_sequence(settings.get("tiebreak_sequence"))
        initial_tiebreak_codes = [item["code"] for item in sequencia_individual]
        tiebreak_editor = TiebreakSequenceEditor(
            tab_rules,
            PLAYER_TIEBREAKS,
            DEFAULT_PLAYER_TIEBREAKS,
            initial_tiebreak_codes,
            {item["code"]: item.get("params", {}) for item in sequencia_individual},
        )
        stack(
            tab_rules,
            tiebreak_editor,
            label="Desempates (individual)",
            section=True,
            help_text=(
                "Ordem aplicada após os pontos. Pontos é sempre o primeiro critério;\n"
                "rating e nome são os critérios técnicos finais."
            ),
        )

        sequencia_equipes = parse_team_tiebreak_sequence(settings.get("team_tiebreak_sequence"))
        initial_team_tiebreak_codes = [item["code"] for item in sequencia_equipes]
        team_tiebreak_editor = TiebreakSequenceEditor(
            tab_rules,
            TEAM_TIEBREAKS,
            DEFAULT_TEAM_TIEBREAKS,
            initial_team_tiebreak_codes,
            {item["code"]: item.get("params", {}) for item in sequencia_equipes},
        )
        stack(
            tab_rules,
            team_tiebreak_editor,
            label="Desempates por equipes",
            section=True,
            help_text="Ordem dos critérios para a classificação por equipes (vazio = match points, game points, Buchholz, vitórias).",
        )

        # Campos especificos de equipes ficam habilitados apenas quando o
        # Formato (aba "Dados gerais") e "Equipes".
        team_only_widgets = [
            setting_entries["team_boards_count"],
            setting_entries["team_match_win_points"],
            setting_entries["team_match_draw_points"],
            setting_entries["team_match_loss_points"],
            team_pairing_option,
            team_primary_option,
            team_secondary_option,
            team_fixed_board_order_check,
        ]

        def refresh_team_fields_state(_value: str | None = None) -> None:
            is_team = competition_by_label.get(competition_option.get()) == "team"
            state = "normal" if is_team else "disabled"
            for widget in team_only_widgets:
                try:
                    widget.configure(state=state)
                except Exception:
                    pass

        competition_option.configure(command=refresh_team_fields_state)
        refresh_team_fields_state()

        # ------------------------------------------------------------------ #
        # Aba 4 - Premiacao
        # ------------------------------------------------------------------ #
        form_prizes = form_of(tab_prizes)
        form_prizes.section("Resumo")
        prize_text_entry = form_prizes.text(
            "Premiação (texto livre)", placeholder="Ex.: 1º R$ 500, 2º R$ 300"
        )
        prize_text_value = settings.get("prizes")
        prize_text_entry.insert(0, "" if prize_text_value is None else str(prize_text_value))
        setting_entries["prizes"] = prize_text_entry

        prize_controls = ctk.CTkFrame(tab_prizes, fg_color="transparent")
        prize_policy_by_label = {label: value for value, label in PRIZE_POLICIES.items()}
        ctk.CTkLabel(prize_controls, text="Política").grid(row=0, column=0, padx=(0, 4), sticky="w")
        prize_policy_option = ctk.CTkOptionMenu(prize_controls, values=list(prize_policy_by_label.keys()), width=240)
        prize_policy_option.grid(row=0, column=1, padx=(0, 16))
        prize_policy_option.set(
            PRIZE_POLICIES.get(settings.get("prize_policy", "best_only"), PRIZE_POLICIES["best_only"])
        )
        ctk.CTkLabel(prize_controls, text="Imposto %").grid(row=0, column=2, padx=(0, 4), sticky="w")
        prize_tax_entry = ctk.CTkEntry(prize_controls, width=80)
        prize_tax_entry.grid(row=0, column=3)
        prize_tax_entry.insert(0, str(settings.get("prize_tax_percent", 0.0) or 0.0))
        stack(tab_prizes, prize_controls, label="Distribuição de prêmios", section=True)

        category_editor = CategoryEditor(
            tab_prizes, self.db.list_tournament_categories(self.current_tournament_id)
        )
        stack(
            tab_prizes,
            category_editor,
            label="Categorias do torneio",
            section=True,
            # Linhas curtas de proposito: rotulo longo puxa a largura minima da
            # tela inteira (B-8), e foi assim que esta secao estourou a janela
            # de 800px na primeira versao.
            help_text=(
                "Sem linhas, valem as faixas padrão.\n"
                "Idade: 'Até' é inclusivo (Sub-12 aceita 12).\n"
                "Rating: 'Até' é exclusivo (Sub-1400 recusa 1400)."
            ),
        )

        category_reference_entry = ctk.CTkEntry(tab_prizes, width=160)
        category_reference_entry.insert(0, str(settings.get("category_reference_date") or ""))
        stack(
            tab_prizes,
            category_reference_entry,
            label="Data de referência da idade",
            help_text=(
                "Vazio = ano do torneio.\n"
                "A idade é a que o jogador COMPLETA no ano."
            ),
        )
        setting_entries["category_reference_date"] = category_reference_entry

        prize_editor = PrizeEditor(tab_prizes, self.db.list_tournament_prizes(self.current_tournament_id))
        stack(
            tab_prizes,
            prize_editor,
            help_text=(
                "Política e imposto são salvos junto com 'Salvar'.\n"
                "Geral/Categoria são distribuídos automaticamente; Especial/Tabuleiro entram como manuais."
            ),
        )

        # ------------------------------------------------------------------ #
        # Aba 5 - Classificacao e agenda
        # ------------------------------------------------------------------ #
        standings_layout = self.list_layout_service.get_columns(self.current_tournament_id, "standings")
        columns_editor = ColumnLayoutEditor(
            tab_reports, STANDINGS_COLUMNS, DEFAULT_STANDINGS_COLUMNS, standings_layout["selected"]
        )
        stack(
            tab_reports,
            columns_editor,
            label="Colunas da classificação",
            section=True,
            help_text="Escolha, ordene e ajuste a largura das colunas da classificação (largura vazia = automática; vazio = padrão).",
        )

        schedule_panel = ctk.CTkFrame(tab_reports, fg_color="transparent")
        schedule_panel.grid_columnconfigure(1, weight=1)
        schedule_panel.grid_columnconfigure(2, weight=1)
        stack(tab_reports, schedule_panel, label="Datas e horários das rodadas", section=True)

        existing_schedule = self.db.list_round_schedule(self.current_tournament_id)
        first_schedule_date = next((str(item.get("date") or "") for item in existing_schedule if item.get("date")), "")
        first_schedule_time = next((str(item.get("time") or "") for item in existing_schedule if item.get("time")), "")
        generator_frame = ctk.CTkFrame(schedule_panel, fg_color="transparent")
        generator_frame.grid(row=0, column=0, columnspan=3, padx=0, pady=(0, 8), sticky="ew")
        for column in range(5):
            generator_frame.grid_columnconfigure(column, weight=1)

        auto_fields = [
            ("start_date", "Data inicial", str(tournament.get("start_date") or first_schedule_date or Database.now()[:10]), 130),
            ("first_time", "Hora inicial", first_schedule_time or "08:00", 95),
            ("rounds_per_day", "Rodadas/dia", str(tournament.get("rounds_count") or len(existing_schedule) or 1), 100),
            ("duration", "Duração min", "45", 95),
            ("break", "Intervalo min", "15", 95),
        ]
        auto_entries: dict[str, ctk.CTkEntry] = {}
        for column, (key, label, value, width) in enumerate(auto_fields):
            ctk.CTkLabel(generator_frame, text=label).grid(
                row=0, column=column, padx=(0 if column == 0 else 8, 0), pady=(0, 2), sticky="w"
            )
            if key == "start_date":
                entry = self._make_date_entry(generator_frame, width=15)
            else:
                entry = ctk.CTkEntry(generator_frame, width=width)
            entry.grid(row=1, column=column, padx=(0 if column == 0 else 8, 0), pady=(0, 6), sticky="ew")
            entry.insert(0, value)
            auto_entries[key] = entry

        all_same_day_check = ctk.CTkCheckBox(generator_frame, text="Todas no mesmo dia")
        all_same_day_check.grid(row=2, column=0, columnspan=2, pady=(2, 0), sticky="w")
        all_same_day_check.select()

        def refresh_auto_rounds_state() -> None:
            auto_entries["rounds_per_day"].configure(state="disabled" if all_same_day_check.get() else "normal")

        all_same_day_check.configure(command=refresh_auto_rounds_state)
        refresh_auto_rounds_state()

        ctk.CTkLabel(schedule_panel, text="Rodada").grid(row=1, column=0, padx=0, sticky="w")
        ctk.CTkLabel(schedule_panel, text="Data").grid(row=1, column=1, padx=8, sticky="w")
        ctk.CTkLabel(schedule_panel, text="Hora").grid(row=1, column=2, padx=8, sticky="w")

        schedule_entries: dict[int, tuple[ctk.CTkEntry, ctk.CTkEntry]] = {}
        for row_index, item in enumerate(existing_schedule, start=2):
            round_number = int(item["round_number"])
            ctk.CTkLabel(schedule_panel, text=str(round_number)).grid(
                row=row_index, column=0, padx=0, pady=(4, 0), sticky="w"
            )
            date_entry = self._make_date_entry(schedule_panel, width=20)
            date_entry.grid(row=row_index, column=1, padx=8, pady=(4, 0), sticky="ew")
            date_entry.insert(0, str(item.get("date") or ""))
            time_entry = ctk.CTkEntry(schedule_panel, width=140)
            time_entry.grid(row=row_index, column=2, padx=(8, 0), pady=(4, 0), sticky="ew")
            time_entry.insert(0, str(item.get("time") or ""))
            schedule_entries[round_number] = (date_entry, time_entry)

        def apply_auto_schedule() -> None:
            try:
                rounds_count = int(tournament_entries["rounds_count"].get() or tournament.get("rounds_count") or 1)
                rounds_per_day = rounds_count if all_same_day_check.get() else auto_entries["rounds_per_day"].get()
                generated_schedule = self.tournament_service.generate_round_schedule(
                    rounds_count=rounds_count,
                    start_date=auto_entries["start_date"].get(),
                    first_time=auto_entries["first_time"].get(),
                    round_duration_minutes=auto_entries["duration"].get(),
                    break_minutes=auto_entries["break"].get(),
                    rounds_per_day=rounds_per_day,
                )
                for item in generated_schedule:
                    entries = schedule_entries.get(int(item["round_number"]))
                    if not entries:
                        continue
                    entries[0].delete(0, "end")
                    entries[0].insert(0, str(item["date"]))
                    entries[1].delete(0, "end")
                    entries[1].insert(0, str(item["time"]))
            except Exception as exc:
                self._show_error(exc)

        btn_auto = ctk.CTkButton(generator_frame, text="Preencher agenda", command=apply_auto_schedule)
        btn_auto.grid(row=2, column=4, padx=(8, 0), pady=(2, 0), sticky="e")
        self._disable_if_unauthorized(btn_auto, "tournament_write")

        # ------------------------------------------------------------------ #
        # Coleta dos campos e persistencia
        # ------------------------------------------------------------------ #
        def profile_payloads() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
            tournament_payload = {key: entry.get() for key, entry in tournament_entries.items()}
            settings_payload = {key: entry.get() for key, entry in setting_entries.items()}

            # Validacao client-side: destaca o campo invalido antes de persistir.
            # Estado de campo unico desde a F5.3 — esta tela guardava a terceira
            # copia da mesma ideia (borda salva a mao, sem mensagem no campo).
            def _reset_border(entry: Any) -> None:
                clear_field_error(entry)

            def _flag_invalid(entry: Any, message: str) -> None:
                set_field_error(entry, message)
                raise AppError(message)

            def _parse_date(value: str) -> datetime | None:
                value = (value or "").strip()
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                    try:
                        return datetime.strptime(value, fmt)
                    except ValueError:
                        continue
                return None

            for _vkey in ("rounds_count", "start_date", "end_date", "bye_points"):
                _reset_border(tournament_entries[_vkey])

            rounds_raw = str(tournament_payload.get("rounds_count", "")).strip()
            if not rounds_raw.isdigit() or int(rounds_raw) < 1:
                _flag_invalid(
                    tournament_entries["rounds_count"],
                    "Informe um numero de rodadas inteiro maior ou igual a 1.",
                )

            # Alerta nao-bloqueante: no Suico, rounds_count > (jogadores ativos - 1)
            # forcaria repeticao de adversario na rodada excedente. Apenas avisa
            # (borda amarela + toast) e deixa salvar: o arbitro pode ainda estar
            # cadastrando jogadores, ou usar outro formato de pareamento.
            _pairing_method = pairing_by_label.get(pairing_option.get(), "swiss")
            _n_active = len(self.db.list_players(self.current_tournament_id, active_only=True))
            _rounds_int = int(rounds_raw)
            if _pairing_method == "swiss" and _n_active >= 2 and _rounds_int > _n_active - 1:
                set_field_warning(
                    tournament_entries["rounds_count"],
                    f"Maximo sem repeticao: {_n_active - 1} rodada(s).",
                )
                self._show_toast(
                    f"Aviso: {_n_active} jogador(es) ativo(s). O maximo sem repeticao de "
                    f"adversario e {_n_active - 1} rodada(s); com {_rounds_int}, a ultima "
                    f"rodada pode nao fechar.",
                    kind="warning",
                    duration_ms=6000,
                )

            bye_raw = str(tournament_payload.get("bye_points", "")).strip().replace(",", ".")
            if bye_raw:
                try:
                    if float(bye_raw) < 0:
                        raise ValueError
                except ValueError:
                    _flag_invalid(
                        tournament_entries["bye_points"],
                        "Pontos do bye deve ser um numero maior ou igual a zero.",
                    )

            start_date = _parse_date(tournament_payload.get("start_date", ""))
            end_date = _parse_date(tournament_payload.get("end_date", ""))
            if start_date and end_date and start_date > end_date:
                _flag_invalid(
                    tournament_entries["end_date"],
                    "A data final nao pode ser anterior a data inicial.",
                )
            scope = TOURNAMENT_SCOPE_VALUES[scope_option.get()]
            tournament_payload["scope"] = scope
            tournament_payload["competition_type"] = competition_by_label[competition_option.get()]
            tournament_payload["club_id"] = None
            tournament_payload["class_id"] = None
            if scope in {"club", "class"}:
                tournament_payload["club_id"] = tournament_club_map.get(tournament_club_option.get())
                if not tournament_payload["club_id"]:
                    raise AppError("Selecione o clube/escola do torneio.")
            if scope == "class":
                tournament_payload["class_id"] = tournament_class_map.get(tournament_class_option.get())
                if not tournament_payload["class_id"]:
                    raise AppError("Selecione a turma do torneio.")
            settings_payload["initial_order"] = initial_order_by_label[initial_order_option.get()]
            settings_payload["tournament_profile"] = profile_by_label[tournament_profile_option.get()]
            settings_payload["tournament_type"] = type_by_label[tournament_type_option.get()]
            settings_payload["pairing_method"] = pairing_by_label[pairing_option.get()]
            settings_payload["pairing_system"] = system_by_label[system_option.get()]
            settings_payload["tiebreak_engine"] = tiebreak_engine_by_label[tiebreak_engine_option.get()]
            settings_payload["team_pairing_method"] = team_pairing_by_label[team_pairing_option.get()]
            settings_payload["team_standing_primary"] = team_criterion_by_label[team_primary_option.get()]
            settings_payload["team_standing_secondary"] = team_criterion_by_label[team_secondary_option.get()]
            settings_payload["tiebreak_sequence"] = serialize_tiebreak_sequence(tiebreak_editor.get_sequence())
            settings_payload["team_tiebreak_sequence"] = serialize_tiebreak_sequence(team_tiebreak_editor.get_sequence())
            speed_by_label = {label: value for value, label in RATING_SPEED_LABELS.items()}
            settings_payload["rating_speed"] = speed_by_label.get(rating_speed_option.get(), "")
            # Campo em branco = "vale o perfil publicado"; por isso o vazio não
            # entra no JSON, em vez de virar zero e zerar o regulamento.
            settings_payload["rating_regulation"] = {
                "cbx": {
                    key: entry.get().strip()
                    for key, entry in rating_regulation_entries.items()
                    if entry.get().strip()
                }
            }
            settings_payload["prize_policy"] = prize_policy_by_label[prize_policy_option.get()]
            settings_payload["prize_tax_percent"] = prize_tax_entry.get()
            settings_payload["team_fixed_board_order"] = team_fixed_board_order_check.get()
            accel_key = acceleration_by_label[acceleration_option.get()]
            if accel_key == "custom":
                try:
                    rounds = int(float(accel_custom_entries["rounds"].get() or 0))
                    bonus = float(accel_custom_entries["bonus"].get() or 0.0)
                    upper = float(accel_custom_entries["upper"].get() or 0.0)
                except (TypeError, ValueError):
                    raise AppError("Aceleracao personalizada: use numeros validos em rodadas, bonus e fracao do topo.")
                if rounds < 1:
                    raise AppError("Aceleracao personalizada: informe ao menos 1 rodada acelerada.")
                if bonus <= 0:
                    raise AppError("Aceleracao personalizada: o bonus por jogador deve ser maior que zero.")
                if not 0 < upper <= 1:
                    raise AppError("Aceleracao personalizada: a fracao do topo deve estar entre 0 (exclusivo) e 1.")
                settings_payload["acceleration_method"] = f"custom:rounds={rounds};bonus={bonus};upper={upper}"
            else:
                settings_payload["acceleration_method"] = accel_key
            for key, checkbox in flag_checks.items():
                settings_payload[key] = checkbox.get()
            schedule_payload = [
                {"round_number": round_number, "date": entries[0].get(), "time": entries[1].get()}
                for round_number, entries in schedule_entries.items()
            ]
            return tournament_payload, settings_payload, schedule_payload

        def save_settings(show_message: bool = True) -> None:
            try:
                tournament_payload, settings_payload, schedule_payload = profile_payloads()
                self.tournament_service.save_profile(
                    self.current_tournament_id,
                    tournament_payload,
                    settings_payload,
                    schedule_payload,
                )
                # Salvamento unificado: premios e colunas vao junto com as configuracoes.
                self.prize_service.replace_prizes(self.current_tournament_id, prize_editor.get_rows())
                self.tournament_service.replace_categories(
                    self.current_tournament_id, category_editor.get_rows()
                )
                self.list_layout_service.save_columns(
                    self.current_tournament_id, columns_editor.get_columns(), "standings"
                )
                self._set_current_tournament(self.current_tournament_id)
                if show_message:
                    self._show_toast("Configurações do torneio salvas.", kind="success")
                self.show_tournament_settings()
            except Exception as exc:
                self._show_error(exc)

        def save_as_new_tournament() -> None:
            try:
                tournament_payload, settings_payload, schedule_payload = profile_payloads()
                new_name = self._ask_string(
                    "Salvar como novo torneio",
                    "Nome do novo torneio (em branco usa o nome do formulario):",
                )
                if new_name is None:
                    return
                if new_name.strip():
                    tournament_payload["name"] = new_name.strip()
                new_tournament_id = self.tournament_service.create_tournament_from_profile(
                    tournament_payload,
                    settings_payload,
                    schedule_payload,
                )
                self._set_current_tournament(new_tournament_id)
                self._show_info("Novo torneio criado com estas configurações. Inclua ou importe os participantes.")
                self.show_tournament_settings()
            except Exception as exc:
                self._show_error(exc)

        # ------------------------------------------------------------------ #
        # Rodape fixo de acoes (visivel em todas as abas)
        # ------------------------------------------------------------------ #
        actions = ctk.CTkFrame(container, fg_color="transparent")
        actions.grid(row=1, column=0, pady=(10, 0), sticky="e")
        btn_save_config = ctk.CTkButton(actions, text="Salvar", command=save_settings)
        btn_save_config.pack(side="right", padx=(8, 0))
        # Enter em qualquer campo de qualquer aba salva (F5.10). As cinco abas
        # compartilham um unico rodape de acoes, entao a acao primaria e a
        # mesma para todas — e cada pilha liga o Enter dos seus campos a ela.
        for pilha in (form_general, form_official, form_rules, form_prizes, form_of(tab_reports)):
            pilha.submit(save_settings)
        self._disable_if_unauthorized(btn_save_config, "tournament_write")
        btn_save_as = ctk.CTkButton(actions, text="Salvar como novo", command=save_as_new_tournament)
        btn_save_as.pack(side="right", padx=(8, 0))
        self._disable_if_unauthorized(btn_save_as, "tournament_write")
        btn_refs = ctk.CTkButton(actions, text="Equipe de Arbitragem", command=self.show_tournament_referees_dialog)
        btn_refs.pack(side="right", padx=(8, 0))
        self._disable_if_unauthorized(btn_refs, "tournament_write")
