import threading
from pathlib import Path

import chess
import chess.engine


class StockfishEngine:
    def __init__(self, engine_path=None, threads=2, hash_mb=128):
        folder = Path(__file__).parent / "engine"
        path = Path(engine_path) if engine_path else folder / "stockfish-windows-x86-64-universal.exe"

        if not path.exists():
            matches = sorted(folder.glob("stockfish*")) if folder.exists() else []
            if not matches:
                raise FileNotFoundError(f"Stockfish executable not found in: {folder}")
            path = matches[0]

        self.engine = chess.engine.SimpleEngine.popen_uci(str(path))
        try:
            self.engine.configure({"Threads": threads, "Hash": hash_mb})
        except chess.engine.EngineError:
            pass
        self.lock = threading.Lock()

    def analyze_position(self, fen=None, depth=15, multipv=3, time_limit=1.0):
        board = chess.Board(fen) if fen else chess.Board()
        if not board.is_valid():
            raise ValueError("Invalid chess position.")
        if board.is_game_over():
            return []

        multipv = max(1, min(multipv, board.legal_moves.count()))

        with self.lock:
            if self.engine is None:
                return []
            infos = self.engine.analyse(
                board,
                chess.engine.Limit(depth=depth, time=time_limit),
                multipv=multipv,
            )

        if isinstance(infos, dict):
            infos = [infos]

        results = []
        for rank, info in enumerate(infos, start=1):
            pv = info.get("pv", [])
            if not pv:
                continue

            pov = info["score"].white()
            eval_text = f"#{pov.mate()}" if pov.is_mate() else f"{pov.score() / 100:+.2f}"

            replay = board.copy(stack=False)
            san_moves = []
            for move in pv:
                san_moves.append(replay.san(move))
                replay.push(move)

            results.append({
                "rank": rank,
                "best_move": san_moves[0],            # SAN, for display
                "move_uci": pv[0].uci(),              # UCI, for arrows
                "evaluation": pov.score(mate_score=100000) / 100,
                "eval_text": eval_text,               # White's point of view
                "depth": info.get("depth", depth),
                "principal_variation": " ".join(san_moves),
            })
        return results

    def close(self):
        with self.lock:
            if self.engine is not None:
                try:
                    self.engine.quit()
                except Exception:
                    pass
                self.engine = None