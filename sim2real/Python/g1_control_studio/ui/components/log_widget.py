from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QPlainTextEdit, QLabel
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor

from ui.styles.theme import PALETTE


_LEVEL_COLORS = {
    "INFO":    PALETTE["TEXT_SEC"],
    "OK":      PALETTE["SUCCESS"],
    "WARN":    PALETTE["WARNING"],
    "ERROR":   PALETTE["DANGER"],
    "DEBUG":   PALETTE["TEXT_MUTED"],
    "SYSTEM":  PALETTE["ACCENT"],
}


class LogWidget(QWidget):
    """
    Filtered log console with color-coded severity levels.

    Supports auto-scroll, clear, and copy buttons.
    Max lines are enforced to prevent unbounded memory growth.
    """

    def __init__(self, title: str = "LOGS", max_lines: int = 2000, parent=None) -> None:
        super().__init__(parent)
        self._max_lines = max_lines
        self._auto_scroll = True
        self._line_count = 0
        self._build_ui(title)

    def _build_ui(self, title: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("section-header")
        toolbar.addWidget(title_lbl)
        toolbar.addStretch()

        self._scroll_btn = QPushButton("Auto-scroll: ON")
        self._scroll_btn.setObjectName("")
        self._scroll_btn.setProperty("class", "ghost")
        self._scroll_btn.setFixedHeight(26)
        self._scroll_btn.clicked.connect(self._toggle_scroll)
        toolbar.addWidget(self._scroll_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("class", "ghost")
        clear_btn.setFixedHeight(26)
        clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        # Log area
        self._text = QPlainTextEdit()
        self._text.setObjectName("log-console")
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._text)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @Slot(str, str)
    def append(self, level: str, message: str) -> None:
        """
        Append a colored log line.

        level: 'INFO', 'WARN', 'ERROR', 'OK', 'DEBUG', 'SYSTEM'
        """
        color = _LEVEL_COLORS.get(level.upper(), PALETTE["TEXT_SEC"])
        prefix = f"[{level.upper():<6}]"

        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(f"{prefix} {message}\n", fmt)

        self._line_count += 1
        if self._line_count > self._max_lines:
            self._trim()

        if self._auto_scroll:
            self._text.ensureCursorVisible()
            sb = self._text.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())

    @Slot(str)
    def append_line(self, line: str) -> None:
        """Auto-detect level from common prefixes, then append."""
        line_lower = line.lower()
        if any(k in line_lower for k in ("error", "fatal", "critical")):
            self.append("ERROR", line)
        elif any(k in line_lower for k in ("warn", "warning")):
            self.append("WARN", line)
        elif any(k in line_lower for k in ("[ok]", "success", "started")):
            self.append("OK", line)
        else:
            self.append("INFO", line)

    def clear(self) -> None:
        self._text.clear()
        self._line_count = 0

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _toggle_scroll(self) -> None:
        self._auto_scroll = not self._auto_scroll
        label = "Auto-scroll: ON" if self._auto_scroll else "Auto-scroll: OFF"
        self._scroll_btn.setText(label)

    def _trim(self) -> None:
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        remove = self._max_lines // 4
        for _ in range(remove):
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
        self._line_count -= remove
