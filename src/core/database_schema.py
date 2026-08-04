"""DDL do schema do banco de dados Albericus.

Constantes com o SQL de criacao de tabelas e indices, extraidas de
``database.py`` para reduzir o tamanho daquele modulo. A orquestracao
(verificacao de versao de schema, migracoes e criacao de indices)
permanece em :meth:`Database.initialize`.
"""

from __future__ import annotations

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER DEFAULT 1,
    class_id INTEGER,
    competition_type TEXT NOT NULL DEFAULT 'individual',
    name TEXT NOT NULL,
    location TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    system TEXT NOT NULL DEFAULT 'Suico',
    rounds_count INTEGER NOT NULL DEFAULT 5,
    time_control TEXT DEFAULT '',
    bye_points REAL NOT NULL DEFAULT 1.0,
    status TEXT NOT NULL DEFAULT 'draft',
    parent_tournament_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE SET NULL,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS clubs (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'club',
    city TEXT DEFAULT '',
    address TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learning_levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    display_order INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER DEFAULT 1,
    learning_level_id INTEGER,
    name TEXT NOT NULL,
    surname TEXT DEFAULT '',
    city TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    document TEXT DEFAULT '',
    birth_date TEXT DEFAULT '',
    rating INTEGER NOT NULL DEFAULT 0,
    category TEXT DEFAULT '',
    age_category TEXT DEFAULT '',
    rating_category TEXT DEFAULT '',
    prize_tags TEXT DEFAULT '',
    member_type TEXT NOT NULL DEFAULT 'socio',
    status TEXT NOT NULL DEFAULT 'active',
    guardian_name TEXT DEFAULT '',
    guardian_phone TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    lichess_username TEXT DEFAULT '',
    chesscom_username TEXT DEFAULT '',
    online_blitz_rating INTEGER DEFAULT 0,
    online_rapid_rating INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE SET NULL,
    FOREIGN KEY (learning_level_id) REFERENCES learning_levels(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS guardians (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    document TEXT DEFAULT '',
    address TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS member_guardians (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    guardian_id INTEGER NOT NULL,
    relationship TEXT DEFAULT '',
    primary_contact INTEGER NOT NULL DEFAULT 0,
    emergency_contact INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (member_id, guardian_id),
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (guardian_id) REFERENCES guardians(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    teacher TEXT DEFAULT '',
    weekday TEXT DEFAULT '',
    time TEXT DEFAULT '',
    location TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS member_class_enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (member_id, class_id),
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exercise_library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER DEFAULT 1,
    learning_level_id INTEGER,
    title TEXT NOT NULL,
    theme TEXT DEFAULT '',
    difficulty TEXT NOT NULL DEFAULT 'basic',
    source TEXT DEFAULT '',
    fen TEXT DEFAULT '',
    pgn TEXT DEFAULT '',
    solution TEXT DEFAULT '',
    objective TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE SET NULL,
    FOREIGN KEY (learning_level_id) REFERENCES learning_levels(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS training_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER DEFAULT 1,
    class_id INTEGER,
    learning_level_id INTEGER,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    target_date TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE SET NULL,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL,
    FOREIGN KEY (learning_level_id) REFERENCES learning_levels(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS training_list_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL,
    position_order INTEGER NOT NULL DEFAULT 1,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (list_id, exercise_id),
    UNIQUE (list_id, position_order),
    FOREIGN KEY (list_id) REFERENCES training_lists(id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES exercise_library(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS training_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER DEFAULT 1,
    class_id INTEGER,
    training_list_id INTEGER,
    title TEXT NOT NULL,
    session_type TEXT NOT NULL DEFAULT 'aula',
    session_date TEXT DEFAULT '',
    start_time TEXT DEFAULT '',
    end_time TEXT DEFAULT '',
    instructor TEXT DEFAULT '',
    location TEXT DEFAULT '',
    learning_level_id INTEGER,
    objective TEXT DEFAULT '',
    content TEXT DEFAULT '',
    homework TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'planned',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE SET NULL,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL,
    FOREIGN KEY (training_list_id) REFERENCES training_lists(id) ON DELETE SET NULL,
    FOREIGN KEY (learning_level_id) REFERENCES learning_levels(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'present',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (session_id, member_id),
    FOREIGN KEY (session_id) REFERENCES training_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exercise_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    list_id INTEGER,
    session_id INTEGER,
    attempt_date TEXT DEFAULT '',
    result TEXT NOT NULL DEFAULT 'attempted',
    score REAL NOT NULL DEFAULT 0.0,
    time_seconds INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (exercise_id) REFERENCES exercise_library(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (list_id) REFERENCES training_lists(id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES training_sessions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS membership_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0.0,
    billing_cycle TEXT NOT NULL DEFAULT 'monthly',
    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    plan_id INTEGER,
    description TEXT DEFAULT '',
    reference_period TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_date TEXT DEFAULT '',
    amount REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'pending',
    method TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES membership_plans(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS club_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER DEFAULT 1,
    tournament_id INTEGER,
    title TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'other',
    event_date TEXT DEFAULT '',
    start_time TEXT DEFAULT '',
    end_time TEXT DEFAULT '',
    location TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'planned',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE SET NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER DEFAULT 1,
    code TEXT DEFAULT '',
    name TEXT NOT NULL,
    item_type TEXT NOT NULL DEFAULT 'other',
    quantity_total INTEGER NOT NULL DEFAULT 1,
    condition_status TEXT NOT NULL DEFAULT 'good',
    storage_location TEXT DEFAULT '',
    acquisition_date TEXT DEFAULT '',
    acquisition_value REAL NOT NULL DEFAULT 0.0,
    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS inventory_loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    loan_date TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    return_date TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (item_id) REFERENCES inventory_items(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inventory_maintenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    opened_date TEXT DEFAULT '',
    resolved_date TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    description TEXT NOT NULL DEFAULT '',
    cost REAL NOT NULL DEFAULT 0.0,
    vendor TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (item_id) REFERENCES inventory_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    member_id INTEGER,
    name TEXT NOT NULL,
    surname TEXT DEFAULT '',
    given_name TEXT DEFAULT '',
    title TEXT DEFAULT '',
    sex TEXT DEFAULT '',
    club TEXT DEFAULT '',
    federation_id TEXT DEFAULT '',
    fide_id TEXT DEFAULT '',
    cbx_id TEXT DEFAULT '',
    lbx_id TEXT DEFAULT '',
    rating INTEGER NOT NULL DEFAULT 0,
    national_rating INTEGER NOT NULL DEFAULT 0,
    international_rating INTEGER NOT NULL DEFAULT 0,
    -- Ratings por ritmo (FED-07). O snapshot da lista oficial ja guardava os
    -- tres; o jogador do torneio so tinha um, e por isso um torneio de rapidas
    -- calculava variacao contra a lista de standard.
    rapid_rating INTEGER NOT NULL DEFAULT 0,
    blitz_rating INTEGER NOT NULL DEFAULT 0,
    -- Partidas ja ratadas do jogador. `0` e DESCONHECIDO, nao estreante: a
    -- coluna nasce vazia para todo mundo, e tratar isso como estreia daria
    -- K = 40 ao plantel inteiro.
    games_played INTEGER NOT NULL DEFAULT 0,
    category TEXT DEFAULT '',
    age_category TEXT DEFAULT '',
    rating_category TEXT DEFAULT '',
    -- Todas as categorias premiaveis do jogador, separadas por `; ` (ORG-01).
    -- `category` continua sendo a PRINCIPAL: um Sub-12 que tambem e Sub-1400 e
    -- Feminino concorre aos tres, e antes so a principal existia.
    categories TEXT DEFAULT '',
    prize_tags TEXT DEFAULT '',
    birth_date TEXT DEFAULT '',
    player_status TEXT NOT NULL DEFAULT 'active',
    starting_points REAL NOT NULL DEFAULT 0.0,
    k_factor INTEGER,
    scheveningen_group TEXT NOT NULL DEFAULT '',
    -- Numero dentro do grupo (PAR-03). Com o grupo, e a ESCALA do Scheveningen:
    -- fixa desde a primeira rodada, para que uma desistencia no meio nao
    -- desloque os confrontos que ainda faltam.
    scheveningen_number INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'generated',
    pairing_engine_version TEXT NOT NULL DEFAULT 'albericus-swiss-1',
    ruleset_version TEXT NOT NULL DEFAULT 'albericus-2026-phase0',
    created_at TEXT NOT NULL,
    closed_at TEXT DEFAULT '',
    UNIQUE (tournament_id, number),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pairings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,
    board_number INTEGER NOT NULL,
    white_player_id INTEGER NOT NULL,
    black_player_id INTEGER,
    result TEXT DEFAULT '',
    is_bye INTEGER NOT NULL DEFAULT 0,
    -- Mesa adiada (ARB-02): partida que nao sera disputada agora e cuja
    -- pendencia e ESPERADA. Sem a marca, uma mesa adiada e uma mesa esquecida
    -- sao a mesma linha em branco no painel, e o arbitro nao tem como saber se
    -- esta cobrando alguem ou aguardando o combinado.
    postponed INTEGER NOT NULL DEFAULT 0,
    postponed_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (white_player_id) REFERENCES players(id) ON DELETE CASCADE,
    FOREIGN KEY (black_player_id) REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    club TEXT DEFAULT '',
    captain TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (tournament_id, name),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS team_players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    board_number INTEGER,
    role TEXT NOT NULL DEFAULT 'starter',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (team_id, player_id),
    UNIQUE (team_id, board_number),
    UNIQUE (player_id),
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS team_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,
    match_number INTEGER NOT NULL,
    white_team_id INTEGER NOT NULL,
    black_team_id INTEGER,
    result TEXT DEFAULT '',
    white_match_points REAL NOT NULL DEFAULT 0.0,
    black_match_points REAL NOT NULL DEFAULT 0.0,
    white_game_points REAL NOT NULL DEFAULT 0.0,
    black_game_points REAL NOT NULL DEFAULT 0.0,
    is_bye INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (round_id, match_number),
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (white_team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (black_team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS team_boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_match_id INTEGER NOT NULL,
    board_number INTEGER NOT NULL,
    white_player_id INTEGER,
    black_player_id INTEGER,
    result TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (team_match_id, board_number),
    FOREIGN KEY (team_match_id) REFERENCES team_matches(id) ON DELETE CASCADE,
    FOREIGN KEY (white_player_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (black_player_id) REFERENCES players(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS team_lineups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_id INTEGER NOT NULL,
    team_match_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'approved',
    submitted_at TEXT DEFAULT '',
    approved_at TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (round_id, team_match_id, team_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (team_match_id) REFERENCES team_matches(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS team_lineup_boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lineup_id INTEGER NOT NULL,
    board_number INTEGER NOT NULL,
    player_id INTEGER,
    color TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'starter',
    created_at TEXT NOT NULL,
    UNIQUE (lineup_id, board_number),
    FOREIGN KEY (lineup_id) REFERENCES team_lineups(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS team_substitution_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_id INTEGER NOT NULL,
    team_match_id INTEGER NOT NULL,
    team_board_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    board_number INTEGER NOT NULL,
    color TEXT NOT NULL,
    out_player_id INTEGER,
    in_player_id INTEGER NOT NULL,
    reason TEXT DEFAULT '',
    requires_correction INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (team_match_id) REFERENCES team_matches(id) ON DELETE CASCADE,
    FOREIGN KEY (team_board_id) REFERENCES team_boards(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (out_player_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (in_player_id) REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tournament_settings (
    tournament_id INTEGER PRIMARY KEY,
    fide_event_id TEXT DEFAULT '',
    organizer TEXT DEFAULT '',
    website TEXT DEFAULT '',
    contact_email TEXT DEFAULT '',
    director TEXT DEFAULT '',
    chief_arbiter TEXT DEFAULT '',
    arbiters TEXT DEFAULT '',
    federation TEXT DEFAULT '',
    state TEXT DEFAULT '',
    categories TEXT DEFAULT '',
    cutoff_date TEXT DEFAULT '',
    comments TEXT DEFAULT '',
    prizes TEXT DEFAULT '',
    initial_order TEXT NOT NULL DEFAULT 'rating',
    tournament_type TEXT NOT NULL DEFAULT 'real',
    tournament_profile TEXT NOT NULL DEFAULT 'free',
    free_mode INTEGER NOT NULL DEFAULT 0,
    allow_public_registration INTEGER NOT NULL DEFAULT 0,
    allow_player_result_edit INTEGER NOT NULL DEFAULT 0,
    allow_dangerous_changes INTEGER NOT NULL DEFAULT 0,
    disable_bye INTEGER NOT NULL DEFAULT 0,
    late_entry_points REAL NOT NULL DEFAULT 0.0,
    accelerated_system INTEGER NOT NULL DEFAULT 0,
    hide_standings INTEGER NOT NULL DEFAULT 0,
    calculate_performance INTEGER NOT NULL DEFAULT 0,
    tiebreak_sequence TEXT NOT NULL DEFAULT '',
    prize_policy TEXT NOT NULL DEFAULT 'best_only',
    prize_tax_percent REAL NOT NULL DEFAULT 0.0,
    pairing_method TEXT NOT NULL DEFAULT 'swiss',
    -- Returno do rodizio (PAR-01): o calendario roda duas vezes, com as cores
    -- invertidas na volta. E o formato padrao de torneio fechado e de norma.
    round_robin_double INTEGER NOT NULL DEFAULT 0,
    -- Disputa de 3o lugar no mata-mata (PAR-03): os dois perdedores da semifinal
    -- jogam junto com a final, na mesma rodada.
    knockout_third_place INTEGER NOT NULL DEFAULT 0,
    pairing_system TEXT NOT NULL DEFAULT 'gacrux_swiss',
    tiebreak_engine TEXT NOT NULL DEFAULT 'gacrux',
    tiebreak_strict INTEGER NOT NULL DEFAULT 0,
    -- Politica de bye SOLICITADO (ARB-04). `0` = sem limite, que e o
    -- comportamento historico. Nao confundir com `disable_bye`, que desativa o
    -- bye ALOCADO (o PAB de quem sobra num numero impar): sao coisas diferentes,
    -- e o regulamento mais comum exige numero par mas aceita ausencia avisada.
    max_requested_byes INTEGER NOT NULL DEFAULT 0,
    last_requested_bye_round INTEGER NOT NULL DEFAULT 0,
    acceleration_method TEXT NOT NULL DEFAULT 'none',
    hide_color_names INTEGER NOT NULL DEFAULT 0,
    show_opponents_in_standings INTEGER NOT NULL DEFAULT 0,
    team_boards_count INTEGER NOT NULL DEFAULT 4,
    team_match_win_points REAL NOT NULL DEFAULT 2.0,
    team_match_draw_points REAL NOT NULL DEFAULT 1.0,
    team_match_loss_points REAL NOT NULL DEFAULT 0.0,
    team_pairing_method TEXT NOT NULL DEFAULT 'swiss',
    team_standing_primary TEXT NOT NULL DEFAULT 'match_points',
    team_standing_secondary TEXT NOT NULL DEFAULT 'game_points',
    team_tiebreak_sequence TEXT NOT NULL DEFAULT '',
    team_fixed_board_order INTEGER NOT NULL DEFAULT 1,
    team_board_order_policy TEXT NOT NULL DEFAULT 'fixed',
    team_reserve_policy TEXT NOT NULL DEFAULT 'same_team',
    team_lineup_deadline TEXT DEFAULT '',
    team_rating_tolerance INTEGER NOT NULL DEFAULT 0,
    team_max_substitutions INTEGER NOT NULL DEFAULT 0,
    rating_fee_fide REAL NOT NULL DEFAULT 0.0,
    rating_fee_cbx REAL NOT NULL DEFAULT 0.0,
    rating_fee_lbx REAL NOT NULL DEFAULT 0.0,
    -- Ritmo do torneio para efeito de rating (FED-07). Vazio = deduzir do
    -- campo de ritmo de jogo; `standard`/`rapid`/`blitz` = declarado.
    rating_speed TEXT NOT NULL DEFAULT '',
    -- Data de referencia da idade para categorias (ORG-01). Vazio = 1o de
    -- janeiro do ano do torneio, que e como o edital de base e escrito.
    -- Categoria pode ter a sua propria e sobrescrever esta.
    category_reference_date TEXT NOT NULL DEFAULT '',
    -- Rateio entre EMPATADOS (ORG-02): `equal` divide o bolo por igual;
    -- `hort` da a cada um 50% do premio da propria posicao no desempate mais
    -- 50% do bolo dividido por igual. O `hort` que existia antes combinava
    -- geral com categoria e nao era o Sistema Hort.
    prize_tie_split TEXT NOT NULL DEFAULT 'equal',
    prize_exclude_withdrawn INTEGER NOT NULL DEFAULT 0,
    -- Tolerancia de atraso em minutos (ORG-03). `0` = perde por ausencia a
    -- hora marcada, que e o default da FIDE desde 2018.
    late_tolerance_minutes INTEGER NOT NULL DEFAULT 0,
    -- Ajustes do regulamento de rating, em JSON por base:
    -- `{"cbx": {"k_top": 10, "rating_floor": 1400}}`. Coluna unica em vez de
    -- uma por parametro: o regulamento e DADO, e dado com forma propria cabe
    -- melhor num campo do que em quatorze colunas que ninguem consulta.
    rating_regulation TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0,
    chess_results_url TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
);

-- Categorias configuraveis por torneio (ORG-01). Antes as faixas eram
-- constantes em `core/categories.py`, e um edital com Sub-07/09/11/13 ou corte
-- 1600/2000 nao tinha onde caber. Torneio sem linha nenhuma usa o conjunto
-- padrao, que reproduz o comportamento anterior.
CREATE TABLE IF NOT EXISTS tournament_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    -- age | rating | sex | tag | open
    kind TEXT NOT NULL DEFAULT 'open',
    -- Idade: maximo INCLUSIVO ("Sub-12" aceita quem completa 12).
    -- Rating: maximo EXCLUSIVO ("Sub-1400" recusa 1400). A assimetria e a do
    -- edital, e e a que o programa ja praticava.
    min_value INTEGER NOT NULL DEFAULT 0,
    max_value INTEGER NOT NULL DEFAULT 0,
    sex TEXT NOT NULL DEFAULT '',
    tag TEXT NOT NULL DEFAULT '',
    reference_date TEXT NOT NULL DEFAULT '',
    awards INTEGER NOT NULL DEFAULT 1,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE (tournament_id, name),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS referees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    federation_id TEXT DEFAULT '',
    fide_id TEXT DEFAULT '',
    cbx_id TEXT DEFAULT '',
    lbx_id TEXT DEFAULT '',
    category TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tournament_referees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    referee_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'arbiter',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (tournament_id, referee_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (referee_id) REFERENCES referees(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS round_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    date TEXT DEFAULT '',
    time TEXT DEFAULT '',
    -- Agenda de verdade (ORG-03): a rodada pode mudar de local e de ritmo, e o
    -- dia de descanso e uma LINHA da agenda — sem ele, a data seguinte parece
    -- rodada atrasada.
    venue TEXT NOT NULL DEFAULT '',
    time_control TEXT NOT NULL DEFAULT '',
    rest_day INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    UNIQUE (tournament_id, round_number),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS official_rating_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    list_date TEXT DEFAULT '',
    file_name TEXT DEFAULT '',
    imported_count INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS official_players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    fide_id TEXT DEFAULT '',
    cbx_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    surname TEXT DEFAULT '',
    given_name TEXT DEFAULT '',
    title TEXT DEFAULT '',
    sex TEXT DEFAULT '',
    federation TEXT DEFAULT '',
    club TEXT DEFAULT '',
    birth_date TEXT DEFAULT '',
    national_rating INTEGER NOT NULL DEFAULT 0,
    international_rating INTEGER NOT NULL DEFAULT 0,
    standard_rating INTEGER NOT NULL DEFAULT 0,
    rapid_rating INTEGER NOT NULL DEFAULT 0,
    blitz_rating INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (snapshot_id) REFERENCES official_rating_snapshots(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS internal_rating_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    tournament_id INTEGER,
    player_id INTEGER,
    old_rating INTEGER NOT NULL DEFAULT 0,
    new_rating INTEGER NOT NULL DEFAULT 0,
    performance INTEGER NOT NULL DEFAULT 0,
    points REAL NOT NULL DEFAULT 0.0,
    games INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT 'tournament_performance',
    created_at TEXT NOT NULL,
    UNIQUE (member_id, tournament_id, player_id, reason),
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE SET NULL,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT DEFAULT '',
    role TEXT DEFAULT '',
    action TEXT NOT NULL,
    entity_type TEXT DEFAULT '',
    entity_id INTEGER,
    description TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    tournament_id INTEGER,
    round_id INTEGER,
    entity_type TEXT NOT NULL DEFAULT '',
    entity_id INTEGER,
    action TEXT NOT NULL,
    actor TEXT DEFAULT '',
    role TEXT DEFAULT '',
    reason TEXT DEFAULT '',
    before_hash TEXT DEFAULT '',
    after_hash TEXT DEFAULT '',
    before_json TEXT DEFAULT '',
    after_json TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS pairing_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_id INTEGER,
    round_number INTEGER NOT NULL,
    stage TEXT NOT NULL,
    pairing_system TEXT NOT NULL DEFAULT '',
    pairing_engine_version TEXT NOT NULL DEFAULT '',
    ruleset_version TEXT NOT NULL DEFAULT '',
    snapshot_json TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS standings_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    standings_json TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (tournament_id, round_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE
);

-- Retratos SUPERADOS da classificacao (ARB-01). O `standings_snapshots` tem
-- UNIQUE (tournament_id, round_id) e faz upsert, entao reconciliar depois de uma
-- correcao sobrescreveria a prova documental. O retrato antigo vem para ca antes
-- de ser reescrito: a linha viva e sempre a reconciliada, e o historico guarda o
-- que foi publicado, quando deixou de valer e por que.
CREATE TABLE IF NOT EXISTS standings_snapshot_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    standings_json TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    superseded_at TEXT NOT NULL,
    superseded_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE
);

-- Desbloqueio PONTUAL de correcao em rodada fechada (ARB-01), no lugar de
-- deixar `allow_dangerous_changes` ligado no torneio inteiro. Tem justificativa
-- e expiracao: vale para a correcao que o arbitro esta fazendo agora.
CREATE TABLE IF NOT EXISTS correction_unlocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_id INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    granted_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tiebreak_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_id INTEGER,
    round_number INTEGER NOT NULL DEFAULT 0,
    player_id INTEGER NOT NULL,
    player_name TEXT NOT NULL DEFAULT '',
    criterion TEXT NOT NULL,
    value REAL,
    components_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (tournament_id, round_id, player_id, criterion),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fide_rating_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    rating_type TEXT NOT NULL DEFAULT 'fide',
    ro INTEGER,
    k INTEGER,
    games_rated INTEGER,
    score REAL,
    we REAL,
    delta REAL,
    rc REAL,
    rp INTEGER,
    n_over_400 INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE (tournament_id, rating_type, player_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tournament_prizes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    kind TEXT NOT NULL DEFAULT 'overall',
    label TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    rank_from INTEGER NOT NULL DEFAULT 1,
    rank_to INTEGER NOT NULL DEFAULT 1,
    amount REAL NOT NULL DEFAULT 0,
    -- Politica POR PREMIO (ORG-02): `1` acumula com os demais mesmo quando a
    -- politica do torneio e "apenas o maior". E o caso do premio Feminino, que
    -- quase todo edital soma ao premio geral.
    cumulative INTEGER NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS report_layouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    report_key TEXT NOT NULL,
    columns_json TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    UNIQUE (tournament_id, report_key),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT NOT NULL UNIQUE,
    tournament_id INTEGER NOT NULL,
    round_id INTEGER NOT NULL,
    pairing_id INTEGER NOT NULL,
    board_number INTEGER NOT NULL DEFAULT 0,
    purpose TEXT NOT NULL DEFAULT 'result_submission',
    status TEXT NOT NULL DEFAULT 'active',
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    used_at TEXT DEFAULT '',
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (pairing_id) REFERENCES pairings(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS result_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_id INTEGER NOT NULL,
    pairing_id INTEGER NOT NULL,
    token_id INTEGER,
    board_number INTEGER NOT NULL DEFAULT 0,
    submitted_result TEXT NOT NULL,
    submitter TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'submitted',
    submitted_at TEXT NOT NULL,
    reviewed_at TEXT DEFAULT '',
    reviewer TEXT DEFAULT '',
    reason TEXT DEFAULT '',
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (pairing_id) REFERENCES pairings(id) ON DELETE CASCADE,
    FOREIGN KEY (token_id) REFERENCES public_tokens(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'assistant',
    status TEXT NOT NULL DEFAULT 'authorized',
    secret_hash TEXT DEFAULT '',
    last_seen_at TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    device_id TEXT NOT NULL DEFAULT '',
    tournament_id INTEGER,
    round_id INTEGER,
    entity_type TEXT NOT NULL DEFAULT '',
    entity_id INTEGER,
    action TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    conflict_policy TEXT NOT NULL DEFAULT 'server_authoritative',
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT DEFAULT '',
    next_attempt_at TEXT DEFAULT '',
    synced_at TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS clock_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    tournament_id INTEGER NOT NULL,
    round_id INTEGER,
    pairing_id INTEGER,
    board_number INTEGER NOT NULL DEFAULT 0,
    player_id INTEGER,
    device_id TEXT DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',
    event_type TEXT NOT NULL,
    side TEXT DEFAULT '',
    seconds_remaining INTEGER,
    note TEXT DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'logged',
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE SET NULL,
    FOREIGN KEY (pairing_id) REFERENCES pairings(id) ON DELETE SET NULL,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS certificate_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    certificate_type TEXT NOT NULL DEFAULT 'participation',
    title_template TEXT NOT NULL DEFAULT '',
    body_template TEXT NOT NULL DEFAULT '',
    footer_template TEXT DEFAULT '',
    orientation TEXT NOT NULL DEFAULT 'landscape',
    signature_left TEXT DEFAULT '',
    signature_right TEXT DEFAULT '',
    logo_path TEXT DEFAULT '',
    background_image_path TEXT DEFAULT '',
    background_opacity REAL NOT NULL DEFAULT 0.18,
    secondary_logo_path TEXT DEFAULT '',
    primary_color TEXT NOT NULL DEFAULT '#1E3A8A',
    accent_color TEXT NOT NULL DEFAULT '#93C5FD',
    title_font_size INTEGER NOT NULL DEFAULT 32,
    body_font_size INTEGER NOT NULL DEFAULT 18,
    footer_font_size INTEGER NOT NULL DEFAULT 10,
    style_preset TEXT NOT NULL DEFAULT 'classic',
    template_kind TEXT NOT NULL DEFAULT 'generated',
    palette_key TEXT NOT NULL DEFAULT '',
    seal_enabled INTEGER NOT NULL DEFAULT 1,
    watermark_enabled INTEGER NOT NULL DEFAULT 1,
    watermark_kind TEXT NOT NULL DEFAULT '',
    watermark_piece TEXT NOT NULL DEFAULT '',
    watermark_image_path TEXT DEFAULT '',
    watermark_opacity REAL NOT NULL DEFAULT 0.08,
    medal_by_placement INTEGER NOT NULL DEFAULT 1,
    field_layout_json TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS certificate_issuances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verification_code TEXT NOT NULL UNIQUE,
    context_type TEXT NOT NULL DEFAULT '',
    source_id INTEGER,
    source_title TEXT DEFAULT '',
    recipient_id INTEGER,
    recipient_name TEXT NOT NULL DEFAULT '',
    recipient_category TEXT DEFAULT '',
    certificate_type TEXT NOT NULL DEFAULT '',
    template_id INTEGER,
    template_name TEXT DEFAULT '',
    file_path TEXT NOT NULL DEFAULT '',
    issued_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0,
    revoked_at TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    payload_json TEXT DEFAULT '',
    FOREIGN KEY (template_id) REFERENCES certificate_templates(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS point_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL DEFAULT 0,
    player_id INTEGER,
    team_id INTEGER,
    aat_type TEXT NOT NULL DEFAULT '',
    match_points REAL NOT NULL DEFAULT 0.0,
    game_points REAL NOT NULL DEFAULT 0.0,
    reason TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prohibited_pairings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    player_a_id INTEGER NOT NULL,
    player_b_id INTEGER NOT NULL,
    first_round INTEGER NOT NULL DEFAULT 1,
    last_round INTEGER NOT NULL DEFAULT 0,
    reason TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (player_a_id) REFERENCES players(id) ON DELETE CASCADE,
    FOREIGN KEY (player_b_id) REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prohibited_team_pairings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    team_a_id INTEGER NOT NULL,
    team_b_id INTEGER NOT NULL,
    first_round INTEGER NOT NULL DEFAULT 1,
    last_round INTEGER NOT NULL DEFAULT 0,
    reason TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (team_a_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (team_b_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL DEFAULT 0,
    board_number INTEGER NOT NULL DEFAULT 0,
    pairing_id INTEGER,
    player_id INTEGER,
    infraction TEXT NOT NULL,
    decision TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    adjustment_id INTEGER,
    clock_event_id INTEGER,
    actor TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS player_status_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS requested_byes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    bye_type TEXT NOT NULL DEFAULT 'H',
    reason TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (tournament_id, player_id, round_number),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS requested_team_byes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    bye_type TEXT NOT NULL DEFAULT 'H',
    reason TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (tournament_id, team_id, round_number),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);

-- Numeros de rodizio (PAR-01): o calendario de um todos-contra-todos e decidido
-- UMA vez. Sem esta tabela ele era recalculado a cada rodada a partir da lista
-- de ativos ordenada por rating, e desativar um jogador embaralhava os
-- confrontos futuros de todos os outros. `number` e o numero da tabela de
-- Berger (FIDE C.05, Anexo 1); campo impar ganha um numero fantasma, que e o
-- bye e nao mora aqui.
-- Avanco de fase no mata-mata quando a MESA nao decide (PAR-03): empate, dupla
-- ausencia ou mesa sem resultado. Antes, qualquer um desses promovia o melhor
-- numero inicial em silencio; agora o arbitro registra QUEM passa e por que
-- criterio (mini-match, rapidas, blitz, armagedom, regulamento, decisao).
CREATE TABLE IF NOT EXISTS knockout_advancements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    pairing_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    criterion TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (tournament_id, pairing_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (pairing_id) REFERENCES pairings(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS round_robin_numbers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    number INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (tournament_id, player_id),
    UNIQUE (tournament_id, number),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);
"""

CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_players_tournament
    ON players(tournament_id);

CREATE INDEX IF NOT EXISTS idx_members_status
    ON members(status, name);

CREATE INDEX IF NOT EXISTS idx_members_club
    ON members(club_id, status, name);

CREATE INDEX IF NOT EXISTS idx_learning_levels_order
    ON learning_levels(active, display_order, name);

CREATE INDEX IF NOT EXISTS idx_members_learning_level
    ON members(learning_level_id, status, name);

CREATE INDEX IF NOT EXISTS idx_guardians_active
    ON guardians(active, name);

CREATE INDEX IF NOT EXISTS idx_member_guardians_member
    ON member_guardians(member_id, primary_contact);

CREATE INDEX IF NOT EXISTS idx_member_guardians_guardian
    ON member_guardians(guardian_id);

CREATE INDEX IF NOT EXISTS idx_classes_club
    ON classes(club_id, active, name);

CREATE INDEX IF NOT EXISTS idx_member_class_enrollments_member
    ON member_class_enrollments(member_id, status);

CREATE INDEX IF NOT EXISTS idx_exercise_library_filters
    ON exercise_library(active, club_id, learning_level_id, theme, difficulty);

CREATE INDEX IF NOT EXISTS idx_exercise_library_title
    ON exercise_library(title);

CREATE INDEX IF NOT EXISTS idx_training_lists_filters
    ON training_lists(status, club_id, class_id, learning_level_id, target_date);

CREATE INDEX IF NOT EXISTS idx_training_list_exercises_list
    ON training_list_exercises(list_id, position_order);

CREATE INDEX IF NOT EXISTS idx_training_sessions_date
    ON training_sessions(session_date, club_id, class_id);

CREATE INDEX IF NOT EXISTS idx_training_sessions_level
    ON training_sessions(learning_level_id, status, session_date);

CREATE INDEX IF NOT EXISTS idx_training_sessions_training_list
    ON training_sessions(training_list_id, session_date);

CREATE INDEX IF NOT EXISTS idx_attendance_session
    ON attendance(session_id, status);

CREATE INDEX IF NOT EXISTS idx_attendance_member
    ON attendance(member_id, status);

CREATE INDEX IF NOT EXISTS idx_exercise_attempts_member
    ON exercise_attempts(member_id, attempt_date);

CREATE INDEX IF NOT EXISTS idx_exercise_attempts_exercise
    ON exercise_attempts(exercise_id, result, attempt_date);

CREATE INDEX IF NOT EXISTS idx_membership_plans_active
    ON membership_plans(active, name);

CREATE INDEX IF NOT EXISTS idx_payments_member
    ON payments(member_id, due_date, status);

CREATE INDEX IF NOT EXISTS idx_payments_due
    ON payments(due_date, status);

CREATE INDEX IF NOT EXISTS idx_club_events_date
    ON club_events(event_date, status, club_id);

CREATE INDEX IF NOT EXISTS idx_club_events_tournament
    ON club_events(tournament_id);

CREATE INDEX IF NOT EXISTS idx_inventory_items_filters
    ON inventory_items(active, club_id, item_type, condition_status, name);

CREATE INDEX IF NOT EXISTS idx_inventory_items_code
    ON inventory_items(code);

CREATE INDEX IF NOT EXISTS idx_inventory_loans_item
    ON inventory_loans(item_id, status, due_date);

CREATE INDEX IF NOT EXISTS idx_inventory_loans_member
    ON inventory_loans(member_id, status, due_date);

CREATE INDEX IF NOT EXISTS idx_inventory_maintenance_item
    ON inventory_maintenance(item_id, status, opened_date);

CREATE INDEX IF NOT EXISTS idx_rounds_tournament
    ON rounds(tournament_id, number);

CREATE INDEX IF NOT EXISTS idx_pairings_round
    ON pairings(round_id, board_number);

CREATE INDEX IF NOT EXISTS idx_pairings_white_player
    ON pairings(white_player_id);

CREATE INDEX IF NOT EXISTS idx_pairings_black_player
    ON pairings(black_player_id);

CREATE INDEX IF NOT EXISTS idx_teams_tournament
    ON teams(tournament_id, active, name);

CREATE INDEX IF NOT EXISTS idx_team_players_team
    ON team_players(team_id, board_number);

CREATE INDEX IF NOT EXISTS idx_team_players_player
    ON team_players(player_id);

CREATE INDEX IF NOT EXISTS idx_team_matches_round
    ON team_matches(round_id, match_number);

CREATE INDEX IF NOT EXISTS idx_team_matches_white_team
    ON team_matches(white_team_id);

CREATE INDEX IF NOT EXISTS idx_team_matches_black_team
    ON team_matches(black_team_id);

CREATE INDEX IF NOT EXISTS idx_team_boards_match
    ON team_boards(team_match_id, board_number);

CREATE INDEX IF NOT EXISTS idx_incidents_tournament
    ON incidents(tournament_id, round_number, id);

CREATE INDEX IF NOT EXISTS idx_player_status_events
    ON player_status_events(tournament_id, player_id, round_number);

CREATE INDEX IF NOT EXISTS idx_team_lineups_round
    ON team_lineups(tournament_id, round_id, team_id);

CREATE INDEX IF NOT EXISTS idx_team_lineup_boards_lineup
    ON team_lineup_boards(lineup_id, board_number);

CREATE INDEX IF NOT EXISTS idx_team_substitutions_round
    ON team_substitution_events(tournament_id, round_id, team_id);

CREATE INDEX IF NOT EXISTS idx_round_schedule_tournament
    ON round_schedule(tournament_id, round_number);

CREATE INDEX IF NOT EXISTS idx_official_players_external
    ON official_players(source, external_id);

CREATE INDEX IF NOT EXISTS idx_official_players_ids
    ON official_players(fide_id, cbx_id);

CREATE INDEX IF NOT EXISTS idx_official_players_name
    ON official_players(name);

CREATE INDEX IF NOT EXISTS idx_internal_rating_history_member
    ON internal_rating_history(member_id, created_at);

CREATE INDEX IF NOT EXISTS idx_internal_rating_history_tournament
    ON internal_rating_history(tournament_id, player_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_created
    ON audit_log(created_at, action);

CREATE INDEX IF NOT EXISTS idx_audit_log_entity
    ON audit_log(entity_type, entity_id, created_at);

CREATE INDEX IF NOT EXISTS idx_audit_events_tournament
    ON audit_events(tournament_id, created_at);

CREATE INDEX IF NOT EXISTS idx_audit_events_entity
    ON audit_events(entity_type, entity_id, created_at);

CREATE INDEX IF NOT EXISTS idx_pairing_snapshots_round
    ON pairing_snapshots(tournament_id, round_number, stage);

CREATE INDEX IF NOT EXISTS idx_standings_snapshots_round
    ON standings_snapshots(tournament_id, round_id);

CREATE INDEX IF NOT EXISTS idx_tiebreak_components_player
    ON tiebreak_components(tournament_id, player_id, criterion);

CREATE INDEX IF NOT EXISTS idx_tiebreak_components_round
    ON tiebreak_components(tournament_id, round_id);

CREATE INDEX IF NOT EXISTS idx_public_tokens_hash
    ON public_tokens(token_hash);

CREATE INDEX IF NOT EXISTS idx_public_tokens_pairing
    ON public_tokens(tournament_id, round_id, pairing_id, status);

CREATE INDEX IF NOT EXISTS idx_result_submissions_status
    ON result_submissions(tournament_id, status, submitted_at);

CREATE INDEX IF NOT EXISTS idx_result_submissions_pairing
    ON result_submissions(pairing_id, status);

CREATE INDEX IF NOT EXISTS idx_devices_status
    ON devices(status, role, name);

CREATE INDEX IF NOT EXISTS idx_sync_outbox_status
    ON sync_outbox(status, next_attempt_at, created_at);

CREATE INDEX IF NOT EXISTS idx_sync_outbox_tournament
    ON sync_outbox(tournament_id, status, created_at);

CREATE INDEX IF NOT EXISTS idx_clock_events_tournament
    ON clock_events(tournament_id, round_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_clock_events_pairing
    ON clock_events(pairing_id, event_type, occurred_at);

CREATE INDEX IF NOT EXISTS idx_certificate_templates_type
    ON certificate_templates(certificate_type, active, name);

CREATE INDEX IF NOT EXISTS idx_certificate_issuances_context
    ON certificate_issuances(context_type, source_id, issued_at);

CREATE INDEX IF NOT EXISTS idx_certificate_issuances_recipient
    ON certificate_issuances(recipient_name, issued_at);

CREATE INDEX IF NOT EXISTS idx_correction_unlocks_round
    ON correction_unlocks(tournament_id, round_id, expires_at);

CREATE INDEX IF NOT EXISTS idx_snapshot_history_round
    ON standings_snapshot_history(tournament_id, round_number, superseded_at);
"""
