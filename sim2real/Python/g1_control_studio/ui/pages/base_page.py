from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame
from PySide6.QtCore import Qt

from ui.styles.theme import PALETTE


class BasePage(QWidget):
    """
    Base class for all pages.

    Provides a standard page header (title + description) and a
    content area below it. Subclasses call `self._content_layout`
    to add their widgets.
    """

    PAGE_KEY: str = ""
    PAGE_TITLE: str = ""
    PAGE_DESCRIPTION: str = ""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("page-container")
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(32, 28, 32, 24)
        self._outer_layout.setSpacing(0)
        self._build_header()
        self._build_separator()
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 20, 0, 0)
        self._content_layout.setSpacing(16)
        self._outer_layout.addLayout(self._content_layout)

    def _build_header(self) -> None:
        header = QHBoxLayout()
        header.setSpacing(0)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        title = QLabel(self.PAGE_TITLE)
        title.setObjectName("page-title")
        text_col.addWidget(title)

        if self.PAGE_DESCRIPTION:
            desc = QLabel(self.PAGE_DESCRIPTION)
            desc.setObjectName("page-description")
            desc.setWordWrap(True)
            text_col.addWidget(desc)

        header.addLayout(text_col)
        header.addStretch()
        self._build_header_actions(header)

        self._outer_layout.addLayout(header)

    def _build_header_actions(self, header_layout: QHBoxLayout) -> None:
        """Override to add action buttons to the page header."""
        pass

    def _build_separator(self) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            f"background-color: {PALETTE['BORDER']}; max-height: 1px; margin-top: 16px;"
        )
        self._outer_layout.addWidget(sep)
