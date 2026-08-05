"""Mixin do dominio pedagogico/treinos da Database.

Turmas, exercicios, listas e sessoes de treino, presencas/attendance.
Extraido de ``src.core.database`` na decomposicao da God Class em mixins por
dominio. Comportamento preservado; a fachada ``Database`` herda deste mixin.
Ver ``_database_base._DatabaseInfra``.
"""
from __future__ import annotations

from typing import Any

from ._database_base import _DatabaseInfra


class EducationMixin(_DatabaseInfra):
    def create_class(
        self,
        club_id: int,
        name: str,
        teacher: str = "",
        weekday: str = "",
        time: str = "",
        location: str = "",
        active: int = 1,
        notes: str = "",
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO classes (
                    club_id, name, teacher, weekday, time, location, active,
                    notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    club_id,
                    name.strip(),
                    teacher.strip(),
                    weekday.strip(),
                    time.strip(),
                    location.strip(),
                    int(active),
                    notes.strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_class(
        self,
        class_id: int,
        club_id: int,
        name: str,
        teacher: str = "",
        weekday: str = "",
        time: str = "",
        location: str = "",
        active: int = 1,
        notes: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE classes
                SET club_id = ?, name = ?, teacher = ?, weekday = ?, time = ?,
                    location = ?, active = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    club_id,
                    name.strip(),
                    teacher.strip(),
                    weekday.strip(),
                    time.strip(),
                    location.strip(),
                    int(active),
                    notes.strip(),
                    self.now(),
                    class_id,
                ),
            )

    def get_class(self, class_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT cl.*, c.name AS club_name
                FROM classes cl
                JOIN clubs c ON c.id = cl.club_id
                WHERE cl.id = ?
                """,
                (class_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_classes(
        self,
        club_id: int | None = None,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if club_id:
            conditions.append("cl.club_id = ?")
            params.append(club_id)
        if active_only:
            conditions.append("cl.active = 1")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    cl.*,
                    c.name AS club_name,
                    (
                        SELECT COUNT(*)
                        FROM member_class_enrollments e
                        JOIN members m ON m.id = e.member_id
                        WHERE e.class_id = cl.id
                            AND e.status = 'active'
                            AND m.status = 'active'
                    ) AS active_members_count
                FROM classes cl
                JOIN clubs c ON c.id = cl.club_id
                {where}
                ORDER BY cl.active DESC, c.name COLLATE NOCASE ASC, cl.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def set_member_active_class(
        self,
        member_id: int,
        class_id: int | None,
        start_date: str = "",
        notes: str = "",
    ) -> None:
        now = self.now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE member_class_enrollments
                SET status = 'inactive', end_date = COALESCE(NULLIF(end_date, ''), ?),
                    updated_at = ?
                WHERE member_id = ? AND status = 'active'
                """,
                (now[:10], now, member_id),
            )
            if not class_id:
                return
            connection.execute(
                """
                INSERT INTO member_class_enrollments (
                    member_id, class_id, status, start_date, end_date, notes,
                    created_at, updated_at
                ) VALUES (?, ?, 'active', ?, '', ?, ?, ?)
                ON CONFLICT(member_id, class_id) DO UPDATE SET
                    status = 'active',
                    start_date = excluded.start_date,
                    end_date = '',
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    member_id,
                    class_id,
                    start_date.strip(),
                    notes.strip(),
                    now,
                    now,
                ),
            )

    def get_member_active_class(self, member_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    e.*,
                    cl.name AS class_name,
                    cl.club_id,
                    c.name AS club_name
                FROM member_class_enrollments e
                JOIN classes cl ON cl.id = e.class_id
                JOIN clubs c ON c.id = cl.club_id
                WHERE e.member_id = ? AND e.status = 'active'
                ORDER BY e.updated_at DESC, e.id DESC
                LIMIT 1
                """,
                (member_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_member_classes(self, member_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    e.*,
                    cl.name AS class_name,
                    cl.club_id,
                    c.name AS club_name
                FROM member_class_enrollments e
                JOIN classes cl ON cl.id = e.class_id
                JOIN clubs c ON c.id = cl.club_id
                WHERE e.member_id = ?
                ORDER BY e.status = 'active' DESC, e.updated_at DESC, e.id DESC
                """,
                (member_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_exercise(self, **data: Any) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO exercise_library (
                    club_id, learning_level_id, title, theme, difficulty, source,
                    fen, pgn, solution, objective, tags, active, notes, created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(data.get("club_id") or 1),
                    data.get("learning_level_id"),
                    str(data.get("title", "")).strip(),
                    str(data.get("theme", "")).strip(),
                    str(data.get("difficulty", "basic")).strip() or "basic",
                    str(data.get("source", "")).strip(),
                    str(data.get("fen", "")).strip(),
                    str(data.get("pgn", "")).strip(),
                    str(data.get("solution", "")).strip(),
                    str(data.get("objective", "")).strip(),
                    str(data.get("tags", "")).strip(),
                    int(data.get("active", 1) or 0),
                    str(data.get("notes", "")).strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_exercise(self, exercise_id: int, **data: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE exercise_library
                SET club_id = ?, learning_level_id = ?, title = ?, theme = ?,
                    difficulty = ?, source = ?, fen = ?, pgn = ?, solution = ?,
                    objective = ?, tags = ?, active = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    int(data.get("club_id") or 1),
                    data.get("learning_level_id"),
                    str(data.get("title", "")).strip(),
                    str(data.get("theme", "")).strip(),
                    str(data.get("difficulty", "basic")).strip() or "basic",
                    str(data.get("source", "")).strip(),
                    str(data.get("fen", "")).strip(),
                    str(data.get("pgn", "")).strip(),
                    str(data.get("solution", "")).strip(),
                    str(data.get("objective", "")).strip(),
                    str(data.get("tags", "")).strip(),
                    int(data.get("active", 1) or 0),
                    str(data.get("notes", "")).strip(),
                    self.now(),
                    exercise_id,
                ),
            )

    def get_exercise(self, exercise_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    e.*,
                    c.name AS club_name,
                    ll.name AS learning_level_name,
                    (
                        SELECT COUNT(*)
                        FROM training_list_exercises tle
                        WHERE tle.exercise_id = e.id
                    ) AS list_usage_count,
                    (
                        SELECT COUNT(*)
                        FROM exercise_attempts ea
                        WHERE ea.exercise_id = e.id
                    ) AS attempt_count
                FROM exercise_library e
                LEFT JOIN clubs c ON c.id = e.club_id
                LEFT JOIN learning_levels ll ON ll.id = e.learning_level_id
                WHERE e.id = ?
                """,
                (exercise_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_exercises(
        self,
        search: str = "",
        club_id: int | None = None,
        learning_level_id: int | None = None,
        theme: str = "",
        difficulty: str = "",
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if search:
            conditions.append(
                """
                (
                    e.title LIKE ? OR e.theme LIKE ? OR e.source LIKE ? OR
                    e.fen LIKE ? OR e.pgn LIKE ? OR e.solution LIKE ? OR
                    e.objective LIKE ? OR e.tags LIKE ? OR e.notes LIKE ?
                )
                """
            )
            params.extend([f"%{search.strip()}%"] * 9)
        if club_id:
            conditions.append("e.club_id = ?")
            params.append(club_id)
        if learning_level_id:
            conditions.append("e.learning_level_id = ?")
            params.append(learning_level_id)
        if theme:
            conditions.append("e.theme = ?")
            params.append(theme.strip())
        if difficulty:
            conditions.append("e.difficulty = ?")
            params.append(difficulty.strip())
        if active_only:
            conditions.append("e.active = 1")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    e.*,
                    c.name AS club_name,
                    ll.name AS learning_level_name,
                    (
                        SELECT COUNT(*)
                        FROM training_list_exercises tle
                        WHERE tle.exercise_id = e.id
                    ) AS list_usage_count,
                    (
                        SELECT COUNT(*)
                        FROM exercise_attempts ea
                        WHERE ea.exercise_id = e.id
                    ) AS attempt_count
                FROM exercise_library e
                LEFT JOIN clubs c ON c.id = e.club_id
                LEFT JOIN learning_levels ll ON ll.id = e.learning_level_id
                {where}
                ORDER BY e.active DESC, e.theme COLLATE NOCASE ASC, e.title COLLATE NOCASE ASC, e.id DESC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def set_exercise_active(self, exercise_id: int, active: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE exercise_library
                SET active = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(active), self.now(), exercise_id),
            )

    def create_training_list(self, **data: Any) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO training_lists (
                    club_id, class_id, learning_level_id, name, description,
                    target_date, status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(data.get("club_id") or 1),
                    data.get("class_id"),
                    data.get("learning_level_id"),
                    str(data.get("name", "")).strip(),
                    str(data.get("description", "")).strip(),
                    str(data.get("target_date", "")).strip(),
                    str(data.get("status", "draft")).strip() or "draft",
                    str(data.get("notes", "")).strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_training_list(self, list_id: int, **data: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE training_lists
                SET club_id = ?, class_id = ?, learning_level_id = ?, name = ?,
                    description = ?, target_date = ?, status = ?, notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    int(data.get("club_id") or 1),
                    data.get("class_id"),
                    data.get("learning_level_id"),
                    str(data.get("name", "")).strip(),
                    str(data.get("description", "")).strip(),
                    str(data.get("target_date", "")).strip(),
                    str(data.get("status", "draft")).strip() or "draft",
                    str(data.get("notes", "")).strip(),
                    self.now(),
                    list_id,
                ),
            )

    def get_training_list(self, list_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    tl.*,
                    c.name AS club_name,
                    cl.name AS class_name,
                    ll.name AS learning_level_name,
                    (
                        SELECT COUNT(*)
                        FROM training_list_exercises tle
                        WHERE tle.list_id = tl.id
                    ) AS exercise_count,
                    (
                        SELECT COUNT(*)
                        FROM exercise_attempts ea
                        WHERE ea.list_id = tl.id
                    ) AS attempt_count
                FROM training_lists tl
                LEFT JOIN clubs c ON c.id = tl.club_id
                LEFT JOIN classes cl ON cl.id = tl.class_id
                LEFT JOIN learning_levels ll ON ll.id = tl.learning_level_id
                WHERE tl.id = ?
                """,
                (list_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_training_lists(
        self,
        club_id: int | None = None,
        class_id: int | None = None,
        learning_level_id: int | None = None,
        status: str = "",
        include_archived: bool = True,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if club_id:
            conditions.append("tl.club_id = ?")
            params.append(club_id)
        if class_id:
            conditions.append("(tl.class_id IS NULL OR tl.class_id = ?)")
            params.append(class_id)
        if learning_level_id:
            conditions.append("tl.learning_level_id = ?")
            params.append(learning_level_id)
        if status:
            conditions.append("tl.status = ?")
            params.append(status.strip())
        if not include_archived:
            conditions.append("tl.status <> 'archived'")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    tl.*,
                    c.name AS club_name,
                    cl.name AS class_name,
                    ll.name AS learning_level_name,
                    (
                        SELECT COUNT(*)
                        FROM training_list_exercises tle
                        WHERE tle.list_id = tl.id
                    ) AS exercise_count,
                    (
                        SELECT COUNT(*)
                        FROM exercise_attempts ea
                        WHERE ea.list_id = tl.id
                    ) AS attempt_count
                FROM training_lists tl
                LEFT JOIN clubs c ON c.id = tl.club_id
                LEFT JOIN classes cl ON cl.id = tl.class_id
                LEFT JOIN learning_levels ll ON ll.id = tl.learning_level_id
                {where}
                ORDER BY
                    CASE tl.status
                        WHEN 'ready' THEN 1
                        WHEN 'draft' THEN 2
                        WHEN 'used' THEN 3
                        ELSE 4
                    END,
                    tl.target_date DESC,
                    tl.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def replace_training_list_exercises(self, list_id: int, rows: list[dict[str, Any]]) -> None:
        now = self.now()
        with self.connect() as connection:
            connection.execute("DELETE FROM training_list_exercises WHERE list_id = ?", (list_id,))
            for index, row in enumerate(rows, start=1):
                connection.execute(
                    """
                    INSERT INTO training_list_exercises (
                        list_id, exercise_id, position_order, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        list_id,
                        int(row.get("exercise_id") or 0),
                        int(row.get("position_order") or index),
                        str(row.get("notes", "")).strip(),
                        now,
                        now,
                    ),
                )

    def list_training_list_exercises(self, list_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    tle.*,
                    e.title,
                    e.theme,
                    e.difficulty,
                    e.source,
                    e.fen,
                    e.pgn,
                    e.solution,
                    e.objective,
                    e.tags,
                    e.active,
                    ll.name AS learning_level_name
                FROM training_list_exercises tle
                JOIN exercise_library e ON e.id = tle.exercise_id
                LEFT JOIN learning_levels ll ON ll.id = e.learning_level_id
                WHERE tle.list_id = ?
                ORDER BY tle.position_order ASC, tle.id ASC
                """,
                (list_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_exercise_attempt(self, **data: Any) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO exercise_attempts (
                    exercise_id, member_id, list_id, session_id, attempt_date,
                    result, score, time_seconds, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(data.get("exercise_id") or 0),
                    int(data.get("member_id") or 0),
                    data.get("list_id"),
                    data.get("session_id"),
                    str(data.get("attempt_date", "")).strip(),
                    str(data.get("result", "attempted")).strip() or "attempted",
                    float(data.get("score", 0.0) or 0.0),
                    int(data.get("time_seconds", 0) or 0),
                    str(data.get("notes", "")).strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def list_exercise_attempts(
        self,
        member_id: int | None = None,
        exercise_id: int | None = None,
        list_id: int | None = None,
        session_id: int | None = None,
        start_date: str = "",
        end_date: str = "",
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if member_id:
            conditions.append("ea.member_id = ?")
            params.append(member_id)
        if exercise_id:
            conditions.append("ea.exercise_id = ?")
            params.append(exercise_id)
        if list_id:
            conditions.append("ea.list_id = ?")
            params.append(list_id)
        if session_id:
            conditions.append("ea.session_id = ?")
            params.append(session_id)
        if start_date:
            conditions.append("ea.attempt_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("ea.attempt_date <= ?")
            params.append(end_date)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    ea.*,
                    e.title AS exercise_title,
                    e.theme AS exercise_theme,
                    m.name AS member_name,
                    tl.name AS list_name,
                    s.title AS session_title
                FROM exercise_attempts ea
                JOIN exercise_library e ON e.id = ea.exercise_id
                JOIN members m ON m.id = ea.member_id
                LEFT JOIN training_lists tl ON tl.id = ea.list_id
                LEFT JOIN training_sessions s ON s.id = ea.session_id
                {where}
                ORDER BY ea.attempt_date DESC, ea.created_at DESC, ea.id DESC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_training_session(
        self,
        club_id: int = 1,
        class_id: int | None = None,
        training_list_id: int | None = None,
        title: str = "",
        session_type: str = "aula",
        session_date: str = "",
        start_time: str = "",
        end_time: str = "",
        instructor: str = "",
        location: str = "",
        learning_level_id: int | None = None,
        objective: str = "",
        content: str = "",
        homework: str = "",
        status: str = "planned",
        notes: str = "",
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO training_sessions (
                    club_id, class_id, training_list_id, title, session_type, session_date,
                    start_time, end_time, instructor, location, learning_level_id,
                    objective, content, homework, status, notes, created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(club_id or 1),
                    class_id,
                    training_list_id,
                    title.strip(),
                    session_type.strip(),
                    session_date.strip(),
                    start_time.strip(),
                    end_time.strip(),
                    instructor.strip(),
                    location.strip(),
                    learning_level_id,
                    objective.strip(),
                    content.strip(),
                    homework.strip(),
                    status.strip(),
                    notes.strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_training_session(
        self,
        session_id: int,
        club_id: int = 1,
        class_id: int | None = None,
        training_list_id: int | None = None,
        title: str = "",
        session_type: str = "aula",
        session_date: str = "",
        start_time: str = "",
        end_time: str = "",
        instructor: str = "",
        location: str = "",
        learning_level_id: int | None = None,
        objective: str = "",
        content: str = "",
        homework: str = "",
        status: str = "planned",
        notes: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE training_sessions
                SET club_id = ?, class_id = ?, training_list_id = ?, title = ?,
                    session_type = ?, session_date = ?, start_time = ?, end_time = ?,
                    instructor = ?, location = ?, learning_level_id = ?, objective = ?,
                    content = ?, homework = ?, status = ?, notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    int(club_id or 1),
                    class_id,
                    training_list_id,
                    title.strip(),
                    session_type.strip(),
                    session_date.strip(),
                    start_time.strip(),
                    end_time.strip(),
                    instructor.strip(),
                    location.strip(),
                    learning_level_id,
                    objective.strip(),
                    content.strip(),
                    homework.strip(),
                    status.strip(),
                    notes.strip(),
                    self.now(),
                    session_id,
                ),
            )

    def get_training_session(self, session_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    s.*,
                    c.name AS club_name,
                    cl.name AS class_name,
                    ll.name AS learning_level_name,
                    tl.name AS training_list_name
                FROM training_sessions s
                LEFT JOIN clubs c ON c.id = s.club_id
                LEFT JOIN classes cl ON cl.id = s.class_id
                LEFT JOIN learning_levels ll ON ll.id = s.learning_level_id
                LEFT JOIN training_lists tl ON tl.id = s.training_list_id
                WHERE s.id = ?
                """,
                (session_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_training_sessions(
        self,
        start_date: str = "",
        end_date: str = "",
        club_id: int | None = None,
        class_id: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if start_date:
            conditions.append("s.session_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("s.session_date <= ?")
            params.append(end_date)
        if club_id:
            conditions.append("s.club_id = ?")
            params.append(club_id)
        if class_id:
            conditions.append("s.class_id = ?")
            params.append(class_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    s.*,
                    c.name AS club_name,
                    cl.name AS class_name,
                    ll.name AS learning_level_name,
                    tl.name AS training_list_name,
                    (SELECT COUNT(*) FROM attendance a WHERE a.session_id = s.id) AS attendance_count,
                    (
                        SELECT COUNT(*)
                        FROM attendance a
                        WHERE a.session_id = s.id AND a.status = 'present'
                    ) AS present_count,
                    (
                        SELECT COUNT(*)
                        FROM attendance a
                        WHERE a.session_id = s.id AND a.status = 'absent'
                    ) AS absent_count,
                    (
                        SELECT COUNT(*)
                        FROM attendance a
                        WHERE a.session_id = s.id AND a.status = 'justified'
                    ) AS justified_count
                FROM training_sessions s
                LEFT JOIN clubs c ON c.id = s.club_id
                LEFT JOIN classes cl ON cl.id = s.class_id
                LEFT JOIN learning_levels ll ON ll.id = s.learning_level_id
                LEFT JOIN training_lists tl ON tl.id = s.training_list_id
                {where}
                ORDER BY s.session_date DESC, s.start_time DESC, s.id DESC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def save_attendance(
        self,
        session_id: int,
        member_id: int,
        status: str = "present",
        notes: str = "",
    ) -> None:
        now = self.now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO attendance (
                    session_id, member_id, status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, member_id) DO UPDATE SET
                    status = excluded.status,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    member_id,
                    status.strip(),
                    notes.strip(),
                    now,
                    now,
                ),
            )

    def list_session_attendance(self, session_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    a.*,
                    m.name AS member_name,
                    -- O sobrenome ja era usado no ORDER BY desta mesma consulta
                    -- e nao vinha no SELECT: o certificado de aula emitido a
                    -- partir da linha de presenca saia com o nome pela metade,
                    -- enquanto o mesmo aluno SEM presenca lancada (outro ramo,
                    -- com `SELECT m.*`) saia completo.
                    m.surname AS surname,
                    m.phone AS member_phone,
                    m.category AS member_category,
                    m.status AS member_status,
                    c.name AS club_name,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name
                FROM attendance a
                JOIN members m ON m.id = a.member_id
                LEFT JOIN clubs c ON c.id = m.club_id
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = m.id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                WHERE a.session_id = ?
                ORDER BY
                    COALESCE(NULLIF(TRIM(m.surname), ''), m.name) COLLATE NOCASE ASC,
                    m.name COLLATE NOCASE ASC
                """,
                (session_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_session_members_for_attendance(self, session_id: int) -> list[dict[str, Any]]:
        session = self.get_training_session(session_id)
        if not session:
            return []
        class_filter = "AND ac.class_id = ?" if session.get("class_id") else ""
        params: list[Any] = [session_id]
        if session.get("class_id"):
            params.append(int(session["class_id"]))
        elif session.get("club_id"):
            class_filter = "AND m.club_id = ?"
            params.append(int(session["club_id"]))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    m.*,
                    c.name AS club_name,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name,
                    a.status AS attendance_status,
                    a.notes AS attendance_notes
                FROM members m
                LEFT JOIN clubs c ON c.id = m.club_id
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = m.id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                LEFT JOIN attendance a
                    ON a.member_id = m.id AND a.session_id = ?
                WHERE m.status = 'active'
                {class_filter}
                ORDER BY
                    COALESCE(NULLIF(TRIM(m.surname), ''), m.name) COLLATE NOCASE ASC,
                    m.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_attendance_report(
        self,
        start_date: str = "",
        end_date: str = "",
        club_id: int | None = None,
        member_id: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if start_date:
            conditions.append("s.session_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("s.session_date <= ?")
            params.append(end_date)
        if club_id:
            conditions.append("s.club_id = ?")
            params.append(club_id)
        if member_id:
            conditions.append("a.member_id = ?")
            params.append(member_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    a.*,
                    s.title,
                    s.session_type,
                    s.session_date,
                    s.start_time,
                    s.end_time,
                    s.instructor,
                    s.location,
                    s.status AS session_status,
                    c.name AS club_name,
                    cl.name AS class_name,
                    m.name AS member_name,
                    m.category AS member_category,
                    m.member_type,
                    m.status AS member_status
                FROM attendance a
                JOIN training_sessions s ON s.id = a.session_id
                JOIN members m ON m.id = a.member_id
                LEFT JOIN clubs c ON c.id = s.club_id
                LEFT JOIN classes cl ON cl.id = s.class_id
                {where}
                ORDER BY
                    s.session_date ASC,
                    s.start_time ASC,
                    COALESCE(NULLIF(TRIM(m.surname), ''), m.name) COLLATE NOCASE ASC,
                    m.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def member_attendance_summary(
        self,
        member_id: int,
        start_date: str = "",
        end_date: str = "",
    ) -> dict[str, Any]:
        conditions = ["a.member_id = ?"]
        params: list[Any] = [member_id]
        if start_date:
            conditions.append("s.session_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("s.session_date <= ?")
            params.append(end_date)
        where = " AND ".join(conditions)
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present,
                    SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) AS absent,
                    SUM(CASE WHEN a.status = 'justified' THEN 1 ELSE 0 END) AS justified
                FROM attendance a
                JOIN training_sessions s ON s.id = a.session_id
                WHERE {where}
                """,
                params,
            ).fetchone()
            total = int(row["total"] or 0) if row else 0
            present = int(row["present"] or 0) if row else 0
            return {
                "total": total,
                "present": present,
                "absent": int(row["absent"] or 0) if row else 0,
                "justified": int(row["justified"] or 0) if row else 0,
                "attendance_rate": round((present / total) * 100, 1) if total else 0,
            }
