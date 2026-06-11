from __future__ import annotations

from ..support import *


# Mixin do "Modo Livre" (Torneio | Livre) — eventos casuais, escolares ou treinos.
# Por ora exibe apenas o aviso informativo do modo, sem alterar nenhuma regra.
# Fica deliberadamente isolado do fluxo oficial (FIDE/CBX) e serve de ponto de
# extensao para o backlog do "Modo Escolar Amistoso" (entrada tardia, re-pair
# manual, pontuacao retroativa) sem tocar no emparceiramento oficial vigente.
class FreeTournamentMixin:
    def show_free_tournament_mode(self) -> ctk.CTkToplevel:
        """Abre o aviso modal do Modo Livre e devolve a janela criada."""
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
        ctk.CTkButton(
            footer,
            text="Iniciar Modo Livre",
            width=190,
            command=lambda: self._start_free_tournament(dialog),
        ).pack(side="right")
        ctk.CTkButton(
            footer,
            text="Cancelar",
            width=110,
            fg_color=THEME_NEUTRAL,
            hover_color=THEME_NEUTRAL_HOVER,
            command=dialog.destroy,
        ).pack(side="right", padx=(0, 8))

        icon = getattr(self, "_ctk_menu_icons", {}).get("torneios")
        ctk.CTkLabel(
            body,
            text="  Modo Livre Ativado",
            image=icon,
            compound="left",
            anchor="w",
            text_color=THEME_ACCENT,
            font=ctk.CTkFont(size=18, weight="bold"),
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
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        dialog.bind("<Return>", lambda _e: self._start_free_tournament(dialog))

        def _grab() -> None:
            try:
                dialog.grab_set()
            except Exception:  # janela ainda nao visivel em alguns gerenciadores
                pass

        dialog.after(50, _grab)
        dialog.lift()
        dialog.focus()
        return dialog

    def _start_free_tournament(self, dialog: ctk.CTkToplevel) -> int | None:
        """Fecha o aviso e cria um torneio ja em Modo Livre (perfil free).

        Nao toca em torneios existentes nem no fluxo oficial: apenas cria um
        evento novo, que por padrao ja nasce com tournament_profile='free'.
        """
        dialog.destroy()
        name = self._ask_string("Novo Torneio Livre", "Nome do torneio:")
        if name is None:
            return None  # usuario cancelou o prompt de nome
        name = name.strip() or f"Torneio Livre {date.today().strftime('%d/%m/%Y')}"
        try:
            tournament_id = self.tournament_service.create_tournament(
                {"name": name, "rounds_count": "5", "bye_points": "1"}
            )
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
    # Mecanicas do Modo Livre (so atuam no perfil Livre/Escolar = free)
    # ------------------------------------------------------------------
    def _is_free_mode(self, tournament_id: int | None = None) -> bool:
        """True se o torneio (atual, por padrao) esta no perfil Livre/Escolar."""
        tid = tournament_id or getattr(self, "current_tournament_id", None)
        if not tid:
            return False
        settings = self.db.get_tournament_settings(int(tid)) or {}
        return str(settings.get("tournament_profile") or "free") == "free"

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
            if not messagebox.askyesno(
                "Re-emparceirar (Modo Livre)",
                "Isto vai limpar o emparceiramento desta rodada e gerar um novo, "
                "considerando apenas os jogadores ativos no momento.\n\nContinuar?",
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
        choice = messagebox.askyesnocancel(
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
            confirmar = messagebox.askyesno(
                "Entrada tardia (Modo Oficial)",
                "Ja ha 2 ou mais rodadas encerradas. Em torneios oficiais "
                "(FIDE/CBX), a inscricao tardia apos a 2a rodada foge ao "
                "regulamento de pareamento.\n\nInscrever este jogador mesmo assim?",
            )
            if not confirmar:
                return False, None
        return True, None

    def _center_over_self(self, win: ctk.CTkToplevel, width: int, height: int) -> None:
        """Centraliza horizontalmente sobre a janela principal, levemente acima."""
        win.update_idletasks()
        try:
            px, py = self.winfo_rootx(), self.winfo_rooty()
            pw, ph = self.winfo_width(), self.winfo_height()
            x = px + max((pw - width) // 2, 0)
            y = py + max((ph - height) // 3, 0)
            win.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            win.geometry(f"{width}x{height}")
