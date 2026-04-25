"""
Bottom macro dock overlay (Stream Deck-style) for macro mode.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QLinearGradient
from PyQt6.QtWidgets import QApplication, QWidget


class MacroDockWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.layer_name = "Layer 1"
        self.layer_index = 0
        self.layer_count = 1
        self.selected_slot = 0
        self.slots: List[Dict] = []

        self.key_labels = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
        self.slot_count = 10
        self.card_w = 124
        self.card_h = 84
        self.spacing = 10
        self.margin = 18
        self.header_h = 30
        self.font_title = QFont("Segoe UI Variable Text Semibold", 10)
        self.font_icon = QFont("Segoe UI Emoji", 18)
        self.font_name = QFont("Segoe UI Variable Text", 9)
        self.font_key = QFont("Segoe UI Variable Text Semibold", 9)

        self._recalculate_geometry()

    def _recalculate_geometry(self):
        width = (self.card_w * self.slot_count) + (self.spacing * (self.slot_count - 1)) + (self.margin * 2)
        height = self.card_h + self.header_h + (self.margin * 2)
        self.setFixedSize(width, height)
        screen = QApplication.primaryScreen()
        if not screen:
            self.move(200, 900)
            return
        geo = screen.availableGeometry()
        x = geo.x() + max(0, (geo.width() - width) // 2)
        y = geo.y() + geo.height() - height - 8
        self.move(x, y)

    def update_data(self, data: Dict):
        self.layer_name = str(data.get("layer_name", "Layer"))
        self.layer_index = int(data.get("layer_index", 0))
        self.layer_count = int(data.get("layer_count", 1))
        self.selected_slot = int(data.get("selected_slot", 0))
        slots = data.get("slots", [])
        self.slots = list(slots) if isinstance(slots, list) else []
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # Dock backplate
        grad = QLinearGradient(0, 0, 0, self.height())
        top = QColor("#151d2b")
        top.setAlpha(232)
        bot = QColor("#0b1018")
        bot.setAlpha(226)
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, bot)
        p.setBrush(grad)
        p.setPen(QPen(QColor("#39414f"), 1.4))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)

        # Header
        p.setPen(QColor("#d7dceb"))
        p.setFont(self.font_title)
        header_text = f"Macro Mode  |  {self.layer_name} ({self.layer_index + 1}/{max(1, self.layer_count)})"
        p.drawText(QRectF(self.margin, 8, self.width() - (self.margin * 2), self.header_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, header_text)

        for i in range(self.slot_count):
            x = self.margin + (i * (self.card_w + self.spacing))
            y = self.margin + self.header_h
            card = QRectF(x, y, self.card_w, self.card_h)
            slot = self.slots[i] if i < len(self.slots) and isinstance(self.slots[i], dict) else {}

            active = (i == self.selected_slot)
            fill = QColor("#1e2430" if not active else "#264770")
            border = QColor("#465066" if not active else "#64a0ff")

            p.setBrush(fill)
            p.setPen(QPen(border, 1.6 if active else 1.2))
            p.drawRoundedRect(card, 10, 10)

            if active:
                glow = QColor("#6aa9ff")
                glow.setAlpha(50)
                p.setBrush(glow)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(card.adjusted(-2, -2, 2, 2), 12, 12)
                p.setPen(QPen(border, 1.6))

            key_label = self.key_labels[i]
            p.setPen(QColor("#ccd3e3"))
            p.setFont(self.font_key)
            p.drawText(QRectF(x + 8, y + 6, 20, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, key_label)

            icon = str(slot.get("icon", "⬡"))
            p.setFont(self.font_icon)
            p.drawText(QRectF(x, y + 16, self.card_w, 30), Qt.AlignmentFlag.AlignCenter, icon)

            name = str(slot.get("name", f"Macro {key_label}"))
            p.setFont(self.font_name)
            p.setPen(QColor("#e9edf7" if active else "#bdc6d8"))
            p.drawText(QRectF(x + 8, y + 50, self.card_w - 16, 26), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, name)


class MacroDockManager:
    def __init__(self):
        self.widget: Optional[MacroDockWidget] = None

    def start(self):
        if self.widget is None:
            self.widget = MacroDockWidget()

    def show(self, data: Dict):
        if not self.widget:
            self.start()
        if not self.widget:
            return

        def _show():
            self.widget.update_data(data)
            self.widget._recalculate_geometry()
            self.widget.show()
            self.widget.raise_()

        QTimer.singleShot(0, _show)

    def hide(self):
        if self.widget:
            QTimer.singleShot(0, self.widget.hide)
