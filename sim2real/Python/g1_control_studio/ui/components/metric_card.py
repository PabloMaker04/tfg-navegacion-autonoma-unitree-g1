from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt

from ui.styles.theme import PALETTE


class MetricCard(QWidget):
    """
    A display card with a title, a large value, optional unit, and an optional
    status indicator dot.

    Usage:
        card = MetricCard("LIDAR STATUS", "Active", status="ok")
        card = MetricCard("MAPPING TIME", "02:34", unit="min")
    """

    _DOT_COLORS = {
        "ok":       PALETTE["SUCCESS"],
        "warning":  PALETTE["WARNING"],
        "error":    PALETTE["DANGER"],
        "inactive": PALETTE["TEXT_MUTED"],
        "info":     PALETTE["ACCENT"],
        "running":  PALETTE["ACCENT_GLOW"],
    }

    def __init__(
        self,
        title: str,
        value: str = "—",
        unit: str = "",
        status: str = "inactive",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._build_ui(title, value, unit, status)

    def _build_ui(self, title: str, value: str, unit: str, status: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        # Header row: title + status dot
        header = QHBoxLayout()
        header.setSpacing(6)

        self._title_lbl = QLabel(title.upper())
        self._title_lbl.setObjectName("card-title")
        header.addWidget(self._title_lbl)
        header.addStretch()

        self._dot = QLabel("●")
        self._dot.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._dot.setFixedWidth(16)
        self._set_dot_color(status)
        header.addWidget(self._dot)

        layout.addLayout(header)

        # Value row
        value_row = QHBoxLayout()
        value_row.setSpacing(6)
        value_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._value_lbl = QLabel(value)
        self._value_lbl.setObjectName("card-value")
        value_row.addWidget(self._value_lbl)

        if unit:
            unit_lbl = QLabel(unit)
            unit_lbl.setObjectName("card-unit")
            unit_lbl.setAlignment(Qt.AlignmentFlag.AlignBottom)
            value_row.addWidget(unit_lbl)
        value_row.addStretch()

        layout.addLayout(value_row)

    def set_value(self, value: str) -> None:
        self._value_lbl.setText(value)

    def set_status(self, status: str) -> None:
        self._set_dot_color(status)

    def _set_dot_color(self, status: str) -> None:
        color = self._DOT_COLORS.get(status, self._DOT_COLORS["inactive"])
        self._dot.setStyleSheet(f"QLabel {{ color: {color}; background: transparent; }}")
