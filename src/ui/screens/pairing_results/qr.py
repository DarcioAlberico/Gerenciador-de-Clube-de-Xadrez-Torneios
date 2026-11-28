"""Resultado por QR: link da mesa, servidor local e fila de aprovação (B-6).

O caminho do QR é uma conversa de três pontas — a tela do árbitro, o celular
de quem joga e a fila de aprovação — e as cinco funções dela estavam
espalhadas entre exportação e troca de jogador.

O que fica registrado aqui: **nada entra sem aprovação**. O envio pelo celular
grava uma *submissão*, não um resultado; o resultado só muda quando o árbitro
aprova. É o que permite deixar o QR ligado numa sala cheia sem abrir mão de
quem manda no placar.
"""
from __future__ import annotations

import logging
from typing import Any

import customtkinter as ctk

from ...components import Dialog, actions_bar
from ...components.dialogs import choice_dialog
from src.services.result_server import lan_addresses
from ...support import AppError, LocalResultServer, SPACE_LG, SPACE_MD

logger = logging.getLogger(__name__)


class QrResultActions:
    """As ações de resultado por QR, montadas sobre o host."""

    def __init__(self, host: Any) -> None:
        self.host = host

    def show_link(self) -> None:
        host = self.host
        try:
            pairing_id = host._selected_pairing_id()
            if not pairing_id:
                raise AppError("Selecione uma mesa.")
            if getattr(host, "pairing_team_mode", False):
                raise AppError("QR de resultado por tabuleiro de equipes será tratado na fase de equipes avançadas.")
            payload = host.qr_result_service.result_url_for_pairing(int(host.current_tournament_id), int(pairing_id))
            # Relatório, não confirmação: o endereço e a entrega, e precisa ser
            # copiado para chegar ao celular do jogador (F5.7).
            host._show_report(
                "Link para envio por QR",
                f"{payload['url']}\n\n"
                "O resultado enviado fica pendente até aprovação do árbitro.",
            )
        except Exception as exc:
            host._show_error(exc)

    def start_server(self) -> None:
        host = self.host
        try:
            if host.local_result_server is None:
                host.local_result_server = LocalResultServer(host.qr_result_service)
            if not choose_network_address(host, host.local_result_server):
                return
            url = host.local_result_server.start()
            host.db.save_app_settings({"local_result_server_url": url})
            host._show_report(
                "Servidor QR ativo",
                f"{url}\n\nUse este endereço na mesma rede local.",
            )
        except Exception as exc:
            host._show_error(exc)

    def approve(self, submission_id: int) -> None:
        host = self.host
        reviewer, _role = host.db._operator_context()
        host.qr_result_service.approve_submission(submission_id, reviewer=reviewer)
        try:
            host._load_selected_round_pairings()
        except Exception:
            logger.debug("Mesas da rodada nao recarregadas apos o QR", exc_info=True)
        host._show_toast("Resultado QR aprovado.", kind="success")

    def reject(self, submission_id: int) -> None:
        host = self.host
        reviewer, _role = host.db._operator_context()
        host.qr_result_service.reject_submission(submission_id, reviewer=reviewer)
        host._show_toast("Resultado QR rejeitado.", kind="success")

    def open_queue(self) -> None:
        host = self.host
        try:
            host.require_permission("tournament_write")
            submissions = host.qr_result_service.pending_submissions(int(host.current_tournament_id))
        except Exception as exc:
            host._show_error(exc)
            return

        window = Dialog(host, "Submissões QR", size=(780, 420), stretch_rows=(0,))

        panel = ctk.CTkFrame(window, fg_color="transparent")
        panel.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(0, weight=1)

        tree = host._make_tree(
            panel,
            ["id", "round", "board", "submitted", "current", "submitter", "time"],
            {
                "id": "ID",
                "round": "Rodada",
                "board": "Mesa",
                "submitted": "Enviado",
                "current": "Atual",
                "submitter": "Enviado por",
                "time": "Horário",
            },
            {
                "id": 60,
                "round": 80,
                "board": 70,
                "submitted": 90,
                "current": 90,
                "submitter": 180,
                "time": 170,
            },
            visible_rows=9,
        )
        for submission in submissions:
            tree.insert(
                "",
                "end",
                values=(
                    submission["id"],
                    submission.get("round_number", ""),
                    submission.get("board_number", ""),
                    submission.get("submitted_result", ""),
                    submission.get("current_result", ""),
                    submission.get("submitter", ""),
                    submission.get("submitted_at", ""),
                ),
            )

        def selected_submission_id() -> int:
            selected = tree.selection()
            if not selected:
                raise AppError("Selecione um envio.")
            values = tree.item(selected[0], "values")
            return int(values[0])

        def approve() -> None:
            try:
                self.approve(selected_submission_id())
                window.close()
            except Exception as exc:
                host._show_error(exc)

        def reject() -> None:
            try:
                self.reject(selected_submission_id())
                window.close()
            except Exception as exc:
                host._show_error(exc)

        actions_bar(
            window,
            row=1,
            primary=("Aprovar", approve),
            danger=("Rejeitar", reject),
            close_text="Fechar",
        )


def choose_network_address(host: Any, server: LocalResultServer) -> bool:
    """Qual IP vai no QR quando a máquina está em mais de uma rede (RG2-45).

    Com uma rede só (ou nenhuma) não pergunta. Devolve ``False`` se o árbitro
    cancelou — aí o servidor não sobe com um endereço que ninguém escolheu.
    """
    enderecos = lan_addresses()
    if len(enderecos) < 2 or server.advertised_host in enderecos:
        return True
    opcoes = [(endereco, endereco, "primary" if indice == 0 else "secondary") for indice, endereco in enumerate(enderecos)]
    escolha = choice_dialog(
        host,
        "Endereço na rede",
        "Esta máquina está em mais de uma rede. Qual endereço os celulares devem usar? "
        "Escolha o da Wi-Fi do torneio.",
        options=[*opcoes, ("Cancelar", None, "secondary")],
        default=enderecos[0],
    )
    if not escolha:
        return False
    server.advertised_host = str(escolha)
    return True
