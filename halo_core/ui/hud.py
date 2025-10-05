# halo_core/ui/hud.py
from __future__ import annotations
import sys
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QGraphicsDropShadowEffect
)
from PySide6.QtCore import (
    Qt, QTimer, QEasingCurve, QPropertyAnimation, QPoint, Signal, Slot, QThread
)
from PySide6.QtGui import QFont, QColor


class HUD(QWidget):
    _instance: Optional["HUD"] = None

    # Thread-safe bridge: any thread can emit this; slot runs on UI thread.
    request_set_text = Signal(str, int)
    request_set_accent = Signal(str)

    def __init__(self):
        super().__init__()

        # ----- Window look/feel -----
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Base container
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            #container {
                /* subtle glass + border */
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(35,35,45,220),
                    stop:1 rgba(18,18,22,220));
                border: 1px solid rgba(255,255,255,40);
                border-radius: 16px;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 17px;
                font-weight: 500;
            }
        """)

        # Accent bar for state (color changes per phase)
        self.accent = QWidget(self.container)
        self.accent.setObjectName("accent")
        self.accent.setFixedHeight(4)
        self.accent.setStyleSheet("background-color: #4EA1FF; border-top-left-radius: 16px; border-top-right-radius: 16px;")

        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.container.setGraphicsEffect(shadow)

        # Layout
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(20, 18, 20, 18)
        self.layout.setSpacing(10)

        self.label = QLabel("Halo is idle")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        font = QFont()
        font.setFamily("Segoe UI Variable Display")
        font.setPointSize(14)
        font.setWeight(QFont.Medium)
        self.label.setFont(font)
        self.layout.addWidget(self.label)

        # Size and position
        self.setFixedWidth(900)  # wide enough for long replies
        self._adjust_height_to_label()
        self._snap_to_top_center()

        # Place accent to span top
        self._layout_accent()

        # Animations / timers
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(260)
        self._fade.setEasingCurve(QEasingCurve.InOutQuad)

        self._autohide_timer = QTimer(self)  # lives on UI thread
        self._autohide_timer.setSingleShot(True)
        self._autohide_timer.timeout.connect(self.fade_out)

        # Dragging
        self._drag_pos: Optional[QPoint] = None

        # Click-through off by default
        self._click_through = False

        # Connect thread-safe bridges
        self.request_set_text.connect(self._set_text_ui)
        self.request_set_accent.connect(self._set_accent_ui)

    # ---------- public API ----------
    @classmethod
    def get_instance(cls) -> "HUD":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_text(self, text: str, *, autohide_ms: int = 2500):
        """Safe from any thread."""
        if QThread.currentThread() == self.thread():
            self._set_text_ui(text, autohide_ms)
        else:
            self.request_set_text.emit(text, autohide_ms)

    def set_accent(self, color_hex: str):
        """Safe from any thread."""
        if QThread.currentThread() == self.thread():
            self._set_accent_ui(color_hex)
        else:
            self.request_set_accent.emit(color_hex)

    # State helpers (no emojis)
    def show_waiting(self):
        self.set_accent("#7A7F8B")
        self.set_text("Waiting for wake word...", autohide_ms=0)

    def show_listening(self):
        self.set_accent("#2DC4FF")
        self.set_text("Listening...", autohide_ms=0)

    def show_transcribing(self):
        self.set_accent("#F2C14E")
        self.set_text("Transcribing...")

    def show_thinking(self):
        self.set_accent("#B085F5")
        self.set_text("Thinking...")

    def show_user_text(self, t: str):
        self.set_accent("#4EA1FF")
        self.set_text(f"You said: {t}", autohide_ms=3500)

    def show_reply(self, t: str):
        self.set_accent("#57D38C")
        self.set_text(f"Halo: {t}", autohide_ms=4000)

    def show_idle(self):
        self.set_accent("#4EA1FF")
        self.set_text("Halo is now listening for your call...", autohide_ms=0)

    def set_click_through(self, enable: bool):
        self._click_through = enable
        if enable:
            self.setWindowFlag(Qt.WindowTransparentForInput, True)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        else:
            self.setWindowFlag(Qt.WindowTransparentForInput, False)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.show()

    # ---------- internal UI-thread slots ----------
    @Slot(str, int)
    def _set_text_ui(self, text: str, autohide_ms: int):
        self.label.setText(text)
        self._adjust_height_to_label()
        self.fade_in()
        if autohide_ms > 0:
            self._autohide_timer.start(autohide_ms)

    @Slot(str)
    def _set_accent_ui(self, color_hex: str):
        self.accent.setStyleSheet(
            f"background-color: {color_hex}; "
            "border-top-left-radius: 16px; border-top-right-radius: 16px;"
        )

    # ---------- effects ----------
    def fade_in(self):
        # Ensure visible before animating to avoid layered-window glitches
        if not self.isVisible():
            self.setWindowOpacity(0.0)
            self.show()

        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(1.0)
        self._fade.start()

    def fade_out(self):
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    # ---------- geometry ----------
    def _layout_accent(self):
        # Span the top edge of the container
        self.accent.setGeometry(0, 0, self.width(), self.accent.height())

    def _snap_to_top_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = int((screen.width() - self.width()) / 2)
        y = 30
        self.move(x, y)

    def _adjust_height_to_label(self):
        # Set wrapping width so QLabel computes a correct sizeHint
        margins = self.layout.contentsMargins()
        label_width = self.width() - (margins.left() + margins.right())
        self.label.setFixedWidth(max(200, label_width))

        # Compute height: label + margins + accent
        sh = self.label.sizeHint().height()
        content_height = sh + margins.top() + margins.bottom() + self.accent.height()
        min_height = 110
        self.setFixedHeight(max(content_height + 10, min_height))

        # Keep container matched and accent spanning
        self.container.setGeometry(0, 0, self.width(), self.height())
        self._layout_accent()

    # ---------- mouse / drag ----------
    def mousePressEvent(self, event):
        if self._click_through:
            return
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._click_through:
            return
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._click_through:
            return
        self._drag_pos = None


# Visual test
if __name__ == "__main__":
    app = QApplication(sys.argv)
    hud = HUD.get_instance()
    hud.show()
    hud.show_reply("This is a very long test line to verify wrapping, width, and dynamic height. Drag me around; I will not clip text.")
    sys.exit(app.exec())
