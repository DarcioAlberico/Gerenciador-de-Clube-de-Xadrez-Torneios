"""Trocas na mesa: inverter cores e substituir jogador (B-6).

Três ações que só o árbitro faz, e sempre com a rodada já gerada: inverter as
cores de uma mesa e trocar quem joga nela — no individual e por equipes.

Ficam juntas porque compartilham a pergunta difícil: **quem pode entrar no
lugar de quem**. Por equipes a resposta é mais estreita (só alguém da mesma
equipe), e é por isso que são dois diálogos e não um com uma bandeira.
"""
from __future__ import annotations

from typing import Any

from ...components import Dialog, FormStack, actions_bar
from ...support import AppError, logger, player_pairing_name


class BoardSwapActions:
    """As trocas de cor e de jogador, montadas sobre o host."""

    def __init__(self, host: Any) -> None:
        self.host = host

    def swap_colors(self) -> None:
        host = self.host
        try:
            host.require_permission("tournament_write")
            if getattr(host, "pairing_team_mode", False):
                team_board_id = host._selected_pairing_id()
                if not team_board_id:
                    raise AppError("Selecione um tabuleiro.")
                if not host.current_round_id:
                    raise AppError("Selecione uma rodada.")
                host.pairing_service.swap_team_board_colors(
                    host.current_tournament_id,
                    host.current_round_id,
                    team_board_id,
                )
                host._load_selected_round_pairings()
                return
            pairing_id = host._selected_pairing_id()
            if not pairing_id:
                raise AppError("Selecione uma mesa.")
            if host.current_round_id:
                round_data = host.db.get_round(host.current_round_id)
                if round_data and round_data["status"] == "closed":
                    raise AppError("Rodada fechada nao pode ser ajustada.")
            host.db.swap_pairing_colors(pairing_id)
            logger.info("Cores trocadas na mesa %s", pairing_id)
            host._load_selected_round_pairings()
        except Exception as exc:
            host._show_error(exc)

    def open_player_swap(self) -> None:
        host = self.host
        try:
            host.require_permission("tournament_write")
            if getattr(host, "pairing_team_mode", False):
                self.open_team_player_swap()
                return
            if not host.current_round_id:
                raise AppError("Selecione uma rodada.")
            pairing = host._selected_pairing()
            if not pairing:
                raise AppError("Selecione uma mesa.")

            players = host.db.list_players(host.current_tournament_id, active_only=True)
            if not players:
                raise AppError("Nao ha jogadores ativos para trocar.")

            player_options = [
                f"{player['id']} - {player_pairing_name(player)} ({player['rating']})"
                for player in players
            ]
            player_map = {option: int(option.split(" ", maxsplit=1)[0]) for option in player_options}
            slot_options = ["Brancas"]
            if not pairing["is_bye"]:
                slot_options.append("Pretas")

            dialog = Dialog(self, "Trocar jogador", size=(460, 320), resizable=False)
            pilha = FormStack(dialog)
            pilha.section(
                f"Mesa {pairing['board_number']}: "
                f"{pairing['white_display_name']} x "
                f"{pairing['black_display_name']}"
            )
            slot_option = pilha.select("Lado a trocar", slot_options)
            player_option = pilha.select("Jogador", player_options)

            def apply_swap() -> None:
                try:
                    color = "white" if slot_option.get() == "Brancas" else "black"
                    replacement_id = player_map[player_option.get()]
                    host.pairing_service.adjust_pairing_player(
                        host.current_tournament_id,
                        host.current_round_id,
                        pairing["id"],
                        color,
                        replacement_id,
                    )
                    dialog.close()
                    host._load_selected_round_pairings()
                except Exception as exc:
                    host._show_error(exc)

            actions_bar(dialog, primary=("Aplicar", apply_swap), close_text="Cancelar")
        except Exception as exc:
            host._show_error(exc)

    def open_team_player_swap(self) -> None:
        host = self.host
        try:
            host.require_permission("tournament_write")
            if not host.current_round_id:
                raise AppError("Selecione uma rodada.")
            board = host._selected_pairing()
            if not board:
                raise AppError("Selecione um tabuleiro.")

            players = host.db.list_players(host.current_tournament_id, active_only=True)
            if not players:
                raise AppError("Nao ha jogadores ativos para trocar.")

            player_options = []
            player_map: dict[str, int] = {}
            for player in players:
                team_assignment = host.db.get_team_player_by_player(int(player["id"]))
                team_name = team_assignment.get("team_name", "Sem equipe") if team_assignment else "Sem equipe"
                option = f"{player['id']} - {player_pairing_name(player)} ({player['rating']}) - {team_name}"
                player_options.append(option)
                player_map[option] = int(player["id"])

            dialog = Dialog(self, "Trocar jogador por equipes", size=(520, 340), resizable=False)
            pilha = FormStack(dialog)
            pilha.section(
                f"Match {board.get('team_match_id', '')} - Tab. {board['board_number']}: "
                f"{board.get('white_display_name', '')} x {board.get('black_display_name', '')}"
            )
            slot_option = pilha.select("Lado a trocar", ["Brancas", "Pretas"])
            player_option = pilha.select("Jogador da mesma equipe", player_options)

            def apply_swap() -> None:
                try:
                    color = "white" if slot_option.get() == "Brancas" else "black"
                    replacement_id = player_map[player_option.get()]
                    host.pairing_service.adjust_team_board_player(
                        host.current_tournament_id,
                        host.current_round_id,
                        int(board["id"]),
                        color,
                        replacement_id,
                    )
                    dialog.close()
                    host._load_selected_round_pairings()
                except Exception as exc:
                    host._show_error(exc)

            actions_bar(dialog, primary=("Aplicar", apply_swap), close_text="Cancelar")
        except Exception as exc:
            host._show_error(exc)
