from __future__ import annotations

import logging
import sys
import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

import customtkinter as ctk
from tkcalendar import DateEntry

from src.core.database import BASE_DIR, Database, default_backup_dir, default_export_dir
from src.core.logging_config import configure_logging, current_log_path
from src.core.services import (
    ATTENDANCE_STATUSES,
    BILLING_CYCLES,
    CERTIFICATE_ORIENTATIONS,
    CERTIFICATE_TYPES,
    COMPETITION_TYPES,
    EVENT_STATUSES,
    EVENT_TYPES,
    EXERCISE_ATTEMPT_RESULTS,
    EXERCISE_DIFFICULTIES,
    INITIAL_ORDER_OPTIONS,
    INVENTORY_CONDITIONS,
    INVENTORY_ITEM_TYPES,
    INVENTORY_LOAN_STATUSES,
    INVENTORY_MAINTENANCE_STATUSES,
    OPERATOR_ROLES,
    PAIRING_METHODS,
    PAYMENT_STATUSES,
    PLAYER_STATUSES,
    RESULTS,
    TEAM_PAIRING_METHODS,
    TEAM_PLAYER_ROLES,
    TEAM_STANDING_CRITERIA,
    TOURNAMENT_FLAG_FIELDS,
    TOURNAMENT_PROFILES,
    TOURNAMENT_SCOPES,
    TOURNAMENT_TYPES,
    TRAINING_LIST_STATUSES,
    TRAINING_SESSION_STATUSES,
    TRAINING_SESSION_TYPES,
    AppError,
    CalendarService,
    CertificateService,
    ClockIntegrationService,
    LibraryService,
    ClubService,
    CommunicationService,
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
    LocalResultServer,
    MemberService,
    OfficialRatingService,
    PairingService,
    QRResultService,
    RefereeService,
    SecurityService,
    SyncService,
    TeamService,
    TournamentService,
    TrainingService,
    pairing_player_name,
    player_full_name,
    player_pairing_name,
)

# Escala tipográfica — use estes tokens em vez de literais em CTkFont(size=...)
SIZE_PAGE_TITLE = 22       # Título de página (consumido por _page_title)
SIZE_PAGE_SUBTITLE = 14    # Subtítulo de página
SIZE_SECTION = 15          # Cabeçalho de painel/seção
SIZE_SUBSECTION = 13       # Mini-cabeçalho dentro de painel
SIZE_KPI_VALUE = 22        # Valor numérico em card de KPI
SIZE_BODY = 12             # Texto corrido


def font_section() -> ctk.CTkFont:
    return ctk.CTkFont(size=SIZE_SECTION, weight="bold")


def font_subsection() -> ctk.CTkFont:
    return ctk.CTkFont(size=SIZE_SUBSECTION, weight="bold")


def font_kpi_value() -> ctk.CTkFont:
    return ctk.CTkFont(size=SIZE_KPI_VALUE, weight="bold")


# Tema Antigravity (Light / Dark)
THEME_APP_BG = ("#F8FAFC", "#0B0F19")
THEME_PANEL_BG = ("#FFFFFF", "#1E293B")
THEME_TEXT_MAIN = ("#0F172A", "#F1F5F9")
THEME_TEXT_SUB = ("#64748B", "#94A3B8")
THEME_STATUSBAR_BG = ("#E2E8F0", "#0F172A")
THEME_TREE_BG = ("#FFFFFF", "#1E293B")
THEME_TREE_FG = ("#0F172A", "#F1F5F9")
THEME_ACCENT = ("#3B82F6", "#38BDF8")
THEME_DANGER = ("#EF4444", "#F87171")
THEME_INFO = ("#10B981", "#34D399")

logger = logging.getLogger("src.ui")


def resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return BASE_DIR / relative_path


MEMBER_TYPE_LABELS = {
    "socio": "Socio",
    "aluno": "Aluno",
    "convidado": "Convidado",
    "visitante": "Visitante",
}
MEMBER_TYPE_VALUES = {label: value for value, label in MEMBER_TYPE_LABELS.items()}
MEMBER_STATUS_LABELS = {
    "active": "Ativo",
    "inactive": "Inativo",
    "visitor": "Visitante",
    "guest": "Convidado",
    "withdrawn": "Desistente",
}
MEMBER_STATUS_VALUES = {label: value for value, label in MEMBER_STATUS_LABELS.items()}
PLAYER_STATUS_VALUES = {label: value for value, label in PLAYER_STATUSES.items()}
TRAINING_TYPE_LABELS = {value: label for value, label in TRAINING_SESSION_TYPES.items()}
TRAINING_TYPE_VALUES = {label: value for value, label in TRAINING_TYPE_LABELS.items()}
TRAINING_STATUS_LABELS = {value: label for value, label in TRAINING_SESSION_STATUSES.items()}
TRAINING_STATUS_VALUES = {label: value for value, label in TRAINING_STATUS_LABELS.items()}
ATTENDANCE_STATUS_LABELS = {value: label for value, label in ATTENDANCE_STATUSES.items()}
ATTENDANCE_STATUS_VALUES = {label: value for value, label in ATTENDANCE_STATUS_LABELS.items()}
EXERCISE_DIFFICULTY_LABELS = {value: label for value, label in EXERCISE_DIFFICULTIES.items()}
EXERCISE_DIFFICULTY_VALUES = {label: value for value, label in EXERCISE_DIFFICULTY_LABELS.items()}
TRAINING_LIST_STATUS_LABELS = {value: label for value, label in TRAINING_LIST_STATUSES.items()}
TRAINING_LIST_STATUS_VALUES = {label: value for value, label in TRAINING_LIST_STATUS_LABELS.items()}
EXERCISE_ATTEMPT_RESULT_LABELS = {value: label for value, label in EXERCISE_ATTEMPT_RESULTS.items()}
EXERCISE_ATTEMPT_RESULT_VALUES = {label: value for value, label in EXERCISE_ATTEMPT_RESULT_LABELS.items()}
BILLING_CYCLE_LABELS = {value: label for value, label in BILLING_CYCLES.items()}
BILLING_CYCLE_VALUES = {label: value for value, label in BILLING_CYCLE_LABELS.items()}
PAYMENT_STATUS_LABELS = {value: label for value, label in PAYMENT_STATUSES.items()}
PAYMENT_STATUS_VALUES = {label: value for value, label in PAYMENT_STATUS_LABELS.items()}
EVENT_TYPE_LABELS = {value: label for value, label in EVENT_TYPES.items()}
EVENT_TYPE_VALUES = {label: value for value, label in EVENT_TYPE_LABELS.items()}
EVENT_STATUS_LABELS = {value: label for value, label in EVENT_STATUSES.items()}
EVENT_STATUS_VALUES = {label: value for value, label in EVENT_STATUS_LABELS.items()}
INVENTORY_ITEM_TYPE_LABELS = {value: label for value, label in INVENTORY_ITEM_TYPES.items()}
INVENTORY_ITEM_TYPE_VALUES = {label: value for value, label in INVENTORY_ITEM_TYPE_LABELS.items()}
INVENTORY_CONDITION_LABELS = {value: label for value, label in INVENTORY_CONDITIONS.items()}
INVENTORY_CONDITION_VALUES = {label: value for value, label in INVENTORY_CONDITION_LABELS.items()}
INVENTORY_LOAN_STATUS_LABELS = {value: label for value, label in INVENTORY_LOAN_STATUSES.items()}
INVENTORY_LOAN_STATUS_VALUES = {label: value for value, label in INVENTORY_LOAN_STATUS_LABELS.items()}
INVENTORY_MAINTENANCE_STATUS_LABELS = {
    value: label for value, label in INVENTORY_MAINTENANCE_STATUSES.items()
}
INVENTORY_MAINTENANCE_STATUS_VALUES = {
    label: value for value, label in INVENTORY_MAINTENANCE_STATUS_LABELS.items()
}
OPERATOR_ROLE_LABELS = {value: label for value, label in OPERATOR_ROLES.items()}
OPERATOR_ROLE_VALUES = {label: value for value, label in OPERATOR_ROLE_LABELS.items()}

FIDE_CATEGORIES = [
    "",
    "Absoluto",
    "Feminino",
    "Sub-8 (U8)",
    "Sub-10 (U10)",
    "Sub-12 (U12)",
    "Sub-14 (U14)",
    "Sub-16 (U16)",
    "Sub-18 (U18)",
    "Sub-20 (U20)",
    "Sênior 50+",
    "Sênior 65+",
    "Escolar Sub-7 (U7)",
    "Escolar Sub-9 (U9)",
    "Escolar Sub-11 (U11)",
    "Escolar Sub-13 (U13)",
    "Escolar Sub-15 (U15)",
    "Escolar Sub-17 (U17)",
]
COMPETITION_TYPE_VALUES = {label: value for value, label in COMPETITION_TYPES.items()}
TEAM_PAIRING_METHOD_VALUES = {label: value for value, label in TEAM_PAIRING_METHODS.items()}
TEAM_PLAYER_ROLE_VALUES = {label: value for value, label in TEAM_PLAYER_ROLES.items()}
TEAM_STANDING_CRITERIA_VALUES = {label: value for value, label in TEAM_STANDING_CRITERIA.items()}
CERTIFICATE_TYPE_VALUES = {label: value for value, label in CERTIFICATE_TYPES.items()}
CERTIFICATE_ORIENTATION_VALUES = {label: value for value, label in CERTIFICATE_ORIENTATIONS.items()}
CLUB_KIND_LABELS = {
    "club": "Clube",
    "school": "Escola",
    "project": "Projeto",
    "partner": "Parceiro",
}
CLUB_KIND_VALUES = {label: value for value, label in CLUB_KIND_LABELS.items()}
TOURNAMENT_SCOPE_VALUES = {label: value for value, label in TOURNAMENT_SCOPES.items()}
PAIRING_METHOD_VALUES = {label: value for value, label in PAIRING_METHODS.items()}

class ErrorCatchingMixin:
    def _disable_if_unauthorized(self, widget: ctk.CTkBaseClass, action: str) -> None:
        """Verifica se o operador atual tem permissão, se não tiver, desabilita o botão/widget."""
        if hasattr(self, "security_service"):
            if not self.security_service.has_permission(action):
                if hasattr(widget, "configure"):
                    try:
                        widget.configure(state="disabled")
                    except Exception:
                        pass
                        
    def _show_error(self, message_or_exception: str | Exception) -> None:
        message = str(message_or_exception)
        logger.error("Erro na interface: %s", message, exc_info=True)
        messagebox.showerror("Erro", message)

    def _show_info(self, message: str) -> None:
        messagebox.showinfo("Sucesso", message)

    def _show_warning(self, message: str) -> None:
        messagebox.showwarning("Aviso", message)

    def _confirm_action(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message)

    def _ask_string(self, title: str, prompt: str) -> str | None:
        dialog = ctk.CTkInputDialog(text=prompt, title=title)
        return dialog.get_input()

    def _print_document(self, path: Path) -> None:
        try:
            document_path = Path(path)
            if not document_path.exists():
                raise FileNotFoundError(document_path)
            if sys.platform == "win32" and hasattr(os, "startfile"):
                os.startfile(str(document_path), "print")
                return

            print_command = shutil.which("lp") or shutil.which("lpr")
            if print_command:
                subprocess.Popen([print_command, str(document_path)])
                self._show_info("Documento enviado para a impressora padrão.")
                return

            if sys.platform == "darwin":
                subprocess.Popen(["open", str(document_path)])
            else:
                webbrowser.open(document_path.resolve().as_uri())
            self._show_info("Nao encontrei comando de impressao. O documento foi aberto para impressao manual.")
        except Exception as exc:
            self._show_error(f"Não foi possível iniciar a impressão: {exc}")

        
class UIBuilderMixin(ErrorCatchingMixin):
    """Helpers de UI que NÃO são reimplementados em AlbericusApp.

    Primitivos como _page_title, _make_panel, _make_scrollable_panel, _make_tree,
    _clear_content e _grid_form_buttons vivem em app.py (AlbericusApp) — fonte única
    de verdade. Não duplique aqui.
    """

    def _make_date_entry(self, parent: Any, width: int = 20) -> DateEntry:
        # width em DateEntry e medido em caracteres, o padrao de 20 e suficiente
        # Ajustamos a estetica para ficar proxima do tema Antigravity
        entry = DateEntry(
            parent,
            width=width,
            background="#3B82F6", # THEME_ACCENT light
            foreground="white",
            headersbackground="#1E293B", # THEME_PANEL_BG dark
            headersforeground="white",
            selectbackground="#38BDF8", # THEME_ACCENT dark
            selectforeground="black",
            normalbackground="#FFFFFF",
            normalforeground="#0F172A",
            weekendbackground="#FFFFFF",
            weekendforeground="#0F172A",
            othermonthforeground="#94A3B8",
            othermonthbackground="#FFFFFF",
            othermonthweforeground="#94A3B8",
            othermonthwebackground="#FFFFFF",
            date_pattern="y-mm-dd",
            showweeknumbers=False,
            font=("Inter", 10),
            borderwidth=1,
            relief="solid",
        )
        return entry

