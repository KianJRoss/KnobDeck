"""
Settings dialog for the KnobDeck Qt app.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Set

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QStyle,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """User-facing settings editor for runtime config and command layout."""
    VM_VARIANT_TO_OUTPUTS = {
        "voicemeeter": ["A1", "A2", "B1"],
        "banana": ["A1", "A2", "A3", "B1", "B2"],
        "potato": ["A1", "A2", "A3", "A4", "A5", "B1", "B2", "B3"],
    }
    VM_VARIANT_MAX_STRIP = {
        "voicemeeter": 2,
        "banana": 4,
        "potato": 7,
    }
    VM_DEFAULT_NAMES = {
        "A1": "Speakers",
        "A2": "Wired",
        "A3": "Wireless",
        "A4": "Alt 1",
        "A5": "Alt 2",
        "B1": "Virtual Out 1",
        "B2": "Virtual Out 2",
        "B3": "Virtual Out 3",
    }
    VM_DEFAULT_ICONS = {
        "A1": "SPK",
        "A2": "WIR",
        "A3": "WLS",
        "A4": "A4",
        "A5": "A5",
        "B1": "B1",
        "B2": "B2",
        "B3": "B3",
    }

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("KnobDeck Settings")
        icon_path = Path(__file__).parent / "assets" / "knobdeck_logo.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.setMinimumWidth(1120)
        self.setMinimumHeight(560)
        self.resize(1180, 700)
        up_icon = (Path(__file__).parent / "spin_up.png").as_posix()
        down_icon = (Path(__file__).parent / "spin_down.png").as_posix()
        self.setStyleSheet(
            f"""
            QDialog {{ background: #10151d; color: #dbe3f5; }}
            QTabWidget::pane {{ border: 1px solid #243248; background: #131b27; border-radius: 8px; }}
            QTabBar::tab {{
                background: #1a2534; color: #b8c8e8; border: 1px solid #2a3a52;
                border-bottom: none; padding: 8px 12px; min-width: 90px;
            }}
            QTabBar::tab:selected {{ background: #223249; color: #eef4ff; }}
            QGroupBox {{
                border: 1px solid #2a3a52; border-radius: 8px; margin-top: 8px; padding: 8px;
                background: #141d2a;
            }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #d9e4fb; }}
            QLabel {{ color: #c8d7f4; }}
            QLineEdit, QComboBox, QSpinBox, QListWidget {{
                background: #172131; border: 1px solid #30435f; border-radius: 6px; color: #edf3ff; padding: 4px;
            }}
            QSpinBox {{ padding-right: 30px; }}
            QSpinBox::up-button, QSpinBox::down-button {{
                subcontrol-origin: border;
                width: 20px;
                border-left: 1px solid #30435f;
                background: #223249;
            }}
            QSpinBox::up-button {{
                subcontrol-position: top right;
                border-top-right-radius: 6px;
            }}
            QSpinBox::down-button {{
                subcontrol-position: bottom right;
                border-bottom-right-radius: 6px;
                border-top: 1px solid #30435f;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: #2d4470; }}
            QSpinBox::up-arrow {{
                image: url("{up_icon}");
                width: 12px;
                height: 12px;
            }}
            QSpinBox::down-arrow {{
                image: url("{down_icon}");
                width: 12px;
                height: 12px;
            }}
            QPushButton {{
                background: #243552; border: 1px solid #3c5a88; border-radius: 8px;
                color: #e9f1ff; padding: 6px 10px;
            }}
            QPushButton:hover {{ background: #2d4470; }}
            QPushButton:pressed {{ background: #20365a; }}
            QCheckBox {{ color: #d5e2fb; }}
            """
        )

        self._build_ui()
        self._load_from_app()

    def _build_ui(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # ------------------------------------------------------------------
        # General tab
        # ------------------------------------------------------------------
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)

        feature_group = QGroupBox("Feature Toggles")
        feature_form = QFormLayout(feature_group)
        self.chk_enable_macro_mode = QCheckBox("Enable Macro Mode on idle double-click")
        self.chk_enable_voicemeeter = QCheckBox("Enable Voicemeeter integration")
        self.chk_enable_plugins = QCheckBox("Enable app/plugin integrations")
        self.chk_enable_context = QCheckBox("Enable context-aware commands")
        self.chk_plugin_hot_reload = QCheckBox("Enable plugin hot-reload")
        self.chk_auto_profile_switch = QCheckBox("Enable automatic profile switching")
        self.chk_status_indicator = QCheckBox("Show profile/mode status indicator")
        self.chk_onboarding_on_start = QCheckBox("Show onboarding tutorial on startup (until completed)")
        self.chk_notifications = QCheckBox("Enable notifications")
        self.chk_submenu_timeout = QCheckBox("Enable submenu auto-timeout")
        self.chk_vm_restore = QCheckBox("Restore Voicemeeter on startup")
        self.cmb_lighting_backend = QComboBox()
        self.cmb_lighting_backend.addItem("SignalRGB (show lighting menu)", "signalrgb")
        self.cmb_lighting_backend.addItem("Onboard / VIA (hide lighting menu)", "via")
        self.cmb_keyboard_profile = QComboBox()
        self.btn_detect_keyboard_profile = QPushButton("Auto-Detect Keyboard")
        self.btn_detect_keyboard_profile.clicked.connect(self._detect_keyboard_profile)
        feature_form.addRow(self.chk_enable_macro_mode)
        feature_form.addRow(self.chk_enable_voicemeeter)
        feature_form.addRow(self.chk_enable_plugins)
        feature_form.addRow(self.chk_enable_context)
        feature_form.addRow(self.chk_plugin_hot_reload)
        feature_form.addRow(self.chk_auto_profile_switch)
        feature_form.addRow(self.chk_status_indicator)
        feature_form.addRow(self.chk_onboarding_on_start)
        feature_form.addRow(self.chk_notifications)
        feature_form.addRow(self.chk_submenu_timeout)
        feature_form.addRow(self.chk_vm_restore)
        feature_form.addRow("Lighting backend:", self.cmb_lighting_backend)
        feature_form.addRow("Keyboard profile:", self.cmb_keyboard_profile)
        feature_form.addRow(self.btn_detect_keyboard_profile)
        general_layout.addWidget(feature_group)

        open_group = QGroupBox("Open Settings")
        open_form = QFormLayout(open_group)
        self.chk_triple_click = QCheckBox("Allow triple-click from idle")
        self.spin_triple_click_window = QSpinBox()
        self.spin_triple_click_window.setRange(300, 1500)
        self.spin_triple_click_window.setSingleStep(50)
        self.spin_triple_click_window.setSuffix(" ms")
        open_form.addRow(self.chk_triple_click)
        open_form.addRow("Triple-click window:", self.spin_triple_click_window)
        self.btn_open_tutorial = QPushButton("Open Tutorial")
        self.btn_open_tutorial.clicked.connect(self._open_tutorial)
        open_form.addRow(self.btn_open_tutorial)
        general_layout.addWidget(open_group)

        backup_group = QGroupBox("Backup / Restore")
        backup_form = QFormLayout(backup_group)
        self.btn_export_settings = QPushButton("Export settings...")
        self.btn_import_settings = QPushButton("Import settings...")
        self.btn_export_settings.clicked.connect(self._export_settings)
        self.btn_import_settings.clicked.connect(self._import_settings)
        backup_form.addRow(self.btn_export_settings)
        backup_form.addRow(self.btn_import_settings)
        general_layout.addWidget(backup_group)

        general_layout.addStretch(1)
        tabs.addTab(general_tab, "General")

        # ------------------------------------------------------------------
        # Behavior tab
        # ------------------------------------------------------------------
        behavior_tab = QWidget()
        behavior_layout = QFormLayout(behavior_tab)
        self.spin_menu_timeout = QSpinBox()
        self.spin_menu_timeout.setRange(500, 10000)
        self.spin_menu_timeout.setSingleStep(100)
        self.spin_menu_timeout.setSuffix(" ms")

        self.spin_double_click = QSpinBox()
        self.spin_double_click.setRange(100, 1000)
        self.spin_double_click.setSingleStep(25)
        self.spin_double_click.setSuffix(" ms")

        self.spin_quick_volume_hide = QSpinBox()
        self.spin_quick_volume_hide.setRange(200, 3000)
        self.spin_quick_volume_hide.setSingleStep(50)
        self.spin_quick_volume_hide.setSuffix(" ms")

        self.spin_volume_step = QSpinBox()
        self.spin_volume_step.setRange(1, 20)
        self.spin_volume_step.setSingleStep(1)

        behavior_layout.addRow("Main menu timeout:", self.spin_menu_timeout)
        behavior_layout.addRow("Double-click window:", self.spin_double_click)
        behavior_layout.addRow("Quick volume hide:", self.spin_quick_volume_hide)
        behavior_layout.addRow("Volume step:", self.spin_volume_step)
        tabs.addTab(behavior_tab, "Behavior")

        # ------------------------------------------------------------------
        # Wheel style tab
        # ------------------------------------------------------------------
        style_tab = QWidget()
        style_layout = QFormLayout(style_tab)
        self.cmb_theme = QComboBox()
        style_layout.addRow("Wheel theme:", self.cmb_theme)

        self.spin_side_label_chars = QSpinBox()
        self.spin_side_label_chars.setRange(10, 28)
        self.spin_side_label_chars.setSingleStep(1)
        style_layout.addRow("Side wedge label chars:", self.spin_side_label_chars)

        style_note = QLabel("Shorter side labels improve readability on curved wedges.")
        style_note.setWordWrap(True)
        style_layout.addRow(style_note)
        tabs.addTab(style_tab, "Wheel Style")

        # ------------------------------------------------------------------
        # Voicemeeter tab
        # ------------------------------------------------------------------
        vm_tab = QWidget()
        vm_layout = QFormLayout(vm_tab)
        self.spin_vm_mic_strip = QSpinBox()
        self.spin_vm_main_strip = QSpinBox()
        self.spin_vm_music_strip = QSpinBox()
        self.spin_vm_comm_strip = QSpinBox()
        for w in (self.spin_vm_mic_strip, self.spin_vm_main_strip, self.spin_vm_music_strip, self.spin_vm_comm_strip):
            w.setRange(0, 7)

        self.vm_output_widgets = {}
        self.cmb_vm_variant = QComboBox()
        self.cmb_vm_variant.addItem("Voicemeeter", "voicemeeter")
        self.cmb_vm_variant.addItem("Voicemeeter Banana", "banana")
        self.cmb_vm_variant.addItem("Voicemeeter Potato", "potato")
        self.cmb_vm_variant.currentIndexChanged.connect(self._on_vm_variant_changed)

        vm_layout.addRow("Variant:", self.cmb_vm_variant)
        vm_layout.addRow("Mic strip:", self.spin_vm_mic_strip)
        vm_layout.addRow("Main strip:", self.spin_vm_main_strip)
        vm_layout.addRow("Music strip:", self.spin_vm_music_strip)
        vm_layout.addRow("Comm strip:", self.spin_vm_comm_strip)

        for output in ["A1", "A2", "A3", "A4", "A5", "B1", "B2", "B3"]:
            chk = QCheckBox(f"Enable {output}")
            edit_name = QLineEdit()
            edit_icon = QLineEdit()
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(chk)
            row_layout.addWidget(QLabel("Name"))
            row_layout.addWidget(edit_name, 1)
            row_layout.addWidget(QLabel("Icon"))
            row_layout.addWidget(edit_icon)
            vm_layout.addRow(f"{output}:", row)
            self.vm_output_widgets[output] = {
                "check": chk,
                "name": edit_name,
                "icon": edit_icon,
                "row": row,
            }
        tabs.addTab(vm_tab, "Voicemeeter")

        # ------------------------------------------------------------------
        # Context Commands tab
        # ------------------------------------------------------------------
        context_tab = QWidget()
        context_layout = QVBoxLayout(context_tab)
        context_layout.addWidget(QLabel("Custom context commands are loaded from JSON rules."))
        self.btn_open_context_file = QPushButton("Open custom_context_commands.json")
        self.btn_open_context_file.clicked.connect(self._open_context_file)
        context_layout.addWidget(self.btn_open_context_file)
        context_layout.addStretch(1)
        tabs.addTab(context_tab, "Context Commands")

        # ------------------------------------------------------------------
        # Plugins tab
        # ------------------------------------------------------------------
        plugins_tab = QWidget()
        plugins_layout = QVBoxLayout(plugins_tab)
        plugins_layout.addWidget(QLabel("Use custom plugins to add commands, modes, and behavior."))
        self.cmb_plugins = QComboBox()
        self.cmb_plugins.currentIndexChanged.connect(self._on_plugin_changed)
        plugins_layout.addWidget(self.cmb_plugins)
        self.lbl_plugin_meta = QLabel("")
        self.lbl_plugin_meta.setWordWrap(True)
        plugins_layout.addWidget(self.lbl_plugin_meta)

        self.plugin_schema_area = QScrollArea()
        self.plugin_schema_area.setWidgetResizable(True)
        self.plugin_schema_host = QWidget()
        self.plugin_schema_form = QFormLayout(self.plugin_schema_host)
        self.plugin_schema_area.setWidget(self.plugin_schema_host)
        plugins_layout.addWidget(self.plugin_schema_area, 1)

        self.btn_open_plugin_folder = QPushButton("Open custom_plugins folder")
        self.btn_open_plugin_folder.clicked.connect(self._open_plugin_folder)
        plugins_layout.addWidget(self.btn_open_plugin_folder)
        self.plugin_catalog: List[Dict[str, object]] = []
        self.plugin_setting_edits: Dict[str, Dict[str, object]] = {}
        tabs.addTab(plugins_tab, "Plugins")

        # ------------------------------------------------------------------
        # Profiles tab
        # ------------------------------------------------------------------
        profiles_tab = QWidget()
        profiles_layout = QVBoxLayout(profiles_tab)
        profiles_layout.addWidget(QLabel("Auto-switch profiles by active app/window rules. Higher priority wins."))

        profile_row = QHBoxLayout()
        self.lst_profiles = QListWidget()
        profile_row.addWidget(self.lst_profiles, 1)

        profile_btn_col = QVBoxLayout()
        self.btn_profile_add = QPushButton("Add")
        self.btn_profile_remove = QPushButton("Remove")
        self.btn_profile_up = QPushButton("Move Up")
        self.btn_profile_down = QPushButton("Move Down")
        profile_btn_col.addWidget(self.btn_profile_add)
        profile_btn_col.addWidget(self.btn_profile_remove)
        profile_btn_col.addWidget(self.btn_profile_up)
        profile_btn_col.addWidget(self.btn_profile_down)
        profile_btn_col.addStretch(1)
        profile_row.addLayout(profile_btn_col)
        profiles_layout.addLayout(profile_row, 1)

        profile_editor = QGroupBox("Selected Profile")
        profile_form = QFormLayout(profile_editor)
        self.edit_profile_name = QLineEdit()
        self.spin_profile_priority = QSpinBox()
        self.spin_profile_priority.setRange(-100, 100)
        self.edit_profile_process_regex = QLineEdit()
        self.edit_profile_title_regex = QLineEdit()
        self.cmb_profile_theme = QComboBox()
        self.cmb_profile_theme.addItem("(Keep current)", "")
        self.spin_profile_macro_layer = QSpinBox()
        self.spin_profile_macro_layer.setRange(-1, 30)
        self.spin_profile_macro_layer.setSpecialValueText("(No macro layer override)")
        self.edit_profile_excludes = QLineEdit()
        self.edit_profile_excludes.setPlaceholderText("discord.exe, spotify.exe")
        profile_form.addRow("Name:", self.edit_profile_name)
        profile_form.addRow("Priority:", self.spin_profile_priority)
        profile_form.addRow("Process regex:", self.edit_profile_process_regex)
        profile_form.addRow("Window title regex:", self.edit_profile_title_regex)
        profile_form.addRow("Theme override:", self.cmb_profile_theme)
        profile_form.addRow("Macro layer:", self.spin_profile_macro_layer)
        profile_form.addRow("Exclude processes:", self.edit_profile_excludes)
        self.btn_profile_apply = QPushButton("Apply Profile Changes")
        profile_form.addRow(self.btn_profile_apply)
        profiles_layout.addWidget(profile_editor)
        tabs.addTab(profiles_tab, "Profiles")

        # ------------------------------------------------------------------
        # Diagnostics tab
        # ------------------------------------------------------------------
        diagnostics_tab = QWidget()
        diagnostics_layout = QVBoxLayout(diagnostics_tab)
        diagnostics_layout.addWidget(QLabel("Runtime health checks and plugin crash guard status."))
        self.txt_diagnostics = QPlainTextEdit()
        self.txt_diagnostics.setReadOnly(True)
        diagnostics_layout.addWidget(self.txt_diagnostics, 1)
        diag_row = QHBoxLayout()
        self.btn_diag_refresh = QPushButton("Refresh")
        self.btn_diag_clear_auto_disabled = QPushButton("Clear Auto-Disabled Plugins")
        self.btn_diag_refresh.clicked.connect(self._refresh_diagnostics)
        self.btn_diag_clear_auto_disabled.clicked.connect(self._clear_auto_disabled_plugins)
        diag_row.addWidget(self.btn_diag_refresh)
        diag_row.addWidget(self.btn_diag_clear_auto_disabled)
        diag_row.addStretch(1)
        diagnostics_layout.addLayout(diag_row)
        tabs.addTab(diagnostics_tab, "Diagnostics")

        # ------------------------------------------------------------------
        # Macros tab
        # ------------------------------------------------------------------
        macro_tab = QWidget()
        macro_layout = QVBoxLayout(macro_tab)
        macro_layout.addWidget(QLabel("Macro Studio lets you build layered macros visually, record input, and edit JSON code."))
        self.btn_open_macro_studio = QPushButton("Open Macro Studio")
        self.btn_open_macro_studio.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon))
        self.btn_open_macro_studio.clicked.connect(self._open_macro_studio)
        macro_layout.addWidget(self.btn_open_macro_studio)
        macro_layout.addStretch(1)
        tabs.addTab(macro_tab, "Macros")

        # ------------------------------------------------------------------
        # Command layout tab
        # ------------------------------------------------------------------
        command_tab = QWidget()
        command_layout = QVBoxLayout(command_tab)
        command_layout.addWidget(QLabel("Reorder wheel commands and toggle visibility:"))

        row = QHBoxLayout()
        self.lst_commands = QListWidget()
        self.lst_commands.setAlternatingRowColors(True)
        row.addWidget(self.lst_commands, 1)

        btn_col = QVBoxLayout()
        self.btn_move_up = QPushButton("Move Up")
        self.btn_move_down = QPushButton("Move Down")
        self.btn_show_all = QPushButton("Show All")
        self.btn_hide_all = QPushButton("Hide All")
        btn_col.addWidget(self.btn_move_up)
        btn_col.addWidget(self.btn_move_down)
        btn_col.addSpacing(12)
        btn_col.addWidget(self.btn_show_all)
        btn_col.addWidget(self.btn_hide_all)
        btn_col.addStretch(1)
        row.addLayout(btn_col)

        command_layout.addLayout(row, 1)
        tabs.addTab(command_tab, "Command Layout")

        self.btn_move_up.clicked.connect(lambda: self._move_selected(-1))
        self.btn_move_down.clicked.connect(lambda: self._move_selected(1))
        self.btn_show_all.clicked.connect(lambda: self._set_all_checks(Qt.CheckState.Checked))
        self.btn_hide_all.clicked.connect(lambda: self._set_all_checks(Qt.CheckState.Unchecked))
        self.lst_profiles.currentRowChanged.connect(self._on_profile_selected)
        self.btn_profile_add.clicked.connect(self._add_profile)
        self.btn_profile_remove.clicked.connect(self._remove_profile)
        self.btn_profile_up.clicked.connect(lambda: self._move_profile(-1))
        self.btn_profile_down.clicked.connect(lambda: self._move_profile(1))
        self.btn_profile_apply.clicked.connect(self._apply_profile_editor)

        # Save / cancel
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        # Keep stacked spin controls with explicit icon assets for readability.
        for spin in self.findChildren(QSpinBox):
            spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)

    def _load_from_app(self):
        settings = self.app.get_runtime_settings()
        self._load_keyboard_profiles()

        self.chk_notifications.setChecked(bool(settings.get("notifications_enabled", True)))
        self.chk_submenu_timeout.setChecked(bool(settings.get("submenu_timeout_enabled", True)))
        self.chk_enable_macro_mode.setChecked(bool(settings.get("macro_mode_enabled", True)))
        self.chk_enable_voicemeeter.setChecked(bool(settings.get("enable_voicemeeter_integration", True)))
        self.chk_enable_plugins.setChecked(bool(settings.get("enable_plugin_integrations", True)))
        self.chk_enable_context.setChecked(bool(settings.get("enable_context_commands", True)))
        self.chk_plugin_hot_reload.setChecked(bool(settings.get("plugin_hot_reload_enabled", True)))
        self.chk_auto_profile_switch.setChecked(bool(settings.get("auto_profile_switch_enabled", True)))
        self.chk_status_indicator.setChecked(bool(settings.get("show_status_indicator", True)))
        self.chk_onboarding_on_start.setChecked(bool(settings.get("show_onboarding_on_start", True)))
        self.chk_vm_restore.setChecked(bool(settings.get("restore_voicemeeter_on_start", False)))
        backend = str(settings.get("lighting_backend", "signalrgb")).strip().lower()
        backend_idx = self.cmb_lighting_backend.findData(backend)
        self.cmb_lighting_backend.setCurrentIndex(backend_idx if backend_idx >= 0 else 0)
        self.chk_triple_click.setChecked(bool(settings.get("triple_click_settings_enabled", True)))
        self.spin_triple_click_window.setValue(int(settings.get("triple_click_window_ms", 700)))

        self.spin_menu_timeout.setValue(int(settings.get("menu_timeout_ms", 3000)))
        self.spin_double_click.setValue(int(settings.get("double_click_ms", 300)))
        self.spin_quick_volume_hide.setValue(int(settings.get("quick_volume_hide_ms", 800)))
        self.spin_volume_step.setValue(int(settings.get("volume_step", 2)))
        self.spin_side_label_chars.setValue(int(settings.get("side_label_max_chars", 18)))
        vm_profile = self.app.get_voicemeeter_profile() if hasattr(self.app, "get_voicemeeter_profile") else {}
        self.spin_vm_mic_strip.setValue(int(vm_profile.get("mic_strip", 0)))
        self.spin_vm_main_strip.setValue(int(vm_profile.get("main_strip", 5)))
        self.spin_vm_music_strip.setValue(int(vm_profile.get("music_strip", 6)))
        self.spin_vm_comm_strip.setValue(int(vm_profile.get("comm_strip", 7)))
        variant = str(vm_profile.get("variant", "potato")).strip().lower()
        vm_idx = self.cmb_vm_variant.findData(variant)
        self.cmb_vm_variant.setCurrentIndex(vm_idx if vm_idx >= 0 else 2)
        active_outputs = vm_profile.get("active_outputs", self.VM_VARIANT_TO_OUTPUTS.get(variant, ["A1", "A2", "B1"]))
        if not isinstance(active_outputs, list):
            active_outputs = self.VM_VARIANT_TO_OUTPUTS.get(variant, ["A1", "A2", "B1"])
        norm_active = {str(x).upper() for x in active_outputs}

        out_names = vm_profile.get("output_names", {})
        if isinstance(out_names, list):
            out_names = {"A1": out_names[0] if len(out_names) > 0 else "",
                         "A2": out_names[1] if len(out_names) > 1 else "",
                         "A3": out_names[2] if len(out_names) > 2 else ""}
        if not isinstance(out_names, dict):
            out_names = {}

        out_icons = vm_profile.get("output_icons", {})
        if isinstance(out_icons, list):
            out_icons = {"A1": out_icons[0] if len(out_icons) > 0 else "",
                         "A2": out_icons[1] if len(out_icons) > 1 else "",
                         "A3": out_icons[2] if len(out_icons) > 2 else ""}
        if not isinstance(out_icons, dict):
            out_icons = {}

        for output, widgets in self.vm_output_widgets.items():
            widgets["check"].setChecked(output in norm_active)
            widgets["name"].setText(str(out_names.get(output, self.VM_DEFAULT_NAMES.get(output, output))))
            widgets["icon"].setText(str(out_icons.get(output, self.VM_DEFAULT_ICONS.get(output, output))))

        self._on_vm_variant_changed()

        self._load_plugin_catalog()
        self._load_profiles()
        self._refresh_diagnostics()

        themes = self.app.get_available_themes()
        self.cmb_theme.clear()
        self.cmb_theme.addItems(themes)
        current_theme = getattr(self.app, "config", {}).get("ui_theme", "DARK")
        idx = self.cmb_theme.findText(current_theme)
        if idx >= 0:
            self.cmb_theme.setCurrentIndex(idx)

        layout_info = self.app.get_command_layout()
        order: List[str] = layout_info["order"]
        hidden: Set[str] = set(layout_info["hidden"])
        descriptions: Dict[str, str] = layout_info["descriptions"]

        self.lst_commands.clear()
        for name in order:
            desc = descriptions.get(name, "")
            text = f"{name} — {desc}" if desc else name
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(Qt.CheckState.Unchecked if name in hidden else Qt.CheckState.Checked)
            self.lst_commands.addItem(item)

    def _load_plugin_catalog(self):
        self.cmb_plugins.blockSignals(True)
        self.cmb_plugins.clear()
        self.plugin_catalog = self.app.get_plugin_catalog() if hasattr(self.app, "get_plugin_catalog") else []
        for p in self.plugin_catalog:
            label = str(p.get("name", p.get("module", "")))
            self.cmb_plugins.addItem(label, str(p.get("module", "")))
        self.cmb_plugins.blockSignals(False)
        if self.cmb_plugins.count() > 0:
            self.cmb_plugins.setCurrentIndex(0)
            self._on_plugin_changed()
        else:
            self.lbl_plugin_meta.setText("No plugins loaded.")

    def _clear_plugin_schema_form(self):
        while self.plugin_schema_form.rowCount() > 0:
            self.plugin_schema_form.removeRow(0)

    def _on_plugin_changed(self):
        self._clear_plugin_schema_form()
        idx = self.cmb_plugins.currentIndex()
        if idx < 0 or idx >= len(self.plugin_catalog):
            self.lbl_plugin_meta.setText("")
            return
        p = self.plugin_catalog[idx]
        module = str(p.get("module", ""))
        desc = str(p.get("description", ""))
        version = str(p.get("version", ""))
        author = str(p.get("author", ""))
        self.lbl_plugin_meta.setText(f"Module: {module}\nVersion: {version}\nAuthor: {author}\n{desc}")

        schema = p.get("settings_schema", [])
        values = p.get("settings_values", {})
        if not isinstance(schema, list):
            schema = []
        if not isinstance(values, dict):
            values = {}

        self.plugin_setting_edits[module] = {}
        if not schema:
            self.plugin_schema_form.addRow(QLabel("No schema-defined settings for this plugin."))
            return

        for item in schema:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).strip()
            if not key:
                continue
            typ = str(item.get("type", "string")).strip().lower()
            default = item.get("default")
            cur = values.get(key, default)
            if typ == "bool":
                w = QCheckBox()
                w.setChecked(bool(cur))
                self.plugin_schema_form.addRow(key, w)
                self.plugin_setting_edits[module][key] = {"widget": w, "type": typ}
                continue
            if typ == "int":
                w = QSpinBox()
                w.setRange(-999999, 999999)
                try:
                    w.setValue(int(cur))
                except Exception:
                    w.setValue(int(default or 0))
                self.plugin_schema_form.addRow(key, w)
                self.plugin_setting_edits[module][key] = {"widget": w, "type": typ}
                continue
            w = QLineEdit(str(cur if cur is not None else ""))
            self.plugin_schema_form.addRow(key, w)
            self.plugin_setting_edits[module][key] = {"widget": w, "type": typ}

    def _collect_plugin_settings(self) -> Dict[str, Dict[str, object]]:
        existing = self.app.get_runtime_settings().get("plugin_settings", {}) if hasattr(self.app, "get_runtime_settings") else {}
        out: Dict[str, Dict[str, object]] = dict(existing) if isinstance(existing, dict) else {}
        for module, fields in self.plugin_setting_edits.items():
            module_vals: Dict[str, object] = {}
            for key, meta in fields.items():
                widget = meta.get("widget")
                typ = str(meta.get("type", "string"))
                if typ == "bool" and isinstance(widget, QCheckBox):
                    module_vals[key] = widget.isChecked()
                elif typ == "int" and isinstance(widget, QSpinBox):
                    module_vals[key] = int(widget.value())
                elif isinstance(widget, QLineEdit):
                    module_vals[key] = widget.text().strip()
            out[module] = module_vals
        return out

    def _load_keyboard_profiles(self):
        self.cmb_keyboard_profile.blockSignals(True)
        self.cmb_keyboard_profile.clear()
        current_id = str(getattr(self.app, "config", {}).get("keyboard_profile_id", "default_qmk_knob"))
        catalog = self.app.get_keyboard_profile_catalog() if hasattr(self.app, "get_keyboard_profile_catalog") else []
        for item in catalog:
            if not isinstance(item, dict):
                continue
            label = str(item.get("name", item.get("id", "")))
            pid = str(item.get("id", ""))
            self.cmb_keyboard_profile.addItem(label, pid)
        self.cmb_keyboard_profile.blockSignals(False)
        idx = self.cmb_keyboard_profile.findData(current_id)
        if idx >= 0:
            self.cmb_keyboard_profile.setCurrentIndex(idx)

    def _detect_keyboard_profile(self):
        if not hasattr(self.app, "detect_and_apply_keyboard_profile"):
            return
        found = self.app.detect_and_apply_keyboard_profile()
        if not found:
            QMessageBox.information(self, "Keyboard Profile", "No known keyboard profile was detected.")
            return
        self._load_keyboard_profiles()
        QMessageBox.information(
            self,
            "Keyboard Profile",
            f"Detected and applied profile:\n{found.get('name', found.get('id', 'Unknown'))}",
        )

    def _load_profiles(self):
        settings = self.app.get_runtime_settings() if hasattr(self.app, "get_runtime_settings") else {}
        raw = settings.get("profiles", [])
        self.profiles_data: List[Dict[str, object]] = [dict(p) for p in raw if isinstance(p, dict)]
        if not self.profiles_data:
            self.profiles_data = [{"name": "Default", "priority": 0, "auto_switch": {}}]

        # Refresh theme options for profiles
        self.cmb_profile_theme.clear()
        self.cmb_profile_theme.addItem("(Keep current)", "")
        for t in self.app.get_available_themes() if hasattr(self.app, "get_available_themes") else []:
            self.cmb_profile_theme.addItem(str(t), str(t))

        self.lst_profiles.blockSignals(True)
        self.lst_profiles.clear()
        for p in self.profiles_data:
            self.lst_profiles.addItem(str(p.get("name", "Profile")))
        self.lst_profiles.blockSignals(False)
        if self.lst_profiles.count() > 0:
            self.lst_profiles.setCurrentRow(0)
            self._on_profile_selected(0)

    def _on_profile_selected(self, row: int):
        if row < 0 or row >= len(getattr(self, "profiles_data", [])):
            return
        p = self.profiles_data[row]
        auto = p.get("auto_switch", {})
        if not isinstance(auto, dict):
            auto = {}
        self.edit_profile_name.setText(str(p.get("name", "")))
        self.spin_profile_priority.setValue(int(p.get("priority", 0)))
        self.edit_profile_process_regex.setText(str(auto.get("process_regex", "")))
        self.edit_profile_title_regex.setText(str(auto.get("title_regex", "")))
        ex = auto.get("exclude_processes", [])
        ex_txt = ", ".join([str(x) for x in ex]) if isinstance(ex, list) else ""
        self.edit_profile_excludes.setText(ex_txt)
        theme = str(p.get("theme", "")).strip()
        idx = self.cmb_profile_theme.findData(theme)
        self.cmb_profile_theme.setCurrentIndex(idx if idx >= 0 else 0)
        macro_layer = p.get("macro_layer")
        self.spin_profile_macro_layer.setValue(int(macro_layer) if isinstance(macro_layer, int) else -1)

    def _apply_profile_editor(self):
        row = self.lst_profiles.currentRow()
        if row < 0 or row >= len(getattr(self, "profiles_data", [])):
            return
        name = self.edit_profile_name.text().strip() or f"Profile {row + 1}"
        excludes = [x.strip() for x in self.edit_profile_excludes.text().split(",") if x.strip()]
        macro_layer = int(self.spin_profile_macro_layer.value())
        self.profiles_data[row] = {
            **self.profiles_data[row],
            "name": name,
            "priority": int(self.spin_profile_priority.value()),
            "theme": str(self.cmb_profile_theme.currentData() or ""),
            "macro_layer": None if macro_layer < 0 else macro_layer,
            "auto_switch": {
                "process_regex": self.edit_profile_process_regex.text().strip(),
                "title_regex": self.edit_profile_title_regex.text().strip(),
                "exclude_processes": excludes,
            },
        }
        self.lst_profiles.item(row).setText(name)

    def _add_profile(self):
        if not hasattr(self, "profiles_data"):
            self.profiles_data = []
        self.profiles_data.append({
            "name": f"Profile {len(self.profiles_data) + 1}",
            "priority": 0,
            "theme": "",
            "command_order": [],
            "command_hidden": [],
            "macro_layer": None,
            "auto_switch": {},
        })
        self.lst_profiles.addItem(self.profiles_data[-1]["name"])
        self.lst_profiles.setCurrentRow(self.lst_profiles.count() - 1)

    def _remove_profile(self):
        row = self.lst_profiles.currentRow()
        if row < 0:
            return
        name = str(self.profiles_data[row].get("name", ""))
        if name.lower() == "default":
            QMessageBox.information(self, "Profiles", "Default profile cannot be removed.")
            return
        self.profiles_data.pop(row)
        self.lst_profiles.takeItem(row)
        if self.lst_profiles.count() > 0:
            self.lst_profiles.setCurrentRow(max(0, row - 1))

    def _move_profile(self, delta: int):
        row = self.lst_profiles.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= self.lst_profiles.count():
            return
        self._apply_profile_editor()
        self.profiles_data[row], self.profiles_data[new_row] = self.profiles_data[new_row], self.profiles_data[row]
        item = self.lst_profiles.takeItem(row)
        self.lst_profiles.insertItem(new_row, item)
        self.lst_profiles.setCurrentRow(new_row)

    def _open_tutorial(self):
        if hasattr(self.app, "open_onboarding_tutorial"):
            self.app.open_onboarding_tutorial()

    def _export_settings(self):
        if not hasattr(self.app, "export_settings_bundle"):
            return
        default_path = str((Path(__file__).parent / "knobdeck_settings_backup.json").resolve())
        path, _ = QFileDialog.getSaveFileName(self, "Export Settings", default_path, "JSON Files (*.json)")
        if not path:
            return
        ok = bool(self.app.export_settings_bundle(path))
        if ok:
            QMessageBox.information(self, "Export", "Settings export completed.")
        else:
            QMessageBox.warning(self, "Export", "Settings export failed.")

    def _import_settings(self):
        if not hasattr(self.app, "import_settings_bundle"):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import Settings", str(Path(__file__).parent), "JSON Files (*.json)")
        if not path:
            return
        ok = bool(self.app.import_settings_bundle(path))
        if ok:
            self._load_from_app()
            QMessageBox.information(self, "Import", "Settings import completed.")
        else:
            QMessageBox.warning(self, "Import", "Settings import failed. Verify the JSON format.")

    def _refresh_diagnostics(self):
        if not hasattr(self.app, "get_health_status"):
            return
        status = self.app.get_health_status()
        failed = status.get("plugin_failed", {}) if isinstance(status, dict) else {}
        failed_lines = []
        if isinstance(failed, dict) and failed:
            for name, err in failed.items():
                failed_lines.append(f"- {name}: {err}")
        else:
            failed_lines.append("- None")
        disabled_auto = []
        settings = self.app.get_runtime_settings() if hasattr(self.app, "get_runtime_settings") else {}
        raw_auto = settings.get("disabled_plugins_auto", [])
        if isinstance(raw_auto, list):
            disabled_auto = [str(x) for x in raw_auto]

        text = (
            f"Hotkeys registered: {status.get('hotkeys_registered', False)}\n"
            f"Tray visible: {status.get('tray_visible', False)}\n"
            f"Voicemeeter connected: {status.get('voicemeeter_connected', False)}\n"
            f"SignalRGB enabled: {status.get('signalrgb_enabled', False)}\n"
            f"Active profile: {status.get('active_profile', 'Default')}\n"
            f"Loaded plugins: {status.get('plugin_count', 0)}\n"
            f"Auto-disabled plugins: {', '.join(disabled_auto) if disabled_auto else '(none)'}\n\n"
            f"Plugin load failures:\n" + "\n".join(failed_lines)
        )
        self.txt_diagnostics.setPlainText(text)

    def _clear_auto_disabled_plugins(self):
        if hasattr(self.app, "clear_auto_disabled_plugins"):
            self.app.clear_auto_disabled_plugins()
        self._refresh_diagnostics()

    def _move_selected(self, delta: int):
        row = self.lst_commands.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= self.lst_commands.count():
            return
        item = self.lst_commands.takeItem(row)
        self.lst_commands.insertItem(new_row, item)
        self.lst_commands.setCurrentRow(new_row)

    def _set_all_checks(self, state: Qt.CheckState):
        for idx in range(self.lst_commands.count()):
            self.lst_commands.item(idx).setCheckState(state)

    def _on_vm_variant_changed(self):
        variant = str(self.cmb_vm_variant.currentData() or "potato")
        allowed_outputs = set(self.VM_VARIANT_TO_OUTPUTS.get(variant, self.VM_VARIANT_TO_OUTPUTS["potato"]))
        max_strip = int(self.VM_VARIANT_MAX_STRIP.get(variant, 7))

        for spin in (self.spin_vm_mic_strip, self.spin_vm_main_strip, self.spin_vm_music_strip, self.spin_vm_comm_strip):
            spin.setRange(0, max_strip)
            if spin.value() > max_strip:
                spin.setValue(max_strip)

        visible_checked = 0
        first_visible = None
        for output, widgets in self.vm_output_widgets.items():
            is_visible = output in allowed_outputs
            widgets["row"].setVisible(is_visible)
            if is_visible:
                first_visible = first_visible or output
                if widgets["check"].isChecked():
                    visible_checked += 1
            else:
                widgets["check"].setChecked(False)

        if visible_checked == 0 and first_visible:
            self.vm_output_widgets[first_visible]["check"].setChecked(True)

    def _open_context_file(self):
        if hasattr(self.app, "open_custom_context_file"):
            self.app.open_custom_context_file()

    def _open_plugin_folder(self):
        if hasattr(self.app, "open_custom_plugin_folder"):
            self.app.open_custom_plugin_folder()

    def _open_macro_studio(self):
        if hasattr(self.app, "open_macro_editor"):
            logger.info("Settings: Open Macro Studio clicked")
            ok = bool(self.app.open_macro_editor())
            if not ok:
                QMessageBox.warning(
                    self,
                    "Macro Studio",
                    "Macro Studio failed to open. Check logs/knobdeck_app.log for details.",
                )

    def _on_save(self):
        self._apply_profile_editor()

        order: List[str] = []
        hidden: List[str] = []
        for idx in range(self.lst_commands.count()):
            item = self.lst_commands.item(idx)
            name = str(item.data(Qt.ItemDataRole.UserRole))
            order.append(name)
            if item.checkState() != Qt.CheckState.Checked:
                hidden.append(name)

        if len(hidden) >= len(order):
            self.app._show_notification("At least one command must stay visible", 1800)
            return

        payload = {
            "settings": {
                "macro_mode_enabled": self.chk_enable_macro_mode.isChecked(),
                "enable_voicemeeter_integration": self.chk_enable_voicemeeter.isChecked(),
                "enable_plugin_integrations": self.chk_enable_plugins.isChecked(),
                "enable_context_commands": self.chk_enable_context.isChecked(),
                "plugin_hot_reload_enabled": self.chk_plugin_hot_reload.isChecked(),
                "auto_profile_switch_enabled": self.chk_auto_profile_switch.isChecked(),
                "show_status_indicator": self.chk_status_indicator.isChecked(),
                "show_onboarding_on_start": self.chk_onboarding_on_start.isChecked(),
                "notifications_enabled": self.chk_notifications.isChecked(),
                "submenu_timeout_enabled": self.chk_submenu_timeout.isChecked(),
                "restore_voicemeeter_on_start": self.chk_vm_restore.isChecked(),
                "lighting_backend": str(self.cmb_lighting_backend.currentData() or "signalrgb"),
                "triple_click_settings_enabled": self.chk_triple_click.isChecked(),
                "triple_click_window_ms": int(self.spin_triple_click_window.value()),
                "menu_timeout_ms": int(self.spin_menu_timeout.value()),
                "double_click_ms": int(self.spin_double_click.value()),
                "quick_volume_hide_ms": int(self.spin_quick_volume_hide.value()),
                "volume_step": int(self.spin_volume_step.value()),
                "side_label_max_chars": int(self.spin_side_label_chars.value()),
            },
            "theme": self.cmb_theme.currentText().strip(),
            "keyboard_profile_id": str(self.cmb_keyboard_profile.currentData() or "default_qmk_knob"),
            "command_order": order,
            "command_hidden": hidden,
            "plugin_settings": self._collect_plugin_settings(),
            "profiles": list(getattr(self, "profiles_data", [])),
            "disabled_plugins_auto": self.app.get_runtime_settings().get("disabled_plugins_auto", []) if hasattr(self.app, "get_runtime_settings") else [],
            "voicemeeter_profile": {
                "mic_strip": int(self.spin_vm_mic_strip.value()),
                "main_strip": int(self.spin_vm_main_strip.value()),
                "music_strip": int(self.spin_vm_music_strip.value()),
                "comm_strip": int(self.spin_vm_comm_strip.value()),
                "variant": str(self.cmb_vm_variant.currentData() or "potato"),
                "active_outputs": [],
                "output_names": {},
                "output_icons": {},
            },
        }

        variant = str(self.cmb_vm_variant.currentData() or "potato")
        allowed_outputs = self.VM_VARIANT_TO_OUTPUTS.get(variant, self.VM_VARIANT_TO_OUTPUTS["potato"])
        active_outputs = []
        output_names = {}
        output_icons = {}
        for output in allowed_outputs:
            widgets = self.vm_output_widgets[output]
            if widgets["check"].isChecked():
                active_outputs.append(output)
            output_names[output] = widgets["name"].text().strip() or self.VM_DEFAULT_NAMES.get(output, output)
            output_icons[output] = widgets["icon"].text().strip() or self.VM_DEFAULT_ICONS.get(output, output)

        if not active_outputs:
            active_outputs = [allowed_outputs[0]]

        payload["voicemeeter_profile"]["active_outputs"] = active_outputs
        payload["voicemeeter_profile"]["output_names"] = output_names
        payload["voicemeeter_profile"]["output_icons"] = output_icons
        self.app.apply_settings_payload(payload)
        self.accept()
