"""
Context-Aware Commands Plugin
Shows commands relevant to the active application
"""

import logging
from context_aware import context_manager, ContextCommand
from menu_system import ModeHandler, AppState, MenuMode
from typing import Dict, List

logger = logging.getLogger("KnobDeck.ContextCommands")

_state_machine = None


class ContextMenuHandler(ModeHandler):
    """Show context-specific commands"""

    def __init__(self, state_machine):
        self.sm = state_machine
        self.commands: List[ContextCommand] = []
        self.app_name = ""

    def on_enter(self, state: AppState):
        """Refresh commands when entering mode"""
        state.submenu_index = 0

        # Get contextual commands
        self.commands = context_manager.get_contextual_commands()
        self.app_name = context_manager.get_current_app_name() or "Application"

        if not self.commands:
            self.sm.show_notification("No contextual commands available", 2000)
            self.sm.exit_menu_mode()

        logger.info(f"Showing {len(self.commands)} context commands for {self.app_name}")

    def on_exit(self, state: AppState):
        self.commands = []

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Select command"""
        if not self.commands:
            return

        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.commands)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.commands)

    def on_press(self, state: AppState):
        """Press: Execute command"""
        if not self.commands or state.submenu_index >= len(self.commands):
            return

        command = self.commands[state.submenu_index]

        try:
            command.callback()
            self.sm.show_notification(f"Executed: {command.name}", 1500)
            # Stay in menu for quick successive commands
        except Exception as e:
            logger.error(f"Error executing context command: {e}")
            self.sm.show_notification(f"Error: {e}", 2000)

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        if not self.commands:
            return {
                'left': '',
                'center': 'No commands',
                'right': '',
                'title': '⚠️ Context Menu'
            }

        if len(self.commands) == 1:
            cmd = self.commands[0]
            return {
                'left': '',
                'center': f"▶ {cmd.name}",
                'right': '',
                'title': f'📱 {self.app_name}',
                'subtitle': cmd.description,
                'icons': {'center': cmd.icon} if cmd.icon else {}
            }

        # Multiple commands
        total = len(self.commands)
        prev_idx = (state.submenu_index - 1) % total
        next_idx = (state.submenu_index + 1) % total

        prev_cmd = self.commands[prev_idx]
        curr_cmd = self.commands[state.submenu_index]
        next_cmd = self.commands[next_idx]

        # Strip emoji prefixes for cleaner display
        def clean_name(name: str) -> str:
            parts = name.split(maxsplit=1)
            if len(parts) > 1:
                return parts[1]
            return name

        return {
            'left': clean_name(prev_cmd.name),
            'center': f"▶ {clean_name(curr_cmd.name)}",
            'right': clean_name(next_cmd.name),
            'title': f'📱 {self.app_name}',
            'subtitle': curr_cmd.description[:30],
            'icons': {
                'left': prev_cmd.icon or '',
                'center': curr_cmd.icon or '',
                'right': next_cmd.icon or ''
            }
        }


# Plugin interface
def get_commands():
    """Return commands to register"""
    return [
        {
            "name": "Context Commands",
            "description": "App-specific shortcuts",
            "callback": _enter_context_menu
        }
    ]


def get_mode_handlers(state_machine):
    """Return mode handlers"""
    global _state_machine
    _state_machine = state_machine

    return {
        MenuMode.CONTEXT_MENU: ContextMenuHandler(state_machine)
    }


def _enter_context_menu():
    """Enter context menu mode"""
    if _state_machine:
        _state_machine.enter_mode(MenuMode.CONTEXT_MENU)
