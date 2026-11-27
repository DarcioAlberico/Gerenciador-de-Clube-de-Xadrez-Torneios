"""“Corrigir resultado…” — um diálogo, um motivo (RGS-20).

Corrigir uma rodada fechada custava cerca de 7 cliques e **dois** motivos
(desbloquear, depois corrigir), ou a rota pelas Configurações: ligar
"mudanças perigosas" para o torneio inteiro e esquecer ligado. Aqui a ação
mora na mesa — clique direito, Shift+F10 ou Ctrl+E, em Rodadas e no Painel — e
são três ações: abrir, escolher o resultado, escrever o motivo + Enter.

O mesmo motivo desbloqueia a rodada (15 min, só para esta correção) e registra
a correção; o serviço valida pela regra mais estrita das duas. A recusa
aparece numa faixa dentro do próprio diálogo (RGS-26), sem apagar o que já foi
digitado. A cascata (rodada seguinte já pareada) é decidida aqui mesmo, e o
histórico da mesa oferece "Reverter esta correção…" pelo mesmo fluxo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import customtkinter as ctk

from src.services.constants import AppError, pairing_player_name
from src.services.pairing.corrections import DEFAULT_UNLOCK_MINUTES, shared_reason_error

from ...components import Dialog, actions_bar, secondary_button, text_field
from ...components.rule_banner import rule_banner
from ...theme import (
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
    THEME_ACCENT,
    THEME_ON_ACCENT,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    THEME_WARNING_TEXT,
    font_section,
)

# Botões do novo resultado, na ordem da súmula: (rótulo, código gravado).
RESULT_BUTTONS: tuple[tuple[str, str], ...] = (
    ("1-0", "1-0"),
    ("½", "1/2-1/2"),
    ("0-1", "0-1"),
    ("+/-", "1F-0F"),
    ("-/+", "0F-1F"),
    ("-/-", "0F-0F"),
)
# Mesa de bye: o que se troca é o tipo de bye, não um placar.
BYE_RESULT_BUTTONS: tuple[tuple[str, str], ...] = (
    ("BYE", "BYE"),
    ("F (1)", "F"),
    ("H (½)", "H"),
    ("Z (0)", "Z"),
)
RESULT_LABELS = {codigo: rotulo for rotulo, codigo in RESULT_BUTTONS + BYE_RESULT_BUTTONS}

# Sugestões de motivo: um clique preenche, e o árbitro completa se quiser.
REASON_SUGGESTIONS: tuple[str, ...] = (
    "Erro de digitação",
    "Súmula diverge do lançado",
    "Decisão de apelação",
)


def result_label(code: str) -> str:
    """Rótulo de súmula de um código ("1/2-1/2" → "½"); vazio vira "pendente"."""
    if not str(code or "").strip():
        return "pendente"
    return RESULT_LABELS.get(code, code)


def _when(created_at: str) -> str:
    """``2026-11-26 14:03:00`` → ``26/11 14:03``."""
    texto = str(created_at or "")
    if len(texto) >= 16 and texto[4] == "-":
        return f"{texto[8:10]}/{texto[5:7]} {texto[11:16]}"
    return texto


@dataclass
class CorrectionContext:
    """Tudo que o diálogo mostra — montado pela tela, sem Tk."""

    target_id: int
    board_label: str
    white: str
    black: str
    current: str
    round_number: int
    round_closed: bool
    permission_note: str
    is_bye: bool = False
    preselect: str = ""
    cascade: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def needs_reason(self) -> bool:
        return self.round_closed


def cascade_text(cascade: dict[str, Any] | None) -> tuple[str, str]:
    """(recado, rótulo da caixa "Reparear") para a rodada seguinte. Puro."""
    if not cascade:
        return "", ""
    numero = int(cascade["number"])
    if not cascade.get("repairable"):
        return (
            f"A rodada {numero} já foi fechada com o resultado antigo: confira os "
            "desempates depois da correção.",
            "",
        )
    if int(cascade.get("results") or 0):
        return (
            f"A rodada {numero} foi pareada com o resultado antigo. Reparear apagaria "
            f"{cascade['message']} — a exclusão pede motivo próprio.",
            f"Reparear rodada {numero} (excluir com motivo e gerar de novo)",
        )
    return (
        f"A rodada {numero} foi pareada com o resultado antigo e ainda não tem resultados.",
        f"Reparear rodada {numero}",
    )


class CorrectionDialog(Dialog):
    """O diálogo. ``confirm(resultado, motivo, reverte)`` grava ou levanta ``AppError``."""

    def __init__(
        self,
        parent: Any,
        context: CorrectionContext,
        confirm: Callable[[str, str, int | None], dict[str, Any]],
    ) -> None:
        super().__init__(parent, "Corrigir resultado", size=(660, 600), resizable=True)
        self.context = context
        self._confirm = confirm
        self.outcome: dict[str, Any] | None = None
        self.unexpected: BaseException | None = None
        self.selected = ""
        self.reverts_event_id: int | None = None
        self.result_buttons: dict[str, ctk.CTkButton] = {}
        self.revert_buttons: list[ctk.CTkButton] = []
        self.repair_check: ctk.CTkCheckBox | None = None
        self.banner: ctk.CTkFrame | None = None

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.grid(row=0, column=0, padx=SPACE_LG, pady=(SPACE_LG, 0), sticky="nsew")
        corpo.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_header(corpo)
        self._build_results(corpo)
        self._build_reason(corpo)
        self._build_cascade(corpo)
        self._build_history(corpo)
        self.banner_slot = ctk.CTkFrame(corpo, fg_color="transparent")
        self.banner_slot.grid(row=9, column=0, pady=(SPACE_SM, 0), sticky="ew")
        self.banner_slot.grid_columnconfigure(0, weight=1)
        actions_bar(
            self,
            row=1,
            primary=("Corrigir", self.submit),
            secondary=[("Cancelar", self.close)],
        )
        if context.preselect and context.preselect != context.current:
            # Enter na mesa traz o resultado do seletor; se é o atual, não há
            # o que marcar — o árbitro escolhe o novo.
            self.select(context.preselect)
        self._focus_reason()

    # ---- Montagem --------------------------------------------------------- #

    def _build_header(self, corpo: ctk.CTkFrame) -> None:
        ctx = self.context
        self.title_label = ctk.CTkLabel(
            corpo,
            text=f"{ctx.board_label} · Rodada {ctx.round_number}",
            font=font_section(),
            text_color=THEME_TEXT_MAIN,
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew")
        adversario = ctx.black or "BYE"
        ctk.CTkLabel(
            corpo,
            text=f"{ctx.white} (brancas)  ×  {adversario}" + ("" if ctx.is_bye else " (pretas)"),
            text_color=THEME_TEXT_MAIN,
            anchor="w",
            justify="left",
            wraplength=600,
        ).grid(row=1, column=0, pady=(SPACE_XS, 0), sticky="ew")
        ctk.CTkLabel(
            corpo,
            text=f"Resultado atual: {result_label(ctx.current)}",
            text_color=THEME_TEXT_SUB,
            anchor="w",
        ).grid(row=2, column=0, sticky="ew")
        if ctx.permission_note:
            # O aviso de desbloqueio vem ANTES do motivo: o árbitro precisa
            # saber o que o Enter vai abrir antes de apertá-lo.
            self.permission_label = ctk.CTkLabel(
                corpo,
                text=ctx.permission_note,
                text_color=THEME_WARNING_TEXT,
                anchor="w",
                justify="left",
                wraplength=600,
            )
            self.permission_label.grid(row=3, column=0, pady=(SPACE_SM, 0), sticky="ew")

    def _build_results(self, corpo: ctk.CTkFrame) -> None:
        ctk.CTkLabel(corpo, text="Novo resultado", text_color=THEME_TEXT_SUB, anchor="w").grid(
            row=4, column=0, pady=(SPACE_MD, SPACE_XS), sticky="ew"
        )
        faixa = ctk.CTkFrame(corpo, fg_color="transparent")
        faixa.grid(row=5, column=0, sticky="w")
        botoes = BYE_RESULT_BUTTONS if self.context.is_bye else RESULT_BUTTONS
        for coluna, (rotulo, codigo) in enumerate(botoes):
            botao = secondary_button(
                faixa, rotulo, lambda valor=codigo: self.select(valor), width=72
            )
            botao.grid(row=0, column=coluna, padx=(0, SPACE_SM))
            if codigo == self.context.current:
                # Mesmo resultado não é correção: o botão fica, apagado, para o
                # árbitro ver onde está.
                botao.configure(state="disabled")
            self.result_buttons[codigo] = botao

    def _build_reason(self, corpo: ctk.CTkFrame) -> None:
        self.reason_entry = text_field(
            corpo,
            placeholder=(
                "Motivo — vai para a auditoria e serve ao desbloqueio"
                if self.context.needs_reason
                else "Motivo (opcional na rodada aberta)"
            ),
            width=600,
        )
        if not self.context.needs_reason:
            # Rodada aberta: lançar não pede motivo, e o campo só atrasaria o Enter.
            return
        ctk.CTkLabel(corpo, text="Motivo", text_color=THEME_TEXT_SUB, anchor="w").grid(
            row=6, column=0, pady=(SPACE_MD, SPACE_XS), sticky="ew"
        )
        self.reason_entry.grid(row=7, column=0, sticky="ew")
        sugestoes = ctk.CTkFrame(corpo, fg_color="transparent")
        sugestoes.grid(row=8, column=0, pady=(SPACE_XS, 0), sticky="w")
        for coluna, texto in enumerate(REASON_SUGGESTIONS):
            secondary_button(
                sugestoes,
                texto,
                lambda valor=texto: self._suggest(valor),
                height=26,
            ).grid(row=0, column=coluna, padx=(0, SPACE_XS))

    def _build_cascade(self, corpo: ctk.CTkFrame) -> None:
        recado, rotulo = cascade_text(self.context.cascade)
        if not recado:
            return
        caixa = ctk.CTkFrame(corpo, fg_color="transparent")
        caixa.grid(row=10, column=0, pady=(SPACE_MD, 0), sticky="ew")
        caixa.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            caixa, text=recado, text_color=THEME_WARNING_TEXT, anchor="w", justify="left",
            wraplength=600,
        ).grid(row=0, column=0, sticky="ew")
        if rotulo:
            self.repair_check = ctk.CTkCheckBox(caixa, text=rotulo)
            self.repair_check.grid(row=1, column=0, pady=(SPACE_XS, 0), sticky="w")

    def _build_history(self, corpo: ctk.CTkFrame) -> None:
        historico = self.context.history[:3]
        if not historico:
            return
        caixa = ctk.CTkFrame(corpo, fg_color="transparent")
        caixa.grid(row=11, column=0, pady=(SPACE_MD, 0), sticky="ew")
        caixa.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(caixa, text="Correções desta mesa", text_color=THEME_TEXT_SUB, anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="ew"
        )
        for linha, item in enumerate(historico, start=1):
            quem = f" ({item['actor']})" if item.get("actor") else ""
            ctk.CTkLabel(
                caixa,
                text=(
                    f"{_when(item['created_at'])} · {result_label(item['before'])} → "
                    f"{result_label(item['after'])} · {item['reason']}{quem}"
                ),
                text_color=THEME_TEXT_MAIN,
                anchor="w",
                justify="left",
                wraplength=430,
            ).grid(row=linha, column=0, pady=(SPACE_XS, 0), sticky="ew")
            if linha == 1:
                # Só a última: desfazer uma do meio reescreveria a história por
                # baixo das que vieram depois (o serviço recusa igual).
                botao = secondary_button(
                    caixa,
                    "Reverter esta correção…",
                    lambda evento=item: self.start_revert(evento),
                    height=28,
                )
                botao.grid(row=linha, column=1, padx=(SPACE_SM, 0), pady=(SPACE_XS, 0), sticky="e")
                self.revert_buttons.append(botao)

    # ---- Comportamento ---------------------------------------------------- #

    def select(self, code: str) -> None:
        """Marca o novo resultado (o botão vira o primário da faixa)."""
        if code not in self.result_buttons:
            return
        self.selected = code
        for codigo, botao in self.result_buttons.items():
            if codigo == code:
                botao.configure(fg_color=THEME_ACCENT, text_color=THEME_ON_ACCENT)
            else:
                botao.configure(fg_color="transparent", text_color=THEME_TEXT_MAIN)
        self._focus_reason()

    def start_revert(self, event: dict[str, Any]) -> None:
        """"Reverter esta correção…": mesmo diálogo, resultado anterior marcado."""
        self.reverts_event_id = int(event["event_id"])
        anterior = str(event.get("before") or "")
        if anterior in self.result_buttons:
            self.select(anterior)
        else:
            self.selected = anterior
        self.title_label.configure(
            text=(
                f"Reverter a correção de {_when(event['created_at'])} · "
                f"volta para {result_label(anterior)}"
            )
        )
        self._focus_reason()

    def _suggest(self, texto: str) -> None:
        self.reason_entry.delete(0, "end")
        self.reason_entry.insert(0, texto)
        self._focus_reason()

    def _focus_reason(self) -> None:
        try:
            alvo = self.reason_entry if self.context.needs_reason else self
            getattr(alvo, "_entry", alvo).focus_set()
        except Exception:
            pass  # diálogo fechado antes do foco

    def refuse(self, message: str, suggestion: str = "") -> None:
        """Recusa dentro do diálogo, em faixa fixa (RGS-26). Nada é apagado."""
        if self.banner is not None:
            try:
                self.banner.destroy()
            except Exception:
                pass  # a faixa já foi destruída junto com o diálogo
        self.banner = rule_banner(
            self.banner_slot,
            message,
            suggestion=suggestion,
            on_close=self._dismiss_banner,
            wraplength=440,
        )
        self.banner.grid(row=0, column=0, sticky="ew")
        self._focus_reason()

    def _dismiss_banner(self) -> None:
        if self.banner is not None:
            self.banner.destroy()
            self.banner = None

    def submit(self) -> None:
        motivo = " ".join(self.reason_entry.get().split()) if self.context.needs_reason else ""
        if not self.selected and not self.reverts_event_id:
            self.refuse(
                "Escolha o novo resultado.",
                "Clique num dos botões de resultado e confirme com Enter.",
            )
            return
        if self.context.needs_reason:
            erro = shared_reason_error(motivo)
            if erro:
                self.refuse(erro, "Use uma das sugestões ou descreva o que aconteceu.")
                return
        try:
            saida = self._confirm(self.selected, motivo, self.reverts_event_id)
        except AppError as exc:
            self.refuse(str(exc), getattr(exc, "suggestion", ""))
            return
        except Exception as exc:  # noqa: BLE001 - relançado por quem abriu
            self.unexpected = exc
            self.close()
            return
        self.outcome = {
            **(saida or {}),
            "result": self.selected,
            "reason": motivo,
            "reverted": self.reverts_event_id,
            "repair": bool(self.repair_check is not None and self.repair_check.get()),
        }
        self.close()


def correction_dialog(
    parent: Any,
    context: CorrectionContext,
    confirm: Callable[[str, str, int | None], dict[str, Any]],
) -> dict[str, Any] | None:
    """Abre o diálogo e espera. ``None`` = cancelou; senão, o que foi gravado."""
    dialogo = CorrectionDialog(parent, context, confirm)
    dialogo.wait_window()
    if dialogo.unexpected is not None:
        raise dialogo.unexpected
    return dialogo.outcome


class ResultCorrectionActions:
    """A ponte da tela (Rodadas ou Painel) para o diálogo e o serviço."""

    def __init__(self, host: Any) -> None:
        self.host = host

    @property
    def tournament_id(self) -> int:
        return int(self.host.current_tournament_id)

    def build_context(
        self, target_id: int, *, detail: dict[str, Any] | None = None, preselect: str = ""
    ) -> CorrectionContext:
        host = self.host
        servico = host.pairing_service
        alvo = servico._result_target(self.tournament_id, int(target_id))
        round_id = int(alvo["round_id"])
        rodada = host.db.get_round(round_id) or {}
        numero = int(rodada.get("number") or 0)
        fechada = str(alvo.get("round_status") or rodada.get("status") or "") == "closed"
        detalhe = dict(detail or {})
        if alvo["entity_type"] == "pairing":
            mesa = next(
                (
                    item
                    for item in host.db.get_pairings_for_round(round_id)
                    if int(item["id"]) == int(target_id)
                ),
                alvo,
            )
            rotulo = f"Mesa {mesa.get('board_number', '?')}"
            brancas = detalhe.get("white_display_name") or pairing_player_name(mesa, "white")
            pretas = "" if mesa.get("is_bye") else (
                detalhe.get("black_display_name") or pairing_player_name(mesa, "black")
            )
            is_bye = bool(mesa.get("is_bye"))
        else:
            rotulo = f"Tabuleiro {alvo.get('board_number', '?')}"
            if detalhe.get("white_team_name"):
                rotulo = f"{detalhe['white_team_name']} × {detalhe.get('black_team_name', '')} · {rotulo}"
            brancas = str(detalhe.get("white_display_name") or "")
            pretas = str(detalhe.get("black_display_name") or "")
            is_bye = False
        nota = ""
        if fechada:
            estado = servico.correction_unlock_state(self.tournament_id, round_id)
            nota = (
                estado.label()
                if estado.allowed
                else (
                    f"A rodada {numero} será desbloqueada por {DEFAULT_UNLOCK_MINUTES} min "
                    "só para esta correção."
                )
            )
        return CorrectionContext(
            target_id=int(target_id),
            board_label=rotulo,
            white=str(brancas or ""),
            black=str(pretas or ""),
            current=str(alvo.get("result") or ""),
            round_number=numero,
            round_closed=fechada,
            permission_note=nota,
            is_bye=is_bye,
            preselect=preselect,
            cascade=servico.correction_cascade(self.tournament_id, round_id) if fechada else None,
            history=servico.pairing_correction_history(self.tournament_id, int(target_id)),
        )

    def open(
        self,
        target_id: int,
        *,
        detail: dict[str, Any] | None = None,
        preselect: str = "",
        on_done: Callable[[], None] | None = None,
    ) -> dict[str, Any] | None:
        host = self.host
        try:
            host.require_permission("tournament_write")
            contexto = self.build_context(target_id, detail=detail, preselect=preselect)
        except Exception as exc:
            host._show_error(exc)
            return None

        servico = host.pairing_service
        tid = self.tournament_id

        def confirmar(resultado: str, motivo: str, reverte: int | None) -> dict[str, Any]:
            if reverte:
                return servico.revert_correction(tid, int(reverte), motivo)
            return servico.correct_result(tid, int(target_id), resultado, motivo)

        try:
            saida = correction_dialog(host, contexto, confirmar)
        except Exception as exc:
            host._show_error(exc)
            return None
        if saida is None:
            return None
        if on_done is not None:
            on_done()
        host._show_toast(self._success_message(contexto, saida), kind="success")
        if saida.get("repair") and contexto.cascade:
            self.repair(contexto.cascade, saida["reason"])
        return saida

    @staticmethod
    def _success_message(contexto: CorrectionContext, saida: dict[str, Any]) -> str:
        verbo = "revertida" if saida.get("reverted") else "corrigida"
        texto = (
            f"{contexto.board_label} {verbo}: {result_label(contexto.current)} → "
            f"{result_label(saida['result'])}."
        )
        if saida.get("unlocked"):
            texto += (
                f" Rodada {contexto.round_number} desbloqueada por "
                f"{DEFAULT_UNLOCK_MINUTES} min."
            )
        return texto

    def repair(self, cascade: dict[str, Any], reason: str) -> None:
        """"Reparear rodada N": exclui a rodada seguinte e gera de novo.

        Sem resultados, o motivo da correção basta. Com resultados, a exclusão
        passa pelo fluxo próprio (RGS-34): motivo e "N resultados serão
        apagados", porque o que se apaga ali é outra coisa.
        """
        host = self.host
        try:
            if int(cascade.get("results") or 0):
                if not host._confirm_and_delete_round(int(cascade["round_id"])):
                    return
            else:
                host.pairing_service.delete_generated_round(int(cascade["round_id"]), reason=reason)
            host._start_round_generation(self.tournament_id, reserve_engine=False)
        except Exception as exc:
            host._show_error(exc)
