from __future__ import annotations

from ..support import *
from ..components import window_scale
from ..dialog_layout import centered_position, fitted_size, geometry_string
from src.services.friendly_mode import (
    FRIENDLY_LATE_ENTRY_POINTS,
    FRIENDLY_MODE_LABEL,
    NOTICE_ITEMS,
    FriendlyModeService,
)


def _rodadas(n: int) -> str:
    return "1 rodada" if n == 1 else f"{n} rodadas"


def _o_que_sera_apagado(previa: dict[str, int]) -> str:
    """"2 resultados anotados e 1 envio por QR"."""
    partes = []
    n = int(previa.get("results") or 0)
    if n:
        partes.append(f"{n} resultado anotado" if n == 1 else f"{n} resultados anotados")
    n = int(previa.get("qr_submissions") or 0)
    if n:
        partes.append(f"{n} envio por QR" if n == 1 else f"{n} envios por QR")
    return " e ".join(partes)


def _pontos(valor: float) -> str:
    texto = f"{valor:g}".replace(".", ",")
    return f"{texto} ponto" if valor < 2 else f"{texto} pontos"


# Mixin do "Modo Livre" (Torneio | Livre) — eventos casuais, escolares ou treinos.
# Por ora exibe apenas o aviso informativo do modo, sem alterar nenhuma regra.
# Fica deliberadamente isolado do fluxo oficial (FIDE/CBX) e serve de ponto de
# extensão para o backlog do "Modo Escolar Amistoso" (entrada tardia, re-pair
# manual, pontuação retroativa) sem tocar no emparceiramento oficial vigente.
class FreeTournamentMixin:
    def _free_mode_notice_hidden(self) -> bool:
        """True se o operador pediu para nao ver mais o aviso do Modo Livre."""
        try:
            return str(self.db.get_app_settings().get("free_mode_notice_hidden") or "0") == "1"
        except Exception:
            return False

    def show_free_tournament_mode(self) -> ctk.CTkToplevel | None:
        """Abre o aviso modal do Modo Livre e devolve a janela criada.

        Se o operador marcou "Nao mostrar novamente", pula o aviso e vai direto
        para a criação do torneio (P1-11) — que ainda pede o nome, então nada e
        criado sem confirmação. Devolve ``None`` nesse caso.
        """
        if self._free_mode_notice_hidden():
            self._start_free_tournament(None)
            return None

        dialog = ctk.CTkToplevel(self)
        dialog.title(FRIENDLY_MODE_LABEL)
        dialog.transient(self.winfo_toplevel())
        dialog.resizable(False, False)

        body = ctk.CTkFrame(dialog, fg_color=THEME_PANEL_BG)
        body.pack(fill="both", expand=True, padx=16, pady=16)

        # Rodapé fixado na parte inferior (empacotado primeiro para ancorar
        # embaixo independentemente da altura do texto). "Iniciar Modo Livre"
        # cria um torneio já no perfil Livre/Escolar; "Cancelar" só fecha.
        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=(12, 0))

        # A escolha e gravada nos dois caminhos de saída (iniciar e cancelar):
        # marcar a caixa e só então cancelar também tem de valer.
        hide_notice = ctk.CTkCheckBox(footer, text="Não mostrar novamente")
        hide_notice.pack(side="left")
        self.free_mode_hide_checkbox = hide_notice

        def remember_choice() -> None:
            if not hide_notice.get():
                return
            try:
                self.db.save_app_settings({"free_mode_notice_hidden": "1"})
            except Exception:
                logger.exception("Falha ao gravar preferencia do aviso do modo amistoso")

        def start() -> None:
            remember_choice()
            self._start_free_tournament(dialog)

        def cancel() -> None:
            remember_choice()
            dialog.destroy()

        ctk.CTkButton(
            footer,
            text=f"Iniciar {FRIENDLY_MODE_LABEL}",
            width=190,
            command=start,
        ).pack(side="right")
        ctk.CTkButton(
            footer,
            text="Cancelar",
            width=110,
            fg_color=THEME_NEUTRAL,
            hover_color=THEME_NEUTRAL_HOVER,
            command=cancel,
        ).pack(side="right", padx=(0, 8))

        icon = getattr(self, "_ctk_menu_icons", {}).get("torneios")
        ctk.CTkLabel(
            body,
            text=f"  {FRIENDLY_MODE_LABEL} Ativado",
            image=icon,
            compound="left",
            anchor="w",
            text_color=THEME_ACCENT,
            font=ctk.CTkFont(size=SIZE_MODAL_TITLE, weight="bold"),
        ).pack(fill="x", padx=4, pady=(4, 12))

        ctk.CTkLabel(
            body,
            text=(
                "Para eventos casuais, escolares ou treinos. O emparceiramento continua "
                "o oficial; o que fica livre é a condução do torneio:"
            ),
            justify="left",
            anchor="w",
            wraplength=440,
            text_color=THEME_TEXT_MAIN,
            font=ctk.CTkFont(size=SIZE_BODY + 1),
        ).pack(fill="x", padx=4, pady=(0, 10))

        for item in NOTICE_ITEMS:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(
                row,
                text="•",
                text_color=THEME_ACCENT,
                font=ctk.CTkFont(size=SIZE_BODY + 3, weight="bold"),
            ).pack(side="left", anchor="n", padx=(0, 8))
            ctk.CTkLabel(
                row,
                text=item,
                justify="left",
                anchor="w",
                wraplength=405,
                text_color=THEME_TEXT_MAIN,
                font=ctk.CTkFont(size=SIZE_BODY + 1),
            ).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            body,
            text="Ideal para uma bagunça organizada onde o importante é jogar!",
            justify="left",
            anchor="w",
            wraplength=440,
            text_color=THEME_ACCENT,
            font=ctk.CTkFont(size=SIZE_BODY + 1, weight="bold"),
        ).pack(fill="x", padx=4, pady=(12, 0))

        self._center_over_self(dialog, 520, 470)
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.bind("<Escape>", lambda _e: cancel())
        dialog.bind("<Return>", lambda _e: start())

        def _grab() -> None:
            try:
                dialog.grab_set()
            except Exception:  # janela ainda não visível em alguns gerenciadores
                pass

        dialog.after(50, _grab)
        dialog.lift()
        dialog.focus()
        return dialog

    def _start_free_tournament(self, dialog: ctk.CTkToplevel | None) -> int | None:
        """Fecha o aviso e cria um torneio já em Modo Livre.

        Não toca em torneios existentes nem no fluxo oficial: cria um evento
        novo e grava a marca dedicada free_mode (set_free_mode). E essa marca,
        não o perfil, que habilita o re-emparceiramento livre, a entrada tardia
        flexível e o indicador 'Modo Livre' apenas neste evento.
        """
        if dialog is not None:  # None quando o aviso foi suprimido pelo operador
            dialog.destroy()
        pedido = self._ask_friendly_tournament()
        if pedido is None:
            return None  # o professor cancelou a criação
        try:
            criado = FriendlyModeService(self.db).create(
                pedido["name"], pedido["rounds_count"], class_id=pedido.get("class_id")
            )
        except Exception as exc:
            self._show_error(exc)
            return None
        tournament_id = int(criado["tournament_id"])
        name = criado["name"]
        self._set_current_tournament(tournament_id)
        logger.info("Torneio livre criado: %s", tournament_id)
        inscritos = int(criado.get("registered") or 0)
        turma = f" {inscritos} aluno(s) da turma já inscritos." if inscritos else ""
        self._show_toast(
            f"{FRIENDLY_MODE_LABEL} iniciado: '{name}'.{turma} Ajuste rodadas, datas e jogadores quando quiser.",
            kind="success",
        )
        self.show_players()
        return tournament_id

    def _ask_friendly_tournament(self) -> dict[str, Any] | None:
        """Pede nome, rodadas e turma (MA-08). ``None`` = cancelou."""
        resultado: dict[str, Any] = {}
        dialogo = self._build_friendly_tournament_dialog(resultado.update)
        self.wait_window(dialogo)
        return resultado or None

    def _build_friendly_tournament_dialog(self, on_done: Any) -> Any:
        """Monta o diálogo de criação; ``on_done(pedido)`` recebe o que foi pedido.

        Nada que o app já sabe é redigitado (WCAG 3.3.7): o nome vem com a data,
        as rodadas vêm com 5 e a turma é uma lista com "Nenhuma" primeiro. Rodadas
        fora da faixa mostram o que digitar, no próprio diálogo. Enter cria.
        """
        from src.services.friendly_mode import DEFAULT_ROUNDS, default_name, rounds_count_error
        from ..components.dialogs import Dialog, actions_bar

        turmas = FriendlyModeService(self.db).school_classes()
        por_rotulo = {item["label"]: item["id"] for item in turmas}
        dialogo = Dialog(self, f"Novo torneio ({FRIENDLY_MODE_LABEL})", size=(480, 360))

        corpo = ctk.CTkFrame(dialogo, fg_color="transparent")
        corpo.grid(row=0, column=0, padx=16, pady=(16, 4), sticky="ew")
        corpo.grid_columnconfigure(1, weight=1)

        def rotulo(texto: str, linha: int) -> None:
            ctk.CTkLabel(corpo, text=texto, anchor="w", text_color=THEME_TEXT_MAIN).grid(
                row=linha, column=0, padx=(0, 12), pady=6, sticky="w"
            )

        rotulo("Nome do torneio", 0)
        nome = ctk.CTkEntry(corpo)
        nome.insert(0, default_name())
        nome.grid(row=0, column=1, pady=6, sticky="ew")
        rotulo("Rodadas", 1)
        rodadas = ctk.CTkEntry(corpo, width=80)
        rodadas.insert(0, str(DEFAULT_ROUNDS))
        rodadas.grid(row=1, column=1, pady=6, sticky="w")
        rotulo("Turma", 2)
        turma = ctk.CTkOptionMenu(corpo, values=["Nenhuma", *por_rotulo])
        turma.set("Nenhuma")
        turma.grid(row=2, column=1, pady=6, sticky="ew")
        ctk.CTkLabel(
            corpo,
            text="Com uma turma, os alunos ativos dela já entram no torneio.",
            anchor="w",
            justify="left",
            wraplength=400,
            text_color=THEME_TEXT_SUB,
        ).grid(row=3, column=0, columnspan=2, pady=(0, 4), sticky="w")
        erro = ctk.CTkLabel(corpo, text="", anchor="w", text_color=THEME_DANGER)
        erro.grid(row=4, column=0, columnspan=2, sticky="w")

        def criar() -> None:
            problema = rounds_count_error(rodadas.get())
            if problema:
                erro.configure(text=problema)
                rodadas.focus_set()
                return
            on_done(
                {
                    "name": nome.get(),
                    "rounds_count": rodadas.get().strip(),
                    "class_id": por_rotulo.get(turma.get()),
                }
            )
            dialogo.close()

        actions_bar(dialogo, primary=("Criar torneio", criar), close_text="Cancelar", row=1)
        self._friendly_name_entry = nome
        self._friendly_rounds_entry = rodadas
        self._friendly_class_menu = turma
        self._friendly_error_label = erro
        self._friendly_submit = criar
        nome.focus_set()
        return dialogo

    def free_mode_add_round(self) -> None:
        """"Mais uma rodada" pelo menu da rodada (MA-09/MA-13)."""
        from ..components.dialogs import confirm_dialog

        try:
            self.require_permission("tournament_write")
            tournament_id = int(self.current_tournament_id)
            if not self._is_free_mode(tournament_id):
                raise AppError(f"Mais uma rodada: disponível apenas no {FRIENDLY_MODE_LABEL}.")
            total = int((self.db.get_tournament(tournament_id) or {}).get("rounds_count") or 0)
            if not confirm_dialog(
                self,
                f"Mais uma rodada ({FRIENDLY_MODE_LABEL})",
                f"O torneio passa de {total} para {total + 1} rodadas.",
                confirm_text="Adicionar rodada",
                cancel_text="Cancelar",
            ):
                return
            novo = FriendlyModeService(self.db).add_round(tournament_id)
            self._set_current_tournament(tournament_id)
            self._show_toast(f"Agora o torneio tem {novo} rodadas.", kind="success")
        except Exception as exc:
            self._show_error(exc)

    def free_mode_offer_extra_round(self, tournament_id: int) -> bool:
        """Antes de gerar: no limite de rodadas do modo, oferece mais uma (MA-09).

        ``True`` = pode seguir para a geração (não se aplica, ou a rodada foi
        adicionada). ``False`` = o professor preferiu não gerar.
        """
        from src.services.friendly_mode import is_round_limit_error
        from ..components.dialogs import confirm_dialog

        if not tournament_id or not self._is_free_mode(int(tournament_id)):
            return True
        torneio = self.db.get_tournament(int(tournament_id))
        if not is_round_limit_error(torneio, self.db.get_latest_round(int(tournament_id))):
            return True
        total = int((torneio or {}).get("rounds_count") or 0)
        if not confirm_dialog(
            self,
            f"Mais uma rodada ({FRIENDLY_MODE_LABEL})",
            f"As {total} rodadas do torneio já foram jogadas. Sobrou tempo? "
            "Dá para adicionar mais uma e gerar agora.",
            confirm_text="Adicionar e gerar",
            cancel_text="Agora não",
        ):
            return False
        FriendlyModeService(self.db).add_round(int(tournament_id))
        self._set_current_tournament(int(tournament_id))
        return True

    def free_mode_confirm_internal_rating(self, tournament_id: int) -> bool:
        """Antes do rating interno: o amistoso só conta se o usuário disser que sim (D2).

        ``True`` = pode aplicar (oficial, ou respondeu "contar"); a tela passa
        ``friendly_confirmed=True`` ao serviço. ``False`` = não aplica.
        """
        from src.services.friendly_mode import (
            INTERNAL_RATING_NO,
            INTERNAL_RATING_YES,
            internal_rating_question,
        )
        from ..components.dialogs import confirm_dialog

        pergunta = internal_rating_question(self.db.get_tournament_settings(int(tournament_id)))
        if not pergunta:
            return True
        if confirm_dialog(
            self,
            f"Rating interno ({FRIENDLY_MODE_LABEL})",
            pergunta,
            confirm_text=INTERNAL_RATING_YES,
            cancel_text=INTERNAL_RATING_NO,
        ):
            return True
        self._show_toast("Rating interno não foi atualizado: o torneio amistoso ficou de fora.")
        return False

    def _build_friendly_mode_section(self, tab: Any, settings: dict[str, Any]) -> None:
        """Configurações, aba Avançado: liga e desliga o modo, gravando na hora (MA-07)."""
        from ..components.form import form_of

        pilha = form_of(tab)
        pilha.section(
            "Modo escolar",
            help_text=(
                "Para eventos casuais, escolares ou treinos: entrada a qualquer momento, "
                "rodada refeita com quem está presente e mais uma rodada quando sobrar "
                "tempo. Não vale rating FIDE nem CBX."
            ),
        )
        caixa = ctk.CTkCheckBox(tab, text=FRIENDLY_MODE_LABEL)
        pilha.widget(caixa, help_text="Grava ao marcar ou desmarcar, sem depender do botão Salvar.")
        if settings.get("free_mode"):
            caixa.select()
        self._friendly_mode_check = caixa

        def alternar() -> None:
            ligar = bool(caixa.get())
            try:
                FriendlyModeService(self.db).set_enabled(int(self.current_tournament_id), ligar)
                self._set_current_tournament(int(self.current_tournament_id))
                self._show_toast(
                    f"{FRIENDLY_MODE_LABEL} {'ligado' if ligar else 'desligado'}.", kind="success"
                )
            except Exception as exc:
                if ligar:
                    caixa.deselect()
                else:
                    caixa.select()
                self._show_error(exc)

        caixa.configure(command=alternar)
        if hasattr(self, "_disable_if_unauthorized"):
            self._disable_if_unauthorized(caixa, "tournament_write")

    # ------------------------------------------------------------------
    # Mecânicas do Modo Livre (só atuam quando a marca free_mode é ligada)
    # ------------------------------------------------------------------
    def _is_free_mode(self, tournament_id: int | None = None) -> bool:
        """True se o torneio (atual, por padrão) foi aberto em Modo Livre.

        Lê a marca dedicada free_mode, gravada só pelo fluxo 'Torneio | Modo
        Livre'. Nao depende mais do perfil 'free' (default de todo torneio):
        assim o re-emparceiramento livre e a entrada tardia flexível não vazam
        para eventos comuns ou legados.
        """
        tid = tournament_id or getattr(self, "current_tournament_id", None)
        if not tid:
            return False
        settings = self.db.get_tournament_settings(int(tid)) or {}
        return bool(settings.get("free_mode"))

    def free_mode_repair_round(self) -> None:
        """Refaz a rodada aberta com quem está presente (MA-03).

        Útil quando alunos entram ou saem de surpresa (metade da turma falta):
        marcam-se os ausentes e a rodada sai de novo só com quem está ativo. A
        regra mora em ``PairingService.repair_open_round`` — atômico, recusa
        torneio oficial e rodada fechada. A tela só mostra o que vai ser
        apagado e pede motivo quando há resultado ou submissão QR pendente.
        """
        try:
            self.require_permission("tournament_write")
            if not self._is_free_mode():
                raise AppError(f"Disponível apenas no {FRIENDLY_MODE_LABEL}.")
            round_id = getattr(self, "current_round_id", None)
            if not round_id:
                raise AppError("Selecione uma rodada para re-emparceirar.")
            tournament_id = int(self.current_tournament_id)
            previa = self.pairing_service.repair_open_round_preview(tournament_id, int(round_id))
            motivo = self._ask_repair_reason(previa)
            if motivo is None:
                return
            self._run_repair(tournament_id, int(round_id), motivo)
        except Exception as exc:
            self._show_error(exc)

    def _ask_repair_reason(
        self, previa: dict[str, int], *, confirm_when_empty: bool = True
    ) -> str | None:
        """``""`` sem nada a apagar (só confirma); texto = motivo; ``None`` = cancelou."""
        from src.services.pairing.corrections import round_deletion_reason_error
        from ..components.dialogs import reason_dialog

        titulo = f"Re-emparceirar ({FRIENDLY_MODE_LABEL})"
        explica = (
            "A rodada sai de novo só com os alunos ativos agora. "
            "Quem já está jogando pode trocar de adversário."
        )
        total = int(previa.get("results") or 0) + int(previa.get("qr_submissions") or 0)
        if not total:
            if not confirm_when_empty:
                return ""
            ok = self._confirm_action(titulo, f"{explica}\n\nContinuar?", danger=True)
            return "" if ok else None
        apagar = _o_que_sera_apagado(previa)
        return reason_dialog(
            self,
            titulo,
            f"{explica}\n\nSerão apagados {apagar}; eles ficam guardados na "
            "auditoria do torneio. Diga por que a rodada vai ser refeita:",
            validate=lambda texto: round_deletion_reason_error(texto, total),
            confirm_text="Re-emparceirar",
            danger=True,
        )

    def _accept_reserve_engine(self, exc: Exception) -> bool:
        """Recusa do Gacrux no modo: nada mudou; pergunta se vai pelo motor reserva."""
        from ..components.dialogs import confirm_dialog

        if not getattr(exc, "offers_reserve", True):
            # Sem pareamento legal (RG2-22): o reserva também não teria saída.
            self._show_error(exc)
            return False
        return bool(
            confirm_dialog(
                self,
                "Motor FIDE recusou a rodada",
                f"{exc}\n\nA rodada atual não foi alterada. A escolha fica registrada "
                "na auditoria do torneio.",
                confirm_text="Parear com o motor reserva",
                cancel_text="Cancelar",
            )
        )

    def _run_repair(
        self, tournament_id: int, round_id: int, motivo: str, *, reserve_engine: bool = False
    ) -> None:
        from src.services.pairing.gacrux_engine import GacruxRefusal

        try:
            self.pairing_service.repair_open_round(
                tournament_id, round_id, motivo, reserve_engine=reserve_engine
            )
        except GacruxRefusal as exc:
            # A rodada original continua lá (a transação desfez tudo).
            if self._accept_reserve_engine(exc):
                self._run_repair(tournament_id, round_id, motivo, reserve_engine=True)
            return
        if hasattr(self, "_load_round_options"):
            self._load_round_options()
        self._show_toast(f"Rodada re-emparceirada no {FRIENDLY_MODE_LABEL}.", kind="success")

    def _closed_rounds_count(self, tournament_id: int) -> int:
        """Quantidade de rodadas ja encerradas do torneio."""
        return sum(
            1
            for r in self.db.list_rounds(int(tournament_id))
            if str(r.get("status")) == "closed"
        )

    def free_mode_late_entry_choice(self, tournament_id: int | None = None) -> Any:
        """O que o professor decide para o aluno que chega depois (MA-04/MA-10).

        ``None``: não se aplica (fora do modo, ou nenhuma rodada gerada) — a
        inscrição segue o caminho normal. ``False``: cancelou. Senão, o dicionário
        ``{"per_round_points", "join_open_round"}`` que vai para
        ``FriendlyModeService.late_entry``. No máximo duas perguntas, com botões
        que dizem o que fazem.
        """
        ultima = self._friendly_latest_round(tournament_id)
        if not ultima:
            return None
        numero = int(ultima.get("number") or 0)
        jogar_ja = self._ask_join_open_round(numero) if str(ultima.get("status")) != "closed" else False
        if jogar_ja is None:
            return False
        pontos = self._ask_late_points(numero - 1 if jogar_ja else numero)
        if pontos is None:
            return False
        return {"per_round_points": pontos, "join_open_round": jogar_ja}

    def _friendly_latest_round(self, tournament_id: int | None) -> dict[str, Any] | None:
        """A última rodada do torneio, se ele está no modo e já tem rodada; senão ``None``."""
        tid = tournament_id or getattr(self, "current_tournament_id", None)
        if not tid or not self._is_free_mode(tid):
            return None
        return self.db.get_latest_round(int(tid)) or None

    def _ask_join_open_round(self, numero: int) -> bool | None:
        """Rodada aberta: jogar já nela (refeita com o aluno) ou esperar a próxima."""
        resposta = self._confirm_or_cancel(
            f"Entrada tardia ({FRIENDLY_MODE_LABEL})",
            f"A rodada {numero} está em andamento.\n\nO aluno pode jogar já nesta "
            "rodada (ela é refeita com ele) ou esperar a próxima.",
            yes_text="Jogar já nesta rodada",
            no_text="Esperar a próxima",
        )
        return None if resposta is None else bool(resposta)

    def _ask_late_points(self, perdidas: int) -> float | None:
        """Pontos por rodada perdida: 0,5 ou zero. Sem rodada perdida, não pergunta."""
        if perdidas <= 0:
            return FRIENDLY_LATE_ENTRY_POINTS
        resposta = self._confirm_or_cancel(
            f"Entrada tardia ({FRIENDLY_MODE_LABEL})",
            f"O aluno perdeu {_rodadas(perdidas)}. Com quantos pontos ele começa?\n\n"
            f"Com 0,5 por rodada, ele entra com {_pontos(perdidas * FRIENDLY_LATE_ENTRY_POINTS)}.",
            yes_text="Dar 0,5 por rodada",
            no_text="Começar com zero",
        )
        if resposta is None:
            return None
        return FRIENDLY_LATE_ENTRY_POINTS if resposta else 0.0

    def free_mode_add_player(self, tournament_id: int, payload: dict[str, Any]) -> bool | None:
        """Inscreve o aluno que chega depois, no modo. ``None`` = caminho normal.

        ``True``: inscrito. ``False``: o professor cancelou ou o motor recusou.
        Erro de regra sobe para a tela, que mostra a recusa.
        """
        escolha = self.free_mode_late_entry_choice(tournament_id)
        if escolha is None or escolha is False:
            return escolha
        motivo = self._join_reason(int(tournament_id)) if escolha["join_open_round"] else ""
        if motivo is None:
            return False
        return self._run_friendly_late_entry(int(tournament_id), payload, escolha, motivo)

    def _join_reason(self, tournament_id: int) -> str | None:
        """"Jogar já" refaz a rodada: pede motivo se houver resultado a apagar."""
        ultima = self.db.get_latest_round(tournament_id) or {}
        previa = self.pairing_service.repair_open_round_preview(tournament_id, int(ultima.get("id") or 0))
        return self._ask_repair_reason(previa, confirm_when_empty=False)

    def _run_friendly_late_entry(
        self,
        tournament_id: int,
        payload: dict[str, Any],
        escolha: dict[str, Any],
        motivo: str,
        *,
        reserve_engine: bool = False,
    ) -> bool:
        from src.services.pairing.gacrux_engine import GacruxRefusal

        try:
            FriendlyModeService(self.db).late_entry(
                tournament_id,
                payload,
                per_round_points=escolha["per_round_points"],
                join_open_round=escolha["join_open_round"],
                reason=motivo,
                reserve_engine=reserve_engine,
            )
        except GacruxRefusal as exc:
            if self._accept_reserve_engine(exc):
                return self._run_friendly_late_entry(
                    tournament_id, payload, escolha, motivo, reserve_engine=True
                )
            return False
        if escolha["join_open_round"] and hasattr(self, "_load_round_options"):
            self._load_round_options()
        return True

    def prepare_late_entry(
        self, tournament_id: int | None = None
    ) -> tuple[bool, float | None]:
        """Entrada tardia pela tela de jogadores, no Modo Oficial.

        O modo amistoso não passa por aqui: a tela chama antes
        ``free_mode_add_player`` (MA-04), que usa o plano do assistente.

        - Modo Oficial: após a 2a rodada encerrada, diz o que vai
          acontecer (rodada de entrada, rodadas perdidas como ausência com os
          pontos de entrada tardia) e pede confirmação -- não bloqueia e mantém
          o cálculo padrão de pontos (starting_points=None).

        O texto antigo dizia que a inscrição tardia "foge ao regulamento" (sem
        acento e impreciso: o C.04 não a proíbe, quem decide e o regulamento do
        torneio) e não mostrava o efeito. O assistente "Entrada tardia..."
        (RGS-24) mostra a rodada e os pontos antes de gravar.
        """
        tid = tournament_id or getattr(self, "current_tournament_id", None)
        if not tid:
            return True, None
        encerradas = self._closed_rounds_count(int(tid))
        if encerradas >= 2:
            confirmar = self._confirm_action(
                "Entrada tardia",
                f"Já há {encerradas} rodadas encerradas. O jogador entra na próxima "
                "rodada a ser gerada; as rodadas anteriores contam como ausência, "
                "com os pontos por entrada tardia das configurações do torneio. "
                "Nada é gravado nas rodadas já disputadas e o limite de byes não "
                "é consumido.\n\nPara ver a rodada de entrada e os pontos antes "
                "de confirmar, use \"Entrada tardia…\" em Rodadas ou no Painel."
                "\n\nInscrever este jogador agora?",
            )
            if not confirmar:
                return False, None
        return True, None

    def _center_over_self(self, win: ctk.CTkToplevel, width: int, height: int) -> None:
        """Centraliza sobre a janela principal, levemente acima, **e cabendo**.

        A conta e a mesma do `Dialog` canônico (F5.8): o pedido passa por
        `fitted_size` antes, porque o customtkinter multiplica a geometria
        pela escala da janela e não olha para o monitor — a 160% um modal de
        500x430 vira 800x688 e o rodapé sai da tela num notebook (P3-10).
        """
        win.update_idletasks()
        try:
            tela = (self.winfo_screenwidth(), self.winfo_screenheight())
            escala = window_scale(win)
            tamanho = fitted_size((width, height), scale=escala, screen=tela)
            dono = (self.winfo_rootx(), self.winfo_rooty(), self.winfo_width(), self.winfo_height())
            posicao = centered_position(
                (int(tamanho[0] * escala), int(tamanho[1] * escala)), owner=dono, screen=tela
            )
            win.geometry(geometry_string(tamanho))
            win.geometry(f"+{posicao[0]}+{posicao[1]}")
        except Exception:
            win.geometry(f"{width}x{height}")
