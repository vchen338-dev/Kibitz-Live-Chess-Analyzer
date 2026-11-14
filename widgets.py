import math

import cv2
import numpy as np
from PySide6.QtCore import Qt, QByteArray, QRect, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from theme import ACCENT, MONO, MUTED, PANEL, RULE


def label(text, name=None):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    return widget


def section(text):
    return label(text.upper(), "Section")


def rule():
    line = QFrame()
    line.setObjectName("Rule")
    line.setFixedHeight(1)
    return line


def setting_row(text, widget):
    row = QHBoxLayout()
    row.addWidget(label(text, "Muted"))
    row.addStretch()
    row.addWidget(widget)
    return row


def to_pixmap(bgr):
    rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    h, w, c = rgb.shape
    return QPixmap.fromImage(QImage(rgb.data, w, h, c * w, QImage.Format.Format_RGB888).copy())


class BoardView(QWidget):
    BAR_W = 12
    GAP = 14

    def __init__(self):
        super().__init__()
        self.renderer = QSvgRenderer()
        self.eval_pawns = 0.0
        self.flipped = False
        self.setMinimumSize(420, 420)

    def set_svg(self, svg_text):
        self.renderer.load(QByteArray(svg_text.encode("utf-8")))
        self.update()

    def set_eval(self, pawns, flipped):
        self.eval_pawns = max(-12.0, min(12.0, pawns))
        self.flipped = flipped
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = max(0, min(self.width() - self.BAR_W - self.GAP, self.height()))
        total = self.BAR_W + self.GAP + side
        x0 = (self.width() - total) // 2
        y0 = (self.height() - side) // 2

        # white share grows from White's side of the board
        share = 1.0 / (1.0 + math.exp(-self.eval_pawns / 2.2))
        white_h = int(round(side * share))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2a2c31"))
        p.drawRoundedRect(QRect(x0, y0, self.BAR_W, side), 2, 2)
        p.setBrush(QColor("#e7e6e1"))
        if self.flipped:
            p.drawRoundedRect(QRect(x0, y0, self.BAR_W, white_h), 2, 2)
        else:
            p.drawRoundedRect(QRect(x0, y0 + side - white_h, self.BAR_W, white_h), 2, 2)
        p.setBrush(QColor(ACCENT))
        p.drawRect(QRect(x0 - 2, y0 + side // 2, self.BAR_W + 4, 1))

        self.renderer.render(p, QRectF(x0 + self.BAR_W + self.GAP, y0, side, side))


class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Overlay")
        self.drag = None
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setFixedSize(190, 70)
        self.setStyleSheet(f"""
            QWidget#Overlay {{
                background-color: {PANEL};
                border: 1px solid {RULE};
                border-radius: 6px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(0)
        self.move_label = label("--")
        self.move_label.setStyleSheet(
            f"font-family: {MONO}; font-size: 17pt; font-weight: 600; color: {ACCENT};")
        self.eval_label = label("Waiting")
        self.eval_label.setStyleSheet(f"font-family: {MONO}; font-size: 8pt; color: {MUTED};")
        layout.addWidget(self.move_label)
        layout.addWidget(self.eval_label)

    def show_result(self, move, evaluation):
        self.move_label.setText(move)
        self.eval_label.setText(evaluation)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton and self.drag is not None:
            self.move(e.globalPosition().toPoint() - self.drag)