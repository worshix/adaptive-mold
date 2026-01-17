"""Entry point for Adaptive Mold application."""

import sys

from loguru import logger
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor

from adaptive_mold.app.main_window import MainWindow
from adaptive_mold.app.welcome_screen import WelcomeScreen
from adaptive_mold.models.db import init_database


class ApplicationWindow(QMainWindow):
    """Main application window with welcome screen and main interface."""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Adaptive Mold - Precision Path Mapping System")
        self.setMinimumSize(1200, 800)
        
        # Stacked widget to switch between welcome and main screens
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # Create welcome screen
        self.welcome_screen = WelcomeScreen(on_start_callback=self._show_main_window)
        self.stack.addWidget(self.welcome_screen)
        
        # Main window will be created when needed
        self.main_window_widget = None
    
    def _show_main_window(self):
        """Switch from welcome screen to main application."""
        if self.main_window_widget is None:
            # Create the main window content
            self.main_window_widget = MainWindow()
            self.stack.addWidget(self.main_window_widget)
        
        # Switch to main window
        self.stack.setCurrentWidget(self.main_window_widget)
        logger.info("Switched to main application window")
    
    def closeEvent(self, event):
        """Handle window close."""
        if self.main_window_widget:
            self.main_window_widget.close()
        super().closeEvent(event)


def set_dark_palette(app: QApplication):
    """Apply a dark color palette to the application."""
    palette = QPalette()
    
    # Base colors
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 40))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(35, 35, 45))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(40, 40, 50))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 55))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 170, 255))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 200))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    
    # Disabled colors
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(120, 120, 120))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(120, 120, 120))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(120, 120, 120))
    
    app.setPalette(palette)


def main() -> int:
    """Main entry point."""
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    logger.info("Starting Adaptive Mold application")
    
    # Initialize database
    init_database()
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Adaptive Mold")
    app.setOrganizationName("AdaptiveMold")
    
    # Apply dark style
    app.setStyle("Fusion")
    set_dark_palette(app)
    
    # Create and show application window with welcome screen
    window = ApplicationWindow()
    window.show()
    
    logger.info("Application started")
    
    # Run event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
