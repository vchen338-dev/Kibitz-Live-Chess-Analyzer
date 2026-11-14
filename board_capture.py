import cv2
import numpy as np
from PySide6.QtCore import Qt, QEventLoop, QRect, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget


def qimage_to_bgr(qimg):
    qimg = qimg.convertToFormat(QImage.Format.Format_RGB888)
    w, h, bpl = qimg.width(), qimg.height(), qimg.bytesPerLine()
    arr = np.frombuffer(qimg.constBits(), np.uint8).reshape(h, bpl)[:, : w * 3]
    arr = arr.reshape(h, w, 3)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)  # returns a fresh copy


class RegionSelector(QWidget):
    finished = Signal()

    CONFIRM_KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)

    def __init__(self, screen, pixmap):
        super().__init__()
        self.pixmap = pixmap
        self.dpr = pixmap.devicePixelRatio()
        self.start = None
        self.current = None
        self.selection = None   # QRect (logical coords) of the current drag
        self.result = None      # QRect once confirmed, None if cancelled
        self._done = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.CursorShape.CrossCursor)

    # ---- focus: make sure Enter / Esc actually reach this window ---------- #
    def showEvent(self, e):
        super().showEvent(e)
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self.grabKeyboard()

    def _finish(self, confirmed):
        if self._done:
            return
        self._done = True
        self.result = self.selection if confirmed else None
        self.releaseKeyboard()
        self.finished.emit()

    # ---- painting --------------------------------------------------------- #
    def _square(self):
        if self.start is None or self.current is None:
            return None
        rect = QRect(self.start, self.current).normalized()
        side = min(rect.width(), rect.height())      # chessboards are square
        return QRect(rect.x(), rect.y(), side, side)

    def paintEvent(self, _):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self.pixmap)
        p.fillRect(self.rect(), QColor(0, 0, 0, 120))

        sel = self.selection
        if sel and sel.width() > 0:
            src = QRect(int(sel.x() * self.dpr), int(sel.y() * self.dpr),
                        int(sel.width() * self.dpr), int(sel.height() * self.dpr))
            p.drawPixmap(sel, self.pixmap, src)
            p.setPen(QPen(QColor("#818cf8"), 2))
            p.drawRect(sel)

        p.setPen(QColor("white"))
        if sel and sel.width() >= 40:
            p.drawText(20, 30, "Press ENTER to save this region   |   drag again to redo   |   Esc = cancel")
        else:
            p.drawText(20, 30, "Drag over the chessboard (only the 8x8 squares), then press ENTER   |   Esc = cancel")

    # ---- mouse ------------------------------------------------------------ #
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self.start = e.position().toPoint()
            self.current = self.start
            self.selection = None
            self.update()

    def mouseMoveEvent(self, e):
        if self.start is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.current = e.position().toPoint()
            self.selection = self._square()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.start is not None:
            self.current = e.position().toPoint()
            self.selection = self._square()
            self.update()

    def mouseDoubleClickEvent(self, e):
        if self.selection is not None and self.selection.width() >= 40:
            self._finish(True)

    # ---- keyboard --------------------------------------------------------- #
    def keyPressEvent(self, e):
        if e.key() in self.CONFIRM_KEYS:
            if self.selection is not None and self.selection.width() >= 40:
                self._finish(True)
            return
        if e.key() == Qt.Key.Key_Escape:
            self._finish(False)
            return
        super().keyPressEvent(e)

    def closeEvent(self, e):
        self.releaseKeyboard()
        super().closeEvent(e)


class BoardCapture:
    def __init__(self):
        self.screen = None
        self.rect = None   # logical (device-independent) coordinates on self.screen

    @staticmethod
    def _wait(ms):
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def select_board_region_initial(self):
        # Give the caller time to hide its own windows so they aren't in the shot.
        self._wait(300)

        screen = QGuiApplication.primaryScreen()
        pixmap = screen.grabWindow(0)

        selector = RegionSelector(screen, pixmap)
        loop = QEventLoop()
        selector.finished.connect(loop.quit)
        selector.showFullScreen()
        loop.exec()

        rect = selector.result
        selector.close()
        selector.deleteLater()

        if rect is None:
            return None

        self.screen = screen
        self.rect = rect
        frame = self.capture_live_frame()
        if frame is None:
            return None
        return {"image": frame, "region": (rect.x(), rect.y(), rect.width(), rect.height())}

    def capture_live_frame(self):
        if self.screen is None or self.rect is None:
            return None
        pixmap = self.screen.grabWindow(0)
        dpr = pixmap.devicePixelRatio()
        r = self.rect
        crop = pixmap.toImage().copy(
            QRect(int(r.x() * dpr), int(r.y() * dpr), int(r.width() * dpr), int(r.height() * dpr))
        )
        if crop.isNull():
            return None
        return qimage_to_bgr(crop)