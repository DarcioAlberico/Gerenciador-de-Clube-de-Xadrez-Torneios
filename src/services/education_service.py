from __future__ import annotations
import csv
import json
import logging
import math
import secrets
import shutil
import sqlite3
import unicodedata
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Mapping, TYPE_CHECKING

from src.core.database import BASE_DIR, DEFAULT_CERTIFICATE_TEMPLATES, Database
from src.services.constants import *

if TYPE_CHECKING:
    from src.services.club_service import ClubService
    from src.services.member_service import MemberService, GuardianService
    from src.services.tournament_service import TournamentService, RefereeService, TeamService
    from src.services.pairing_service import PairingService
    from src.services.finance_service import FinanceService
    from src.services.event_service import EventService, CalendarService
    from src.services.education_service import TrainingService, ExerciseService, LibraryService, LearningLevelService
    from src.services.inventory_service import InventoryService
    from src.services.security_service import SecurityService
    from src.services.export_service import ExportService, ImportService, CertificateService
    from src.services.rating_service import OfficialRatingService, InternalRatingService
    from src.services.dashboard_service import DashboardService, CommunicationService

logger = logging.getLogger(__name__)

class TrainingService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_session(self, data: dict[str, Any], session_id: int | None = None) -> int:
        payload = self._validated_session_payload(data)
        if session_id:
            if not self.db.get_training_session(session_id):
                raise AppError("Aula/treino nao encontrado.")
            self.db.update_training_session(session_id, **payload)
            logger.info("Aula/treino atualizado: %s", session_id)
            return session_id
        saved_id = self.db.create_training_session(**payload)
        logger.info("Aula/treino criado: %s", saved_id)
        return saved_id

    def record_attendance(self, session_id: int, rows: list[dict[str, Any]]) -> dict[str, int]:
        session = self.db.get_training_session(session_id)
        if not session:
            raise AppError("Aula/treino nao encontrado.")
        saved = 0
        skipped = 0
        for item in rows:
            try:
                member_id = int(item.get("member_id") or 0)
            except ValueError as exc:
                raise AppError("Membro invalido na chamada.") from exc
            member = self.db.get_member(member_id)
            if not member:
                skipped += 1
                continue
            status = str(item.get("status", "")).strip()
            if not status:
                skipped += 1
                continue
            if status not in ATTENDANCE_STATUSES:
                raise AppError("Status de presenca invalido.")
            self.db.save_attendance(
                session_id=session_id,
                member_id=member_id,
                status=status,
                notes=str(item.get("notes", "")),
            )
            saved += 1
        logger.info("Chamada da sessao %s atualizada: %s registros", session_id, saved)
        return {"saved": saved, "skipped": skipped}

    def member_attendance_summary(
        self,
        member_id: int,
        start_date: str = "",
        end_date: str = "",
    ) -> dict[str, Any]:
        if not self.db.get_member(member_id):
            raise AppError("Membro nao encontrado.")
        self._validate_optional_date(start_date, "Data inicial invalida.")
        self._validate_optional_date(end_date, "Data final invalida.")
        return self.db.member_attendance_summary(member_id, start_date.strip(), end_date.strip())

    def attendance_report(
        self,
        start_date: str = "",
        end_date: str = "",
        club_id: int | None = None,
        member_id: int | None = None,
    ) -> list[dict[str, Any]]:
        self._validate_optional_date(start_date, "Data inicial invalida.")
        self._validate_optional_date(end_date, "Data final invalida.")
        return self.db.list_attendance_report(
            start_date=start_date.strip(),
            end_date=end_date.strip(),
            club_id=club_id,
            member_id=member_id,
        )

    def _validated_session_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        title = str(data.get("title", "")).strip()
        if not title:
            raise AppError("Informe o titulo da aula/treino.")

        try:
            club_id = int(data.get("club_id") or 1)
        except ValueError as exc:
            raise AppError("Clube/escola da aula invalido.") from exc
        if not self.db.get_club(club_id):
            raise AppError("Clube/escola da aula nao encontrado.")

        try:
            class_id = int(data.get("class_id") or 0)
        except ValueError as exc:
            raise AppError("Turma da aula invalida.") from exc
        if class_id:
            class_data = self.db.get_class(class_id)
            if not class_data or int(class_data["club_id"]) != club_id:
                raise AppError("Turma nao pertence ao clube/escola selecionado.")

        try:
            learning_level_id = int(data.get("learning_level_id") or 0)
        except ValueError as exc:
            raise AppError("Nivel pedagogico da aula invalido.") from exc
        if learning_level_id and not self.db.get_learning_level(learning_level_id):
            raise AppError("Nivel pedagogico da aula nao encontrado.")

        try:
            training_list_id = int(data.get("training_list_id") or 0)
        except ValueError as exc:
            raise AppError("Lista de treino da aula invalida.") from exc
        if training_list_id:
            training_list = self.db.get_training_list(training_list_id)
            if not training_list:
                raise AppError("Lista de treino da aula nao encontrada.")
            if int(training_list.get("club_id") or 1) != club_id:
                raise AppError("Lista de treino nao pertence ao clube/escola selecionado.")
            list_class_id = int(training_list.get("class_id") or 0)
            if list_class_id and list_class_id != class_id:
                raise AppError("Lista de treino nao pertence a turma selecionada.")

        session_type = str(data.get("session_type", "aula")).strip() or "aula"
        if session_type not in TRAINING_SESSION_TYPES:
            raise AppError("Tipo de aula/treino invalido.")

        status = str(data.get("status", "planned")).strip() or "planned"
        if status not in TRAINING_SESSION_STATUSES:
            raise AppError("Status de aula/treino invalido.")

        session_date = str(data.get("session_date", "")).strip()
        self._validate_optional_date(session_date, "Data da aula invalida.")

        return {
            "club_id": club_id,
            "class_id": class_id or None,
            "training_list_id": training_list_id or None,
            "title": title,
            "session_type": session_type,
            "session_date": session_date,
            "start_time": str(data.get("start_time", "")),
            "end_time": str(data.get("end_time", "")),
            "instructor": str(data.get("instructor", "")),
            "location": str(data.get("location", "")),
            "learning_level_id": learning_level_id or None,
            "objective": str(data.get("objective", "")),
            "content": str(data.get("content", "")),
            "homework": str(data.get("homework", "")),
            "status": status,
            "notes": str(data.get("notes", "")),
        }

    @staticmethod
    def _validate_optional_date(value: str, message: str) -> None:
        cleaned = value.strip()
        if not cleaned:
            return
        try:
            date.fromisoformat(cleaned)
        except ValueError as exc:
            raise AppError(message) from exc

class ExerciseService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_exercise(self, data: dict[str, Any], exercise_id: int | None = None) -> int:
        payload = self._validated_exercise_payload(data)
        if exercise_id:
            if not self.db.get_exercise(exercise_id):
                raise AppError("Exercicio nao encontrado.")
            self.db.update_exercise(exercise_id, **payload)
            logger.info("Exercicio atualizado: %s", exercise_id)
            return exercise_id
        saved_id = self.db.create_exercise(**payload)
        logger.info("Exercicio criado: %s", saved_id)
        return saved_id

    def toggle_exercise_active(self, exercise_id: int) -> int:
        exercise = self.db.get_exercise(exercise_id)
        if not exercise:
            raise AppError("Exercicio nao encontrado.")
        next_active = 0 if exercise.get("active") else 1
        self.db.set_exercise_active(exercise_id, next_active)
        logger.info("Exercicio %s alterado para active=%s", exercise_id, next_active)
        return next_active

    def save_training_list(self, data: dict[str, Any], list_id: int | None = None) -> int:
        payload = self._validated_training_list_payload(data)
        if list_id:
            if not self.db.get_training_list(list_id):
                raise AppError("Lista de treino nao encontrada.")
            self.db.update_training_list(list_id, **payload)
            logger.info("Lista de treino atualizada: %s", list_id)
            return list_id
        saved_id = self.db.create_training_list(**payload)
        logger.info("Lista de treino criada: %s", saved_id)
        return saved_id

    def set_training_list_exercises(self, list_id: int, exercise_ids: list[int]) -> None:
        training_list = self.db.get_training_list(list_id)
        if not training_list:
            raise AppError("Lista de treino nao encontrada.")
        unique_ids: list[int] = []
        for exercise_id in exercise_ids:
            value = int(exercise_id or 0)
            if not value or value in unique_ids:
                continue
            exercise = self.db.get_exercise(value)
            if not exercise:
                raise AppError("Exercicio da lista nao encontrado.")
            if int(exercise.get("club_id") or 1) != int(training_list.get("club_id") or 1):
                raise AppError("Exercicio nao pertence ao clube/escola da lista.")
            unique_ids.append(value)
        rows = [
            {"exercise_id": exercise_id, "position_order": index}
            for index, exercise_id in enumerate(unique_ids, start=1)
        ]
        self.db.replace_training_list_exercises(list_id, rows)
        logger.info("Lista de treino %s atualizada com %s exercicios", list_id, len(rows))

    def add_exercise_to_training_list(self, list_id: int, exercise_id: int) -> None:
        current = [int(item["exercise_id"]) for item in self.db.list_training_list_exercises(list_id)]
        if exercise_id not in current:
            current.append(exercise_id)
        self.set_training_list_exercises(list_id, current)

    def remove_exercise_from_training_list(self, list_id: int, exercise_id: int) -> None:
        current = [
            int(item["exercise_id"])
            for item in self.db.list_training_list_exercises(list_id)
            if int(item["exercise_id"]) != int(exercise_id)
        ]
        self.set_training_list_exercises(list_id, current)

    def record_attempt(self, data: dict[str, Any]) -> int:
        payload = self._validated_attempt_payload(data)
        attempt_id = self.db.create_exercise_attempt(**payload)
        logger.info("Tentativa de exercicio registrada: %s", attempt_id)
        return attempt_id

    def _validated_exercise_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        title = str(data.get("title", "")).strip()
        if not title:
            raise AppError("Informe o titulo do exercicio.")

        try:
            club_id = int(data.get("club_id") or 1)
        except ValueError as exc:
            raise AppError("Clube/escola do exercicio invalido.") from exc
        if not self.db.get_club(club_id):
            raise AppError("Clube/escola do exercicio nao encontrado.")

        try:
            learning_level_id = int(data.get("learning_level_id") or 0)
        except ValueError as exc:
            raise AppError("Nivel pedagogico do exercicio invalido.") from exc
        if learning_level_id and not self.db.get_learning_level(learning_level_id):
            raise AppError("Nivel pedagogico do exercicio nao encontrado.")

        difficulty = str(data.get("difficulty", "basic")).strip() or "basic"
        if difficulty not in EXERCISE_DIFFICULTIES:
            raise AppError("Dificuldade do exercicio invalida.")

        return {
            "club_id": club_id,
            "learning_level_id": learning_level_id or None,
            "title": title,
            "theme": str(data.get("theme", "")),
            "difficulty": difficulty,
            "source": str(data.get("source", "")),
            "fen": str(data.get("fen", "")),
            "pgn": str(data.get("pgn", "")),
            "solution": str(data.get("solution", "")),
            "objective": str(data.get("objective", "")),
            "tags": str(data.get("tags", "")),
            "active": 1 if data.get("active", 1) else 0,
            "notes": str(data.get("notes", "")),
        }

    def _validated_training_list_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        if not name:
            raise AppError("Informe o nome da lista de treino.")

        try:
            club_id = int(data.get("club_id") or 1)
        except ValueError as exc:
            raise AppError("Clube/escola da lista invalido.") from exc
        if not self.db.get_club(club_id):
            raise AppError("Clube/escola da lista nao encontrado.")

        try:
            class_id = int(data.get("class_id") or 0)
        except ValueError as exc:
            raise AppError("Turma da lista invalida.") from exc
        if class_id:
            class_data = self.db.get_class(class_id)
            if not class_data or int(class_data["club_id"]) != club_id:
                raise AppError("Turma nao pertence ao clube/escola selecionado.")

        try:
            learning_level_id = int(data.get("learning_level_id") or 0)
        except ValueError as exc:
            raise AppError("Nivel pedagogico da lista invalido.") from exc
        if learning_level_id and not self.db.get_learning_level(learning_level_id):
            raise AppError("Nivel pedagogico da lista nao encontrado.")

        target_date = str(data.get("target_date", "")).strip()
        TrainingService._validate_optional_date(target_date, "Data alvo da lista invalida.")

        status = str(data.get("status", "draft")).strip() or "draft"
        if status not in TRAINING_LIST_STATUSES:
            raise AppError("Status da lista de treino invalido.")

        return {
            "club_id": club_id,
            "class_id": class_id or None,
            "learning_level_id": learning_level_id or None,
            "name": name,
            "description": str(data.get("description", "")),
            "target_date": target_date,
            "status": status,
            "notes": str(data.get("notes", "")),
        }

    def _validated_attempt_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            exercise_id = int(data.get("exercise_id") or 0)
        except ValueError as exc:
            raise AppError("Exercicio da tentativa invalido.") from exc
        if not self.db.get_exercise(exercise_id):
            raise AppError("Exercicio da tentativa nao encontrado.")

        try:
            member_id = int(data.get("member_id") or 0)
        except ValueError as exc:
            raise AppError("Aluno da tentativa invalido.") from exc
        if not self.db.get_member(member_id):
            raise AppError("Aluno da tentativa nao encontrado.")

        try:
            list_id = int(data.get("list_id") or 0)
        except ValueError as exc:
            raise AppError("Lista da tentativa invalida.") from exc
        if list_id and not self.db.get_training_list(list_id):
            raise AppError("Lista da tentativa nao encontrada.")

        try:
            session_id = int(data.get("session_id") or 0)
        except ValueError as exc:
            raise AppError("Aula da tentativa invalida.") from exc
        if session_id and not self.db.get_training_session(session_id):
            raise AppError("Aula da tentativa nao encontrada.")

        attempt_date = str(data.get("attempt_date", "")).strip() or date.today().isoformat()
        TrainingService._validate_optional_date(attempt_date, "Data da tentativa invalida.")

        result = str(data.get("result", "incorrect")).strip() or "incorrect"
        if result not in EXERCISE_ATTEMPT_RESULTS:
            raise AppError("Resultado da tentativa invalido.")

        score_value = data.get("score")
        if score_value in (None, ""):
            score = {"correct": 1.0, "partial": 0.5}.get(result, 0.0)
        else:
            try:
                score = float(str(score_value).replace(",", "."))
            except ValueError as exc:
                raise AppError("Pontuacao da tentativa invalida.") from exc
        if score < 0 or score > 1:
            raise AppError("Pontuacao da tentativa deve ficar entre 0 e 1.")

        try:
            time_seconds = int(data.get("time_seconds") or 0)
        except ValueError as exc:
            raise AppError("Tempo da tentativa invalido.") from exc
        if time_seconds < 0:
            raise AppError("Tempo da tentativa nao pode ser negativo.")

        return {
            "exercise_id": exercise_id,
            "member_id": member_id,
            "list_id": list_id or None,
            "session_id": session_id or None,
            "attempt_date": attempt_date,
            "result": result,
            "score": score,
            "time_seconds": time_seconds,
            "notes": str(data.get("notes", "")),
        }

class LearningLevelService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_level(self, data: dict[str, Any]) -> int:
        payload = self._validated_payload(data)
        try:
            level_id = self.db.create_learning_level(**payload)
        except sqlite3.IntegrityError as exc:
            raise AppError("Ja existe um nivel com este nome.") from exc
        logger.info("Nivel de aprendizagem criado: %s", level_id)
        return level_id

    def update_level(self, learning_level_id: int, data: dict[str, Any]) -> None:
        if not self.db.get_learning_level(learning_level_id):
            raise AppError("Nivel de aprendizagem nao encontrado.")
        payload = self._validated_payload(data)
        try:
            self.db.update_learning_level(learning_level_id, **payload)
        except sqlite3.IntegrityError as exc:
            raise AppError("Ja existe um nivel com este nome.") from exc
        logger.info("Nivel de aprendizagem atualizado: %s", learning_level_id)

    def toggle_level_active(self, learning_level_id: int) -> int:
        level = self.db.get_learning_level(learning_level_id)
        if not level:
            raise AppError("Nivel de aprendizagem nao encontrado.")
        next_active = 0 if level.get("active") else 1
        self.db.set_learning_level_active(learning_level_id, next_active)
        logger.info("Nivel de aprendizagem %s ativo=%s", learning_level_id, next_active)
        return next_active

    @staticmethod
    def _validated_payload(data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        if not name:
            raise AppError("Informe o nome do nivel.")
        try:
            display_order = int(data.get("display_order") or 0)
        except ValueError as exc:
            raise AppError("Ordem do nivel invalida.") from exc
        if display_order < 0:
            raise AppError("A ordem do nivel nao pode ser negativa.")
        return {
            "name": name,
            "description": str(data.get("description", "")),
            "display_order": display_order,
            "active": 1 if data.get("active", 1) else 0,
        }

class LibraryService:
    def __init__(self, db: Database):
        self.db = db

    def save_item(self, data: dict[str, Any], item_id: int | None = None) -> int:
        from src.services.chess_validation import ChessValidationService
        fen_pgn = data.get('fen_pgn', '').strip()
        if fen_pgn:
            if '[' in fen_pgn or '1.' in fen_pgn:
                ChessValidationService.parse_pgn(fen_pgn, strict=False)
            else:
                ChessValidationService.validate_fen(fen_pgn)

        now = self.db.now()
        payload = {
            "title": data.get("title", "").strip(),
            "item_type": data.get("item_type", "exercise"),
            "phase": data.get("phase", "general"),
            "theme": data.get("theme", ""),
            "level": data.get("level", ""),
            "fen_pgn": data.get("fen_pgn", ""),
            "content": data.get("content", ""),
            "solution": data.get("solution", ""),
            "tags": data.get("tags", ""),
            "author": data.get("author", ""),
            "cover_image": data.get("cover_image", "").strip(),
            "updated_at": now
        }
        with self.db.connect() as conn:
            if item_id:
                cols = ", ".join(f"{k}=?" for k in payload.keys())
                conn.execute(f"UPDATE library_items SET {cols} WHERE id=?", (*payload.values(), item_id))
                return item_id
            else:
                payload["created_at"] = now
                cols = ", ".join(payload.keys())
                vals = ", ".join("?" for _ in payload)
                cursor = conn.execute(f"INSERT INTO library_items ({cols}) VALUES ({vals})", tuple(payload.values()))
                return cursor.lastrowid

    def list_items(self, phase: str = "", theme: str = "", level: str = "", item_type: str = "", search: str = "") -> list[dict[str, Any]]:
        conditions = []
        params = []
        if phase:
            conditions.append("phase = ?")
            params.append(phase)
        if theme:
            conditions.append("theme = ?")
            params.append(theme)
        if level:
            conditions.append("level = ?")
            params.append(level)
        if item_type:
            conditions.append("item_type = ?")
            params.append(item_type)
        if search:
            conditions.append("(title LIKE ? OR tags LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
            
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return self.db._fetch_all(f"SELECT * FROM library_items {where} ORDER BY title ASC", tuple(params))
        
    def delete_item(self, item_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM library_items WHERE id = ?", (item_id,))

    def export_to_html(self, item_id: int, export_dir: Path) -> Path:
        items = self.list_items()
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            raise AppError("Item não encontrado.")
        
        svg_content = ""
        fen = item.get("fen_pgn", "").strip()
        if fen:
            try:
                import chess
                import chess.svg
                board = chess.Board(fen)
                svg_content = chess.svg.board(board, size=400)
            except Exception as e:
                svg_content = f"<p><em>Erro ao renderizar tabuleiro: {e}</em></p>"

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{item.get('title')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; color: #333; }}
        .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #ccc; padding-bottom: 10px; }}
        .board {{ text-align: center; margin: 30px 0; }}
        .solution {{ margin-top: 50px; padding: 20px; background-color: #f9f9f9; border-left: 4px solid #3B82F6; page-break-inside: avoid; }}
        @media print {{
            .solution {{ page-break-before: always; }}
            button {{ display: none; }}
        }}
    </style>
</head>
<body>
    <button onclick="window.print()" style="float: right; padding: 8px 16px; cursor: pointer;">Imprimir PDF</button>
    <div class="header">
        <h1>{item.get('title')}</h1>
        <p><strong>Fase:</strong> {item.get('phase')} | <strong>Nível:</strong> {item.get('level')} | <strong>Autor:</strong> {item.get('author')}</p>
    </div>
    <div class="content">
        <p>{item.get('content')}</p>
    </div>
    <div class="board">
        {("<img src='" + item.get("cover_image") + "' style='max-width: 100%; max-height: 400px;' />") if item.get("cover_image") else svg_content}
    </div>
    <div class="solution">
        <h3>Solução / Gabarito</h3>
        <p>{item.get('solution')}</p>
    </div>
</body>
</html>"""
        
        safe_title = "".join(c if c.isalnum() else "_" for c in item.get("title", "exercicio"))
        file_path = export_dir / f"{safe_title}_{item_id}.html"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)
        return file_path

    # --- Collections ---
    def list_collections(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            cursor = conn.execute("SELECT id, name, description, created_at, updated_at FROM library_collections ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_collection(self, collection_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            cursor = conn.execute("SELECT * FROM library_collections WHERE id = ?", (collection_id,))
            col = cursor.fetchone()
            if not col:
                return None
            res = dict(col)
            # get items
            c_items = conn.execute(
                "SELECT item_id FROM library_collection_items WHERE collection_id = ? ORDER BY display_order",
                (collection_id,)
            ).fetchall()
            res["items"] = [row["item_id"] for row in c_items]
            return res

    def save_collection(self, payload: dict[str, Any], collection_id: int | None = None) -> None:
        now = self.db.now()
        with self.db.connect() as conn:
            if collection_id:
                conn.execute(
                    "UPDATE library_collections SET name=?, description=?, updated_at=? WHERE id=?",
                    (payload["name"], payload.get("description", ""), now, collection_id)
                )
            else:
                cursor = conn.execute(
                    "INSERT INTO library_collections (name, description, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (payload["name"], payload.get("description", ""), now, now)
                )
                collection_id = cursor.lastrowid
            
            # Update items
            if collection_id is not None:
                conn.execute("DELETE FROM library_collection_items WHERE collection_id = ?", (collection_id,))
                items = payload.get("items", [])
                for i, item_id in enumerate(items):
                    conn.execute(
                        "INSERT INTO library_collection_items (collection_id, item_id, display_order) VALUES (?, ?, ?)",
                        (collection_id, item_id, i)
                    )

    def delete_collection(self, collection_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM library_collections WHERE id = ?", (collection_id,))

    def export_collection_html(self, collection_id: int, export_dir: Path, for_student: bool = True) -> Path:
        col = self.get_collection(collection_id)
        if not col:
            raise AppError("Apostila não encontrada.")
        
        all_items = self.list_items()
        col_items = []
        for iid in col["items"]:
            it = next((i for i in all_items if i["id"] == iid), None)
            if it:
                col_items.append(it)
        
        if not col_items:
            raise AppError("Apostila vazia.")

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{col['name']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; color: #333; }}
        .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #ccc; padding-bottom: 10px; }}
        .item-box {{ margin-bottom: 50px; page-break-inside: avoid; }}
        .board {{ text-align: center; margin: 15px 0; }}
        .solution-section {{ page-break-before: always; margin-top: 50px; padding-top: 20px; border-top: 2px solid #3B82F6; }}
        .sol-item {{ margin-bottom: 20px; background-color: #f9f9f9; padding: 15px; border-left: 4px solid #3B82F6; }}
        @media print {{
            button {{ display: none; }}
        }}
    </style>
</head>
<body>
    <button onclick="window.print()" style="float: right; padding: 8px 16px; cursor: pointer;">Imprimir PDF</button>
    <div class="header">
        <h1>{col['name']}</h1>
        <p>{col.get('description', '')}</p>
        <p><strong>Total de itens:</strong> {len(col_items)}</p>
    </div>
"""
        
        import chess
        import chess.svg

        # Renderizar Exercicios
        for idx, item in enumerate(col_items, 1):
            svg_content = ""
            fen = item.get("fen_pgn", "").strip()
            if fen:
                try:
                    board = chess.Board(fen)
                    svg_content = chess.svg.board(board, size=350)
                except Exception as e:
                    svg_content = f"<p><em>Erro ao renderizar: {e}</em></p>"

            html += f"""
    <div class="item-box">
        <h3>{idx}. {item.get('title')}</h3>
        <p><em>Fase: {item.get('phase')} | Nível: {item.get('level')}</em></p>
        <p>{item.get('content', '')}</p>
        {("<img src='" + item.get("cover_image") + "' style='max-width: 100%; max-height: 400px;' />") if item.get("cover_image") else svg_content}
    </div>
"""

        # Renderizar Gabaritos (Se for para professor)
        if not for_student:
            html += """
    <div class="solution-section">
        <h2>Gabarito do Professor</h2>
"""
            for idx, item in enumerate(col_items, 1):
                html += f"""
        <div class="sol-item">
            <h4>{idx}. {item.get('title')}</h4>
            <p>{item.get('solution', 'Sem solução cadastrada.')}</p>
        </div>
"""
            html += "    </div>"

        html += "\n</body>\n</html>"
        
        safe_title = "".join(c if c.isalnum() else "_" for c in col['name'])
        suffix = "Aluno" if for_student else "Professor"
        file_path = export_dir / f"Apostila_{safe_title}_{suffix}_{collection_id}.html"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)
        return file_path

    def export_collection_pdf(self, collection_id: int, export_dir: Path, for_student: bool = True) -> Path:
        col = self.get_collection(collection_id)
        if not col:
            raise AppError("Apostila não encontrada.")
        
        all_items = self.list_items()
        col_items = []
        for iid in col["items"]:
            it = next((i for i in all_items if i["id"] == iid), None)
            if it:
                col_items.append(it)
        
        if not col_items:
            raise AppError("Apostila vazia.")

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from svglib.svglib import svg2rlg
            import chess
            import chess.svg
            import tempfile
            import os
        except ImportError as exc:
            raise AppError("Instale reportlab e svglib para gerar PDF nativo.") from exc

        safe_title = "".join(c if c.isalnum() else "_" for c in col['name'])
        suffix = "Aluno" if for_student else "Professor"
        file_path = export_dir / f"Apostila_{safe_title}_{suffix}_{collection_id}.pdf"

        doc = SimpleDocTemplate(str(file_path), pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(col['name'], styles['Title']))
        if col.get('description'):
            elements.append(Paragraph(col['description'], styles['Normal']))
        elements.append(Spacer(1, 20))

        with tempfile.TemporaryDirectory() as temp_dir:
            for idx, item in enumerate(col_items, 1):
                elements.append(Paragraph(f"<b>{idx}. {item.get('title')}</b>", styles['Heading3']))
                meta_text = f"<i>Fase: {item.get('phase')} | Nível: {item.get('level')}</i>"
                elements.append(Paragraph(meta_text, styles['Normal']))
                
                if item.get('content'):
                    elements.append(Spacer(1, 5))
                    elements.append(Paragraph(item['content'], styles['Normal']))

                fen = item.get("fen_pgn", "").strip()
                if fen:
                    try:
                        board = chess.Board(fen)
                        svg_data = chess.svg.board(board, size=250)
                        svg_path = os.path.join(temp_dir, f"board_{idx}.svg")
                        with open(svg_path, "w", encoding="utf-8") as f:
                            f.write(svg_data)
                        
                        drawing = svg2rlg(svg_path)
                        if drawing:
                            drawing.hAlign = 'CENTER'
                            elements.append(Spacer(1, 10))
                            elements.append(drawing)
                    except Exception as e:
                        elements.append(Paragraph(f"<i>Erro ao renderizar: {e}</i>", styles['Normal']))
                
                elements.append(Spacer(1, 20))

            if not for_student:
                elements.append(PageBreak())
                elements.append(Paragraph("Gabarito do Professor", styles['Title']))
                elements.append(Spacer(1, 20))
                for idx, item in enumerate(col_items, 1):
                    elements.append(Paragraph(f"<b>{idx}. {item.get('title')}</b>", styles['Heading4']))
                    elements.append(Paragraph(item.get('solution') or "Sem solução cadastrada.", styles['Normal']))
                    elements.append(Spacer(1, 10))

            doc.build(elements)

        return file_path

    # --- History ---
    def record_history(self, class_id: int, collection_id: int | None = None, item_id: int | None = None, notes: str = "") -> None:
        now = self.db.now()[:10]
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO library_history (class_id, collection_id, item_id, sent_date, notes) VALUES (?, ?, ?, ?, ?)",
                (class_id, collection_id, item_id, now, notes)
            )

    def list_history(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            cursor = conn.execute('''
                SELECT h.*, c.name as class_name, col.name as collection_name, i.title as item_name
                FROM library_history h
                LEFT JOIN classes c ON h.class_id = c.id
                LEFT JOIN library_collections col ON h.collection_id = col.id
                LEFT JOIN library_items i ON h.item_id = i.id
                ORDER BY h.id DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def check_repetition(self, class_id: int, collection_id: int | None = None, item_id: int | None = None) -> list[str]:
        """Verifica se os itens foram aplicados nesta turma nos últimos 183 dias.
        Retorna uma lista de nomes de itens que estão repetidos.
        """
        repeated_items = []
        limit_date = (date.today() - timedelta(days=183)).isoformat()
        
        items_to_check = []
        if item_id:
            items_to_check.append(item_id)
        elif collection_id:
            col = self.get_collection(collection_id)
            if col and "items" in col:
                items_to_check.extend(col["items"])
        
        if not items_to_check:
            return []

        with self.db.connect() as conn:
            for i_id in items_to_check:
                # Check history either by item_id directly or via collection_id
                # (if the item was sent as part of a collection)
                cursor = conn.execute('''
                    SELECT h.sent_date, i.title
                    FROM library_history h
                    LEFT JOIN library_items i ON i.id = ?
                    WHERE h.class_id = ? 
                      AND h.sent_date >= ?
                      AND (h.item_id = ? OR h.collection_id IN (
                          SELECT collection_id FROM library_collection_items WHERE item_id = ?
                      ))
                ''', (i_id, class_id, limit_date, i_id, i_id))
                
                row = cursor.fetchone()
                if row:
                    repeated_items.append(row["title"] or f"Item {i_id}")
                    
        return list(set(repeated_items))

    # --- PGN Import ---
    def import_pgn(self, pgn_content: str) -> int:
        """Parseia um bloco de texto PGN e salva as posições-chave no Acervo.
        Retorna o número de itens importados."""
        import chess.pgn
        import io
        
        imported_count = 0
        pgn_file = io.StringIO(pgn_content)
        
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break
                
            base_title = game.headers.get("Event", "Estudo PGN")
            if base_title == "?":
                base_title = "Exercício Importado"

            # Se o PGN já inicia com FEN (como em puzzles)
            initial_fen = game.headers.get("FEN")
            
            # Vamos iterar pela partida procurando posições com "!" ou "!!" (NAG 1 ou 3)
            # Ou se for um puzzle curto (menos de 10 lances), salvar a posição inicial
            node = game
            tactics_found = 0
            
            while node.variations:
                next_node = node.variation(0)
                # Verifica se o próximo lance é brilhante ou bom (NAGs)
                # NAG 1 = !, NAG 3 = !!
                if 1 in next_node.nags or 3 in next_node.nags:
                    board = node.board()
                    fen = board.fen()
                    sol_move = next_node.move
                    sol_san = board.san(sol_move)
                    
                    payload = {
                        "title": f"{base_title} - Lance Tático",
                        "item_type": "exercise",
                        "phase": "middlegame",
                        "level": "intermediate",
                        "fen_pgn": fen,
                        "solution": f"Lance correto: {sol_san}",
                        "tags": "importado, tática",
                        "author": game.headers.get("White", "") + " vs " + game.headers.get("Black", "")
                    }
                    self.save_item(payload)
                    imported_count += 1
                    tactics_found += 1
                
                node = next_node
                
            # Se não achou táticas específicas marcadas com !, e tinha FEN inicial, salva o início
            if tactics_found == 0 and initial_fen:
                # O PGN é provávelmente um único problema tático
                board = game.board()
                solution_text = []
                n = game
                while n.variations:
                    n = n.variation(0)
                    solution_text.append(n.board().san(n.move)) # wait, san needs previous board
                
                # reconstruindo SAN:
                san_moves = []
                n = game
                while n.variations:
                    b = n.board()
                    san_moves.append(b.san(n.variation(0).move))
                    n = n.variation(0)

                payload = {
                    "title": f"{base_title} - Puzzle",
                    "item_type": "exercise",
                    "phase": "general",
                    "level": "intermediate",
                    "fen_pgn": initial_fen,
                    "solution": " ".join(san_moves),
                    "tags": "importado, puzzle",
                    "author": game.headers.get("Site", "")
                }
                self.save_item(payload)
                imported_count += 1

        return imported_count
