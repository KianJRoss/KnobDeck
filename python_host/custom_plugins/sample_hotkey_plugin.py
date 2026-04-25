"""Example custom plugin loaded from python_host/custom_plugins."""

import subprocess


def get_commands():
    def open_calculator():
        subprocess.Popen(["calc.exe"], shell=False)

    return [
        {
            "name": "Open Calculator",
            "description": "Sample custom plugin command",
            "callback": open_calculator,
        }
    ]
