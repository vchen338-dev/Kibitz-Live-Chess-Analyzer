from PySide6.QtCore import QThread, Signal

from ai_model import BoardReader, build_dataset, train_model, verify_reader


class AnalysisWorker(QThread):
    result_ready = Signal(str, list)
    error_occurred = Signal(str)

    def __init__(self, engine, fen, depth, multipv, seconds):
        super().__init__()
        self.engine, self.fen = engine, fen
        self.depth, self.multipv, self.seconds = depth, multipv, seconds

    def run(self):
        try:
            self.result_ready.emit(
                self.fen,
                self.engine.analyze_position(self.fen, self.depth, self.multipv, self.seconds),
            )
        except Exception as error:
            self.error_occurred.emit(str(error))


class TrainWorker(QThread):
    progress = Signal(int, str)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, board_img, flipped):
        super().__init__()
        self.board_img, self.flipped = board_img, flipped

    def run(self):
        try:
            self.progress.emit(3, "Generating training data...")
            x, y = build_dataset(self.board_img, self.flipped)

            def report(epoch, total, loss, acc):
                self.progress.emit(5 + int(90 * epoch / total),
                                   f"Epoch {epoch}/{total}  loss {loss:.3f}  val {acc * 100:.1f}%")

            train_model(x, y, progress=report)
            correct = verify_reader(BoardReader(), self.board_img, self.flipped)
            self.done.emit(f"Training finished. Starting position read correctly: {correct}/64 squares.")
        except Exception as error:
            self.failed.emit(str(error))