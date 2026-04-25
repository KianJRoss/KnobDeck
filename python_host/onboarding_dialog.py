"""
First-run onboarding tutorial for KnobDeck.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class OnboardingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to KnobDeck")
        icon_path = Path(__file__).parent / "assets" / "knobdeck_logo.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setMinimumSize(760, 460)
        self._index = 0

        self.setStyleSheet(
            """
            QDialog { background: #0f1520; color: #dbe5fb; }
            QLabel { color: #dbe5fb; font-size: 14px; }
            QLabel#title { color: #f2f7ff; font-size: 22px; font-weight: 700; }
            QPushButton {
                background: #253656;
                border: 1px solid #3d5a88;
                border-radius: 8px;
                color: #f0f5ff;
                padding: 8px 12px;
                min-width: 96px;
            }
            QPushButton:hover { background: #2d4570; }
            QPushButton:pressed { background: #22375a; }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)

        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)

        self._add_page(
            "Welcome",
            "This app turns your encoder keyboard into a radial control system.\n\n"
            "Core gestures:\n"
            "- Single click (idle): open main wheel\n"
            "- Double click (idle): toggle Macro Mode\n"
            "- Triple click (idle): open Settings\n"
            "- Hold + turn: quick volume\n"
            "- Double click in menus: go back one level",
        )
        self._add_page(
            "Lighting",
            "Lighting backend can be set to SignalRGB or Onboard/VIA.\n\n"
            "- SignalRGB mode shows lighting menus and effect browser.\n"
            "- VIA mode keeps lighting on firmware side and hides SignalRGB menu.\n"
            "- Switching mode is available in Settings > General.",
        )
        self._add_page(
            "Voicemeeter & Integrations",
            "Enable only what you use for best stability.\n\n"
            "- Configure Voicemeeter variant and outputs in Settings > Voicemeeter.\n"
            "- Disable integrations/plugins globally if you do not need them.\n"
            "- Plugin failures are auto-disabled and visible in Diagnostics.",
        )
        self._add_page(
            "Macros & Profiles",
            "Macro Studio supports visual editing plus JSON.\n\n"
            "- Build layers for 1..0 keys\n"
            "- Add conditions and repeats\n"
            "- Use profiles to auto-switch command sets by active app\n"
            "- Reopen this tutorial anytime from Settings",
        )

        nav = QHBoxLayout()
        self.lbl_step = QLabel("")
        self.lbl_step.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        nav.addWidget(self.lbl_step, 1)

        self.btn_prev = QPushButton("Back")
        self.btn_next = QPushButton("Next")
        self.btn_done = QPushButton("Finish")

        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.btn_done.clicked.connect(self.accept)

        nav.addWidget(self.btn_prev)
        nav.addWidget(self.btn_next)
        nav.addWidget(self.btn_done)
        root.addLayout(nav)

        self._sync()

    def _add_page(self, title: str, body: str):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        t = QLabel(title)
        t.setObjectName("title")
        t.setWordWrap(True)
        b = QLabel(body)
        b.setWordWrap(True)
        b.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(t)
        lay.addSpacing(10)
        lay.addWidget(b, 1)
        self.pages.addWidget(w)

    def _sync(self):
        count = self.pages.count()
        self.pages.setCurrentIndex(self._index)
        self.lbl_step.setText(f"Step {self._index + 1} of {count}")
        self.btn_prev.setEnabled(self._index > 0)
        self.btn_next.setVisible(self._index < count - 1)
        self.btn_done.setVisible(self._index == count - 1)

    def _prev(self):
        self._index = max(0, self._index - 1)
        self._sync()

    def _next(self):
        self._index = min(self.pages.count() - 1, self._index + 1)
        self._sync()

