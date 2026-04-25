"""
Macro Studio dialog:
- Visual drag/drop macro builder
- Recording mode for key capture
- Code mode (full JSON editing)
"""

from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

import keyboard
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)


class PaletteList(QListWidget):
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)


class SequenceList(QListWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)


class MacroEditorDialog(QDialog):
    def __init__(self, config_path: Path, on_saved=None, parent=None):
        super().__init__(parent)
        self.config_path = Path(config_path)
        self.on_saved = on_saved
        self.setWindowTitle("Macro Studio")
        icon_path = Path(__file__).parent / "assets" / "knobdeck_logo.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon))
        self.setMinimumSize(1220, 760)
        self.setStyleSheet(
            """
            QDialog { background: #11161f; color: #dbe3f5; }
            QLabel { color: #c7d2ea; }
            QPlainTextEdit, QLineEdit, QListWidget {
                background: #171e2a;
                border: 1px solid #2d3a52;
                border-radius: 8px;
                color: #e8eefc;
                padding: 4px;
            }
            QPushButton {
                background: #243552;
                border: 1px solid #3c5a88;
                border-radius: 8px;
                color: #e9f1ff;
                padding: 6px 10px;
            }
            QPushButton:hover { background: #2d4470; }
            QPushButton:pressed { background: #20365a; }
            """
        )

        self.config: Dict[str, Any] = {"layers": []}
        self.current_layer_idx = 0
        self.current_slot_idx = 0
        self.record_hook = None
        self.record_started_ts = 0.0
        self.record_points: List[tuple[float, str]] = []
        self._ui_syncing = False

        self.templates = self._build_templates()
        self._build_ui()
        self._load_config()

    def _build_templates(self) -> List[Dict[str, Any]]:
        return [
            {"name": "Open OBS", "action": {"type": "shell", "command": "start \"\" \"C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe\""}},
            {"name": "OBS Toggle Record", "action": {"type": "hotkey", "keys": "ctrl+shift+r"}},
            {"name": "OBS Toggle Stream", "action": {"type": "hotkey", "keys": "ctrl+shift+s"}},
            {"name": "Discord Mute", "action": {"type": "hotkey", "keys": "ctrl+shift+m"}},
            {"name": "Discord Deafen", "action": {"type": "hotkey", "keys": "ctrl+shift+d"}},
            {"name": "Open Discord", "action": {"type": "url", "url": "discord://-/channels/@me"}},
            {"name": "Open Steam Library", "action": {"type": "url", "url": "steam://open/library"}},
            {"name": "Open Steam Friends", "action": {"type": "url", "url": "steam://open/friends"}},
            {"name": "Open SignalRGB", "action": {"type": "url", "url": "signalrgb://"}},
            {"name": "Run App (Shell)", "action": {"type": "shell", "command": "start \"\" \"C:\\Path\\To\\App.exe\""}},
            {"name": "Type Text", "action": {"type": "text", "text": "Hello world"}},
            {"name": "Hotkey", "action": {"type": "hotkey", "keys": "ctrl+alt+h"}},
            {"name": "Delay 100ms", "action": {"type": "delay", "ms": 100}},
            {"name": "AHK Inline", "action": {"type": "ahk", "script": "Send \"Hello from AHK\""}},
            {"name": "If Window: Discord", "action": {"type": "if_window", "process": "discord\\.exe", "then": [{"type": "hotkey", "keys": "ctrl+shift+m"}], "else": [{"type": "noop"}]}},
            {"name": "If Setting Enabled", "action": {"type": "if_setting", "key": "macro_mode_enabled", "value": True, "then": [{"type": "text", "text": "Enabled"}], "else": [{"type": "text", "text": "Disabled"}]}},
            {"name": "Repeat x3", "action": {"type": "repeat", "count": 3, "actions": [{"type": "hotkey", "keys": "tab"}, {"type": "delay", "ms": 120}]}},
            {"name": "Type Active App", "action": {"type": "text", "text": "App: {ACTIVE_EXE} | Title: {WINDOW_TITLE} | #{COUNTER:session}"}},
        ]

    def _build_ui(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        visual_tab = QWidget()
        visual_layout = QVBoxLayout(visual_tab)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        visual_layout.addWidget(splitter, 1)

        # Left: layers + slots
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Layers"))
        self.lst_layers = QListWidget()
        left_layout.addWidget(self.lst_layers, 1)
        row_layers = QHBoxLayout()
        self.btn_add_layer = QPushButton("Add Layer")
        self.btn_del_layer = QPushButton("Delete Layer")
        row_layers.addWidget(self.btn_add_layer)
        row_layers.addWidget(self.btn_del_layer)
        left_layout.addLayout(row_layers)

        left_layout.addWidget(QLabel("Slots (1..0)"))
        self.lst_slots = QListWidget()
        left_layout.addWidget(self.lst_slots, 2)
        splitter.addWidget(left)

        # Middle: sequence
        middle = QWidget()
        middle_layout = QVBoxLayout(middle)
        middle_layout.addWidget(QLabel("Macro Sequence (drag templates here)"))
        self.lst_steps = SequenceList()
        middle_layout.addWidget(self.lst_steps, 1)
        row_steps = QHBoxLayout()
        self.btn_step_remove = QPushButton("Remove Step")
        self.btn_step_up = QPushButton("Move Up")
        self.btn_step_down = QPushButton("Move Down")
        row_steps.addWidget(self.btn_step_remove)
        row_steps.addWidget(self.btn_step_up)
        row_steps.addWidget(self.btn_step_down)
        middle_layout.addLayout(row_steps)

        rec_row = QHBoxLayout()
        self.btn_rec_start = QPushButton("Start Recording")
        self.btn_rec_stop = QPushButton("Stop Recording")
        self.btn_rec_stop.setEnabled(False)
        rec_row.addWidget(self.btn_rec_start)
        rec_row.addWidget(self.btn_rec_stop)
        middle_layout.addLayout(rec_row)
        splitter.addWidget(middle)

        # Right: templates + slot metadata + step json
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Action Templates"))
        self.lst_templates = PaletteList()
        right_layout.addWidget(self.lst_templates, 1)
        self.btn_add_template = QPushButton("Add Template To Sequence")
        right_layout.addWidget(self.btn_add_template)

        right_layout.addWidget(QLabel("Selected Slot Name"))
        self.edit_slot_name = QLineEdit()
        right_layout.addWidget(self.edit_slot_name)
        right_layout.addWidget(QLabel("Selected Slot Icon"))
        self.edit_slot_icon = QLineEdit()
        right_layout.addWidget(self.edit_slot_icon)

        right_layout.addWidget(QLabel("Selected Step JSON"))
        self.edit_step_json = QPlainTextEdit()
        self.edit_step_json.setPlaceholderText('{"type":"hotkey","keys":"ctrl+shift+r"}')
        right_layout.addWidget(self.edit_step_json, 1)
        self.btn_apply_step_json = QPushButton("Apply Step JSON")
        right_layout.addWidget(self.btn_apply_step_json)

        splitter.addWidget(right)
        splitter.setSizes([260, 560, 360])

        visual_footer = QHBoxLayout()
        self.btn_save_slot = QPushButton("Save Slot")
        self.btn_open_config = QPushButton("Open JSON Path")
        visual_footer.addWidget(self.btn_save_slot)
        visual_footer.addWidget(self.btn_open_config)
        visual_footer.addStretch(1)
        visual_layout.addLayout(visual_footer)

        tabs.addTab(visual_tab, "Visual Builder")

        # Code mode
        code_tab = QWidget()
        code_layout = QVBoxLayout(code_tab)
        code_layout.addWidget(QLabel("Code Mode (full macro_layers.json)"))
        self.edit_json = QPlainTextEdit()
        code_layout.addWidget(self.edit_json, 1)
        code_row = QHBoxLayout()
        self.btn_validate_json = QPushButton("Validate")
        self.btn_apply_json = QPushButton("Apply JSON To Visual")
        code_row.addWidget(self.btn_validate_json)
        code_row.addWidget(self.btn_apply_json)
        code_row.addStretch(1)
        code_layout.addLayout(code_row)
        tabs.addTab(code_tab, "Code Mode")

        # Bottom buttons
        bottom = QHBoxLayout()
        self.btn_save_all = QPushButton("Save Macro Studio")
        self.btn_close = QPushButton("Close")
        bottom.addWidget(self.btn_save_all)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_close)
        root.addLayout(bottom)

        # signals
        self.lst_layers.currentRowChanged.connect(self._on_layer_changed)
        self.lst_slots.currentRowChanged.connect(self._on_slot_changed)
        self.lst_steps.currentRowChanged.connect(self._on_step_changed)
        self.btn_add_layer.clicked.connect(self._add_layer)
        self.btn_del_layer.clicked.connect(self._delete_layer)
        self.btn_add_template.clicked.connect(self._add_template_to_steps)
        self.btn_step_remove.clicked.connect(self._remove_step)
        self.btn_step_up.clicked.connect(lambda: self._move_step(-1))
        self.btn_step_down.clicked.connect(lambda: self._move_step(1))
        self.btn_apply_step_json.clicked.connect(self._apply_step_json)
        self.btn_rec_start.clicked.connect(self._start_recording)
        self.btn_rec_stop.clicked.connect(self._stop_recording)
        self.btn_save_slot.clicked.connect(self._save_current_slot)
        self.btn_open_config.clicked.connect(self._open_config_path)
        self.btn_validate_json.clicked.connect(self._validate_json)
        self.btn_apply_json.clicked.connect(self._apply_json_to_visual)
        self.btn_save_all.clicked.connect(self._save_all)
        self.btn_close.clicked.connect(self.reject)

        for template in self.templates:
            item = QListWidgetItem(template["name"])
            item.setData(Qt.ItemDataRole.UserRole, deepcopy(template["action"]))
            self.lst_templates.addItem(item)

    def _load_config(self):
        if self.config_path.exists():
            try:
                self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception:
                self.config = {"layers": []}
        if not isinstance(self.config.get("layers"), list) or not self.config["layers"]:
            self.config = {"layers": [{"name": "Layer 1", "slots": []}]}

        self.edit_json.setPlainText(json.dumps(self.config, indent=4))
        self._refresh_layers()

    def _refresh_layers(self):
        self._ui_syncing = True
        self.lst_layers.blockSignals(True)
        self.lst_layers.clear()
        for idx, layer in enumerate(self.config.get("layers", [])):
            self.lst_layers.addItem(f"{idx + 1}. {layer.get('name', f'Layer {idx+1}')}")
        self.lst_layers.blockSignals(False)
        if self.lst_layers.count() > 0:
            self.current_layer_idx = max(0, min(self.current_layer_idx, self.lst_layers.count() - 1))
            self.lst_layers.setCurrentRow(self.current_layer_idx)
        self._refresh_slots()
        self._ui_syncing = False

    def _ensure_slots(self, layer: Dict[str, Any]) -> List[Dict[str, Any]]:
        slots = layer.get("slots", [])
        if not isinstance(slots, list):
            slots = []
        while len(slots) < 10:
            slots.append({"name": f"Macro {len(slots) + 1}", "icon": "⬡", "action": {"type": "noop"}})
        layer["slots"] = slots[:10]
        return layer["slots"]

    def _refresh_slots(self):
        self._ui_syncing = True
        layers = self.config.get("layers", [])
        if not layers:
            self._ui_syncing = False
            return
        layer = layers[self.current_layer_idx]
        slots = self._ensure_slots(layer)
        labels = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
        self.lst_slots.blockSignals(True)
        self.lst_slots.clear()
        for i, slot in enumerate(slots):
            self.lst_slots.addItem(f"{labels[i]}  {slot.get('icon', '⬡')}  {slot.get('name', f'Macro {i+1}')}")
        self.lst_slots.blockSignals(False)
        self.current_slot_idx = max(0, min(self.current_slot_idx, 9))
        self.lst_slots.setCurrentRow(self.current_slot_idx)
        self._load_slot_editor()
        self._ui_syncing = False

    def _on_layer_changed(self, row: int):
        if self._ui_syncing:
            return
        if row < 0:
            return
        self._save_current_slot()
        self.current_layer_idx = row
        self.current_slot_idx = 0
        self._refresh_slots()

    def _on_slot_changed(self, row: int):
        if self._ui_syncing:
            return
        if row < 0:
            return
        self._save_current_slot()
        self.current_slot_idx = row
        self._load_slot_editor()

    def _load_slot_editor(self):
        slot = self._current_slot()
        if not slot:
            return
        self.edit_slot_name.setText(str(slot.get("name", "")))
        self.edit_slot_icon.setText(str(slot.get("icon", "")))

        action = slot.get("action", {"type": "noop"})
        if isinstance(action, dict) and action.get("type") == "sequence" and isinstance(action.get("steps"), list):
            steps = list(action.get("steps", []))
        else:
            steps = [action] if isinstance(action, dict) else [{"type": "noop"}]

        self.lst_steps.clear()
        for step in steps:
            item = QListWidgetItem(self._step_label(step))
            item.setData(Qt.ItemDataRole.UserRole, deepcopy(step))
            self.lst_steps.addItem(item)
        if self.lst_steps.count() > 0:
            self.lst_steps.setCurrentRow(0)
        else:
            self.edit_step_json.setPlainText("")

    def _step_label(self, step: Dict[str, Any]) -> str:
        t = str(step.get("type", "noop"))
        if t == "hotkey":
            return f"Hotkey: {step.get('keys', '')}"
        if t == "shell":
            return f"Shell: {step.get('command', '')}"
        if t == "url":
            return f"URL: {step.get('url', '')}"
        if t == "text":
            return f"Text: {step.get('text', '')[:42]}"
        if t == "delay":
            return f"Delay: {step.get('ms', 0)}ms"
        if t == "ahk":
            return f"AHK: {str(step.get('script', ''))[:42]}"
        if t == "media":
            return f"Media: {step.get('command', '')}"
        if t == "if_window":
            return f"If Window: {step.get('process', '') or step.get('title_regex', '')}"
        if t == "if_setting":
            return f"If Setting: {step.get('key', '')} == {step.get('value', '')}"
        if t == "repeat":
            return f"Repeat: {step.get('count', 0)}x"
        return json.dumps(step)

    def _on_step_changed(self, row: int):
        if row < 0 or row >= self.lst_steps.count():
            self.edit_step_json.setPlainText("")
            return
        item = self.lst_steps.item(row)
        step = item.data(Qt.ItemDataRole.UserRole)
        self.edit_step_json.setPlainText(json.dumps(step, indent=4))

    def _add_layer(self):
        layers = self.config.setdefault("layers", [])
        layers.append({"name": f"Layer {len(layers) + 1}", "slots": []})
        self.current_layer_idx = len(layers) - 1
        self._refresh_layers()

    def _delete_layer(self):
        layers = self.config.get("layers", [])
        if len(layers) <= 1:
            QMessageBox.warning(self, "Macro Studio", "At least one layer is required.")
            return
        del layers[self.current_layer_idx]
        self.current_layer_idx = max(0, self.current_layer_idx - 1)
        self._refresh_layers()

    def _add_template_to_steps(self):
        item = self.lst_templates.currentItem()
        if not item:
            return
        action = item.data(Qt.ItemDataRole.UserRole)
        step = deepcopy(action)
        step_item = QListWidgetItem(self._step_label(step))
        step_item.setData(Qt.ItemDataRole.UserRole, step)
        self.lst_steps.addItem(step_item)
        self.lst_steps.setCurrentItem(step_item)

    def _remove_step(self):
        row = self.lst_steps.currentRow()
        if row >= 0:
            self.lst_steps.takeItem(row)

    def _move_step(self, delta: int):
        row = self.lst_steps.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= self.lst_steps.count():
            return
        item = self.lst_steps.takeItem(row)
        self.lst_steps.insertItem(new_row, item)
        self.lst_steps.setCurrentRow(new_row)

    def _apply_step_json(self):
        row = self.lst_steps.currentRow()
        if row < 0:
            return
        try:
            step = json.loads(self.edit_step_json.toPlainText().strip())
            if not isinstance(step, dict):
                raise ValueError("Step must be a JSON object")
        except Exception as e:
            QMessageBox.warning(self, "Invalid Step JSON", str(e))
            return
        item = self.lst_steps.item(row)
        item.setData(Qt.ItemDataRole.UserRole, step)
        item.setText(self._step_label(step))

    def _start_recording(self):
        if self.record_hook is not None:
            return
        self.record_points = []
        self.record_started_ts = time.time()
        self.btn_rec_start.setEnabled(False)
        self.btn_rec_stop.setEnabled(True)

        def _on_event(event):
            if event.event_type != "down":
                return
            ts = time.time()
            key_name = str(event.name)
            if not key_name:
                return
            if self.record_points and self.record_points[-1][1] == key_name and (ts - self.record_points[-1][0]) < 0.05:
                return
            self.record_points.append((ts, key_name))

        self.record_hook = keyboard.hook(_on_event, suppress=False)

    def _stop_recording(self):
        if self.record_hook is None:
            return
        try:
            keyboard.unhook(self.record_hook)
        except Exception:
            pass
        self.record_hook = None
        self.btn_rec_start.setEnabled(True)
        self.btn_rec_stop.setEnabled(False)

        if not self.record_points:
            return

        prev_ts = self.record_started_ts
        for ts, key_name in self.record_points:
            delay_ms = int(max(0, (ts - prev_ts) * 1000))
            if delay_ms > 40:
                delay_step = {"type": "delay", "ms": delay_ms}
                delay_item = QListWidgetItem(self._step_label(delay_step))
                delay_item.setData(Qt.ItemDataRole.UserRole, delay_step)
                self.lst_steps.addItem(delay_item)

            step = {"type": "hotkey", "keys": key_name}
            item = QListWidgetItem(self._step_label(step))
            item.setData(Qt.ItemDataRole.UserRole, step)
            self.lst_steps.addItem(item)
            prev_ts = ts

    def _current_slot(self) -> Optional[Dict[str, Any]]:
        layers = self.config.get("layers", [])
        if not layers:
            return None
        slots = self._ensure_slots(layers[self.current_layer_idx])
        return slots[self.current_slot_idx]

    def _save_current_slot(self):
        if self._ui_syncing:
            return
        slot = self._current_slot()
        if not slot:
            return
        slot["name"] = self.edit_slot_name.text().strip() or f"Macro {self.current_slot_idx + 1}"
        slot["icon"] = self.edit_slot_icon.text().strip() or "⬡"

        steps: List[Dict[str, Any]] = []
        for i in range(self.lst_steps.count()):
            step = self.lst_steps.item(i).data(Qt.ItemDataRole.UserRole)
            if isinstance(step, dict):
                steps.append(deepcopy(step))

        if not steps:
            slot["action"] = {"type": "noop"}
        elif len(steps) == 1:
            slot["action"] = steps[0]
        else:
            slot["action"] = {"type": "sequence", "steps": steps}
        row = self.lst_slots.currentRow()
        if 0 <= row < self.lst_slots.count():
            labels = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
            self.lst_slots.item(row).setText(
                f"{labels[row]}  {slot.get('icon', 'â¬¡')}  {slot.get('name', f'Macro {row+1}')}"
            )

    def _validate_json(self):
        try:
            parsed = json.loads(self.edit_json.toPlainText())
            if not isinstance(parsed, dict):
                raise ValueError("Top-level JSON must be an object.")
            if "layers" not in parsed or not isinstance(parsed["layers"], list):
                raise ValueError("JSON must contain a 'layers' list.")
            QMessageBox.information(self, "Macro Studio", "JSON is valid.")
        except Exception as e:
            QMessageBox.warning(self, "Macro Studio", f"Invalid JSON:\n{e}")

    def _apply_json_to_visual(self):
        try:
            parsed = json.loads(self.edit_json.toPlainText())
            if not isinstance(parsed, dict):
                raise ValueError("Top-level JSON must be an object.")
            if "layers" not in parsed or not isinstance(parsed["layers"], list):
                raise ValueError("JSON must contain a 'layers' list.")
            self.config = parsed
            self.current_layer_idx = 0
            self.current_slot_idx = 0
            self._refresh_layers()
        except Exception as e:
            QMessageBox.warning(self, "Macro Studio", f"Could not apply JSON:\n{e}")

    def _open_config_path(self):
        try:
            import os
            os.startfile(str(self.config_path))
        except Exception as e:
            QMessageBox.warning(self, "Macro Studio", f"Could not open file:\n{e}")

    def _save_all(self):
        self._save_current_slot()
        self.edit_json.setPlainText(json.dumps(self.config, indent=4))
        try:
            self.config_path.write_text(self.edit_json.toPlainText(), encoding="utf-8")
            if callable(self.on_saved):
                self.on_saved()
            QMessageBox.information(self, "Macro Studio", "Saved.")
        except Exception as e:
            QMessageBox.warning(self, "Macro Studio", f"Save failed:\n{e}")
