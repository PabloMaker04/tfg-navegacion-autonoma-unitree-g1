from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel,
)
from PySide6.QtCore import Slot

from core.process_manager import ProcessManager
from ui.pages.base_page import BasePage
from ui.components.log_widget import LogWidget
from ui.styles.theme import PALETTE


class LogsPage(BasePage):
    PAGE_KEY = "logs"
    PAGE_TITLE = "Logs"
    PAGE_DESCRIPTION = "Filtered output from all managed processes."

    def __init__(self, process_manager: ProcessManager, parent=None) -> None:
        self._pm = process_manager
        super().__init__(parent)
        self._populate()
        self._connect_signals()

    def _populate(self) -> None:
        # Filter bar
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        filter_lbl = QLabel("Process:")
        filter_lbl.setStyleSheet(f"color: {PALETTE['TEXT_SEC']}; font-size: 13px;")
        filter_row.addWidget(filter_lbl)

        self._proc_filter = QComboBox()
        self._proc_filter.addItem("All processes", "")
        self._proc_filter.setFixedWidth(200)
        filter_row.addWidget(self._proc_filter)
        filter_row.addStretch()

        filter_widget = QWidget()
        filter_widget.setLayout(filter_row)
        self._content_layout.addWidget(filter_widget)

        # Log widget
        self._log = LogWidget("ALL LOGS", max_lines=5000)
        self._content_layout.addWidget(self._log, 1)

    def _connect_signals(self) -> None:
        self._pm.stdout_line.connect(self._on_line)
        self._pm.stderr_line.connect(self._on_err_line)
        self._pm.process_started.connect(self._on_proc_started)
        self._pm.process_stopped.connect(self._on_proc_stopped)
        self._pm.error_occurred.connect(self._on_proc_error)

    @Slot(str, str)
    def _on_line(self, key: str, line: str) -> None:
        if self._should_show(key):
            self._log.append_line(f"[{key}] {line}")

    @Slot(str, str)
    def _on_err_line(self, key: str, line: str) -> None:
        if self._should_show(key):
            self._log.append("WARN", f"[{key}] {line}")

    @Slot(str)
    def _on_proc_started(self, key: str) -> None:
        self._log.append("SYSTEM", f"Process started: {key}")
        self._add_filter_option(key)

    @Slot(str, int)
    def _on_proc_stopped(self, key: str, code: int) -> None:
        level = "OK" if code == 0 else "WARN"
        self._log.append(level, f"Process stopped: {key} (exit code {code})")

    @Slot(str, str)
    def _on_proc_error(self, key: str, message: str) -> None:
        self._log.append("ERROR", f"[{key}] {message}")

    def _should_show(self, key: str) -> bool:
        current_filter = self._proc_filter.currentData()
        return not current_filter or current_filter == key

    def _add_filter_option(self, key: str) -> None:
        for i in range(self._proc_filter.count()):
            if self._proc_filter.itemData(i) == key:
                return
        self._proc_filter.addItem(key.replace("_", " ").title(), key)
