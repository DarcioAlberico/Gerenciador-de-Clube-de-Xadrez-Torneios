"""As mesas aguardando resultado — a tela dentro do painel do árbitro.

Busca, tabela e lançamento inline. Ganhou módulo próprio porque é o que o
árbitro de fato **usa** durante a rodada: as outras partes do painel informam,
esta age. Junto vem o contrato que os testes conhecem
(``arbitration_pending_tree`` / ``arbitration_pending_row_map`` /
``arbitration_pending_query_entry``), guardado no host porque os atalhos de
teclado precisam alcançá-lo de qualquer tela.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ...components import WrapRow, reason_dialog, secondary_button
from ...i18n import t
from ...support import THEME_TEXT_SUB

PENDING_COLUMNS = ("board", "context", "white", "black")

# Atalhos de teclado da lista de mesas: tecla → resultado lançado. O árbitro
# digita "1" com a mão esquerda enquanto a direita segura a súmula, e o teclado
# numérico precisa valer o mesmo que o de cima.
RESULT_SHORTCUTS = {
    "1": "1-0",
    "<KP_1>": "1-0",
    "0": "0-1",
    "<KP_0>": "0-1",
    "-": "1/2-1/2",
    "<KP_Subtract>": "1/2-1/2",
    "<BackSpace>": "",
    "<Delete>": "",
    # W.O. (ARB-02): letras, e não números, porque passam por confirmação — um
    # dedo torto no teclado numérico não pode lançar ausência. `w` = brancas
    # vencem, `p` = pretas vencem, `a` = dupla ausência.
    "w": "1F-0F",
    "p": "0F-1F",
    "a": "0F-0F",
}

# Resultados oferecidos como botão, na ordem em que a súmula os traz.
INLINE_RESULTS = (("1-0", "1-0"), ("1/2", "1/2-1/2"), ("0-1", "0-1"))

# W.O. no painel (ARB-02): era lançável só na tela `Rodadas`, justamente o que o
# árbitro NÃO tem à mão quando está em pé no salão decidindo uma ausência. Os
# rótulos são os códigos da súmula, os mesmos que a tela `Rodadas` mostra.
WALKOVER_INLINE_RESULTS = (
    ("1F-0F", "1F-0F"),
    ("0F-1F", "0F-1F"),
    ("0F-0F", "0F-0F"),
)

# Resultados que exigem confirmação antes de gravar: são DECISÃO do árbitro
# sobre alguém que não jogou, não a transcrição de um placar.
CONFIRMED_RESULTS = frozenset(code for _rotulo, code in WALKOVER_INLINE_RESULTS)


class PendingTablesSection:
    """Monta a lista de mesas pendentes dentro do painel do árbitro."""

    def __init__(self, host: Any, controller: Any) -> None:
        self.host = host
        self.controller = controller

    @property
    def tournament_id(self) -> int:
        return int(self.host.current_tournament_id)

    # ---- Montagem --------------------------------------------------------- #

    def build(
        self, main: ctk.CTkFrame, metrics: dict[str, Any], pending_items: list[dict[str, Any]]
    ) -> None:
        host = self.host
        painel = host._make_panel(main)
        painel.grid(row=1, column=0, padx=(0, 12), pady=(12, 0), sticky="nsew")
        painel.grid_columnconfigure(0, weight=1)

        self._build_header(painel, metrics, len(pending_items))
        if pending_items:
            self._build_table(painel, pending_items)
            return
        # Sem mesa pendente o contrato precisa dizer isso, e não apontar para a
        # tabela da visita anterior: o atalho de teclado ainda alcança o host.
        host.arbitration_pending_row_map = {}
        host.arbitration_pending_tree = None
        ctk.CTkLabel(painel, text=t("arbitration.pending.empty"), text_color=THEME_TEXT_SUB).grid(
            row=1, column=0, padx=14, pady=(0, 12), sticky="w"
        )

    def _build_header(self, painel: ctk.CTkFrame, metrics: dict[str, Any], exibidos: int) -> None:
        host = self.host
        cabecalho = ctk.CTkFrame(painel, fg_color="transparent")
        cabecalho.grid(row=0, column=0, padx=14, pady=(12, 6), sticky="ew")
        cabecalho.grid_columnconfigure(0, weight=1)
        host._section_title(cabecalho, t("arbitration.pending.title")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(
            cabecalho,
            text=t(
                "arbitration.pending.showing",
                exibidos=exibidos,
                total=metrics["pending_results"],
            ),
            text_color=THEME_TEXT_SUB,
        ).grid(row=0, column=1, padx=(8, 0), sticky="e")
        secondary_button(
            cabecalho, t("arbitration.pending.open"), host.show_pairings, width=140
        ).grid(row=0, column=2, padx=(10, 0), sticky="e")

        # A faixa de busca quebra linha (B-8): campo mais dois botões somam
        # ~400px numa coluna que divide a largura com as "Ações rápidas". Aqui a
        # faixa funciona porque a coluna é larga e sua posição não depende dela.
        faixa = WrapRow(cabecalho)
        faixa.grid(row=1, column=0, columnspan=3, pady=(8, 0), sticky="ew")
        # O campo nasce dentro da faixa: no Tk um widget não troca de pai depois
        # de criado, e um `master` reatribuído à mão mente para o layout.
        busca = ctk.CTkEntry(
            faixa.frame, width=160, placeholder_text=t("arbitration.pending.search_placeholder")
        )
        busca.insert(0, getattr(host, "_arbitration_pending_query", ""))
        host.arbitration_pending_query_entry = busca
        faixa.add(busca, 160, grow=True)
        faixa.add(
            secondary_button(
                faixa.frame, t("arbitration.pending.search"), self.apply_query, width=120
            ),
            120,
        )
        faixa.add(
            secondary_button(
                faixa.frame, t("arbitration.pending.clear"), self.clear_query, width=120
            ),
            120,
        )
        busca.bind("<Return>", self.apply_query)
        faixa.bind_to(host.content)

    def _build_table(self, painel: ctk.CTkFrame, pending_items: list[dict[str, Any]]) -> None:
        host = self.host
        tabela = host._make_tree(
            painel,
            list(PENDING_COLUMNS),
            {
                "board": t("arbitration.pending.column.board"),
                "context": t("arbitration.pending.column.context"),
                "white": t("arbitration.pending.column.white"),
                "black": t("arbitration.pending.column.black"),
            },
            {"board": 70, "context": 100, "white": 320, "black": 320},
            visible_rows=min(6, len(pending_items)),
        )
        tabela.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="ew")
        host.arbitration_pending_tree = tabela
        host.arbitration_pending_row_map = {}
        for item in pending_items:
            iid = tabela.insert(
                "", "end", values=(item["board"], item["context"], item["white"], item["black"])
            )
            host.arbitration_pending_row_map[iid] = int(item["pairing_id"])

        tabela.bind("<Double-1>", lambda _evento: host.show_pairings())
        for tecla, resultado in RESULT_SHORTCUTS.items():
            tabela.bind(
                tecla, lambda _evento, valor=resultado: host._save_arbitration_panel_result(valor)
            )
        primeira = tabela.get_children()
        if primeira:
            # A primeira mesa já nasce selecionada: o atalho de teclado só serve
            # se houver alvo, e o árbitro lança de cima para baixo.
            tabela.selection_set(primeira[0])
            tabela.focus(primeira[0])
            tabela.see(primeira[0])

        self._build_inline_actions(painel)
        tabela.focus_set()

    def _build_inline_actions(self, painel: ctk.CTkFrame) -> None:
        host = self.host
        faixa = WrapRow(painel)
        faixa.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="ew")
        faixa.add(
            ctk.CTkLabel(
                faixa.frame, text=t("arbitration.pending.enter_result"), text_color=THEME_TEXT_SUB
            ),
            130,
        )
        for rotulo, resultado in (*INLINE_RESULTS, (t("arbitration.pending.clear_result"), "")):
            faixa.add(
                ctk.CTkButton(
                    faixa.frame,
                    text=rotulo,
                    width=70,
                    command=lambda valor=resultado: host._save_arbitration_panel_result(valor),
                ),
                70,
            )
        faixa.add(
            ctk.CTkLabel(
                faixa.frame, text=t("arbitration.pending.walkover"), text_color=THEME_TEXT_SUB
            ),
            60,
        )
        for rotulo, resultado in WALKOVER_INLINE_RESULTS:
            faixa.add(
                secondary_button(
                    faixa.frame,
                    rotulo,
                    lambda valor=resultado: host._save_arbitration_panel_result(valor),
                    width=76,
                ),
                76,
            )
        # Adiar/retomar (ARB-02) fica na mesma faixa: é a terceira coisa que se
        # faz com uma mesa em aberto, junto de lançar placar e lançar W.O.
        faixa.add(
            secondary_button(
                faixa.frame, t("arbitration.pending.postpone"), self.postpone, width=90
            ),
            90,
        )
        faixa.add(
            secondary_button(
                faixa.frame, t("arbitration.pending.resume"), self.resume, width=90
            ),
            90,
        )
        faixa.add(
            ctk.CTkLabel(
                faixa.frame, text=t("arbitration.pending.shortcuts"), text_color=THEME_TEXT_SUB
            ),
            250,
        )
        faixa.bind_to(host.content)

    # ---- Ponte ------------------------------------------------------------ #

    def apply_query(self, _event: Any = None) -> None:
        entrada = self.host.arbitration_pending_query_entry
        self.host._arbitration_pending_query = entrada.get().strip()
        self.host.show_arbitration_panel()

    def clear_query(self) -> None:
        self.host._arbitration_pending_query = ""
        self.host.show_arbitration_panel()

    def save_result(self, result: str) -> str:
        """Lança o resultado da mesa selecionada. Devolve "break" (é um bind)."""
        host = self.host
        try:
            tabela = getattr(host, "arbitration_pending_tree", None)
            if tabela is None:
                raise self._app_error(t("arbitration.error.no_pending"))
            selecionado = tabela.selection()
            if not selecionado:
                raise self._app_error(t("arbitration.error.select_table"))
            pairing_id = host.arbitration_pending_row_map.get(selecionado[0])
            if not pairing_id:
                raise self._app_error(t("arbitration.error.table_not_found"))
            if not self._confirmed(tabela, selecionado[0], result):
                return "break"
            self.controller.save_result(self.tournament_id, int(pairing_id), result)
            host.show_arbitration_panel()
        except Exception as exc:
            host._show_error(exc)
        return "break"

    def postpone(self) -> None:
        """Marca a mesa selecionada como adiada, perguntando o combinado."""
        host = self.host
        try:
            pairing_id = self._selected_pairing_id()
            # Nota OPCIONAL, e por isso o `validate` que aceita vazio: adiar sem
            # saber quando ainda é melhor do que a mesa parecer esquecida. Quem
            # exige texto é a correção de rodada fechada (ARB-01), que é prova
            # documental — esta aqui é um lembrete.
            nota = reason_dialog(
                host,
                t("arbitration.pending.postpone_title"),
                t("arbitration.pending.postpone_prompt"),
                validate=lambda _texto: "",
            )
            if nota is None:  # cancelou
                return
            self.controller.postpone_pairing(self.tournament_id, pairing_id, nota)
            host.show_arbitration_panel()
        except Exception as exc:
            host._show_error(exc)

    def resume(self) -> None:
        """Desfaz o adiamento da mesa selecionada."""
        host = self.host
        try:
            pairing_id = self._selected_pairing_id()
            self.controller.resume_pairing(self.tournament_id, pairing_id)
            host.show_arbitration_panel()
        except Exception as exc:
            host._show_error(exc)

    def _selected_pairing_id(self) -> int:
        tabela = getattr(self.host, "arbitration_pending_tree", None)
        if tabela is None:
            raise self._app_error(t("arbitration.error.no_pending"))
        selecionado = tabela.selection()
        if not selecionado:
            raise self._app_error(t("arbitration.error.select_table"))
        pairing_id = self.host.arbitration_pending_row_map.get(selecionado[0])
        if not pairing_id:
            raise self._app_error(t("arbitration.error.table_not_found"))
        return int(pairing_id)

    def _confirmed(self, tabela: Any, iid: str, result: str) -> bool:
        """Pede confirmação para o que é decisão, não transcrição (ARB-02).

        Um W.O. declara que alguém não compareceu — e a tecla que o lança fica a
        um dedo de distância da que lança o placar. A confirmação nomeia a mesa e
        os dois jogadores, porque o erro que ela precisa pegar é o de mesa
        errada, não o de código errado.
        """
        if result not in CONFIRMED_RESULTS:
            return True
        valores = list(tabela.item(iid, "values") or [])
        mesa, brancas, pretas = "?", "?", "?"
        if len(valores) >= len(PENDING_COLUMNS):
            mesa, brancas, pretas = valores[0], valores[2], valores[3]
        return bool(
            self.host._confirm_action(
                t("arbitration.pending.walkover_confirm_title"),
                t(
                    "arbitration.pending.walkover_confirm",
                    resultado=result,
                    mesa=mesa,
                    brancas=brancas,
                    pretas=pretas,
                ),
                danger=True,
            )
        )

    @staticmethod
    def _app_error(message: str) -> Exception:
        from src.services.constants import AppError

        return AppError(message)
