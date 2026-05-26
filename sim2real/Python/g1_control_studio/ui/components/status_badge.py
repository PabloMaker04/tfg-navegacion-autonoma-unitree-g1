from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt

from ui.styles.theme import PALETTE


class StatusBadge(QLabel):
    """
    Colored pill badge for status indicators.

    States: 'ok', 'warning', 'error', 'inactive', 'info', 'running'
    """

    _BG = {
        "ok":       ("#0B2820", PALETTE["SUCCESS"]),
        "warning":  ("#3D2A00", PALETTE["WARNING"]),
        "error":    ("#2D1010", PALETTE["DANGER"]),
        "inactive": ("#1A1F2E", PALETTE["TEXT_MUTED"]),
        "info":     ("#0D1535", PALETTE["ACCENT"]),
        "running":  ("#0A2030", PALETTE["ACCENT_GLOW"]),
    }

    def __init__(self, text: str = "", state: str = "inactive", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("badge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state(state, text)

    def set_state(self, state: str, text: str | None = None) -> None:
        self._state = state
        if text is not None:
            self.setText(text)
        bg, fg = self._BG.get(state, self._BG["inactive"])
        self.setStyleSheet(
            f"QLabel#badge {{"
            f"  background-color: {bg};"
            f"  color: {fg};"
            f"  border: 1px solid {fg};"
            f"  border-radius: 10px;"
            f"  padding: 3px 10px;"
            f"  font-size: 11px;"
            f"  font-weight: 600;"
            f"}}"
        )
