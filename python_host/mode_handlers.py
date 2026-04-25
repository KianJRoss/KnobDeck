"""
Mode Handlers - Implement behavior for each menu mode

Each handler implements:
- on_enter: Setup when mode is activated
- on_exit: Cleanup when mode is exited
- on_rotation: Handle encoder rotation (CW/CCW)
- on_press: Handle encoder press
- get_display_text: Return text for overlay UI
"""

from menu_system import ModeHandler, AppState, MenuMode
from windows_api import SystemAPI
from typing import Dict
import time
import threading


# ============================================================================
# MEDIA CONTROL MODE
# ============================================================================

class MediaModeHandler(ModeHandler):
    """Media control: Play/Pause, Next/Prev track"""

    def __init__(self, api: SystemAPI, state_machine):
        self.api = api
        self.sm = state_machine
        self.last_active = -1
        self.reset_timer: threading.Timer = None

    def on_enter(self, state: AppState):
        self.last_active = -1
        if self.reset_timer:
            self.reset_timer.cancel()

    def on_exit(self, state: AppState):
        if self.reset_timer:
            self.reset_timer.cancel()

    def _trigger_highlight(self, index: int):
        """Highlight an item briefly"""
        self.last_active = index
        
        if self.reset_timer:
            self.reset_timer.cancel()
            
        self.reset_timer = threading.Timer(0.5, self._reset_active)
        self.reset_timer.start()

    def _reset_active(self):
        """Reset highlight to neutral"""
        self.last_active = -1
        self.sm.update_display()

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Next/Previous track"""
        # Clockwise brings left (Previous) to center, CCW brings right (Next) to center
        if clockwise:
            self.api.media.prev_track()
            self._trigger_highlight(0)
        else:
            self.api.media.next_track()
            self._trigger_highlight(2)

    def on_press(self, state: AppState):
        """Press: Play/Pause"""
        self.api.media.play_pause()
        self._trigger_highlight(1)

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        return {
            'left': 'Previous Track',
            'center': 'Play/Pause',
            'right': 'Next Track',
            'title': '',
            'icons': {'left': '⏮', 'center': '⏯', 'right': '⏭'},
            'active_index': self.last_active,
            'pulsing': self.last_active != -1
        }


# ============================================================================
# VOLUME CONTROL MODE
# ============================================================================

class VolumeModeHandler(ModeHandler):
    """System volume control"""

    def __init__(self, api: SystemAPI, volume_step: int = 2):
        self.api = api
        self.volume_step = volume_step

    def on_enter(self, state: AppState):
        pass

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Adjust volume"""
        # Clockwise = volume up, counter-clockwise = volume down.
        if clockwise:
            self.api.volume.adjust_volume(self.volume_step)
        else:
            self.api.volume.adjust_volume(-self.volume_step)

    def on_press(self, state: AppState):
        """Press: Toggle mute"""
        self.api.volume.toggle_mute()

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        volume = self.api.volume.get_volume()
        muted = self.api.volume.get_mute()

        return {
            'left': 'Volume Down',
            'center': f'{volume}%',
            'right': 'Volume Up',
            'title': '🔇 MUTED' if muted else '🔊 Volume',
            'progress': volume / 100.0,
            'icons': {'left': '−', 'center': '🔇' if muted else '🔊', 'right': '+'}
        }


# ============================================================================
# WINDOW MENU MODE (Submenu selector)
# ============================================================================

class VolumeMixerModeHandler(ModeHandler):
    """Per-app volume mixer mode."""

    def __init__(self, api: SystemAPI, state_machine, volume_step: int = 2):
        self.api = api
        self.sm = state_machine
        self.volume_step = volume_step
        self.sessions = []
        self.selected = 0

    def _reload(self):
        self.sessions = self.api.volume.get_app_sessions()
        if not self.sessions:
            self.selected = 0
            return
        self.selected = max(0, min(self.selected, len(self.sessions) - 1))

    def on_enter(self, state: AppState):
        self._reload()

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        if not self.sessions:
            self._reload()
            return
        sess = self.sessions[self.selected]
        delta = self.volume_step if clockwise else -self.volume_step
        ok = self.api.volume.adjust_app_volume(sess.get("session"), delta)
        if ok:
            self._reload()

    def on_press(self, state: AppState):
        if not self.sessions:
            self._reload()
            return
        sess = self.sessions[self.selected]
        ok = self.api.volume.toggle_app_mute(sess.get("session"))
        if ok:
            self._reload()
            return
        self.selected = (self.selected + 1) % len(self.sessions)

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        self._reload()
        if not self.sessions:
            return {
                'left': '',
                'center': 'No app audio sessions',
                'right': 'Play audio in an app',
                'title': 'App Volume Mixer',
                'subtitle': 'Rotate=Volume, Press=Mute app',
                'active_index': 1,
            }

        total = len(self.sessions)
        idx = self.selected % total
        prev_idx = (idx - 1) % total
        next_idx = (idx + 1) % total
        curr = self.sessions[idx]
        prev = self.sessions[prev_idx]
        nxt = self.sessions[next_idx]
        muted = bool(curr.get("muted"))
        vol = int(curr.get("volume", 0))

        return {
            'left': prev.get("name", ""),
            'center': f"{curr.get('name', '')} {vol}%",
            'right': nxt.get("name", ""),
            'title': 'App Mixer' + (' (Muted)' if muted else ''),
            'subtitle': 'Rotate=Volume, Press=Mute app',
            'progress': max(0.0, min(1.0, vol / 100.0)),
            'icons': {'left': 'APP', 'center': 'MUT' if muted else 'VOL', 'right': 'APP'},
            'active_index': 1,
        }
class WindowMenuHandler(ModeHandler):
    """Window manager submenu selector"""

    def __init__(self, state_machine):
        self.sm = state_machine
        self.submenus = [
            {'name': 'Window Cycle', 'mode': MenuMode.WINDOW_CYCLE},
            {'name': 'Window Snap', 'mode': MenuMode.WINDOW_SNAP},
            {'name': 'Show Desktop', 'action': self._show_desktop}
        ]

    def _show_desktop(self):
        """Action: Show desktop"""
        self.sm.api.windows.show_desktop()
        self.sm.exit_menu_mode()

    def on_enter(self, state: AppState):
        state.submenu_index = 0

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Cycle through submenus"""
        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.submenus)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.submenus)

    def on_press(self, state: AppState):
        """Press: Execute selected submenu"""
        submenu = self.submenus[state.submenu_index]
        if 'mode' in submenu:
            # Enter submenu mode
            self.sm.enter_mode(submenu['mode'])
        elif 'action' in submenu:
            # Execute action
            submenu['action']()

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        total = len(self.submenus)
        prev_idx = (state.submenu_index - 1) % total
        next_idx = (state.submenu_index + 1) % total

        return {
            'left': self.submenus[prev_idx]['name'],
            'center': f"> {self.submenus[state.submenu_index]['name']}",
            'right': self.submenus[next_idx]['name'],
            'title': 'Voicemeeter',
            'active_index': 1
        }


# ============================================================================
# WINDOW CYCLE MODE (Alt-Tab like)
# ============================================================================

class WindowCycleHandler(ModeHandler):
    """Alt-Tab like window cycling"""

    def __init__(self, api: SystemAPI):
        self.api = api

    def on_enter(self, state: AppState):
        """Build window list"""
        state.window_list = self.api.windows.get_visible_windows()
        state.submenu_index = 0

    def on_exit(self, state: AppState):
        state.window_list = []

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Cycle through windows"""
        if not state.window_list:
            return

        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(state.window_list)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(state.window_list)

    def on_press(self, state: AppState):
        """Press: Switch to selected window"""
        if state.window_list and 0 <= state.submenu_index < len(state.window_list):
            window = state.window_list[state.submenu_index]
            if self.api.windows.activate_window(window.hwnd):
                # Exit after successful switch
                from menu_system import MenuMode
                state.menu_mode = MenuMode.NORMAL

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        if not state.window_list:
            return {
                'left': '',
                'center': '⚠ No windows found',
                'right': ''
            }

        if len(state.window_list) == 1:
            title = state.window_list[0].title[:22]
            return {
                'left': '',
                'center': f'> {title}',
                'right': ''
            }

        # Multiple windows
        total = len(state.window_list)
        prev_idx = (state.submenu_index - 1) % total
        next_idx = (state.submenu_index + 1) % total

        prev_title = state.window_list[prev_idx].title[:22]
        curr_title = state.window_list[state.submenu_index].title[:22]
        next_title = state.window_list[next_idx].title[:22]

        return {
            'left': prev_title,
            'center': f'> {curr_title}',
            'right': next_title
        }


# ============================================================================
# WINDOW SNAP MODE
# ============================================================================

class WindowSnapHandler(ModeHandler):
    """Window snapping to screen edges"""

    def __init__(self, api: SystemAPI, state_machine):
        self.api = api
        self.sm = state_machine
        self.snap_options = [
            {'name': '◧ Snap Left', 'action': api.windows.snap_window_left},
            {'name': '◨ Snap Right', 'action': api.windows.snap_window_right},
            {'name': '⬜ Maximize', 'action': api.windows.maximize_window}
        ]

    def on_enter(self, state: AppState):
        state.submenu_index = 0

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Cycle through snap options"""
        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.snap_options)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.snap_options)

    def on_press(self, state: AppState):
        """Press: Execute snap action and exit"""
        option = self.snap_options[state.submenu_index]
        option['action']()
        # Exit after snapping
        self.sm.exit_menu_mode()

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        total = len(self.snap_options)
        prev_idx = (state.submenu_index - 1) % total
        next_idx = (state.submenu_index + 1) % total

        return {
            'left': self.snap_options[prev_idx]['name'],
            'center': f"> {self.snap_options[state.submenu_index]['name']}",
            'right': self.snap_options[next_idx]['name']
        }


# ============================================================================
# VOICEMEETER HANDLERS
# ============================================================================

class VoicemeeterMenuHandler(ModeHandler):
    """Voicemeeter submenu selector"""

    def __init__(self, state_machine, vm_controller):
        self.sm = state_machine
        self.vm = vm_controller
        self.submenus = [
            {'name': 'Microphone Control', 'mode': MenuMode.VM_MIC},
            {'name': 'Main Routing', 'mode': MenuMode.VM_MAIN_ROUTING},
            {'name': 'Music Gain', 'mode': MenuMode.VM_MUSIC_GAIN},
            {'name': 'Music Routing', 'mode': MenuMode.VM_MUSIC_ROUTING},
            {'name': 'Comm Gain', 'mode': MenuMode.VM_COMM_GAIN},
            {'name': 'Comm Routing', 'mode': MenuMode.VM_COMM_ROUTING},
        ]

    def on_enter(self, state: AppState):
        state.submenu_index = 0

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Cycle through submenus"""
        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.submenus)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.submenus)

    def on_press(self, state: AppState):
        """Press: Enter selected submenu"""
        submenu = self.submenus[state.submenu_index]
        self.sm.enter_mode(submenu['mode'])

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        total = len(self.submenus)
        prev_idx = (state.submenu_index - 1) % total
        next_idx = (state.submenu_index + 1) % total

        return {
            'left': self.submenus[prev_idx]['name'],
            'center': f"> {self.submenus[state.submenu_index]['name']}",
            'right': self.submenus[next_idx]['name']
        }


class VMMicHandler(ModeHandler):
    """Microphone Gain + Mute control (Strip 0)"""

    def __init__(self, vm_controller):
        self.vm = vm_controller
        self.strip = 0 # Strip 0 is Mic
        self.gain_step = 3.0

    def on_enter(self, state: AppState):
        pass

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Adjust mic gain"""
        if clockwise:
            self.vm.adjust_strip_gain(self.strip, self.gain_step)
        else:
            self.vm.adjust_strip_gain(self.strip, -self.gain_step)

    def on_press(self, state: AppState):
        """Press: Toggle mic mute"""
        self.vm.toggle_mic_mute()

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        gain = round(self.vm.get_strip_gain(self.strip))
        muted = self.vm.get_mic_mute()
        
        # Normalize gain to 0-1 range (-60 to +12 dB)
        progress = (gain + 60) / 72.0

        return {
            'left': 'Gain Down',
            'center': f'{gain} dB',
            'right': 'Gain Up',
            'title': '🎤 MIC MUTED' if muted else '🎤 Microphone',
            'progress': max(0.0, min(1.0, progress)),
            'icons': {'left': '−', 'center': '🔇' if muted else '🎤', 'right': '+'}
        }


class VMRoutingHandler(ModeHandler):
    """Audio routing control (Main/Music/Comm to enabled outputs)."""

    def __init__(self, vm_controller, strip: int, strip_name: str, outputs=None, output_names=None, output_icons=None):
        self.vm = vm_controller
        self.strip = strip
        self.strip_name = strip_name
        self.outputs = list(outputs or ['A1', 'A2', 'A3'])
        default_names = {
            'A1': 'Speakers', 'A2': 'Wired', 'A3': 'Wireless', 'A4': 'Alt 1', 'A5': 'Alt 2',
            'B1': 'Virtual Out 1', 'B2': 'Virtual Out 2', 'B3': 'Virtual Out 3'
        }
        default_icons = {
            'A1': 'SPK', 'A2': 'WIR', 'A3': 'WLS', 'A4': 'A4', 'A5': 'A5',
            'B1': 'B1', 'B2': 'B2', 'B3': 'B3'
        }

        if isinstance(output_names, dict):
            name_map = {str(k).upper(): str(v) for k, v in output_names.items()}
        else:
            provided_names = list(output_names or [])
            name_map = {f"A{i+1}": provided_names[i] for i in range(min(3, len(provided_names)))}

        if isinstance(output_icons, dict):
            icon_map = {str(k).upper(): str(v) for k, v in output_icons.items()}
        else:
            provided_icons = list(output_icons or [])
            icon_map = {f"A{i+1}": provided_icons[i] for i in range(min(3, len(provided_icons)))}

        self.output_names = [name_map.get(out, default_names.get(out, out)) for out in self.outputs]
        self.output_icons = [icon_map.get(out, default_icons.get(out, out)) for out in self.outputs]

    def on_enter(self, state: AppState):
        # Start from first enabled output if available.
        states = [self.vm.get_routing(self.strip, out) for out in self.outputs]
        try:
            state.routing_selection = states.index(True)
        except ValueError:
            state.routing_selection = 0

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Select output"""
        count = len(self.outputs)
        if count <= 0:
            state.routing_selection = 0
            return
        if clockwise:
            state.routing_selection = (state.routing_selection + 1) % count
        else:
            state.routing_selection = (state.routing_selection - 1) % count

    def on_press(self, state: AppState):
        """Press: Toggle selected output"""
        if not self.outputs:
            return
        output = self.outputs[state.routing_selection]
        self.vm.toggle_routing(self.strip, output)

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        if not self.outputs:
            return {
                'left': '',
                'center': 'No outputs enabled',
                'right': '',
                'title': f'{self.strip_name} Routing',
                'active_index': 1
            }
        # Get current routing states
        states = [self.vm.get_routing(self.strip, out) for out in self.outputs]
        count = len(self.outputs)
        state.routing_selection %= count
        prev_idx = (state.routing_selection - 1) % count
        next_idx = (state.routing_selection + 1) % count

        # Show status
        status = "ON" if states[state.routing_selection] else "OFF"

        return {
            'left': self.output_names[prev_idx],
            'center': f"{self.output_names[state.routing_selection]} [{status}]",
            'right': self.output_names[next_idx],
            'title': f'🎚 {self.strip_name} Routing',
            'icons': {
                'left': self.output_icons[prev_idx] if states[prev_idx] else '⊘',
                'center': self.output_icons[state.routing_selection] if states[state.routing_selection] else '⊘',
                'right': self.output_icons[next_idx] if states[next_idx] else '⊘'
            }
        }


class VMGainHandler(ModeHandler):
    """Strip gain control"""

    def __init__(self, vm_controller, strip: int, strip_name: str, icon: str):
        self.vm = vm_controller
        self.strip = strip
        self.strip_name = strip_name
        self.icon = icon
        self.gain_step = 3.0

    def on_enter(self, state: AppState):
        pass

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Adjust gain"""
        if clockwise:
            self.vm.adjust_strip_gain(self.strip, self.gain_step)
        else:
            self.vm.adjust_strip_gain(self.strip, -self.gain_step)

    def on_press(self, state: AppState):
        """Press: Reset gain to 0 dB"""
        self.vm.set_strip_gain(self.strip, 0.0)

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        gain = round(self.vm.get_strip_gain(self.strip))
        # Normalize gain to 0-1 range (assuming -60 to +12 dB range)
        progress = (gain + 60) / 72.0

        return {
            'left': 'Gain Down',
            'center': f'{gain} dB',
            'right': 'Gain Up',
            'title': f'{self.icon} {self.strip_name} Gain',
            'progress': max(0.0, min(1.0, progress)),
            'icons': {'left': '−', 'center': self.icon, 'right': '+'}
        }


import json
import os

# ============================================================================
# THEME SELECTION MODE
# ============================================================================

class ThemeMenuHandler(ModeHandler):
    """Theme submenu selector"""

    def __init__(self, state_machine):
        self.sm = state_machine
        self.submenus = [
            {'name': 'Presets', 'mode': MenuMode.THEME_PRESET},
            {'name': 'Box Color', 'mode': MenuMode.THEME_BOX},
            {'name': 'Accent Color', 'mode': MenuMode.THEME_ACCENT},
            {'name': 'Glow Color', 'mode': MenuMode.THEME_GLOW},
            {'name': 'Text Color', 'mode': MenuMode.THEME_TEXT},
        ]

    def on_enter(self, state: AppState):
        state.submenu_index = 0

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Cycle submenus"""
        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.submenus)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.submenus)

    def on_press(self, state: AppState):
        """Enter selected submenu"""
        submenu = self.submenus[state.submenu_index]
        self.sm.enter_mode(submenu['mode'])

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        total = len(self.submenus)
        prev_idx = (state.submenu_index - 1) % total
        next_idx = (state.submenu_index + 1) % total

        return {
            'left': self.submenus[prev_idx]['name'],
            'center': f"> {self.submenus[state.submenu_index]['name']}",
            'right': self.submenus[next_idx]['name'],
            'title': '🎨 Theme Settings'
        }


class ThemePresetHandler(ModeHandler):
    """Select from available theme presets"""

    def __init__(self, state_machine):
        self.sm = state_machine
        self.themes = []
        self._load_theme_list()

    def _load_theme_list(self):
        """Load available themes from themes.json"""
        import json
        import os
        try:
            theme_file = os.path.join(os.path.dirname(__file__), 'themes.json')
            if os.path.exists(theme_file):
                with open(theme_file, 'r') as f:
                    data = json.load(f)
                    self.themes = list(data.keys())
            else:
                self.themes = ['DARK', 'LIGHT', 'CYBER']
        except:
            self.themes = ['DARK', 'LIGHT', 'CYBER']

    def on_enter(self, state: AppState):
        self._load_theme_list()
        state.submenu_index = 0
        # Try to find current theme index
        # We don't track current theme name in state, so default to 0

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Cycle presets"""
        if not self.themes: return

        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.themes)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.themes)

    def on_press(self, state: AppState):
        """Apply theme and return"""
        theme_name = self.themes[state.submenu_index]
        # set_theme will also trigger save_config via the UI callback
        self.sm.ui_callback({'set_theme': theme_name})
        
        self.sm.show_notification(f"Theme: {theme_name}", 1000)
        from menu_system import MenuMode
        self.sm.enter_mode(MenuMode.THEME_MENU)

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        if not self.themes:
            return {'center': 'No Themes', 'left': '', 'right': '', 'title': 'Error'}

        total = len(self.themes)
        prev_idx = (state.submenu_index - 1) % total
        next_idx = (state.submenu_index + 1) % total
        
        curr_theme = self.themes[state.submenu_index]

        # Preview the theme instantly (Preview only, no save)
        return {
            'left': self.themes[prev_idx],
            'center': f"> {curr_theme}",
            'right': self.themes[next_idx],
            'title': '🎨 Select Theme',
            'preview_theme': curr_theme 
        }


class ThemeColorHandler(ModeHandler):
    """Color picker for theme elements"""

    COLORS = [
        ("White", "#FFFFFF"), ("Red", "#FF0000"), ("Green", "#00FF00"), 
        ("Blue", "#0088FF"), ("Yellow", "#FFFF00"), ("Cyan", "#00FFFF"), 
        ("Magenta", "#FF00FF"), ("Orange", "#FFA500"), ("Purple", "#800080"), 
        ("Black", "#000000"), ("Gray", "#808080"), ("Dark Gray", "#2d2d2d")
    ]

    def __init__(self, color_type: str):
        self.color_type = color_type
        self.current_idx = 0
        self.should_save = False

    def on_enter(self, state: AppState):
        self.current_idx = 0
        self.should_save = False

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Cycle colors"""
        if clockwise:
            self.current_idx = (self.current_idx + 1) % len(self.COLORS)
        else:
            self.current_idx = (self.current_idx - 1) % len(self.COLORS)

    def on_press(self, state: AppState):
        """Confirm and Save"""
        self.should_save = True
        from menu_system import MenuMode
        state.menu_mode = MenuMode.THEME_MENU

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        total = len(self.COLORS)
        prev_idx = (self.current_idx - 1) % total
        next_idx = (self.current_idx + 1) % total
        
        prev_name, _ = self.COLORS[prev_idx]
        curr_name, hex_code = self.COLORS[self.current_idx]
        next_name, _ = self.COLORS[next_idx]
        
        # Build theme update dictionary
        settings = {}
        if self.color_type == 'box':
            settings = {'segment_inactive': hex_code, 'progress_bg': hex_code}
        elif self.color_type == 'accent':
            settings = {
                'segment_active': hex_code, 
                'accent': hex_code, 
                'accent_glow': hex_code,
                'progress_fill': hex_code,
                'border': hex_code,
                'glow': hex_code
            }
        elif self.color_type == 'glow':
            settings = {'glow': hex_code, 'accent_glow': hex_code}
        elif self.color_type == 'text':
            settings = {'text_active': hex_code}

        res = {
            'left': prev_name,
            'center': f"> {curr_name}",
            'right': next_name,
            'title': f'🎨 {self.color_type.title()} Color',
            'set_theme_color': settings
        }

        if self.should_save:
            # We don't know the exact theme name here easily, 
            # but we can save to 'CUSTOM' or the currently active one.
            # For simplicity, let's assume the user is updating the current active theme.
            # In keychron_app.py we can pass the theme name or just have it save the current.
            res['save_theme'] = 'CUSTOM' 
            self.should_save = False
            
        return res


# ============================================================================
# LIGHTING MENU (SignalRGB)
# ============================================================================

class LightingEffectsHandler(ModeHandler):
    """Browse and apply installed SignalRGB effects."""

    def __init__(self, state_machine, signalrgb_controller):
        self.sm = state_machine
        self.srgb = signalrgb_controller
        self.effects = []

    def _load_effects(self, force_refresh: bool = False):
        if not self.srgb:
            self.effects = []
            return
        self.effects = self.srgb.list_effects(force_refresh=force_refresh)

    def on_enter(self, state: AppState):
        self._load_effects(force_refresh=False)
        state.submenu_index = 0

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        if not self.effects:
            return
        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.effects)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.effects)

    def on_press(self, state: AppState):
        if not self.effects and self.srgb:
            self._load_effects(force_refresh=True)
            if not self.effects:
                self.sm.show_notification("No SignalRGB effects found", 1500)
                return

        selected = self.effects[state.submenu_index] if self.effects else None
        if not selected:
            self.sm.show_notification("No SignalRGB effects found", 1500)
            return

        ok = self.srgb.apply_effect(selected.get("id", "")) if self.srgb else False
        if ok:
            self.sm.show_notification(f"Effect: {selected.get('name', 'Applied')}", 1200)
        else:
            self.sm.show_notification("Failed to apply effect", 1800)

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        if not self.effects:
            return {
                "left": "",
                "center": "No effects found",
                "right": "Click to refresh",
                "title": "SignalRGB Effects",
                "active_index": 1,
            }

        total = len(self.effects)
        idx = state.submenu_index % total
        prev_idx = (idx - 1) % total
        next_idx = (idx + 1) % total

        return {
            "left": self.effects[prev_idx]["name"],
            "center": f"> {self.effects[idx]['name']}",
            "right": self.effects[next_idx]["name"],
            "title": "SignalRGB Effects",
            "active_index": 1,
        }


class LightingMenuHandler(ModeHandler):
    """SignalRGB lighting controls."""

    def __init__(self, state_machine, signalrgb_controller):
        self.sm = state_machine
        self.srgb = signalrgb_controller
        self.items = [
            {'name': 'Browse Effects', 'mode': MenuMode.LIGHTING_EFFECTS},
            {'name': 'Open SignalRGB App', 'action': self._open_srgb},
        ]

    def _notify(self, ok: bool, ok_msg: str, fail_msg: str):
        self.sm.show_notification(ok_msg if ok else fail_msg, 1200 if ok else 1800)

    def _open_srgb(self):
        ok = self.srgb.open_signalrgb() if self.srgb else False
        self._notify(ok, "Opening SignalRGB", "SignalRGB app not found")

    def on_enter(self, state: AppState):
        state.submenu_index = 0
        if self.srgb:
            self.srgb.sync_if_signalrgb_mode()

    def on_exit(self, state: AppState):
        if self.srgb:
            self.srgb.sync_if_signalrgb_mode()

    def on_rotation(self, state: AppState, clockwise: bool):
        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.items)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.items)

    def on_press(self, state: AppState):
        item = self.items[state.submenu_index]
        if 'mode' in item:
            self.sm.enter_mode(item['mode'])
            return
        item['action']()

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        total = len(self.items)
        prev_idx = (state.submenu_index - 1) % total
        next_idx = (state.submenu_index + 1) % total
        return {
            'left': self.items[prev_idx]['name'],
            'center': f"> {self.items[state.submenu_index]['name']}",
            'right': self.items[next_idx]['name'],
            'title': "SignalRGB Lighting",
            'active_index': 1
        }


class RecentActionsHandler(ModeHandler):
    """Show and rerun recent actions from main command interactions."""

    def __init__(self, state_machine, provider):
        self.sm = state_machine
        self.provider = provider

    def _items(self):
        if callable(self.provider):
            try:
                items = self.provider()
                return items if isinstance(items, list) else []
            except Exception:
                return []
        return []

    def on_enter(self, state: AppState):
        state.submenu_index = 0

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        items = self._items()
        if not items:
            return
        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(items)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(items)

    def on_press(self, state: AppState):
        items = self._items()
        if not items:
            return
        idx = state.submenu_index % len(items)
        cb = items[idx].get("callback")
        if callable(cb):
            cb()

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        items = self._items()
        if not items:
            return {
                'left': '',
                'center': 'No recent actions',
                'right': '',
                'title': 'Recent Actions',
                'subtitle': 'Use app to build history',
                'active_index': 1,
            }
        total = len(items)
        idx = state.submenu_index % total
        prev_idx = (idx - 1) % total
        next_idx = (idx + 1) % total
        return {
            'left': str(items[prev_idx].get("name", "")),
            'center': f"> {str(items[idx].get('name', ''))}",
            'right': str(items[next_idx].get("name", "")),
            'title': 'Recent Actions',
            'subtitle': 'Press to rerun',
            'active_index': 1,
        }


# ============================================================================
# HANDLER FACTORY
# ============================================================================

def create_handlers(
    api: SystemAPI,
    state_machine,
    vm_controller=None,
    signalrgb_controller=None,
    recent_provider=None,
) -> Dict[MenuMode, ModeHandler]:
    """Create all mode handlers

    Args:
        api: SystemAPI instance
        state_machine: MenuStateMachine instance
        vm_controller: VoicemeeterController instance (optional)

    Returns:
        Dict mapping MenuMode to ModeHandler instance
    """
    handlers = {
        MenuMode.MEDIA: MediaModeHandler(api, state_machine),
        MenuMode.VOLUME: VolumeModeHandler(api),
        MenuMode.VOLUME_MIXER: VolumeMixerModeHandler(api, state_machine),
        MenuMode.RECENT_ACTIONS: RecentActionsHandler(state_machine, recent_provider),
        MenuMode.THEME_MENU: ThemeMenuHandler(state_machine),
        MenuMode.THEME_PRESET: ThemePresetHandler(state_machine),
        MenuMode.THEME_BOX: ThemeColorHandler('box'),
        MenuMode.THEME_ACCENT: ThemeColorHandler('accent'),
        MenuMode.THEME_GLOW: ThemeColorHandler('glow'),
        MenuMode.THEME_TEXT: ThemeColorHandler('text'),
        MenuMode.LIGHTING_MENU: LightingMenuHandler(state_machine, signalrgb_controller),
        MenuMode.LIGHTING_EFFECTS: LightingEffectsHandler(state_machine, signalrgb_controller),
        MenuMode.WINDOW_MENU: WindowMenuHandler(state_machine),
        MenuMode.WINDOW_CYCLE: WindowCycleHandler(api),
        MenuMode.WINDOW_SNAP: WindowSnapHandler(api, state_machine),
    }

    # Add Voicemeeter handlers if available
    if vm_controller and vm_controller.is_available():
        config = vm_controller.config
        outputs = list(getattr(config, "ACTIVE_OUTPUTS", ["A1", "A2", "A3"]))
        out_names = getattr(config, "OUTPUT_NAMES", {"A1": "Speakers", "A2": "Wired", "A3": "Wireless"})
        out_icons = getattr(config, "OUTPUT_ICONS", {"A1": "SPK", "A2": "WIR", "A3": "WLS"})

        handlers.update({
            MenuMode.VOICEMEETER_MENU: VoicemeeterMenuHandler(state_machine, vm_controller),
            MenuMode.VM_MIC: VMMicHandler(vm_controller),
            MenuMode.VM_MAIN_ROUTING: VMRoutingHandler(vm_controller, config.MAIN_STRIP, "Main", outputs, out_names, out_icons),
            MenuMode.VM_MUSIC_GAIN: VMGainHandler(vm_controller, config.MUSIC_STRIP, "Music", "🎵"),
            MenuMode.VM_MUSIC_ROUTING: VMRoutingHandler(vm_controller, config.MUSIC_STRIP, "Music", outputs, out_names, out_icons),
            MenuMode.VM_COMM_GAIN: VMGainHandler(vm_controller, config.COMM_STRIP, "Comm", "💬"),
            MenuMode.VM_COMM_ROUTING: VMRoutingHandler(vm_controller, config.COMM_STRIP, "Comm", outputs, out_names, out_icons),
        })

    return handlers





