# halo_core/ui/hud.py
from __future__ import annotations
import sys
from typing import Optional
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, QEasingCurve, QPropertyAnimation, QPoint
from PySide6.QtGui import QFont, QColor

class HUD(QWidget):
    _instance: Optional["HUD"] = None

    def __init__(self):
        super().__init__()

        # --- Window look/feel ---
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
                background-color: rgba(24, 24, 28, 190);
                border-radius: 14px;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 16px;
            }
        """)

        # Shadow for depth
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.container.setGraphicsEffect(shadow)

        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(16, 12, 16, 12)

        self.label = QLabel("✨ Halo is idle")
        self.label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(12)
        self.label.setFont(font)
        self.layout.addWidget(self.label)

        # Size & position
        self.resize(360, 90)
        self.container.resize(self.width(), self.height())
        self._snap_to_top_center()

        # --- Animation / timers ---
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(200)
        self._fade.setEasingCurve(QEasingCurve.InOutQuad)

        self._autohide_timer = QTimer(self)
        self._autohide_timer.setSingleShot(True)
        self._autohide_timer.timeout.connect(self.fade_out)

        # --- Dragging ---
        self._drag_pos: Optional[QPoint] = None

        # Click-through off by default (so you can drag). Toggle via set_click_through(True)
        self._click_through = False

    # ---------- public API ----------
    @classmethod
    def get_instance(cls) -> "HUD":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_text(self, text: str, *, autohide_ms: int = 2200):
        self.label.setText(text)
        self.container.resize(self.width(), self.height())
        self.fade_in()
        # Autohide unless we’re in a long state (listening, waiting)
        if autohide_ms > 0:
            self._autohide_timer.start(autohide_ms)

    def show_waiting(self):
        self.set_text("👂 Waiting for wake word...", autohide_ms=0)

    def show_listening(self):
        self.set_text("🎙️ Listening...", autohide_ms=0)

    def show_transcribing(self):
        self.set_text("🧠 Transcribing...")

    def show_thinking(self):
        self.set_text("🤔 Thinking...")

    def show_user_text(self, t: str):
        self.set_text(f"📝 You said: {t}", autohide_ms=3000)

    def show_reply(self, t: str):
        self.set_text(f"💬 Halo: {t}", autohide_ms=3200)

    def show_idle(self):
        self.set_text("🌟 Halo is now listening for your call...", autohide_ms=0)

    def set_click_through(self, enable: bool):
        # When enabled, HUD won’t catch mouse; you can click apps under it.
        self._click_through = enable
        if enable:
            # Qt6: WindowTransparentForInput makes entire window ignore input
            self.setWindowFlag(Qt.WindowTransparentForInput, True)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        else:
            self.setWindowFlag(Qt.WindowTransparentForInput, False)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.show()  # re-apply flags

    # ---------- effects ----------
    def fade_in(self):
        if self.windowOpacity() < 1.0:
            self._fade.stop()
            self._fade.setStartValue(self.windowOpacity())
            self._fade.setEndValue(1.0)
            self._fade.start()
        else:
            # Reset autohide if already visible
            pass
        self.show()

    def fade_out(self):
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    # ---------- positioning ----------
    def _snap_to_top_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = 30
        self.move(x, y)

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

# Allow running as a module for quick visual test:
if __name__ == "__main__":
    app = QApplication(sys.argv)
    hud = HUD.get_instance()
    hud.show()
    hud.set_text("✨ Halo is idle", autohide_ms=0)
    sys.exit(app.exec())
