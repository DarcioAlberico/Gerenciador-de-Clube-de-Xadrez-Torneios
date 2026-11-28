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
from src.core.resources import bundled_resource
from src.domain.dates import Ano, Data, DataInvalida, ResultadoData, parse_date, storage_text
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
    ColumnLayoutService,
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
from .feedback import REPORT, plan_feedback
from .i18n import t
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
    SIZE_MODAL_TITLE,
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
    THEME_ON_ACCENT,
    THEME_APP_BG,
    THEME_DANGER,
    THEME_DANGER_HOVER,
    THEME_FIELD_BG,
    THEME_FIELD_BORDER,
    THEME_FIELD_BORDER_ERROR,
    THEME_FIELD_BORDER_FOCUS,
    THEME_FIELD_TEXT,
    THEME_PLACEHOLDER,
    THEME_INFO,
    THEME_NEUTRAL,
    THEME_NEUTRAL_HOVER,
    THEME_PANEL_BG,
    THEME_STATUSBAR_BG,
    THEME_SUCCESS,
    THEME_SUCCESS_HOVER,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    THEME_RESULT_BYE,
    THEME_RESULT_DRAW,
    THEME_RESULT_WIN,
    THEME_TREE_BG,
    THEME_TREE_EVEN,
    THEME_TREE_FG,
    THEME_TREE_HEADING,
    THEME_TREE_ODD,
    THEME_TREE_SELECTED,
    THEME_TREE_SELECTED_FG,
    THEME_ON_WARNING,
    THEME_WARNING,
    THEME_WARNING_HOVER,
    THEME_WARNING_TEXT,
    RESULT_STATE_COLORS,
    ColorToken,
    apply_accent_preset,
    apply_bg_preset,
    apply_frame_bg_preset,
    curated_theme_swatches,
    font_kpi_value,
    font_section,
    font_subsection,
    match_curated_theme,
    pick,
    notify_theme_change,
    off_theme_change,
    on_theme_change,
)

logger = logging.getLogger("src.ui")


def resource_path(relative_path: str) -> Path:
    """Recurso empacotado (``assets/...``). Uma regra só: ``src.core.resources``."""
    return bundled_resource(relative_path)


MEMBER_TYPE_LABELS = {
    "socio": "Sócio",
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


def round_option_label(round_data: dict[str, Any]) -> str:
    """"Rodada 3 - encerrada": rótulo de tela de uma rodada (RGS-27).

    O status gravado em ``rounds.status`` (``generated``/``closed``) é dado,
    não texto: o rótulo vem do catálogo, ``round.status.*``. As chaves ficam
    escritas por extenso para o teste do catálogo enxergá-las; status que o
    banco não grava hoje aparece cru, que ao menos diz o que está gravado.
    """
    status = str(round_data["status"])
    rotulos = {
        "generated": t("round.status.generated"),
        "closed": t("round.status.closed"),
    }
    return t("round.option", numero=round_data["number"], status=rotulos.get(status, status))

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
    """Classifica um erro em ``(título, mensagem, inesperado)`` — puro e testavel.

    Strings e exceções de dominio/IO conhecidas são "recuperaveis"
    (``inesperado=False``) e viram toast; o resto vira modal com código e caminho
    do log. Aceitar ``str`` e proposital: muitas telas chamam ``_show_error`` com
    uma mensagem pronta (validação de formulário, regra de negócio)."""
    if isinstance(error, str):
        return "Erro", error, False
    if isinstance(error, AppError):
        return "Erro", str(error), False
    if isinstance(error, PermissionError):
        return (
            "Erro de permissão",
            f"Sem permissão para acessar o arquivo ou pasta.\n\n{error}",
            False,
        )
    if isinstance(error, FileNotFoundError):
        return (
            "Arquivo não encontrado",
            f"O arquivo ou pasta informado não foi encontrado.\n\n{error}",
            False,
        )
    if isinstance(error, OSError):
        return (
            "Erro de arquivo",
            f"Não foi possível acessar o arquivo ou pasta.\n\n{error}",
            False,
        )
    if isinstance(error, ValueError):
        return "Dados inválidos", str(error), False
    return (
        "Erro inesperado",
        "Ocorreu uma falha inesperada.\n\n"
        f"Código: {error_id}\n"
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
                        pass  # widget sem a opção state: não há o que desabilitar
                        
    def _modal_is_open(self) -> bool:
        """True se ha um modal com grab ativo (um toast ficaria escondido atras)."""
        try:
            return bool(self.grab_current())
        except Exception:
            return False

    def _feedback(self, message: str, kind: str, title: str) -> None:
        """Manda o recado pelo canal que o formato pede (F5.7).

        Uma linha vira toast, como sempre. Duas viram toast **com Copiar** — o
        segundo pedaço quase sempre e um caminho ou endereço. Três ou mais viram
        relatório rolavel: um texto desses num toast de 320px que some em 3,5
        segundos é pior do que o messagebox que a F2.2 aposentou. A regra mora
        em `feedback.plan_feedback`, pura e testavel sem janela.
        """
        plano = plan_feedback(message, kind)
        if plano.channel == REPORT and not self._modal_is_open():
            self._show_report(title, message, kind=kind)
            return
        if self._modal_is_open() or not hasattr(self, "_show_toast"):
            from .components.dialogs import alert_dialog

            alert_dialog(self, title, message, kind=kind)
            return
        duration = 5000 if kind in ("error", "warning") else 3500
        action = (t("dialog.copy"), lambda: self._copy_to_clipboard(message))
        self._show_toast(
            message,
            kind=kind,
            duration_ms=duration,
            action=action if plano.copyable else None,
        )

    def _copy_to_clipboard(self, text: str) -> None:
        """Leva ``text`` para a area de transferencia (acao Copiar do toast)."""
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:  # pragma: no cover - area de transferencia indisponivel
            logger.warning("Nao foi possivel copiar para a area de transferencia")

    def _show_report(self, title: str, body: str, *, kind: str = "info") -> None:
        """Relatório que o usuário lê com calma e copia: diálogo rolavel (F5.7).

        Use quando o conteúdo **e** a entrega — narrativa de desempate, endereço
        do servidor QR, caminho do backup. Mensagens curtas continuam no toast.
        """
        from .components.dialogs import report_dialog

        report_dialog(self, title, body, kind=kind)

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
            self._show_rule_error(
                message,
                title="" if title == "Erro" else title,
                suggestion=getattr(message_or_exception, "suggestion", ""),
            )

    def _show_rule_error(
        self,
        message: str,
        *,
        title: str = "",
        suggestion: str = "",
        action: tuple[str, Callable[[], None]] | None = None,
    ) -> None:
        """Recusa de regra numa faixa fixa, com fechar e ação sugerida (RGS-26).

        Era um toast de 5 s — o mesmo canal do sucesso. Com um modal aberto a
        faixa da janela ficaria atrás do *grab*; aí vale o alerta, que também
        não some sozinho. Os diálogos que recusam sem fechar (correção de
        resultado) montam a própria faixa com ``rule_banner``.
        """
        if self._modal_is_open() or not hasattr(self, "_show_rule_banner"):
            from .components.dialogs import alert_dialog

            corpo = f"{message}\n\n{suggestion}" if suggestion else message
            alert_dialog(self, title or "Erro", corpo, kind="error")
            return
        self._show_rule_banner(message, title=title, suggestion=suggestion, action=action)

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
        exclusão — o id novo pode diferir do original, então só serve para
        registros sem dependentes. Em exclusão com cascata passe ``None``: o
        toast sai sem ação e a confirmação explicita segue sendo a proteção.
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
                self._show_toast("Exclusão desfeita.", kind="info")
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
            self._show_info("Não encontrei comando de impressão. O documento foi aberto para impressão manual.")
        except Exception as exc:
            self._show_error(f"Não foi possível iniciar a impressão: {exc}")

        
def clamp_popup_position(
    x: int,
    y: int,
    field_height: int,
    width: int,
    height: int,
    screen_width: int,
    screen_height: int,
    gap: int = 2,
) -> tuple[int, int]:
    """Posição de um popup ancorado num campo, sempre dentro da tela (RGS-12).

    Abre abaixo do campo; sem espaço abaixo, acima; sem espaço nos dois, encosta
    na borda. A largura também é contida: campo perto da borda direita puxava o
    calendário para fora da tela.
    """
    abaixo = y + field_height + gap
    if abaixo + height <= screen_height:
        topo = abaixo
    elif y - height - gap >= 0:
        topo = y - height - gap
    else:
        topo = max(0, min(abaixo, screen_height - height))
    esquerda = max(0, min(x, screen_width - width))
    return esquerda, topo


def _unbind_exact(widget: Any, sequence: str, funcid: str) -> None:
    """Remove UM binding, e não todos os da sequência.

    O ``unbind(seq, funcid)`` do tkinter (até o Python 3.12) apaga a sequência
    inteira — inclusive os bindings de outros campos e do próprio app no mesmo
    toplevel. Aqui sai só a linha deste ``funcid``.
    """
    try:
        script = str(widget.tk.call("bind", str(widget), sequence))
        restante = "\n".join(linha for linha in script.splitlines() if funcid not in linha)
        widget.tk.call("bind", str(widget), sequence, restante)
    except Exception:
        logger.debug("Falha ao remover binding %s", sequence, exc_info=True)
    try:
        widget.deletecommand(funcid)
    except Exception:
        pass  # o comando Tcl já foi removido junto com o widget


_DATA_INCOMPLETA = "data incompleta; use dd/mm/aaaa."
_LARGURA_BOTAO_CALENDARIO = 22


class MaskedDateEntry(ctk.CTkEntry):
    """Campo de data com máscara DD/MM/AAAA, seguindo o tema do app.

    Exibe no formato brasileiro e faz entrada/saída em ISO (AAAA-MM-DD). A
    leitura de qualquer valor passa por ``src.domain.dates.parse_date`` (RGS-06):

    - ``insert(0, valor)`` aceita tudo o que a regra única aceita (ISO, ISO com
      hora, ``dd/mm/aaaa``, ``d/m/aaaa``, ``aaaa/mm/dd``) e mostra DD/MM/AAAA;
    - valor que a regra **recusa** aparece **como está gravado**, com borda de
      erro — nunca a máscara mutilada (``2010/05/12`` virava ``0512-10-20``);
    - ``permite_ano=True`` (nascimento) mostra ``1985`` como ano (RGS-33);
    - ``value()`` devolve o resultado tri-estado (vazio / data ou ano /
      inválido) e ``has_invalid()`` diz se há o que recusar;
    - ``get()`` mantém o contrato antigo: ISO (ou o ano, no nascimento) quando
      válido, senão ``""``. Por isso quem salva consulta ``has_invalid()``
      antes — ``""`` gravaria vazio por cima do valor (ver
      ``refuse_invalid_dates``).

    Calendário (RGS-12): abre por F4, Alt+↓ ou pelo botão ▾ no campo — a seta ↓
    sozinha é navegação, não atalho. Sem ``grab_set()``: o popup fecha no Esc,
    ao clicar fora e quando o foco vai para outro campo, e fica dentro da tela.
    """

    def __init__(self, master: Any, *, permite_ano: bool = False, **kwargs: Any) -> None:
        kwargs.setdefault("placeholder_text", "dd/mm/aaaa")
        self._permite_ano = bool(permite_ano)
        # Texto exibido como veio, fora da máscara: valor inválido gravado, ou
        # o ano sozinho. Qualquer edição recomeça a digitação do zero.
        self._literal = False
        self.calendar_button: ctk.CTkButton | None = None
        super().__init__(master, **kwargs)
        self._cal_popup: Toplevel | None = None
        self._calendar: Calendar | None = None
        self._outside_click: tuple[Any, str] | None = None
        # Estados (foco/erro/desabilitado) vem do componente único (F5.3).
        from .components.fields import attach_field_states

        attach_field_states(self)
        try:
            self._entry.bind("<KeyPress>", self._on_key)
            self._entry.bind("<Alt-KeyPress-Down>", self._on_alt_down)
            self._entry.bind("<FocusOut>", self._on_blur, add="+")
            self._entry.bind("<<Paste>>", self._on_paste)
        except Exception:
            logger.debug("Falha ao ligar os eventos do campo de data", exc_info=True)
        self._build_calendar_button()

    # -- helpers internos --------------------------------------------------
    def _build_calendar_button(self) -> None:
        try:
            fundo = self.cget("fg_color")
            self.calendar_button = ctk.CTkButton(
                self,
                text="▾",
                width=_LARGURA_BOTAO_CALENDARIO,
                height=max(16, int(self.cget("height")) - 8),
                corner_radius=4,
                fg_color=fundo,
                bg_color=fundo,
                hover_color=THEME_NEUTRAL_HOVER,
                text_color=THEME_TEXT_SUB,
                command=self._toggle_calendar,
            )
            borda = int(self.cget("border_width") or 0)
            self.calendar_button.place(relx=1.0, rely=0.5, x=-(borda + 3), anchor="e")
            self._create_grid()
        except Exception:
            logger.debug("Falha ao criar o botão do calendário", exc_info=True)

    def _create_grid(self) -> None:
        super()._create_grid()
        if getattr(self, "calendar_button", None) is None:
            return
        # Reserva a faixa do botão à direita, para o texto não passar por baixo.
        try:
            padx = self._entry.grid_info().get("padx", 0)
            esquerda = int(padx[0]) if isinstance(padx, (tuple, list)) else int(str(padx).split()[0])
        except Exception:
            esquerda = 6
        direita = esquerda + int(self._apply_widget_scaling(_LARGURA_BOTAO_CALENDARIO))
        self._entry.grid_configure(padx=(esquerda, direita))

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

    def _limit(self, digits: str) -> str:
        # No nascimento o ano sozinho (``1985``) e digitavel: o clamp de dia/mes
        # descartaria o ``8``. A validação fica com o ``value()``.
        return digits[:8] if self._permite_ano else self._clamp(digits)

    def _set_text(self, text: str) -> None:
        super().delete(0, "end")
        if text:
            super().insert(0, text)
        try:
            self._entry.icursor("end")
        except Exception:
            pass  # campo destruído antes de posicionar o cursor

    def _render(self, digits: str) -> None:
        self._literal = False
        self._set_text(self._mask(digits))
        self._set_valid(True)

    def _show_literal(self, text: str) -> None:
        self._literal = True
        self._set_text(text)
        self._refresh_error()

    def _show_value(self, raw: Any) -> None:
        resultado = parse_date(raw, permite_ano=self._permite_ano)
        if isinstance(resultado, Data):
            valor = resultado.valor
            self._render(f"{valor.day:02d}{valor.month:02d}{valor.year:04d}")
        elif isinstance(resultado, Ano):
            self._show_literal(str(resultado.valor))
        elif isinstance(resultado, DataInvalida):
            self._show_literal(resultado.texto)
        else:
            self._render("")

    def _set_valid(self, ok: bool, message: str = "") -> None:
        """Delega ao estado de campo unico (F5.3)."""
        from .components.fields import clear_field_error, set_field_error

        if ok:
            clear_field_error(self)
        else:
            set_field_error(self, message or "Data inválida. Use dd/mm/aaaa.")

    def _refresh_error(self) -> None:
        resultado = self.value()
        if isinstance(resultado, DataInvalida):
            self._set_valid(False, f"Data inválida: {resultado.motivo}")
        else:
            self._set_valid(True)

    # -- leitura -------------------------------------------------------------
    def value(self) -> ResultadoData:
        """O que o campo contém: ``DataVazia``, ``Data``/``Ano`` ou ``DataInvalida``."""
        texto = super().get().strip()
        if self._literal or not texto:
            return parse_date(texto, permite_ano=self._permite_ano)
        digitos = self._current_digits()
        if self._permite_ano and len(digitos) == 4:
            return parse_date(digitos, permite_ano=True)
        if len(digitos) != 8:
            return DataInvalida(texto, _DATA_INCOMPLETA)
        return parse_date(self._mask(digitos), permite_ano=self._permite_ano)

    def has_invalid(self) -> bool:
        return isinstance(self.value(), DataInvalida)

    # -- eventos -----------------------------------------------------------
    def _on_key(self, event: Any) -> str | None:
        if event.state & 0x4:  # Control: não interfere em copiar/colar/selecionar
            return None
        if event.keysym == "F4":
            self._toggle_calendar()
            return "break"
        if event.keysym == "Escape" and self._cal_popup is not None:
            self._close_calendar()
            return "break"
        if event.keysym in (
            "Left", "Right", "Home", "End", "Tab", "ISO_Left_Tab",
            "Return", "KP_Enter", "Up", "Down", "Escape",
        ):
            return None
        if event.keysym in ("BackSpace", "Delete"):
            self._render("" if self._literal else self._current_digits()[:-1])
            return "break"
        char = event.char or (event.keysym if len(event.keysym) == 1 else "")
        if char and char.isdigit():
            base = "" if self._literal else self._current_digits()
            self._render(self._limit(base + char))
            return "break"
        if char and char.isprintable():
            return "break"  # bloqueia letras e simbolos
        return None

    def _on_alt_down(self, _event: Any = None) -> str:
        self._toggle_calendar()
        return "break"

    def _on_paste(self, _event: Any) -> str:
        try:
            text = self.clipboard_get()
        except Exception:
            text = ""
        self._show_value(text)
        return "break"

    def _on_blur(self, _event: Any = None) -> None:
        if not self._literal and self._permite_ano and len(self._current_digits()) == 4:
            resultado = self.value()
            if isinstance(resultado, Ano):
                self._show_literal(str(resultado.valor))
        self._refresh_error()
        if self._cal_popup is not None:
            # Depois do evento: o clique que tirou o foco ainda não chegou.
            self.after(1, self._close_if_focus_left)

    # -- calendário (F4 / Alt+seta / botão) --------------------------------
    def _inside(self, widget: Any, container: Any) -> bool:
        if widget is None or container is None:
            return False
        caminho, base = str(widget), str(container)
        return caminho == base or caminho.startswith(base + ".")

    def _close_if_focus_left(self) -> None:
        popup = self._cal_popup
        if popup is None:
            return
        try:
            focado = self.focus_get()
        except Exception:
            focado = None
        if focado is not None and (self._inside(focado, self) or self._inside(focado, popup)):
            return
        if focado is None:
            # O foco saiu do app OU foi para o próprio popup (Windows ativa a
            # janela clicada). Com o ponteiro sobre o calendário, e o segundo.
            try:
                sob = self.winfo_containing(*self.winfo_pointerxy())
            except Exception:
                sob = None
            if sob is not None and self._inside(sob, popup):
                return
        self._close_calendar()

    def _on_outside_click(self, event: Any) -> None:
        if self._cal_popup is None:
            return
        if self._inside(event.widget, self) or self._inside(event.widget, self._cal_popup):
            return
        self._close_calendar()

    def _toggle_calendar(self) -> None:
        if self._cal_popup is not None:
            self._close_calendar()
            return
        try:
            if str(self._entry.cget("state")) == "disabled":
                return
        except Exception:
            pass  # campo destruído: segue como se estivesse habilitado
        self._open_calendar()

    def _close_calendar(self) -> None:
        popup = self._cal_popup
        self._cal_popup = None
        self._calendar = None
        ligacao = self._outside_click
        self._outside_click = None
        if ligacao is not None:
            _unbind_exact(ligacao[0], "<Button-1>", ligacao[1])
        if popup is not None:
            try:
                popup.destroy()
            except Exception:
                pass  # o popup já foi destruído

    def _open_calendar(self) -> None:
        if self._cal_popup is not None:  # já aberto: alterna (fecha)
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

            atual = self.value()
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
            if isinstance(atual, Data):
                cal_kwargs.update(year=atual.valor.year, month=atual.valor.month, day=atual.valor.day)
            try:
                cal = Calendar(popup, **cal_kwargs)
            except Exception:
                cal_kwargs.pop("locale", None)  # ambiente sem locale pt_BR
                cal = Calendar(popup, **cal_kwargs)
            cal.pack(padx=6, pady=6)
            self._calendar = cal

            def choose(_event: Any = None) -> None:
                selected = cal.selection_get()
                if selected is not None:
                    self._render(f"{selected.day:02d}{selected.month:02d}{selected.year:04d}")
                self._close_calendar()
                try:
                    self._entry.focus_set()
                except Exception:
                    pass  # campo destruído antes do foco

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
            x, y = clamp_popup_position(
                self.winfo_rootx(),
                self.winfo_rooty(),
                self.winfo_height(),
                popup.winfo_reqwidth(),
                popup.winfo_reqheight(),
                self.winfo_screenwidth(),
                self.winfo_screenheight(),
            )
            popup.geometry(f"+{x}+{y}")
            popup.lift()
            popup.bind("<Escape>", lambda _e: self._close_calendar())
            # Sem grab_set() (RGS-12): o grab global fazia a janela ignorar
            # cliques. O "clicar fora" e um binding no toplevel do campo, que
            # sai junto com o popup.
            topo = self.winfo_toplevel()
            funcid = topo.bind("<Button-1>", self._on_outside_click, add="+")
            self._outside_click = (topo, funcid)
        except Exception:
            logger.debug("Falha ao abrir o calendario do campo de data", exc_info=True)
            self._close_calendar()

    # -- API compatível com CTkEntry --------------------------------------
    def insert(self, index: Any, value: Any) -> None:  # type: ignore[override]
        self._show_value(value)

    def delete(self, first_index: Any = 0, last_index: Any = None) -> None:  # type: ignore[override]
        self._literal = False
        super().delete(0, "end")
        self._set_valid(True)

    def get(self) -> str:  # type: ignore[override]
        resultado = self.value()
        if isinstance(resultado, (Data, Ano)):
            return storage_text(resultado)
        return ""

    def destroy(self) -> None:
        self._close_calendar()
        super().destroy()


def _date_fields(*alvos: Any) -> list[MaskedDateEntry]:
    """Campos de data em widgets, dicionários, listas ou contêineres."""
    encontrados: list[MaskedDateEntry] = []

    def visitar(alvo: Any) -> None:
        if alvo is None:
            return
        if isinstance(alvo, MaskedDateEntry):
            encontrados.append(alvo)
            return
        if isinstance(alvo, dict):
            for item in alvo.values():
                visitar(item)
            return
        if isinstance(alvo, (list, tuple, set)):
            for item in alvo:
                visitar(item)
            return
        filhos = getattr(alvo, "winfo_children", None)
        if callable(filhos):
            for filho in filhos():
                visitar(filho)

    for alvo in alvos:
        visitar(alvo)
    return encontrados


def refuse_invalid_dates(*alvos: Any) -> None:
    """Recusa salvar com data inválida (RGS-06): destaca o campo e levanta.

    O ``get()`` de um campo inválido devolve ``""``; salvar assim apagaria a
    data gravada sem aviso. Aceita os próprios campos, o dicionário de campos do
    formulário ou o contêiner inteiro.
    """
    invalidos = [campo for campo in _date_fields(*alvos) if campo.has_invalid()]
    if not invalidos:
        return
    for campo in invalidos:
        campo._refresh_error()
    primeiro = invalidos[0]
    try:
        primeiro._entry.focus_set()
    except Exception:
        pass  # campo destruído antes do foco
    resultado = primeiro.value()
    motivo = resultado.motivo if isinstance(resultado, DataInvalida) else _DATA_INCOMPLETA
    texto = resultado.texto if isinstance(resultado, DataInvalida) else ""
    raise AppError(f"Data inválida \"{texto}\": {motivo} Corrija o campo destacado antes de salvar.")


class UIBuilderMixin(ErrorCatchingMixin):
    """Helpers de UI que NÃO são reimplementados em AlbericusApp.

    Primitivos como _page_title, _make_panel, _make_scrollable_panel, _make_tree,
    _clear_content e _grid_form_buttons vivem em app.py (AlbericusApp) — fonte única
    de verdade. Não duplique aqui.
    """

    def _make_date_entry(self, parent: Any, width: int = 20, *, permite_ano: bool = False) -> MaskedDateEntry:
        """Campo de data brasileiro: DD/MM/AAAA na tela, ISO (AAAA-MM-DD) por baixo.

        Mantém a assinatura antiga; o ``width`` herdado (em caracteres da época do
        tkcalendar) e convertido para pixels com um teto, pois a data cabe em
        ~120-220px. Os call-sites seguem usando get()/insert()/delete() normalmente.
        """
        width_px = max(120, min(220, int(width) * 7))
        return MaskedDateEntry(parent, width=width_px, permite_ano=permite_ano)

    def _refuse_invalid_dates(self, *alvos: Any) -> None:
        """Atalho de ``refuse_invalid_dates`` para as telas (RGS-06)."""
        refuse_invalid_dates(*alvos)

