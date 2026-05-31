
from __future__ import annotations
import io
from typing import Any
import chess
import chess.pgn

from src.services.constants import AppError

PIECE_VALUES_CP = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

class ChessValidationService:
    @staticmethod
    def validate_fen(fen: str) -> dict[str, Any]:
        fen = (fen or '').strip()
        if not fen:
            raise AppError('Informe uma FEN.')

        try:
            board = chess.Board(fen)
        except ValueError as exc:
            raise AppError('FEN mal formatada.') from exc

        status_code = int(board.status())
        if not board.is_valid():
            raise AppError(f'FEN inválida ou posição ilegal. Status: {status_code}')

        white_material = 0
        black_material = 0
        for piece in board.piece_map().values():
            value = PIECE_VALUES_CP[piece.piece_type]
            if piece.color == chess.WHITE:
                white_material += value
            else:
                black_material += value

        return {
            'valid': True,
            'fen': fen,
            'normalized_fen': board.fen(),
            'side_to_move': 'white' if board.turn == chess.WHITE else 'black',
            'legal_moves_count': sum(1 for _ in board.legal_moves),
            'material_balance_cp': white_material - black_material,
            'is_check': board.is_check(),
            'is_checkmate': board.is_checkmate(),
            'is_stalemate': board.is_stalemate(),
            'status_code': status_code,
            'message': 'FEN válida.',
        }

    @staticmethod
    def parse_pgn(pgn_text: str, strict: bool = True) -> dict[str, Any]:
        pgn_text = (pgn_text or '').strip()
        if not pgn_text:
            raise AppError('Informe um PGN.')

        handle = io.StringIO(pgn_text)
        games: list[dict[str, Any]] = []
        index = 0

        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break

            index += 1
            errors = [str(error) for error in getattr(game, 'errors', [])]
            if strict and errors:
                raise AppError(f'PGN contém erros no jogo {index}: {errors[0]}')

            board = game.board()
            moves = []
            positions = [board.fen()]

            for move_number, move in enumerate(game.mainline_moves(), start=1):
                san = board.san(move)
                uci = move.uci()
                board.push(move)
                moves.append({
                    'ply': move_number,
                    'san': san,
                    'uci': uci,
                    'fen_after': board.fen(),
                })
                positions.append(board.fen())

            games.append({
                'headers': dict(game.headers),
                'moves': moves,
                'initial_fen': game.board().fen(),
                'final_fen': board.fen(),
                'ply_count': len(moves),
                'result': game.headers.get('Result', '*'),
                'errors': errors,
                'parse_status': 'warning' if errors else 'valid',
            })

        if not games:
            raise AppError('PGN vazio ou mal formatado.')

        return {
            'valid': all(not game['errors'] for game in games),
            'game_count': len(games),
            'games': games,
        }
