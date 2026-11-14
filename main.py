import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import sys

import chess
import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QLabel, QVBoxLayout, QWidget,
)

from ai_model import BoardReader, grid_to_board
from board_capture import BoardCapture
from detector import MIN_CONFIDENCE, RESYNC_FRAMES, find_moves, resync_board
from engine import StockfishEngine
from render import build_board_svg, lines_html
from theme import STYLE
from widgets import BoardView, OverlayWindow, label, rule, section, setting_row, to_pixmap
from workers import AnalysisWorker, TrainWorker

APP_NAME = "Kibitz"
APP_VERSION = "1.0.1"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  {APP_VERSION}")
        self.resize(1180, 760)
        self.setMinimumSize(980, 640)

        self.board = chess.Board()
        self.board_capture = BoardCapture()
        self.reader = BoardReader()
        self.grid_roi = None
        self.is_live = False

        self.candidate, self.candidate_count = None, 0
        self.last_board_img = None
        self.results, self.results_fen = [], None
        self.worker, self.worker_fen = None, None
        self.train_worker = None

        self.stockfish = None
        try:
            self.stockfish = StockfishEngine()
        except Exception as error:
            QMessageBox.warning(self, "Stockfish", f"Engine could not start:\n{error}")

        self.overlay = OverlayWindow()
        self.overlay.move(80, 80)

        self.timer = QTimer(self)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.live_tick)

        self.build_ui()
        self.refresh_model_label()
        self.refresh_board()

    # UI 
    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(28)
        root.addLayout(self.build_left(), stretch=1)
        root.addWidget(self.build_side())

    def build_left(self):
        left = QVBoxLayout()
        left.setSpacing(14)

        header = QHBoxLayout()
        header.setAlignment(Qt.AlignmentFlag.AlignBottom)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(label(APP_NAME, "Title"))
        title_row.addWidget(label(f"v{APP_VERSION}", "Version"))
        title_row.addStretch()
        header.addLayout(title_row, stretch=1)

        eval_box = QVBoxLayout()
        eval_box.setSpacing(0)
        self.eval_label = label("+0.00", "Eval")
        self.eval_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.turn_label = label("White to move", "Turn")
        self.turn_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        eval_box.addWidget(self.eval_label)
        eval_box.addWidget(self.turn_label)
        header.addLayout(eval_box)
        left.addLayout(header)

        self.board_view = BoardView()
        left.addWidget(self.board_view, stretch=1)

        lines_panel = QFrame()
        lines_panel.setObjectName("Panel")
        pl = QVBoxLayout(lines_panel)
        pl.setContentsMargins(16, 12, 16, 12)
        pl.setSpacing(8)
        pl.addWidget(section("Engine lines"))
        self.lines_label = QLabel("Start monitoring to see suggestions.")
        self.lines_label.setObjectName("Muted")
        self.lines_label.setTextFormat(Qt.TextFormat.RichText)
        self.lines_label.setWordWrap(True)
        self.lines_label.setMinimumHeight(70)
        self.lines_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        pl.addWidget(self.lines_label)
        left.addWidget(lines_panel)
        return left

    def build_side(self):
        side = QVBoxLayout()
        side.setSpacing(14)
        side_widget = QWidget()
        side_widget.setFixedWidth(320)
        side_widget.setLayout(side)

        # capture
        side.addWidget(section("Capture"))
        self.region_btn = QPushButton("Select board region")
        self.region_btn.setObjectName("Primary")
        self.region_btn.clicked.connect(self.setup_board_region)
        self.grid_btn = QPushButton("Adjust grid")
        self.grid_btn.setEnabled(False)
        self.grid_btn.clicked.connect(self.calibrate_grid)
        self.live_btn = QPushButton("Start monitoring")
        self.live_btn.setEnabled(False)
        self.live_btn.clicked.connect(self.toggle_live)
        side.addWidget(self.region_btn)
        pair = QHBoxLayout()
        pair.setSpacing(8)
        pair.addWidget(self.grid_btn)
        pair.addWidget(self.live_btn)
        side.addLayout(pair)

        self.preview = QLabel("No region selected")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedHeight(150)
        self.preview.setObjectName("Preview")
        side.addWidget(self.preview)

        # vision model
        side.addSpacing(4)
        side.addWidget(rule())
        side.addWidget(section("Vision model"))
        self.model_label = label("", "Muted")
        self.model_label.setWordWrap(True)
        side.addWidget(self.model_label)
        self.train_btn = QPushButton("Train on starting position")
        self.train_btn.setEnabled(False)
        self.train_btn.clicked.connect(self.start_training)
        side.addWidget(self.train_btn)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        side.addWidget(self.progress)
        self.progress_text = label("", "Status")
        self.progress_text.hide()
        side.addWidget(self.progress_text)

        # analysis settings
        side.addSpacing(4)
        side.addWidget(rule())
        side.addWidget(section("Analysis"))

        self.color_combo = QComboBox()
        self.color_combo.addItems(["White", "Black"])
        self.color_combo.currentIndexChanged.connect(self.refresh_board)
        side.addLayout(setting_row("Board orientation", self.color_combo))

        self.turn_combo = QComboBox()
        self.turn_combo.addItems(["Auto", "White", "Black"])
        self.turn_combo.currentIndexChanged.connect(self.turn_overridden)
        side.addLayout(setting_row("Side to move", self.turn_combo))

        self.depth_combo = QComboBox()
        self.depth_combo.addItems(["10", "15", "20", "25"])
        self.depth_combo.setCurrentText("15")
        side.addLayout(setting_row("Max depth", self.depth_combo))

        self.time_spin = QDoubleSpinBox()
        self.time_spin.setRange(0.2, 10.0)
        self.time_spin.setSingleStep(0.2)
        self.time_spin.setValue(1.0)
        self.time_spin.setSuffix(" s")
        side.addLayout(setting_row("Time per position", self.time_spin))

        # actions
        side.addSpacing(4)
        side.addWidget(rule())
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        undo = QPushButton("Undo")
        undo.clicked.connect(self.undo_move)
        reset = QPushButton("Reset")
        reset.clicked.connect(self.reset_board)
        self.overlay_btn = QPushButton("Overlay: off")
        self.overlay_btn.clicked.connect(self.toggle_overlay)
        for w in (undo, reset, self.overlay_btn):
            buttons.addWidget(w)
        side.addLayout(buttons)

        side.addStretch()
        self.status = label("Ready", "Status")
        self.status.setWordWrap(True)
        side.addWidget(self.status)
        return side_widget

    # board view 
    def flipped(self):
        return self.color_combo.currentText() == "Black"

    def refresh_board(self):
        fresh = self.results if self.results_fen == self.board.fen() else []
        self.board_view.set_svg(build_board_svg(self.board, self.flipped(), fresh))
        self.turn_label.setText(("White" if self.board.turn else "Black") + " to move")

    def refresh_lines(self):
        if not self.results:
            self.lines_label.setText("Waiting for analysis...")
            return
        self.lines_label.setText(lines_html(self.results))

    def refresh_model_label(self):
        if self.reader.ready:
            self.model_label.setText("Model loaded. Ready for live scanning.")
        else:
            self.model_label.setText(
                "No model yet. Put the board in the starting position, set the orientation, then train."
            )

    # capture 
    def setup_board_region(self):
        try:
            result = self.board_capture.select_board_region_initial()
            if not result:
                return
            self.grid_btn.setEnabled(True)
            self.calibrate_grid()
        except Exception as error:
            QMessageBox.critical(self, "Error", str(error))

    def calibrate_grid(self):
        frame = self.board_capture.capture_live_frame()
        if frame is None:
            QMessageBox.information(self, "Grid", "Could not capture the screen region.")
            return
        title = "Drag over 8x8 squares only, then press ENTER"
        x, y, w, h = cv2.selectROI(title, frame, showCrosshair=False)
        cv2.destroyAllWindows()
        if w < 80 or h < 80:
            return
        self.grid_roi = (int(x), int(y), int(w // 8 * 8), int(h // 8 * 8))
        self.last_board_img = None
        self.live_btn.setEnabled(True)
        self.train_btn.setEnabled(True)
        self.show_preview(self.crop_grid(frame))
        self.status.setText("Grid set. Train the model, then start monitoring.")

    def crop_grid(self, frame):
        if self.grid_roi is None:
            return frame
        x, y, w, h = self.grid_roi
        return frame[y:y + h, x:x + w]

    def show_preview(self, board_img):
        self.preview.setPixmap(to_pixmap(board_img).scaled(
            self.preview.width(), self.preview.height(),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    # training 
    def start_training(self):
        if self.train_worker is not None and self.train_worker.isRunning():
            return
        frame = self.board_capture.capture_live_frame()
        if frame is None:
            return
        answer = QMessageBox.question(
            self, "Train vision model",
            "The board on screen must be in the STARTING position, with no arrows drawn "
            "and the orientation setting matching the board.\n\nTrain now?")
        if answer != QMessageBox.StandardButton.Yes:
            return

        board_img = self.crop_grid(frame)
        self.train_btn.setEnabled(False)
        self.progress.show(); self.progress_text.show()
        self.progress.setValue(0)
        self.train_worker = TrainWorker(board_img.copy(), self.flipped())
        self.train_worker.progress.connect(self.on_train_progress)
        self.train_worker.done.connect(self.on_train_done)
        self.train_worker.failed.connect(self.on_train_failed)
        self.train_worker.start()

    def on_train_progress(self, value, text):
        self.progress.setValue(value)
        self.progress_text.setText(text)

    def on_train_done(self, message):
        self.reader.load()
        self.refresh_model_label()
        self.progress.hide(); self.progress_text.hide()
        self.train_btn.setEnabled(True)
        self.candidate, self.candidate_count = None, 0
        self.status.setText(message)

    def on_train_failed(self, message):
        self.progress.hide(); self.progress_text.hide()
        self.train_btn.setEnabled(True)
        QMessageBox.warning(self, "Training failed", message)

    # live loop 
    def toggle_live(self):
        self.is_live = not self.is_live
        if self.is_live:
            self.live_btn.setText("Stop")
            self.live_btn.setObjectName("Danger")
            self.timer.start()
            self.status.setText("Monitoring active...")
            self.request_analysis()
        else:
            self.live_btn.setText("Start monitoring")
            self.live_btn.setObjectName("")
            self.timer.stop()
            self.status.setText("Monitoring stopped.")
        self.live_btn.style().unpolish(self.live_btn)
        self.live_btn.style().polish(self.live_btn)

    def live_tick(self):
        frame = self.board_capture.capture_live_frame()
        if frame is None:
            return
        board_img = self.crop_grid(frame)
        if self.last_board_img is not None and board_img.shape == self.last_board_img.shape \
                and np.array_equal(board_img, self.last_board_img):
            return
        self.last_board_img = board_img.copy()
        self.show_preview(board_img)

        if not self.reader.ready:
            self.status.setText("Train the vision model first.")
            return

        grid, conf = self.reader.read(board_img)
        if float(conf.mean()) < MIN_CONFIDENCE:
            self.status.setText("Reading board... (low confidence)")
            return

        seen = grid_to_board(grid, self.flipped())
        placement = seen.board_fen()

        if placement == self.board.board_fen():
            self.candidate, self.candidate_count = None, 0
            return

        # 1. Direct legal move detection
        moves = find_moves(self.board, placement)
        if moves:
            for move in moves:
                self.board.push(move)
            self.status.setText("Move detected: " + " ".join(m.uci() for m in moves))
            self.candidate, self.candidate_count = None, 0
            self.board_changed()
            return

        # 2. Resync fallback: same unexplained placement on consecutive frames
        if placement == self.candidate:
            self.candidate_count += 1
        else:
            self.candidate, self.candidate_count = placement, 1
            return

        if self.candidate_count >= RESYNC_FRAMES:
            synced = resync_board(seen, self.turn_combo.currentText(), self.board.turn)
            if synced is not None:
                self.board = synced
                self.status.setText("Board synced directly to screen view.")
                self.candidate, self.candidate_count = None, 0
                self.board_changed()
            else:
                self.status.setText("Waiting for valid board state...")

    def board_changed(self):
        self.results, self.results_fen = [], None
        self.refresh_board()
        self.refresh_lines()
        self.request_analysis()

    # analysis 
    def request_analysis(self):
        if self.stockfish is None or (self.worker is not None and self.worker.isRunning()):
            return
        fen = self.board.fen()
        self.worker_fen = fen
        self.worker = AnalysisWorker(self.stockfish, fen, int(self.depth_combo.currentText()),
                                     3, self.time_spin.value())
        self.worker.result_ready.connect(self.on_results)
        self.worker.error_occurred.connect(lambda msg: self.status.setText("Engine: " + msg))
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_finished(self):
        if self.worker_fen != self.board.fen():       # board moved while analysing
            self.request_analysis()

    def on_results(self, fen, results):
        if fen != self.board.fen():                    # stale result, ignore
            return
        self.results, self.results_fen = results, fen
        self.refresh_board()
        self.refresh_lines()
        if results:
            best = results[0]
            self.eval_label.setText(best["eval_text"])
            self.board_view.set_eval(best["evaluation"], self.flipped())
            self.overlay.show_result(best["best_move"], best["eval_text"] + "  (White's view)")
        else:
            self.eval_label.setText("--")
            self.lines_label.setText("Game over.")

    # misc 
    def turn_overridden(self):
        mode = self.turn_combo.currentText()
        if mode == "Auto":
            return
        self.board.turn = (mode == "White")
        self.board_changed()

    def undo_move(self):
        if self.board.move_stack:
            self.board.pop()
            self.board_changed()
        else:
            self.status.setText("Nothing to undo.")

    def reset_board(self):
        self.board = chess.Board()
        self.candidate, self.candidate_count = None, 0
        self.eval_label.setText("+0.00")
        self.board_view.set_eval(0.0, self.flipped())
        self.board_changed()
        self.status.setText("Board reset to starting position.")

    def toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide(); self.overlay_btn.setText("Overlay: off")
        else:
            self.overlay.show(); self.overlay_btn.setText("Overlay: on")

    def closeEvent(self, event):
        self.timer.stop()
        for t in (self.worker, self.train_worker):
            if t is not None and t.isRunning():
                t.wait()
        if self.stockfish is not None:
            self.stockfish.close()
        self.overlay.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()