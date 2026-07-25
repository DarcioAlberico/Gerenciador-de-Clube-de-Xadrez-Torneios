from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import date, datetime
from pathlib import Path
from tkinter import Toplevel, filedialog, ttk
from typing import Any, Callable

import customtkinter as ctk
from tkcalendar import Calendar

from src.core.database import BASE_DIR, Database, default_backup_dir, default_export_dir
from src.core.logging_config import configure_logging, current_log_path
from src.core.services import (
    ACCELERATION_METHODS,
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
    MEMBER_TYPES,
    OPERATOR_ROLES,
    PAIRING_METHODS,
    PAYMENT_STATUSES,
    PLAYER_STATUSES,
    REQUESTED_BYE_TYPES,
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
    BatchExportService,
    CalendarService,
    CertificateService,
    ChessResultsService,
    ClockIntegrationService,
    LibraryService,
    ClubService,
    CommunicationService,
    DashboardService,
    EventService,
    ExerciseService,
    ExportService,
    FideRatingService,
    FinanceService,
    GoogleFormsService,
    GuardianService,
    ImportService,
    InternalRatingService,
    InventoryService,
    LearningLevelService,
    ListLayoutService,
    LocalResultServer,
    MemberService,
    NormAssistantService,
    OfficialRatingService,
    PairingService,
    PhotoAlbumService,
    PrizeService,
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

# Tokens e presets vivem em theme.py (fonte única). Re-exportados aqui porque as
# telas ainda fazem `from ..support import *` — some quando elas migrarem para
# imports explícitos (F1.6). Código novo deve importar de `..theme`.
from .theme import (  # noqa: F401
    ACCENT_PRESET_LABELS,
    ACCENT_PRESETS,
    BG_COLOR_PRESET_LABELS,
    BG_COLOR_PRESETS,
    BG_PRESET_LABELS,
    BG_PRESETS,
    CURATED_THEMES,
    FRAME_BG_PRESET_LABELS,
    FRAME_BG_PRESETS,
    SIZE_BODY,
    SIZE_KPI_VALUE,
    SIZE_PAGE_SUBTITLE,
    SIZE_PAGE_TITLE,
    SIZE_SECTION,
    SIZE_SUBSECTION,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
    SPACE_XS,
    THEME_ACCENT,
    THEME_APP_BG,
    THEME_DANGER,
    THEME_DANGER_HOVER,
    THEME_INFO,
    THEME_NEUTRAL,
    THEME_NEUTRAL_HOVER,
    THEME_PANEL_BG,
    THEME_STATUSBAR_BG,
    THEME_SUCCESS,
    THEME_SUCCESS_HOVER,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    THEME_TREE_BG,
    THEME_TREE_FG,
    THEME_WARNING,
    THEME_WARNING_TEXT,
    ColorToken,
    apply_accent_preset,
    apply_bg_preset,
    apply_frame_bg_preset,
    curated_theme_swatches,
    font_kpi_value,
    font_section,
    font_subsection,
    match_curated_theme,
    notify_theme_change,
    off_theme_change,
    on_theme_change,
)

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

def _classify_error(error: str | Exception, error_id: str) -> tuple[str, str, bool]:
    """Classifica um erro em ``(titulo, mensagem, inesperado)`` — puro e testavel.

    Strings e excecoes de dominio/IO conhecidas sao "recuperaveis"
    (``inesperado=False``) e viram toast; o resto vira modal com codigo e caminho
    do log. Aceitar ``str`` e proposital: muitas telas chamam ``_show_error`` com
    uma mensagem pronta (validacao de formulario, regra de negocio)."""
    if isinstance(error, str):
        return "Erro", error, False
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
                        
    def _modal_is_open(self) -> bool:
        """True se ha um modal com grab ativo (um toast ficaria escondido atras)."""
        try:
            return bool(self.grab_current())
        except Exception:
            return False

    def _feedback(self, message: str, kind: str, title: str) -> None:
        """Feedback nao-bloqueante (toast); se ha um modal aberto por cima, usa um
        alerta bloqueante -- senao o toast ficaria escondido atras do modal."""
        if self._modal_is_open() or not hasattr(self, "_show_toast"):
            from .components.dialogs import alert_dialog

            alert_dialog(self, title, message, kind=kind)
        else:
            duration = 5000 if kind in ("error", "warning") else 3500
            self._show_toast(message, kind=kind, duration_ms=duration)

    def _show_error(self, message_or_exception: str | Exception) -> None:
        error_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        title, message, is_unexpected = _classify_error(message_or_exception, error_id)
        if is_unexpected:
            logger.error(
                "Erro inesperado [%s]",
                error_id,
                exc_info=(
                    type(message_or_exception),
                    message_or_exception,
                    getattr(message_or_exception, "__traceback__", None),
                ),
            )
            from .components.dialogs import alert_dialog

            alert_dialog(self, title, message, kind="error")
        else:
            logger.warning("%s: %s", title, message_or_exception)
            self._feedback(message, "error", title)

    def _show_info(self, message: str) -> None:
        self._feedback(message, "success", "Sucesso")

    def _show_warning(self, message: str) -> None:
        self._feedback(message, "warning", "Aviso")

    def _confirm_action(self, title: str, message: str, *, danger: bool = False) -> bool:
        from .components.dialogs import confirm_dialog

        return confirm_dialog(self, title, message, danger=danger)

    def _delete_with_undo(
        self,
        delete: Callable[[], None],
        restore: Callable[[], None] | None,
        message: str,
        refresh: Callable[[], None] | None = None,
    ) -> None:
        """Exclui e oferece **Desfazer** no toast (ESPEC_UI_UX §5.1 / P1-6).

        ``restore`` recria o registro a partir de um retrato tirado **antes** da
        exclusao — o id novo pode diferir do original, entao so serve para
        registros sem dependentes. Em exclusao com cascata passe ``None``: o
        toast sai sem acao e a confirmacao explicita segue sendo a protecao.
        """
        delete()
        if refresh is not None:
            refresh()
        if restore is None:
            self._show_toast(message, kind="success")
            return

        def undo() -> None:
            try:
                restore()
                if refresh is not None:
                    refresh()
                self._show_toast("Exclusao desfeita.", kind="info")
            except Exception as exc:
                self._show_error(exc)

        self._show_toast(message, kind="success", action=("Desfazer", undo))

    def _confirm_or_cancel(
        self,
        title: str,
        message: str,
        *,
        yes_text: str = "Sim",
        no_text: str = "Não",
        cancel_text: str = "Cancelar",
    ) -> bool | None:
        from .components.dialogs import tri_state_dialog

        return tri_state_dialog(
            self, title, message, yes_text=yes_text, no_text=no_text, cancel_text=cancel_text
        )

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
                self._show_toast("Documento enviado para a impressora padrão.", kind="success")
                return

            if sys.platform == "darwin":
                subprocess.Popen(["open", str(document_path)])
            else:
                webbrowser.open(document_path.resolve().as_uri())
            self._show_info("Nao encontrei comando de impressao. O documento foi aberto para impressao manual.")
        except Exception as exc:
            self._show_error(f"Não foi possível iniciar a impressão: {exc}")

        
def _date_digits_from_any(value: str) -> str:
    """Extrai os 8 digitos (DDMMAAAA) de um valor ISO, BR ou solto."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = date.fromisoformat(text)
        return f"{parsed.day:02d}{parsed.month:02d}{parsed.year:04d}"
    except ValueError:
        pass
    return re.sub(r"\D", "", text)[:8]


def parse_br_date(text: str) -> date | None:
    """Converte 'DD/MM/AAAA' (ou so digitos) em date; None se invalida/incompleta."""
    digits = re.sub(r"\D", "", str(text or ""))
    if len(digits) != 8:
        return None
    try:
        return date(int(digits[4:8]), int(digits[2:4]), int(digits[0:2]))
    except ValueError:
        return None


class MaskedDateEntry(ctk.CTkEntry):
    """Campo de data com mascara DD/MM/AAAA, seguindo o tema do app.

    Exibe no formato brasileiro mas faz entrada/saida em ISO (AAAA-MM-DD):
      - ``insert(0, valor)`` aceita ISO (vindo do banco) ou BR e mostra DD/MM/AAAA;
      - ``get()`` devolve AAAA-MM-DD quando a data e valida, senao "" (vazio).

    A mascara aceita apenas digitos (as barras entram sozinhas), bloqueia mes > 12
    e dia > 31 enquanto digita, e pinta a borda de vermelho ao sair do campo quando
    a data esta incompleta/invalida. Datas vazias sao permitidas.
    """

    def __init__(self, master: Any, **kwargs: Any) -> None:
        kwargs.setdefault("placeholder_text", "dd/mm/aaaa")
        super().__init__(master, **kwargs)
        self._cal_popup: Toplevel | None = None
        try:
            self._default_border = self.cget("border_color")
        except Exception:
            self._default_border = None
        try:
            self._entry.bind("<KeyPress>", self._on_key)
            self._entry.bind("<FocusOut>", self._on_blur, add="+")
            self._entry.bind("<<Paste>>", self._on_paste)
        except Exception:
            pass

    # -- helpers internos --------------------------------------------------
    def _current_digits(self) -> str:
        return re.sub(r"\D", "", super().get())[:8]

    @staticmethod
    def _mask(digits: str) -> str:
        d = digits[:8]
        out = d[:2]
        if len(d) > 2:
            out += "/" + d[2:4]
        if len(d) > 4:
            out += "/" + d[4:8]
        return out

    @staticmethod
    def _clamp(digits: str) -> str:
        """Descarta digitos que tornariam o dia > 31 ou o mes > 12."""
        out = ""
        for index, char in enumerate(digits[:8]):
            candidate = out + char
            if index == 0 and int(char) > 3:
                continue
            if index == 1 and not 1 <= int(candidate[0:2]) <= 31:
                continue
            if index == 2 and int(char) > 1:
                continue
            if index == 3 and not 1 <= int(candidate[2:4]) <= 12:
                continue
            out = candidate
        return out

    def _render(self, digits: str) -> None:
        super().delete(0, "end")
        masked = self._mask(digits)
        if masked:
            super().insert(0, masked)
        try:
            self._entry.icursor("end")
        except Exception:
            pass
        self._set_valid(True)

    def _set_valid(self, ok: bool) -> None:
        if self._default_border is None:
            return
        try:
            self.configure(border_color=self._default_border if ok else THEME_DANGER)
        except Exception:
            pass

    # -- eventos -----------------------------------------------------------
    def _on_key(self, event: Any) -> str | None:
        if event.state & 0x4:  # Control: nao interfere em copiar/colar/selecionar
            return None
        if event.keysym in ("Down", "F4"):  # abre o calendario (atalho de date picker)
            self._open_calendar()
            return "break"
        if event.keysym in (
            "Left", "Right", "Home", "End", "Tab", "ISO_Left_Tab",
            "Return", "KP_Enter", "Up",
        ):
            return None
        if event.keysym in ("BackSpace", "Delete"):
            self._render(self._current_digits()[:-1])
            return "break"
        char = event.char
        if char and char.isdigit():
            self._render(self._clamp(self._current_digits() + char))
            return "break"
        if char and char.isprintable():
            return "break"  # bloqueia letras e simbolos
        return None

    def _on_paste(self, _event: Any) -> str:
        try:
            text = self.clipboard_get()
        except Exception:
            text = ""
        self._render(self._clamp(_date_digits_from_any(text)))
        return "break"

    def _on_blur(self, _event: Any = None) -> None:
        raw = super().get().strip()
        self._set_valid(not raw or parse_br_date(raw) is not None)

    # -- calendario (F4 / seta para baixo) --------------------------------
    def _close_calendar(self) -> None:
        popup = self._cal_popup
        self._cal_popup = None
        if popup is not None:
            try:
                popup.grab_release()
            except Exception:
                pass
            try:
                popup.destroy()
            except Exception:
                pass

    def _open_calendar(self) -> None:
        if self._cal_popup is not None:  # ja aberto: alterna (fecha)
            self._close_calendar()
            return
        try:
            face = 1 if ctk.get_appearance_mode() == "Dark" else 0
            panel = THEME_PANEL_BG[face]
            popup = Toplevel(self)
            popup.overrideredirect(True)
            popup.configure(bg=panel, highlightthickness=1, highlightbackground=THEME_ACCENT[face])
            popup.transient(self.winfo_toplevel())
            self._cal_popup = popup

            current = parse_br_date(super().get())
            cal_kwargs: dict[str, Any] = dict(
                selectmode="day",
                locale="pt_BR",
                showweeknumbers=False,
                firstweekday="sunday",
                background=THEME_STATUSBAR_BG[face],
                foreground=THEME_TEXT_MAIN[face],
                headersbackground=THEME_STATUSBAR_BG[face],
                headersforeground=THEME_TEXT_MAIN[face],
                normalbackground=panel,
                normalforeground=THEME_TEXT_MAIN[face],
                weekendbackground=panel,
                weekendforeground=THEME_TEXT_MAIN[face],
                othermonthbackground=panel,
                othermonthwebackground=panel,
                othermonthforeground=THEME_TEXT_SUB[face],
                othermonthweforeground=THEME_TEXT_SUB[face],
                selectbackground=THEME_ACCENT[face],
                selectforeground="#FFFFFF",
                bordercolor=panel,
            )
            if current:
                cal_kwargs.update(year=current.year, month=current.month, day=current.day)
            try:
                cal = Calendar(popup, **cal_kwargs)
            except Exception:
                cal_kwargs.pop("locale", None)  # ambiente sem locale pt_BR
                cal = Calendar(popup, **cal_kwargs)
            cal.pack(padx=6, pady=6)

            def choose(_event: Any = None) -> None:
                selected = cal.selection_get()
                if selected is not None:
                    self._render(f"{selected.day:02d}{selected.month:02d}{selected.year:04d}")
                self._close_calendar()
                try:
                    self._entry.focus_set()
                except Exception:
                    pass

            cal.bind("<<CalendarSelected>>", choose)

            footer = ctk.CTkFrame(popup, fg_color="transparent")
            footer.pack(fill="x", padx=6, pady=(0, 6))
            ctk.CTkButton(
                footer, text="Hoje", width=70, height=26,
                command=lambda: (cal.selection_set(date.today()), choose()),
            ).pack(side="left")
            ctk.CTkButton(
                footer, text="Limpar", width=70, height=26,
                fg_color=THEME_NEUTRAL, hover_color=THEME_NEUTRAL_HOVER,
                command=lambda: (self.delete(0, "end"), self._close_calendar(), self._entry.focus_set()),
            ).pack(side="right")

            popup.update_idletasks()
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height() + 2
            popup.geometry(f"+{x}+{y}")
            popup.lift()
            popup.bind("<Escape>", lambda _e: self._close_calendar())
            try:
                popup.grab_set()
            except Exception:
                pass
        except Exception:
            logger.debug("Falha ao abrir o calendario do campo de data", exc_info=True)
            self._close_calendar()

    # -- API compativel com CTkEntry --------------------------------------
    def insert(self, index: Any, value: Any) -> None:  # type: ignore[override]
        self._render(_date_digits_from_any(str(value or "")))

    def delete(self, first_index: Any = 0, last_index: Any = None) -> None:  # type: ignore[override]
        super().delete(0, "end")
        self._set_valid(True)

    def get(self) -> str:  # type: ignore[override]
        parsed = parse_br_date(super().get())
        return parsed.isoformat() if parsed else ""


class UIBuilderMixin(ErrorCatchingMixin):
    """Helpers de UI que NÃO são reimplementados em AlbericusApp.

    Primitivos como _page_title, _make_panel, _make_scrollable_panel, _make_tree,
    _clear_content e _grid_form_buttons vivem em app.py (AlbericusApp) — fonte única
    de verdade. Não duplique aqui.
    """

    def _make_date_entry(self, parent: Any, width: int = 20) -> MaskedDateEntry:
        """Campo de data brasileiro: DD/MM/AAAA na tela, ISO (AAAA-MM-DD) por baixo.

        Mantem a assinatura antiga; o ``width`` herdado (em caracteres da epoca do
        tkcalendar) e convertido para pixels com um teto, pois a data cabe em
        ~120-220px. Os call-sites seguem usando get()/insert()/delete() normalmente.
        """
        width_px = max(120, min(220, int(width) * 7))
        return MaskedDateEntry(parent, width=width_px)

