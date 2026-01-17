"""Welcome screen for Adaptive Mold application.

Displays project information and provides entry point to the main application.
"""

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property, QTimer
from PySide6.QtGui import QFont, QLinearGradient, QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QGraphicsDropShadowEffect,
    QSizePolicy,
)


class AnimatedButton(QPushButton):
    """Animated button with hover effects."""
    
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._animation_value = 0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Animation for pulse effect
        self._pulse_animation = QPropertyAnimation(self, b"pulse_value")
        self._pulse_animation.setDuration(1500)
        self._pulse_animation.setStartValue(0)
        self._pulse_animation.setEndValue(100)
        self._pulse_animation.setLoopCount(-1)
        self._pulse_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_animation.start()
    
    def get_pulse_value(self):
        return self._animation_value
    
    def set_pulse_value(self, value):
        self._animation_value = value
        self.update()
    
    pulse_value = Property(int, get_pulse_value, set_pulse_value)


class GlowingFrame(QFrame):
    """Frame with animated glowing border."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 150, 255, 100))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)


class WelcomeScreen(QWidget):
    """Welcome screen with project information."""
    
    def __init__(self, on_start_callback, parent=None):
        super().__init__(parent)
        self.on_start_callback = on_start_callback
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the welcome screen UI."""
        self.setMinimumSize(900, 700)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Background widget
        bg_widget = QWidget()
        bg_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0a0a1a,
                    stop: 0.3 #0d1f3c,
                    stop: 0.6 #1a1a3e,
                    stop: 1 #0a0a1a
                );
            }
        """)
        
        bg_layout = QVBoxLayout(bg_widget)
        bg_layout.setContentsMargins(60, 50, 60, 50)
        bg_layout.setSpacing(20)
        
        # Top decorative line
        top_line = QFrame()
        top_line.setFixedHeight(3)
        top_line.setStyleSheet("""
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 0,
                stop: 0 transparent,
                stop: 0.2 #00aaff,
                stop: 0.5 #00ffaa,
                stop: 0.8 #00aaff,
                stop: 1 transparent
            );
        """)
        bg_layout.addWidget(top_line)
        
        bg_layout.addStretch(1)
        
        # Header section with icon/logo area
        header_frame = GlowingFrame()
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(15)
        
        # Logo/Icon representation (using text art for now)
        logo_label = QLabel("⬡")  # Hexagon as logo
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("""
            QLabel {
                font-size: 72px;
                color: #00aaff;
                padding: 10px;
            }
        """)
        header_layout.addWidget(logo_label)
        
        # Title
        title_label = QLabel("ADAPTIVE MOLD")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 48px;
                font-weight: bold;
                color: #ffffff;
                letter-spacing: 8px;
                padding: 5px;
            }
        """)
        header_layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Precision Path Mapping System")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #00ddff;
                letter-spacing: 3px;
                font-weight: 300;
            }
        """)
        header_layout.addWidget(subtitle_label)
        
        bg_layout.addWidget(header_frame)
        
        bg_layout.addSpacing(30)
        
        # Description card
        desc_frame = QFrame()
        desc_frame.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(0, 170, 255, 0.3);
                border-radius: 15px;
                padding: 25px;
            }
        """)
        desc_layout = QVBoxLayout(desc_frame)
        desc_layout.setSpacing(15)
        
        # Project description
        desc_title = QLabel("About This Project")
        desc_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #00aaff;
                padding-bottom: 10px;
            }
        """)
        desc_layout.addWidget(desc_title)
        
        description_text = """
        <p style='text-align: center; line-height: 1.8; color: #cccccc; font-size: 14px;'>
        <b>Adaptive Mold</b> is a desktop application designed for loading and processing 
        CAD geometry from STEP files, visualizing 3D wireframe models, and computing 
        optimal mapping paths for CNC and robotic applications.
        </p>
        <p style='text-align: center; line-height: 1.8; color: #aaaaaa; font-size: 13px;'>
        The system extracts precise vertex and edge data using OpenCASCADE technology, 
        applies intelligent path planning algorithms, and communicates waypoint sequences 
        to hardware controllers via serial protocol for automated surface mapping operations.
        </p>
        """
        
        desc_label = QLabel(description_text)
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("background: transparent; border: none;")
        desc_layout.addWidget(desc_label)
        
        bg_layout.addWidget(desc_frame)
        
        bg_layout.addSpacing(20)
        
        # Credits section
        credits_frame = QFrame()
        credits_frame.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)
        credits_layout = QHBoxLayout(credits_frame)
        credits_layout.setSpacing(80)
        
        # Student info
        student_card = self._create_person_card(
            "Student",
            "Joseph B Mawodzeka",
            "🎓"
        )
        credits_layout.addWidget(student_card)
        
        # Divider
        divider = QFrame()
        divider.setFixedWidth(2)
        divider.setStyleSheet("""
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 transparent,
                stop: 0.3 #00aaff,
                stop: 0.7 #00aaff,
                stop: 1 transparent
            );
        """)
        credits_layout.addWidget(divider)
        
        # Supervisor info
        supervisor_card = self._create_person_card(
            "Supervisor",
            "Worship L Mugomeza",
            "👨‍🏫"
        )
        credits_layout.addWidget(supervisor_card)
        
        bg_layout.addWidget(credits_frame)
        
        bg_layout.addStretch(1)
        
        # Start button
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 20, 0, 20)
        
        self.start_button = AnimatedButton("▶  START APPLICATION")
        self.start_button.setFixedSize(300, 60)
        self.start_button.clicked.connect(self._on_start_clicked)
        self.start_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #0066aa,
                    stop: 0.5 #0088cc,
                    stop: 1 #0066aa
                );
                color: white;
                font-size: 16px;
                font-weight: bold;
                letter-spacing: 2px;
                border: 2px solid #00aaff;
                border-radius: 30px;
                padding: 15px 40px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #0088cc,
                    stop: 0.5 #00aaee,
                    stop: 1 #0088cc
                );
                border: 2px solid #00ddff;
            }
            QPushButton:pressed {
                background: #004488;
            }
        """)
        
        # Add glow effect to button
        button_shadow = QGraphicsDropShadowEffect()
        button_shadow.setBlurRadius(25)
        button_shadow.setColor(QColor(0, 150, 255, 150))
        button_shadow.setOffset(0, 0)
        self.start_button.setGraphicsEffect(button_shadow)
        
        button_layout.addStretch()
        button_layout.addWidget(self.start_button)
        button_layout.addStretch()
        
        bg_layout.addWidget(button_container)
        
        # Bottom decorative line
        bottom_line = QFrame()
        bottom_line.setFixedHeight(3)
        bottom_line.setStyleSheet("""
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 0,
                stop: 0 transparent,
                stop: 0.2 #00aaff,
                stop: 0.5 #00ffaa,
                stop: 0.8 #00aaff,
                stop: 1 transparent
            );
        """)
        bg_layout.addWidget(bottom_line)
        
        # Footer
        footer_label = QLabel("© 2026 - Final Year Project - Engineering Department")
        footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #666666;
                padding-top: 15px;
            }
        """)
        bg_layout.addWidget(footer_label)
        
        main_layout.addWidget(bg_widget)
    
    def _create_person_card(self, role: str, name: str, icon: str) -> QWidget:
        """Create a card for displaying person info."""
        card = QWidget()
        card.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 36px;")
        layout.addWidget(icon_label)
        
        # Role
        role_label = QLabel(role.upper())
        role_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        role_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #00aaff;
                letter-spacing: 2px;
                font-weight: bold;
            }
        """)
        layout.addWidget(role_label)
        
        # Name
        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                color: #ffffff;
                font-weight: 500;
            }
        """)
        layout.addWidget(name_label)
        
        return card
    
    def _on_start_clicked(self):
        """Handle start button click."""
        if self.on_start_callback:
            self.on_start_callback()
