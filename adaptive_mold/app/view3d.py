"""3D wireframe visualization widget using OpenGL.

Provides a simple 3D view with rotate/pan/zoom for wireframe geometry.
"""

import math
from typing import Optional

import numpy as np
from loguru import logger
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QWheelEvent
from PySide6.QtWidgets import QWidget

try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    from OpenGL import GL
    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False
    logger.warning("OpenGL not available, using fallback 2D view")


class View3DWidget(QWidget):
    """3D wireframe view widget.
    
    Uses OpenGL if available, otherwise falls back to a simple 2D projection.
    """
    
    # Signal emitted when a vertex is clicked (vertex_index)
    vertex_clicked = Signal(int)
    # Signal emitted when hovering over a vertex (vertex_index or -1)
    vertex_hovered = Signal(int)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Geometry data
        self._vertices: np.ndarray = np.array([]).reshape(0, 3)
        self._edges: np.ndarray = np.array([]).reshape(0, 2)
        self._visited: set[int] = set()  # Visited vertex indices
        self._path: list[int] = []  # Path order (indices into vertices)
        
        # Camera state
        self._rotation_x = 30.0  # degrees
        self._rotation_y = 45.0  # degrees
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        
        # Interaction state
        self._last_pos = QPoint()
        self._dragging = False
        self._panning = False
        
        # Colors
        self._edge_color = QColor(100, 100, 200)
        self._vertex_color = QColor(50, 50, 150)
        self._visited_color = QColor(200, 50, 50)
        self._path_color = QColor(50, 200, 50)
        self._background_color = QColor(30, 30, 40)
        
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def set_geometry(
        self,
        vertices: np.ndarray,
        edges: np.ndarray
    ) -> None:
        """Set the geometry to display.
        
        Args:
            vertices: (N, 3) array of vertex positions
            edges: (M, 2) array of vertex index pairs
        """
        self._vertices = vertices.astype(np.float64)
        self._edges = edges.astype(np.int64)
        self._visited.clear()
        self._path.clear()
        self._auto_fit()
        self.update()
    
    def clear_geometry(self) -> None:
        """Clear all geometry."""
        self._vertices = np.array([]).reshape(0, 3)
        self._edges = np.array([]).reshape(0, 2)
        self._visited.clear()
        self._path.clear()
        self.update()
    
    def set_path(self, path_indices: list[int]) -> None:
        """Set the path to display.
        
        Args:
            path_indices: Ordered list of vertex indices forming the path
        """
        self._path = path_indices
        self.update()
    
    def mark_visited(self, vertex_index: int) -> None:
        """Mark a vertex as visited.
        
        Args:
            vertex_index: Index of vertex to mark
        """
        self._visited.add(vertex_index)
        self.update()
    
    def mark_position_visited(self, position: tuple[float, float, float], tolerance: float = 1.0) -> None:
        """Mark the nearest vertex to a position as visited.
        
        Args:
            position: (x, y, z) position
            tolerance: Maximum distance to match
        """
        if len(self._vertices) == 0:
            return
        
        pos = np.array(position)
        distances = np.linalg.norm(self._vertices - pos, axis=1)
        min_idx = np.argmin(distances)
        
        if distances[min_idx] <= tolerance:
            self.mark_visited(int(min_idx))
    
    def clear_visited(self) -> None:
        """Clear visited markers."""
        self._visited.clear()
        self.update()
    
    def reset_view(self) -> None:
        """Reset camera to default view."""
        self._rotation_x = 30.0
        self._rotation_y = 45.0
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._auto_fit()
        self.update()
    
    def _auto_fit(self) -> None:
        """Auto-fit view to geometry."""
        if len(self._vertices) == 0:
            return
        
        # Compute bounding box
        min_pt = self._vertices.min(axis=0)
        max_pt = self._vertices.max(axis=0)
        size = max_pt - min_pt
        max_dim = max(size) if max(size) > 0 else 1.0
        
        # Adjust zoom to fit
        self._zoom = 200.0 / max_dim
    
    def _project_point(self, point: np.ndarray) -> tuple[float, float]:
        """Project a 3D point to 2D screen coordinates.
        
        Args:
            point: 3D point (x, y, z)
            
        Returns:
            (screen_x, screen_y)
        """
        # Center geometry
        if len(self._vertices) > 0:
            center = (self._vertices.min(axis=0) + self._vertices.max(axis=0)) / 2
            p = point - center
        else:
            p = point.copy()
        
        # Apply rotation (simple Euler rotation)
        rx = math.radians(self._rotation_x)
        ry = math.radians(self._rotation_y)
        
        # Rotate around Y
        cos_y, sin_y = math.cos(ry), math.sin(ry)
        x = p[0] * cos_y + p[2] * sin_y
        z = -p[0] * sin_y + p[2] * cos_y
        y = p[1]
        
        # Rotate around X
        cos_x, sin_x = math.cos(rx), math.sin(rx)
        y2 = y * cos_x - z * sin_x
        # z2 = y * sin_x + z * cos_x  # Not needed for projection
        
        # Apply zoom and pan
        screen_x = x * self._zoom + self.width() / 2 + self._pan_x
        screen_y = -y2 * self._zoom + self.height() / 2 + self._pan_y
        
        return screen_x, screen_y
    
    def paintEvent(self, event) -> None:
        """Paint the 3D view."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), self._background_color)
        
        if len(self._vertices) == 0:
            # Draw placeholder text
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "No geometry loaded\n\nCreate a new job to load geometry"
            )
            return
        
        # Draw edges
        painter.setPen(self._edge_color)
        for edge in self._edges:
            v1, v2 = self._vertices[edge[0]], self._vertices[edge[1]]
            p1 = self._project_point(v1)
            p2 = self._project_point(v2)
            painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))
        
        # Draw path (if set)
        if len(self._path) > 1:
            painter.setPen(self._path_color)
            for i in range(len(self._path) - 1):
                v1 = self._vertices[self._path[i]]
                v2 = self._vertices[self._path[i + 1]]
                p1 = self._project_point(v1)
                p2 = self._project_point(v2)
                painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))
        
        # Draw vertices
        vertex_radius = 4
        for i, vertex in enumerate(self._vertices):
            p = self._project_point(vertex)
            
            if i in self._visited:
                painter.setBrush(self._visited_color)
                painter.setPen(self._visited_color)
            else:
                painter.setBrush(self._vertex_color)
                painter.setPen(self._vertex_color)
            
            painter.drawEllipse(
                int(p[0] - vertex_radius),
                int(p[1] - vertex_radius),
                vertex_radius * 2,
                vertex_radius * 2
            )
        
        # Draw info overlay
        painter.setPen(QColor(200, 200, 200))
        info_text = f"Vertices: {len(self._vertices)} | Edges: {len(self._edges)} | Visited: {len(self._visited)}"
        painter.drawText(10, 20, info_text)
        
        if len(self._vertices) > 0:
            min_pt = self._vertices.min(axis=0)
            max_pt = self._vertices.max(axis=0)
            size = max_pt - min_pt
            bbox_text = f"Size: {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f}"
            painter.drawText(10, 40, bbox_text)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for rotation/panning."""
        self._last_pos = event.position().toPoint()
        
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
        elif event.button() == Qt.MouseButton.RightButton:
            self._panning = True
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        self._dragging = False
        self._panning = False
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for rotation/panning."""
        pos = event.position().toPoint()
        dx = pos.x() - self._last_pos.x()
        dy = pos.y() - self._last_pos.y()
        
        if self._dragging:
            # Rotate
            self._rotation_y += dx * 0.5
            self._rotation_x += dy * 0.5
            self._rotation_x = max(-90, min(90, self._rotation_x))
            self.update()
        elif self._panning:
            # Pan
            self._pan_x += dx
            self._pan_y += dy
            self.update()
        
        self._last_pos = pos
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        self._zoom *= factor
        self._zoom = max(0.1, min(100, self._zoom))
        self.update()
    
    def keyPressEvent(self, event) -> None:
        """Handle key presses."""
        if event.key() == Qt.Key.Key_R:
            self.reset_view()
        elif event.key() == Qt.Key.Key_Home:
            self.reset_view()
        else:
            super().keyPressEvent(event)
