"""
Modern Radial Wheel Overlay - PyQt6 Implementation

High-quality GPU-accelerated rendering with:
- Full antialiasing
- Smooth gradients
- Blur/glassmorphism effects
- Crisp text rendering
- Smooth animations
"""

import sys
import math
import json
import os
from typing import Dict, Optional, List
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QApplication, QWidget, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import (
    Qt, QTimer, QPointF, QRectF, QPropertyAnimation,
    QEasingCurve, pyqtProperty, QPoint
)
from PyQt6.QtGui import (
    QPainter, QPainterPath, QColor, QBrush, QPen,
    QRadialGradient, QLinearGradient, QFont, QFontDatabase,
    QCursor, QTextOption, QFontMetrics, QGuiApplication
)


# Cursor hiding is intentionally disabled:
# Windows ShowCursor uses a process-global counter and can desync when
# overlays/settings overlap, causing a stuck invisible cursor.


@dataclass
class ThemeColors:
    """Theme color definitions"""
    bg: str = "#1a1a1a"
    bg_alpha: float = 0.95
    segment_inactive: str = "#2a2a2a"
    segment_active: str = "#3d8aff"
    text_inactive: str = "#808080"
    text_active: str = "#ffffff"
    accent: str = "#3d8aff"
    accent_glow: str = "#5ba3ff"
    border: str = "#404040"
    progress_bg: str = "#2a2a2a"
    progress_fill: str = "#3d8aff"
    glow: str = "#3d8aff"


def load_theme(theme_name: str) -> ThemeColors:
    """Load theme from themes.json"""
    theme_file = os.path.join(os.path.dirname(__file__), 'themes.json')
    if os.path.exists(theme_file):
        try:
            with open(theme_file, 'r') as f:
                themes = json.load(f)
                if theme_name in themes:
                    data = themes[theme_name]
                    return ThemeColors(**{k: v for k, v in data.items() if hasattr(ThemeColors, k)})
        except Exception as e:
            print(f"Error loading theme: {e}")
    return ThemeColors()


def save_theme(theme_name: str, colors: ThemeColors):
    """Save theme to themes.json"""
    theme_file = os.path.join(os.path.dirname(__file__), 'themes.json')
    themes = {}
    if os.path.exists(theme_file):
        try:
            with open(theme_file, 'r') as f:
                themes = json.load(f)
        except:
            pass

    themes[theme_name] = {
        'bg': colors.bg,
        'bg_alpha': colors.bg_alpha,
        'segment_inactive': colors.segment_inactive,
        'segment_active': colors.segment_active,
        'text_inactive': colors.text_inactive,
        'text_active': colors.text_active,
        'accent': colors.accent,
        'accent_glow': colors.accent_glow,
        'border': colors.border,
        'progress_bg': colors.progress_bg,
        'progress_fill': colors.progress_fill,
        'glow': colors.glow,
    }

    try:
        with open(theme_file, 'w') as f:
            json.dump(themes, f, indent=4)
    except Exception as e:
        print(f"Error saving theme: {e}")


class RadialWheelWidget(QWidget):
    """Modern radial wheel menu widget"""

    def __init__(self, theme_name: str = 'DARK'):
        super().__init__()

        # Window setup - frameless, transparent, always on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Size
        self.wheel_size = 340
        self.setFixedSize(self.wheel_size, self.wheel_size)

        # Theme
        self.theme_name = theme_name
        self.theme = load_theme(theme_name)

        # Menu state
        self.options: List[str] = ['', '', '']
        self.icons: Dict[str, str] = {}
        self.active_index = 1
        self.title = ""
        self.subtitle = "Double-tap to exit"
        self.progress: Optional[float] = None
        self.pulsing = False

        # Geometry
        self.center = QPointF(self.wheel_size / 2, self.wheel_size / 2)
        self.outer_radius = 130
        self.inner_radius = 55
        self.hub_radius = 45

        # Segment angles (degrees): Left, Top, Right
        self.segments = [
            (135, 70),   # Left: start at 135°, span 70°
            (55, 70),    # Top: start at 55°, span 70°
            (-25, 70),   # Right: start at -25°, span 70°
        ]

        # Animation
        self._scale = 0.0
        self._pulse_phase = 0.0
        self._target_scale = 1.0

        self.animation = QPropertyAnimation(self, b"scale")
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.setDuration(200)

        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self._update_pulse)
        self.pulse_timer.setInterval(16)  # ~60fps

        self.follow_timer = QTimer()
        self.follow_timer.timeout.connect(self._follow_cursor)
        self.follow_timer.setInterval(12)

        # Fonts
        self.font_title = QFont("Bahnschrift SemiBold", 13)
        self.font_option = QFont("Segoe UI Variable Text", 10)
        self.font_option_active = QFont("Segoe UI Variable Text Semibold", 11)
        self.font_icon = QFont("Segoe UI Emoji", 13)
        self.font_small = QFont("Segoe UI Variable Small", 9)
        self._last_cursor_pos: Optional[QPoint] = None
        self.side_label_max_chars = 18
        self.cursor_hidden = False
        self.theme_override: Dict[str, str] = {}

    def _theme_value(self, key: str):
        """Read theme value with optional runtime override."""
        if key in self.theme_override:
            return self.theme_override[key]
        return getattr(self.theme, key)

    def _get_scale(self) -> float:
        return self._scale

    def _set_scale(self, value: float):
        self._scale = value
        self.update()

    scale = pyqtProperty(float, _get_scale, _set_scale)

    def set_theme(self, theme_name: str):
        """Change theme"""
        self.theme_name = theme_name
        self.theme = load_theme(theme_name)
        self.update()

    def update_theme_colors(self, settings: Dict[str, str]):
        """Update specific theme colors"""
        for key, value in settings.items():
            if hasattr(self.theme, key):
                setattr(self.theme, key, value)
        self.update()

    def save_current_theme(self, name: str):
        """Save current theme"""
        save_theme(name, self.theme)

    def _hide_cursor_for_menu(self):
        if not self.cursor_hidden:
            QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
            self.cursor_hidden = True

    def _restore_cursor(self):
        if not self.cursor_hidden:
            return
        # Balance any override cursor stack to avoid stuck hidden cursor.
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        self.cursor_hidden = False

    def ensure_cursor_visible(self):
        self._restore_cursor()

    def show_menu(
        self,
        display: Dict,
        progress: float = None,
        icons: Dict = None,
        hide_cursor: bool = True,
        theme_override: Dict[str, str] = None,
    ):
        """Show the wheel menu"""
        self.options = [
            display.get('left', ''),
            display.get('center', ''),
            display.get('right', '')
        ]
        self.title = display.get('title', '')
        self.subtitle = display.get('subtitle', 'Double-tap to exit')
        self.active_index = display.get('active_index', 1)
        self.pulsing = display.get('pulsing', False)
        self.progress = None if progress is None else max(0.0, min(1.0, progress))
        self.icons = icons or {}
        self.theme_override = dict(theme_override or {})

        # Position at cursor
        cursor_pos = QCursor.pos()
        self.move(
            cursor_pos.x() - self.wheel_size // 2,
            cursor_pos.y() - self.wheel_size // 2
        )

        # Animate in
        self._target_scale = 1.0
        self.animation.stop()
        self.animation.setStartValue(self._scale)
        self.animation.setEndValue(1.0)
        self.animation.start()

        self.follow_timer.start()
        if self.pulsing:
            self.pulse_timer.start()
        else:
            self.pulse_timer.stop()

        self.show()
        if hide_cursor:
            self._hide_cursor_for_menu()
        else:
            self._restore_cursor()

    def hide_menu(self):
        """Hide with animation"""
        self._target_scale = 0.0
        self.animation.stop()
        self.animation.setStartValue(self._scale)
        self.animation.setEndValue(0.0)
        self.animation.finished.connect(self._on_hide_complete)
        self.animation.start()

    def _on_hide_complete(self):
        self.animation.finished.disconnect(self._on_hide_complete)
        self.follow_timer.stop()
        self.pulse_timer.stop()
        self.hide()
        self._restore_cursor()

    def _follow_cursor(self):
        """Keep centered on cursor"""
        cursor_pos = QCursor.pos()
        if cursor_pos == self._last_cursor_pos:
            return
        self._last_cursor_pos = QPoint(cursor_pos)
        self.move(
            cursor_pos.x() - self.wheel_size // 2,
            cursor_pos.y() - self.wheel_size // 2
        )

    def _update_pulse(self):
        """Update pulse animation"""
        self._pulse_phase += 0.12
        self.update()

    def paintEvent(self, event):
        """Render the wheel"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if self._scale <= 0.01:
            return

        # Apply scale transform from center
        painter.translate(self.center)
        painter.scale(self._scale, self._scale)
        painter.translate(-self.center)

        # Draw layers
        self._draw_backplate(painter)
        self._draw_glow(painter)
        self._draw_segments(painter)
        self._draw_hub(painter)
        if self.progress is not None:
            self._draw_progress_hub(painter)
        self._draw_title(painter)
        if self.subtitle and self._scale > 0.5:
            self._draw_subtitle(painter)

    def _draw_backplate(self, painter: QPainter):
        """Draw the translucent body behind the wheel."""
        shell_color = QColor(self._theme_value('bg'))
        shell_color.setAlphaF(float(self._theme_value('bg_alpha')))
        shell_gradient = QRadialGradient(self.center, self.outer_radius + 26)
        shell_gradient.setColorAt(0.0, shell_color.lighter(125))
        shell_gradient.setColorAt(0.65, shell_color)
        shell_gradient.setColorAt(1.0, QColor(shell_color.red(), shell_color.green(), shell_color.blue(), 0))

        painter.setBrush(QBrush(shell_gradient))
        painter.setPen(QPen(QColor(self._theme_value('border')), 1.5))
        painter.drawEllipse(self.center, self.outer_radius + 18, self.outer_radius + 18)

    def _draw_glow(self, painter: QPainter):
        """Draw outer glow"""
        # Use glow color for the outer rings
        glow_color = QColor(self._theme_value('glow'))

        for i in range(3):
            glow_color.setAlpha(40 - i * 12)
            pen = QPen(glow_color, 3 - i * 0.5)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            radius = self.outer_radius + 8 + i * 6
            painter.drawEllipse(self.center, radius, radius)

    def _fit_label(self, font: QFont, text: str, width: int) -> str:
        """Elide long labels based on actual font metrics."""
        metrics = QFontMetrics(font)
        return metrics.elidedText(text, Qt.TextElideMode.ElideRight, width)

    def _fit_wrapped_label(
        self,
        base_font: QFont,
        text: str,
        width: int,
        height: int,
        min_point_size: int = 8,
    ) -> QFont:
        """Pick a font size that allows wrapped label text to fit inside a wedge."""
        clean = " ".join((text or "").split())
        if not clean:
            return QFont(base_font)

        option = QTextOption()
        option.setAlignment(Qt.AlignmentFlag.AlignCenter)
        option.setWrapMode(QTextOption.WrapMode.WordWrap)

        candidate = QFont(base_font)
        for size in range(candidate.pointSize(), min_point_size - 1, -1):
            candidate.setPointSize(size)
            metrics = QFontMetrics(candidate)
            bounds = metrics.boundingRect(
                0,
                0,
                max(1, width),
                max(1, height),
                int(Qt.TextFlag.TextWordWrap),
                clean,
            )
            if bounds.height() <= height and bounds.width() <= width:
                return QFont(candidate)

        candidate.setPointSize(min_point_size)
        return candidate

    def _wrap_label_lines(self, text: str, font: QFont, max_width: int, max_lines: int) -> str:
        """Wrap label text into a bounded number of lines for wedge rendering."""
        if not text:
            return ""

        # Improve break opportunities for common separator-heavy labels.
        clean = " ".join(
            text.replace("_", " ")
            .replace("/", " / ")
            .replace("-", "- ")
            .split()
        )
        words = clean.split(" ")
        metrics = QFontMetrics(font)

        lines: List[str] = []
        current = ""

        for word in words:
            if not word:
                continue
            candidate = word if not current else f"{current} {word}"
            if metrics.horizontalAdvance(candidate) <= max_width:
                current = candidate
                continue

            if current:
                lines.append(current)
            current = word

            if len(lines) >= max_lines:
                break

        if current and len(lines) < max_lines:
            lines.append(current)

        if len(lines) > max_lines:
            lines = lines[:max_lines]

        # If original text still doesn't fit, elide the final line.
        joined = " ".join(lines)
        if joined != clean and lines:
            lines[-1] = metrics.elidedText(lines[-1], Qt.TextElideMode.ElideRight, max_width)

        return "\n".join(lines)

    def _compact_side_label(self, text: str, max_chars: Optional[int] = None) -> str:
        """Shorten verbose labels for side wedges where space is tighter."""
        if not text:
            return ""
        if max_chars is None:
            max_chars = int(self.side_label_max_chars)

        compact = " ".join(text.split())
        substitutions = {
            "Context Commands": "Ctx Cmds",
            "Context": "Ctx",
            "Commands": "Cmds",
            "Control": "Ctrl",
            "Controls": "Ctrls",
            "Settings": "Settings",
            "Routing": "Route",
            "Microphone": "Mic",
            "Lighting": "Light",
            "Voicemeeter": "VM",
            "SignalRGB": "SRGB",
            "Previous": "Prev",
            "Volume": "Vol",
        }
        for old, new in substitutions.items():
            compact = compact.replace(old, new)

        # Drop low-signal filler words for side wedges.
        fillers = {"the", "and", "for", "to", "of", "in", "on"}
        parts = [p for p in compact.split() if p.lower() not in fillers]
        compact = " ".join(parts) if parts else compact

        # Keep side wedges concise and readable.
        if len(compact) > max_chars:
            compact = compact[: max_chars - 1].rstrip() + "…"
        return compact

    def set_side_label_max_chars(self, value: int):
        """Update side-wedge compaction threshold."""
        self.side_label_max_chars = max(10, min(28, int(value)))
        self.update()

    def _draw_segments(self, painter: QPainter):
        """Draw wheel segments"""
        for i, (start_angle, span) in enumerate(self.segments):
            if i >= len(self.options) or not self.options[i]:
                continue

            is_active = (i == self.active_index)

            # Determine colors
            if is_active and self.pulsing:
                pulse = (math.sin(self._pulse_phase) + 1) / 2
                bg_color = self._blend_colors(
                    self._theme_value('segment_active'),
                    self._theme_value('accent_glow'),
                    pulse * 0.4
                )
            elif is_active:
                bg_color = QColor(self._theme_value('segment_active'))
            else:
                bg_color = QColor(self._theme_value('segment_inactive'))

            border_color = QColor(self._theme_value('accent') if is_active else self._theme_value('border'))
            text_color = QColor(self._theme_value('text_active') if is_active else self._theme_value('text_inactive'))

            # Create arc path
            path = self._create_arc_path(start_angle, span)

            # Draw segment with gradient
            gradient = QRadialGradient(self.center, self.outer_radius)
            gradient.setColorAt(0.3, bg_color.lighter(115))
            gradient.setColorAt(1.0, bg_color)

            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(border_color, 2 if is_active else 1.5))
            painter.drawPath(path)

            # TEXT CLIPPING
            # Save state before setting clip path
            painter.save()
            painter.setClipPath(path)

            # Calculate text position
            mid_angle = math.radians(start_angle + span / 2)

            # Dynamic positioning based on text length
            label_full = self.options[i]
            is_long_text = len(label_full) > 12

            base_radius = (self.inner_radius + self.outer_radius) / 2
            text_radius = base_radius + (8 if is_long_text else 0)

            text_x = self.center.x() + text_radius * math.cos(mid_angle)
            text_y = self.center.y() - text_radius * math.sin(mid_angle)

            # Draw icon if present
            icon_key = ['left', 'center', 'right'][i]
            icon = self.icons.get(icon_key, '')

            if icon:
                painter.save()
                if is_active:
                     icon_cy = text_y + (-22 if not is_long_text else -18) + 12
                     painter.translate(text_x, icon_cy)
                     scale_factor = 1.08 + (0.04 * math.sin(self._pulse_phase))
                     painter.scale(scale_factor, scale_factor)
                     painter.translate(-text_x, -icon_cy)

                painter.setFont(self.font_icon)
                painter.setPen(text_color)
                # If text is moved out, move icon out a bit too but keep separation
                icon_y_offset = -22 if not is_long_text else -18
                icon_rect = QRectF(text_x - 20, text_y + icon_y_offset, 40, 24)
                painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, icon)

                painter.restore()

                text_y += 8 if not is_long_text else 12

            # Draw wrapped label instead of clipping/ellipsis.
            base_font = self.font_option_active if is_active else self.font_option
            if is_long_text:
                base_font = QFont(self.font_small)
                if is_active:
                    base_font.setWeight(QFont.Weight.Medium)

            is_center_wedge = (i == 1)
            side_wedge = not is_center_wedge

            # Side wedges are strongly curved; use a tighter single-line text lane.
            rect_width = 136 if is_center_wedge else 104
            rect_height = 56 if is_center_wedge else 24
            text_rect = QRectF(
                text_x - (rect_width / 2),
                text_y - (rect_height / 2),
                rect_width,
                rect_height,
            )

            font = self._fit_wrapped_label(
                base_font,
                label_full,
                int(rect_width - 8),
                int(rect_height - 4),
            )
            painter.setFont(font)
            painter.setPen(text_color)

            label_text = label_full
            if side_wedge:
                label_text = self._compact_side_label(label_full)
                # Move side text slightly inward where wedge width is more stable.
                text_rect.translate(0, 2)

            wrapped = self._wrap_label_lines(
                label_text,
                font,
                int(rect_width - 10),
                3 if is_center_wedge else 1,
            )

            flags = (
                Qt.AlignmentFlag.AlignHCenter
                | Qt.AlignmentFlag.AlignVCenter
                | Qt.TextFlag.TextWordWrap
            )
            painter.drawText(text_rect, flags, wrapped)

            # Restore painter state (removes clip)
            painter.restore()

    def _create_arc_path(self, start_angle: float, span: float) -> QPainterPath:
        """Create a donut arc segment path"""
        path = QPainterPath()

        # Convert to radians
        start_rad = math.radians(start_angle)
        end_rad = math.radians(start_angle + span)

        # Outer arc points
        outer_start = QPointF(
            self.center.x() + self.outer_radius * math.cos(start_rad),
            self.center.y() - self.outer_radius * math.sin(start_rad)
        )

        # Start at outer arc start
        path.moveTo(outer_start)

        # Draw outer arc
        outer_rect = QRectF(
            self.center.x() - self.outer_radius,
            self.center.y() - self.outer_radius,
            self.outer_radius * 2,
            self.outer_radius * 2
        )
        path.arcTo(outer_rect, start_angle, span)

        # Line to inner arc
        inner_end = QPointF(
            self.center.x() + self.inner_radius * math.cos(end_rad),
            self.center.y() - self.inner_radius * math.sin(end_rad)
        )
        path.lineTo(inner_end)

        # Draw inner arc (reverse direction)
        inner_rect = QRectF(
            self.center.x() - self.inner_radius,
            self.center.y() - self.inner_radius,
            self.inner_radius * 2,
            self.inner_radius * 2
        )
        path.arcTo(inner_rect, start_angle + span, -span)

        path.closeSubpath()
        return path

    def _draw_hub(self, painter: QPainter):
        """Draw center hub"""
        # Hub background with gradient
        hub_gradient = QRadialGradient(self.center, self.hub_radius)
        bg_color = QColor(self._theme_value('bg'))
        bg_color.setAlphaF(min(1.0, float(self._theme_value('bg_alpha')) + 0.03))
        hub_gradient.setColorAt(0, bg_color.lighter(135))
        hub_gradient.setColorAt(1, bg_color)

        painter.setBrush(QBrush(hub_gradient))
        painter.setPen(QPen(QColor(self._theme_value('border')), 2))
        painter.drawEllipse(self.center, self.hub_radius, self.hub_radius)

        # Center dot with glow
        dot_radius = 6
        accent = QColor(self._theme_value('accent'))
        accent_glow = QColor(self._theme_value('accent_glow'))

        # Glow
        glow_gradient = QRadialGradient(self.center, self.hub_radius*0.7)
        accent_glow.setAlpha(100)
        glow_gradient.setColorAt(0, accent_glow)
        glow_gradient.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.center, self.hub_radius*0.7, self.hub_radius*0.7)

        # Dot
        painter.setBrush(QBrush(accent))
        painter.setPen(QPen(accent_glow, 2))
        painter.drawEllipse(self.center, dot_radius, dot_radius)

    def _draw_progress_hub(self, painter: QPainter):
        """Draw progress ring in hub (around center dot)"""
        if self.progress is None:
            return

        # Tighter ring around the center dot (dot is r=6)
        ring_radius = 22
        ring_width = 6

        # Background ring
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(self._theme_value('progress_bg')), ring_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawEllipse(self.center, ring_radius, ring_radius)

        # Progress arc
        if self.progress > 0:
            # Determine color based on context (Title)
            title_lower = self.title.lower() if self.title else ""
            is_audio = any(x in title_lower for x in ['volume', 'gain', 'mic'])

            if is_audio:
                # Audio Gradient: Green -> Yellow -> Red
                # 0.0 -> 0.8 (0dB for VM) -> 1.0
                if self.progress < 0.8:
                    # Green to Yellow
                    ratio = self.progress / 0.8
                    r = int(255 * ratio)
                    g = 255
                    b = 0
                    progress_color = QColor(r, g, b)
                else:
                    # Yellow to Red
                    ratio = (self.progress - 0.8) / 0.2
                    r = 255
                    g = int(255 * (1 - ratio))
                    b = 0
                    progress_color = QColor(r, g, b)
            else:
                # Use accent color for non-audio progress rings
                progress_color = QColor(self._theme_value('accent'))

            painter.setPen(QPen(progress_color, ring_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))

            rect = QRectF(
                self.center.x() - ring_radius,
                self.center.y() - ring_radius,
                ring_radius * 2,
                ring_radius * 2
            )
            # Start from top (90°), go clockwise (negative span)
            span = -360 * self.progress
            painter.drawArc(rect, 90 * 16, int(span * 16))

    def _draw_volume_indicator(self, painter: QPainter):
        """Draw volume indicator arc around inner circle (cursor position)

        Fills clockwise from top (pi/2) based on progress value:
        - 0%: starts at top (90°)
        - 100%: full circle back to top
        """
        if self.progress is None:
            return

        # Volume indicator around inner circle where cursor is
        indicator_radius = self.inner_radius + 8  # Just outside inner circle
        indicator_width = 4

        # Background arc (full circle)
        bg_color = QColor(self._theme_value('progress_bg'))
        bg_color.setAlpha(80)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(bg_color, indicator_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawEllipse(self.center, indicator_radius, indicator_radius)

        # Progress arc - starts at top (90°) and fills clockwise
        if self.progress > 0:
            accent_color = QColor(self._theme_value('accent'))
            accent_color.setAlpha(220)
            painter.setPen(QPen(accent_color, indicator_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))

            rect = QRectF(
                self.center.x() - indicator_radius,
                self.center.y() - indicator_radius,
                indicator_radius * 2,
                indicator_radius * 2
            )

            # Start from top (90°), go clockwise (negative span)
            # Full circle = -360°
            span = -360 * self.progress
            painter.drawArc(rect, 90 * 16, int(span * 16))

    def _draw_title(self, painter: QPainter):
        """Draw title above wheel"""
        if not self.title:
            return

        painter.setFont(self.font_title)
        title_color = QColor(self._theme_value('text_active'))
        title_color.setAlpha(235)
        painter.setPen(title_color)

        title_rect = QRectF(32, self.center.y() - self.outer_radius - 46, self.wheel_size - 64, 28)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self._fit_label(self.font_title, self.title, int(title_rect.width())))

    def _draw_subtitle(self, painter: QPainter):
        """Draw subtitle in the bottom free space of the wheel"""
        if not self.subtitle:
            return

        font = QFont(self.font_small)
        font.setPointSize(9)
        painter.setFont(font)

        hint_color = QColor(self.theme.text_inactive)
        hint_color.setAlpha(int(255 * min(1.0, (self._scale - 0.5) * 2)))
        painter.setPen(hint_color)

        subtitle_rect = QRectF(
            self.center.x() - 78,
            self.center.y() + 72,
            156,
            42
        )

        # Word wrap if needed
        option = QTextOption()
        option.setAlignment(Qt.AlignmentFlag.AlignCenter)
        option.setWrapMode(QTextOption.WrapMode.WordWrap)

        painter.drawText(subtitle_rect, self.subtitle, option)

    def _blend_colors(self, color1: str, color2: str, factor: float) -> QColor:
        """Blend two hex colors"""
        try:
            c1 = QColor(color1)
            c2 = QColor(color2)

            r = int(c1.red() + (c2.red() - c1.red()) * factor)
            g = int(c1.green() + (c2.green() - c1.green()) * factor)
            b = int(c1.blue() + (c2.blue() - c1.blue()) * factor)

            return QColor(r, g, b)
        except:
            return QColor(color1)


class QtOverlayManager:
    """Thread-safe manager for Qt overlay"""

    def __init__(self, theme: str = 'DARK'):
        self.widget: Optional[RadialWheelWidget] = None
        self.status_widget: Optional['StatusPillWidget'] = None
        self.theme = theme
        self.hide_timer: Optional[QTimer] = None
        self._status_text: str = ""
        self._status_visible: bool = True
        self._status_update_seq: int = 0

    def start(self):
        """Initialize widget"""
        self.widget = RadialWheelWidget(self.theme)
        self.status_widget = StatusPillWidget()
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._do_hide)

    def set_theme(self, theme_name: str):
        """Change theme (thread-safe)"""
        if self.widget:
            QTimer.singleShot(0, lambda: self.widget.set_theme(theme_name))

    def update_theme_color(self, settings: Dict[str, str]):
        """Update theme colors (thread-safe)"""
        if self.widget:
            QTimer.singleShot(0, lambda: self.widget.update_theme_colors(settings))

    def set_side_label_max_chars(self, value: int):
        """Set side wedge label length preference (thread-safe)."""
        if self.widget:
            QTimer.singleShot(0, lambda: self.widget.set_side_label_max_chars(value))

    def save_theme(self, name: str):
        """Save theme to file (thread-safe)"""
        if self.widget:
            QTimer.singleShot(0, lambda: self.widget.save_current_theme(name))

    def show_menu(
        self,
        display: Dict,
        progress: float = None,
        icons: Dict = None,
        hide_cursor: bool = True,
        theme_override: Dict[str, str] = None,
    ):
        """Show menu (thread-safe)"""
        if not self.widget:
            return

        def _show():
            self.hide_timer.stop()
            self.widget.show_menu(display, progress, icons, hide_cursor=hide_cursor, theme_override=theme_override)

        QTimer.singleShot(0, _show)

    def hide_menu(self):
        """Hide menu (thread-safe)"""
        if self.widget:
            QTimer.singleShot(0, self._do_hide)

    def _do_hide(self):
        if self.widget and self.widget.isVisible():
            self.widget.hide_menu()
        elif self.widget:
            self.widget.ensure_cursor_visible()

    def ensure_cursor_visible(self):
        if self.widget:
            QTimer.singleShot(0, self.widget.ensure_cursor_visible)

    def show_notification(self, message: str, duration_ms: int = 1500):
        """Show notification (thread-safe)"""
        if not self.widget:
            return

        def _show_notif():
            self.hide_timer.stop()
            display = {
                'center': message,
                'left': '',
                'right': '',
                'subtitle': ''
            }
            self.widget.show_menu(display, hide_cursor=False)
            self.hide_timer.start(duration_ms)

        QTimer.singleShot(0, _show_notif)

    def set_status(self, text: str, visible: bool = True):
        """Show/hide persistent status pill."""
        if not self.status_widget:
            return
        self._status_text = str(text or "")
        self._status_visible = bool(visible)
        self._status_update_seq += 1
        seq = self._status_update_seq

        def _set():
            # Drop stale queued updates; latest call wins.
            if seq != self._status_update_seq:
                return
            if not visible:
                self.status_widget.set_text("")
                self.status_widget.hide()
                return
            self.status_widget.set_text(self._status_text)
            self.status_widget.show()

        QTimer.singleShot(0, _set)


class StatusPillWidget(QWidget):
    """Small always-on-top status pill (profile/mode indicator)."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._text = ""
        self._font = QFont("Segoe UI Variable Text", 9)
        self._padding_x = 10
        self._height = 24
        self._margin = 16
        self.setFixedHeight(self._height)

    def set_text(self, text: str):
        self._text = str(text or "").strip()
        metrics = QFontMetrics(self._font)
        text_w = metrics.horizontalAdvance(self._text) if self._text else 0
        width = max(140, min(520, text_w + (self._padding_x * 2)))
        self.resize(width, self._height)

        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - width - self._margin, geo.top() + self._margin)
        self.update()

    def paintEvent(self, event):
        if not self._text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bg = QColor(17, 22, 31, 214)
        border = QColor(69, 95, 138, 220)
        text = QColor(233, 241, 255, 240)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(bg)
        painter.setPen(QPen(border, 1.2))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setFont(self._font)
        painter.setPen(text)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)


# Wrapper class matching the Tkinter interface
class EnhancedUIManager:
    """Drop-in replacement for Tkinter EnhancedUIManager"""

    def __init__(self, theme: str = 'DARK'):
        self.qt_manager = QtOverlayManager(theme)
        self.menu = self  # Compatibility
        self.current_theme_name = theme  # For theme preset handler

    def start(self):
        self.qt_manager.start()

    def set_theme(self, theme_name: str):
        self.current_theme_name = theme_name
        self.qt_manager.set_theme(theme_name)

    def update_theme_color(self, settings: Dict[str, str]):
        self.qt_manager.update_theme_color(settings)

    def set_side_label_max_chars(self, value: int):
        self.qt_manager.set_side_label_max_chars(value)

    def save_theme(self, name: str):
        self.qt_manager.save_theme(name)

    def show_menu(
        self,
        display: Dict,
        progress: float = None,
        icons: Dict = None,
        hide_cursor: bool = True,
        theme_override: Dict[str, str] = None,
    ):
        self.qt_manager.show_menu(display, progress, icons, hide_cursor=hide_cursor, theme_override=theme_override)

    def hide_menu(self):
        self.qt_manager.hide_menu()

    def ensure_cursor_visible(self):
        self.qt_manager.ensure_cursor_visible()

    def show_notification(self, message: str, duration_ms: int = 1500):
        self.qt_manager.show_notification(message, duration_ms)

    def set_status(self, text: str, visible: bool = True):
        self.qt_manager.set_status(text, visible=visible)

    def quit(self):
        pass  # Qt app handles quit
