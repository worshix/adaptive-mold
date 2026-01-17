"""Entry point for Adaptive Mold application."""

import sys

from loguru import logger
from PySide6.QtWidgets import QApplication

from adaptive_mold.app.main_window import MainWindow
from adaptive_mold.models.db import init_database


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
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    logger.info("Application started")
    
    # Run event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
