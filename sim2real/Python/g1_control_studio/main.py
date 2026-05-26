#!/usr/bin/env python3
"""
G1 Control Studio — entry point.

Usage:
    python3 main.py

Requirements:
    pip install PySide6
"""
import sys
import os
from pathlib import Path

# Make the project root importable regardless of where the script is run from
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# Also add the SDK parent directory so unitree_sdk2py can be imported later
_SDK_ROOT = _HERE.parent
if str(_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(_SDK_ROOT))


def _check_dependencies() -> None:
    try:
        import PySide6  # noqa: F401
    except ImportError:
        print(
            "ERROR: PySide6 is not installed.\n"
            "Install it with:  pip install PySide6\n"
        )
        sys.exit(1)


def main() -> None:
    _check_dependencies()

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    from config.app_config import AppConfig
    from ui.main_window import MainWindow

    # High-DPI support
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("G1 Control Studio")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Unitree Robotics")

    config = AppConfig.load()
    window = MainWindow(config)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()