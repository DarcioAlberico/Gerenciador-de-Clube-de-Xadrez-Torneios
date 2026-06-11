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

        # Rodape com o botao "Entendi" fixado na parte inferior (empacotado
        # primeiro para ancorar embaixo independentemente da altura do texto).
        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=(12, 0))
        ctk.CTkButton(footer, text="Entendi", width=150, command=dialog.destroy).pack()

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
        dialog.bind("<Return>", lambda _e: dialog.destroy())

        def _grab() -> None:
            try:
                dialog.grab_set()
            except Exception:  # janela ainda nao visivel em alguns gerenciadores
                pass

        dialog.after(50, _grab)
        dialog.lift()
        dialog.focus()
        return dialog

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
