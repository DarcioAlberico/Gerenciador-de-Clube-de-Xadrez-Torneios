"""Mata-mata: registrar o avanço e ler a chave (PAR-03).

Duas ações que só existem neste formato. A primeira é a que destrava a próxima
fase quando a mesa terminou empatada (ou por dupla ausência): o árbitro diz QUEM
passou e POR QUE — antes, o melhor número inicial passava sozinho e em silêncio.
A segunda é a chave, que é onde essa resposta aparece depois.
"""
from __future__ import annotations

from typing import Any

from ...components import Dialog, FormStack, actions_bar
from ...support import AppError, player_pairing_name
from .state import format_knockout_bracket


class KnockoutActions:
    """As ações de mata-mata, montadas sobre o host (a tela de rodadas)."""

    def __init__(self, host: Any) -> None:
        self.host = host

    def open_advancement(self) -> None:
        host = self.host
        try:
            host.require_permission("tournament_write")
            pairing = host._selected_pairing()
            if not pairing:
                raise AppError("Selecione a mesa que terminou sem vencedor.")
            if pairing.get("is_bye") or not pairing.get("black_player_id"):
                raise AppError("Mesa de bye nao tem desempate: o jogador ja avanca sozinho.")

            criterios = host.pairing_service.knockout_advancement_criteria()
            jogadores = {
                int(player["id"]): player_pairing_name(player)
                for player in host.db.list_players(host.current_tournament_id, active_only=False)
            }
            lados = {
                f"{jogadores.get(int(pairing['white_player_id']), '')} (brancas)": int(
                    pairing["white_player_id"]
                ),
                f"{jogadores.get(int(pairing['black_player_id']), '')} (pretas)": int(
                    pairing["black_player_id"]
                ),
            }

            dialog = Dialog(host, "Registrar avanço de fase", size=(520, 380), resizable=False)
            pilha = FormStack(dialog)
            pilha.section(
                f"Mesa {pairing['board_number']}: "
                f"{pairing.get('white_display_name', '')} x "
                f"{pairing.get('black_display_name', '')}"
            )
            pilha.note(
                "A partida não decidiu. Diga quem avança e por qual critério — a "
                "chave passa a mostrar isso."
            )
            jogador_option = pilha.select("Quem avançou", list(lados))
            criterio_option = pilha.select("Critério", list(criterios.values()))
            observacao = pilha.text(
                "Observação",
                placeholder="Obrigatória no critério do regulamento e na decisão do árbitro",
            )
            criterio_por_rotulo = {rotulo: codigo for codigo, rotulo in criterios.items()}

            def aplicar() -> None:
                try:
                    host.pairing_service.register_knockout_advancement(
                        host.current_tournament_id,
                        int(pairing["id"]),
                        lados[jogador_option.get()],
                        criterio_por_rotulo[criterio_option.get()],
                        observacao.get(),
                        actor=getattr(host, "current_user_name", "") or "",
                    )
                    dialog.close()
                    host._show_toast("Avanço registrado.", kind="success")
                    host._load_selected_round_pairings()
                except Exception as exc:
                    host._show_error(exc)

            actions_bar(dialog, primary=("Registrar", aplicar), close_text="Cancelar")
        except Exception as exc:
            host._show_error(exc)

    def show_bracket(self) -> None:
        host = self.host
        try:
            chave = host.pairing_service.knockout_bracket(host.current_tournament_id)
            host._show_info(format_knockout_bracket(chave))
        except Exception as exc:
            host._show_error(exc)
