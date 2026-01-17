"""UI helper utilities."""

from typing import Optional

from PySide6.QtWidgets import QMessageBox, QWidget


def show_error(parent: Optional[QWidget], title: str, message: str) -> None:
    """Show an error message box."""
    QMessageBox.critical(parent, title, message)


def show_warning(parent: Optional[QWidget], title: str, message: str) -> None:
    """Show a warning message box."""
    QMessageBox.warning(parent, title, message)


def show_info(parent: Optional[QWidget], title: str, message: str) -> None:
    """Show an info message box."""
    QMessageBox.information(parent, title, message)


def confirm(parent: Optional[QWidget], title: str, message: str) -> bool:
    """Show a confirmation dialog.
    
    Returns:
        True if user clicked Yes
    """
    result = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    return result == QMessageBox.StandardButton.Yes
