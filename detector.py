import chess

MIN_CONFIDENCE = 0.30   # mean CNN confidence below this = ignore the frame
RESYNC_FRAMES = 2       # identical unexplained frames before we trust the screen


def find_moves(board, target):
    """Legal move (or two, if a ply was missed) that produces the placement `target`."""
    probe = board.copy(stack=False)
    for first in list(probe.legal_moves):
        probe.push(first)
        if probe.board_fen() == target:
            return [first]
        for second in list(probe.legal_moves):
            probe.push(second)
            if probe.board_fen() == target:
                return [first, second]
            probe.pop()
        probe.pop()
    return None


def castling_string(b):
    def has(square, piece_type, color):
        p = b.piece_at(square)
        return p is not None and p.piece_type == piece_type and p.color == color
    s = ""
    if has(chess.E1, chess.KING, True) and has(chess.H1, chess.ROOK, True): s += "K"
    if has(chess.E1, chess.KING, True) and has(chess.A1, chess.ROOK, True): s += "Q"
    if has(chess.E8, chess.KING, False) and has(chess.H8, chess.ROOK, False): s += "k"
    if has(chess.E8, chess.KING, False) and has(chess.A8, chess.ROOK, False): s += "q"
    return s or "-"


def resync_board(seen, mode, current_turn):
    """Valid Board matching the screen, or None. `mode` is "Auto", "White" or "Black"."""
    if mode == "White":
        turns = [True]
    elif mode == "Black":
        turns = [False]
    else:
        turns = [current_turn, not current_turn]

    for turn in turns:
        fen = f"{seen.board_fen()} {'w' if turn else 'b'} {castling_string(seen)} - 0 1"
        try:
            candidate = chess.Board(fen)
        except ValueError:
            continue
        if candidate.is_valid():
            return candidate
    return None