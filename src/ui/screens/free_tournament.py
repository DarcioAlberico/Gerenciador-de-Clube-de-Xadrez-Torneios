from __future__ import annotations

from ..support import *
from ..components import window_scale
from ..dialog_layout import centered_position, fitted_size, geometry_string


# Mixin do "Modo Livre" (Torneio | Livre) — eventos casuais, escolares ou treinos.
# Por ora exibe apenas o aviso informativo do modo, sem alterar nenhuma regra.
# Fica deliberadamente isolado do fluxo oficial (FIDE/CBX) e serve de ponto de
# extensao para o backlog do "Modo Escolar Amistoso" (entrada tardia, re-pair
# manual, pontuacao retroativa) sem tocar no emparceiramento oficial vigente.
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
        para a criacao do torneio (P1-11) — que ainda pede o nome, entao nada e
        criado sem confirmacao. Devolve ``None`` nesse caso.
        """
        if self._free_mode_notice_hidden():
            self._start_free_tournament(None)
            return None

        dialog = ctk.CTkToplevel(self)
        dialog.title("Modo Livre")
        dialog.transient(self.winfo_toplevel())
        dialog.resizable(False, False)

        body = ctk.CTkFrame(dialog, fg_color=THEME_PANEL_BG)
        body.pack(fill="both", expand=True, padx=16, pady=16)

        # Rodape fixado na parte inferior (empacotado primeiro para ancorar
        # embaixo independentemente da altura do texto). "Iniciar Modo Livre"
        # cria um torneio ja no perfil Livre/Escolar; "Cancelar" so fecha.
        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=(12, 0))

        # A escolha e gravada nos dois caminhos de saida (iniciar e cancelar):
        # marcar a caixa e so entao cancelar tambem tem de valer.
        hide_notice = ctk.CTkCheckBox(footer, text="Não mostrar novamente")
        hide_notice.pack(side="left")
        self.free_mode_hide_checkbox = hide_notice

        def remember_choice() -> None:
            if not hide_notice.get():
                return
            try:
                self.db.save_app_settings({"free_mode_notice_hidden": "1"})
            except Exception:
                logger.exception("Falha ao gravar preferencia do aviso do Modo Livre")

        def start() -> None:
            remember_choice()
            self._start_free_tournament(dialog)

        def cancel() -> None:
            remember_choice()
            dialog.destroy()

        ctk.CTkButton(
            footer,
            text="Iniciar Modo Livre",
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
            text="  Modo Livre Ativado",
            image=icon,
            compound="left",
            anchor="w",
            text_color=THEME_ACCENT,
            font=ctk.CTkFont(size=SIZE_MODAL_TITLE, weight="bold"),
        ).pack(fill="x", padx=4, pady=(4, 12))

        ctk.CTkLabel(
            body,
            text=(
                "Este módulo é voltado para eventos casuais, escolares ou treinos. "
                "As regras oficiais de emparceiramento e restrições de rodadas são "
                "flexibilizadas para permitir:"
            ),
            justify="left",
            anchor="w",
            wraplength=440,
            text_color=THEME_TEXT_MAIN,
            font=ctk.CTkFont(size=SIZE_BODY + 1),
        ).pack(fill="x", padx=4, pady=(0, 10))

        for item in (
            "Entrada tardia de jogadores a qualquer momento.",
            "Emparceiramentos e ajustes manuais nas rodadas.",
            "Ausência de punições estritas por atraso.",
        ):
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

        self._center_over_self(dialog, 500, 430)
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.bind("<Escape>", lambda _e: cancel())
        dialog.bind("<Return>", lambda _e: start())

        def _grab() -> None:
            try:
                dialog.grab_set()
            except Exception:  # janela ainda nao visivel em alguns gerenciadores
                pass

        dialog.after(50, _grab)
        dialog.lift()
        dialog.focus()
        return dialog

    def _start_free_tournament(self, dialog: ctk.CTkToplevel | None) -> int | None:
        """Fecha o aviso e cria um torneio ja em Modo Livre.

        Nao toca em torneios existentes nem no fluxo oficial: cria um evento
        novo e grava a marca dedicada free_mode (set_free_mode). E essa marca,
        nao o perfil, que habilita o re-emparceiramento livre, a entrada tardia
        flexivel e o indicador 'Modo Livre' apenas neste evento.
        """
        if dialog is not None:  # None quando o aviso foi suprimido pelo operador
            dialog.destroy()
        name = self._ask_string("Novo Torneio Livre", "Nome do torneio:")
        if name is None:
            return None  # usuario cancelou o prompt de nome
        name = name.strip() or f"Torneio Livre {date.today().strftime('%d/%m/%Y')}"
        try:
            tournament_id = self.tournament_service.create_tournament(
                {"name": name, "rounds_count": "5", "bye_points": "1"}
            )
            self.db.set_free_mode(tournament_id, True)
        except Exception as exc:
            self._show_error(exc)
            return None
        self._set_current_tournament(tournament_id)
        logger.info("Torneio livre criado: %s", tournament_id)
        self._show_toast(
            f"Modo Livre iniciado: '{name}'. Ajuste rodadas, datas e jogadores quando quiser.",
            kind="success",
        )
        self.show_players()
        return tournament_id

    # ------------------------------------------------------------------
    # Mecanicas do Modo Livre (so atuam quando a marca free_mode esta ligada)
    # ------------------------------------------------------------------
    def _is_free_mode(self, tournament_id: int | None = None) -> bool:
        """True se o torneio (atual, por padrao) foi aberto em Modo Livre.

        Le a marca dedicada free_mode, gravada so pelo fluxo 'Torneio | Modo
        Livre'. Nao depende mais do perfil 'free' (default de todo torneio):
        assim o re-emparceiramento livre e a entrada tardia flexivel nao vazam
        para eventos comuns ou legados.
        """
        tid = tournament_id or getattr(self, "current_tournament_id", None)
        if not tid:
            return False
        settings = self.db.get_tournament_settings(int(tid)) or {}
        return bool(settings.get("free_mode"))

    def free_mode_repair_round(self) -> None:
        """Modo Livre: limpa o emparceiramento da rodada atual e regera.

        Util quando jogadores entram ou saem de surpresa (ex.: metade de uma
        escola falta de repente): marca-se os ausentes e re-emparceira so com
        quem esta presente. So opera no perfil Livre/Escolar e nunca em rodada
        ja encerrada (delete_generated_round ja protege isso). Nao interfere em
        torneios oficiais.
        """
        try:
            self.require_permission("tournament_write")
            if not self._is_free_mode():
                raise AppError("Disponivel apenas no Modo Livre (perfil Livre/Escolar).")
            round_id = getattr(self, "current_round_id", None)
            if not round_id:
                raise AppError("Selecione uma rodada para re-emparceirar.")
            if not self._confirm_action(
                "Re-emparceirar (Modo Livre)",
                "Isto vai limpar o emparceiramento desta rodada e gerar um novo, "
                "considerando apenas os jogadores ativos no momento.\n\nContinuar?",
                danger=True,
            ):
                return
            self.pairing_service.delete_generated_round(int(round_id))
            self.pairing_service.generate_next_round(self.current_tournament_id)
            if hasattr(self, "_load_round_options"):
                self._load_round_options()
            self._show_toast("Rodada re-emparceirada no Modo Livre.", kind="success")
        except Exception as exc:
            self._show_error(exc)

    def _closed_rounds_count(self, tournament_id: int) -> int:
        """Quantidade de rodadas ja encerradas do torneio."""
        return sum(
            1
            for r in self.db.list_rounds(int(tournament_id))
            if str(r.get("status")) == "closed"
        )

    def free_mode_late_entry_starting_points(
        self, tournament_id: int | None = None
    ) -> tuple[bool, float | None]:
        """Decide os pontos iniciais de um jogador que entra tarde no Modo Livre.

        Retorna (prosseguir, starting_points):
        - Fora do Modo Livre ou sem rodadas encerradas: (True, None) -> mantem o
          calculo padrao do sistema (late_entry_points global).
        - Com rodadas encerradas no Modo Livre: pergunta se o jogador herda
          meio-ponto pedagogico (0,5) ou zero (0,0) por rodada ausente.
          Devolve (True, valor) ao escolher, ou (False, None) se cancelar.
        """
        tid = tournament_id or getattr(self, "current_tournament_id", None)
        if not tid or not self._is_free_mode(tid):
            return True, None
        closed = self._closed_rounds_count(int(tid))
        if closed <= 0:
            return True, None
        choice = self._confirm_or_cancel(
            "Entrada tardia (Modo Livre)",
            f"Este jogador esta entrando apos {closed} rodada(s) ja encerrada(s).\n\n"
            "Ele deve herdar meio-ponto pedagogico (0,5) por rodada ausente?\n\n"
            "Sim  =  0,5 por rodada (mantem o aluno motivado)\n"
            "Nao  =  0,0 (zero)\n"
            "Cancelar  =  nao adicionar agora",
        )
        if choice is None:
            return False, None
        return True, round((0.5 if choice else 0.0) * closed, 2)

    def prepare_late_entry(
        self, tournament_id: int | None = None
    ) -> tuple[bool, float | None]:
        """Fluxo de entrada tardia que chaveia conforme o perfil do torneio.

        - Modo Livre (free): delega ao free_mode_late_entry_starting_points
          (pergunta 0,0 ou 0,5 por rodada ausente).
        - Modo Oficial (fide/club): apos a 2a rodada encerrada, avisa que a
          inscricao tardia foge ao regulamento FIDE e pede confirmacao -- nao
          bloqueia e mantem o calculo padrao de pontos (starting_points=None).
        """
        tid = tournament_id or getattr(self, "current_tournament_id", None)
        if not tid:
            return True, None
        if self._is_free_mode(tid):
            return self.free_mode_late_entry_starting_points(tid)
        if self._closed_rounds_count(int(tid)) >= 2:
            confirmar = self._confirm_action(
                "Entrada tardia (Modo Oficial)",
                "Ja ha 2 ou mais rodadas encerradas. Em torneios oficiais "
                "(FIDE/CBX), a inscricao tardia apos a 2a rodada foge ao "
                "regulamento de pareamento.\n\nInscrever este jogador mesmo assim?",
            )
            if not confirmar:
                return False, None
        return True, None

    def _center_over_self(self, win: ctk.CTkToplevel, width: int, height: int) -> None:
        """Centraliza sobre a janela principal, levemente acima, **e cabendo**.

        A conta e a mesma do `Dialog` canonico (F5.8): o pedido passa por
        `fitted_size` antes, porque o customtkinter multiplica a geometria
        pela escala da janela e nao olha para o monitor — a 160% um modal de
        500x430 vira 800x688 e o rodape sai da tela num notebook (P3-10).
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
