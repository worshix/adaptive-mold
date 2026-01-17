"""Main window for Adaptive Mold application.

Provides the main UI with dashboard, settings, and 3D view.
"""

import os
from pathlib import Path
from typing import Optional

from loguru import logger
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from adaptive_mold.app.ui_helpers import confirm, show_error, show_info
from adaptive_mold.app.view3d import View3DWidget
from adaptive_mold.core.path_planner import PathPlanner, PlannerConfig, PlannerMode
from adaptive_mold.core.serial_manager import SerialController, list_serial_ports
from adaptive_mold.core.step_loader import GeometryData, load_sample_geometry, load_step
from adaptive_mold.models.db import Database, Job, get_database
from adaptive_mold.models.schemas import CompleteMessage, PositionMessage, ProgressMessage, ValidationMessage


class CreateJobDialog(QDialog):
    """Dialog for creating a new mapping job."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.setWindowTitle("Create New Job")
        self.setMinimumWidth(400)
        
        self.geometry_data: Optional[GeometryData] = None
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        # Job name
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter job name")
        form.addRow("Job Name:", self.name_edit)
        layout.addLayout(form)
        
        # File selection
        file_group = QGroupBox("Geometry Source")
        file_layout = QVBoxLayout(file_group)
        
        file_row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText("Select STEP file or use sample geometry")
        file_row.addWidget(self.file_edit)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(browse_btn)
        
        file_layout.addLayout(file_row)
        
        sample_btn = QPushButton("Use Sample Geometry")
        sample_btn.clicked.connect(self._use_sample)
        file_layout.addWidget(sample_btn)
        
        layout.addWidget(file_group)
        
        # Geometry info
        self.info_label = QLabel("No geometry loaded")
        self.info_label.setStyleSheet("color: gray;")
        layout.addWidget(self.info_label)
        
        # Planner settings
        planner_group = QGroupBox("Planner Settings")
        planner_layout = QFormLayout(planner_group)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Greedy Nearest-Neighbor", PlannerMode.GREEDY)
        self.mode_combo.addItem("Edge Sampling", PlannerMode.EDGE_SAMPLE)
        planner_layout.addRow("Mode:", self.mode_combo)
        
        self.spacing_spin = QSpinBox()
        self.spacing_spin.setRange(1, 100)
        self.spacing_spin.setValue(5)
        self.spacing_spin.setSuffix(" mm")
        planner_layout.addRow("Sample Spacing:", self.spacing_spin)
        
        layout.addWidget(planner_group)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _browse_file(self) -> None:
        """Open file browser for CAD file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CAD File",
            "",
            "CAD Files (*.step *.stp *.STEP *.STP *.stl *.STL *.obj *.OBJ *.ply *.PLY *.off *.OFF);;"
            "STEP Files (*.step *.stp *.STEP *.STP);;"
            "Mesh Files (*.stl *.obj *.ply *.off);;"
            "All Files (*)"
        )
        
        if file_path:
            self._load_geometry(file_path)
    
    def _use_sample(self) -> None:
        """Load sample geometry."""
        self.file_edit.setText("[Sample Geometry]")
        self.geometry_data = load_sample_geometry()
        self._update_info()
    
    def _load_geometry(self, file_path: str) -> None:
        """Load geometry from file."""
        self.file_edit.setText(file_path)
        self.geometry_data = load_step(file_path)
        self._update_info()
    
    def _update_info(self) -> None:
        """Update geometry info label."""
        if self.geometry_data:
            min_pt, max_pt = self.geometry_data.bounding_box
            size = self.geometry_data.bounding_box_size
            self.info_label.setText(
                f"Vertices: {self.geometry_data.vertex_count} | "
                f"Edges: {self.geometry_data.edge_count}\n"
                f"Size: {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm"
            )
            self.info_label.setStyleSheet("color: green;")
        else:
            self.info_label.setText("No geometry loaded")
            self.info_label.setStyleSheet("color: gray;")
    
    def _validate_and_accept(self) -> None:
        """Validate inputs and accept dialog."""
        if not self.name_edit.text().strip():
            show_error(self, "Validation Error", "Please enter a job name.")
            return
        
        if self.geometry_data is None:
            show_error(self, "Validation Error", "Please load geometry.")
            return
        
        self.accept()
    
    def get_job_data(self) -> dict:
        """Get the job data from dialog.
        
        Returns:
            Dict with job name, geometry, and planner config
        """
        # Get mode from combo - ensure it's a PlannerMode enum
        mode_data = self.mode_combo.currentData()
        if isinstance(mode_data, str):
            mode = PlannerMode(mode_data)
        else:
            mode = mode_data if mode_data else PlannerMode.GREEDY
        
        return {
            "name": self.name_edit.text().strip(),
            "filename": self.file_edit.text() if "[Sample" not in self.file_edit.text() else None,
            "geometry": self.geometry_data,
            "planner_config": PlannerConfig(
                mode=mode,
                edge_sample_spacing=self.spacing_spin.value(),
            ),
        }


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Adaptive Mold - Path Mapper")
        self.setMinimumSize(1200, 800)
        
        # State
        self._db: Database = get_database()
        self._current_job: Optional[Job] = None
        self._current_geometry: Optional[GeometryData] = None
        self._current_path: Optional[list[tuple[float, float, float]]] = None
        
        # Serial controller
        self._serial = SerialController(mock_mode=True)
        self._serial.signals.connected.connect(self._on_serial_connected)
        self._serial.signals.disconnected.connect(self._on_serial_disconnected)
        self._serial.signals.validation_received.connect(self._on_validation)
        self._serial.signals.position_received.connect(self._on_position)
        self._serial.signals.progress_received.connect(self._on_progress)
        self._serial.signals.complete_received.connect(self._on_complete)
        
        self._setup_ui()
        self._refresh_job_list()
        
        # Auto-connect in mock mode
        self._serial.connect()
    
    def _setup_ui(self) -> None:
        """Set up the main UI."""
        # Central widget with splitter
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Left panel - Dashboard
        left_panel = self._create_dashboard_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - 3D View and controls
        right_panel = self._create_view_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([300, 900])
        
        # Settings dock
        self._create_settings_dock()
        
        # Status bar
        self.statusBar().showMessage("Ready - Mock Mode Active")
    
    def _create_dashboard_panel(self) -> QWidget:
        """Create the dashboard panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Title
        title = QLabel("Jobs")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Job list
        self.job_list = QListWidget()
        self.job_list.itemClicked.connect(self._on_job_selected)
        layout.addWidget(self.job_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        new_btn = QPushButton("New Job")
        new_btn.clicked.connect(self._create_new_job)
        btn_layout.addWidget(new_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_selected_job)
        btn_layout.addWidget(delete_btn)
        
        layout.addLayout(btn_layout)
        
        refresh_btn = QPushButton("Refresh List")
        refresh_btn.clicked.connect(self._refresh_job_list)
        layout.addWidget(refresh_btn)
        
        return panel
    
    def _create_view_panel(self) -> QWidget:
        """Create the 3D view panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 3D View
        self.view3d = View3DWidget()
        layout.addWidget(self.view3d, stretch=1)
        
        # Control buttons
        controls = QHBoxLayout()
        
        self.plan_btn = QPushButton("Plan Path")
        self.plan_btn.clicked.connect(self._plan_path)
        self.plan_btn.setEnabled(False)
        controls.addWidget(self.plan_btn)
        
        self.start_btn = QPushButton("Start Mapping")
        self.start_btn.clicked.connect(self._start_mapping)
        self.start_btn.setEnabled(False)
        controls.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self._stop_mapping)
        self.stop_btn.setEnabled(False)
        controls.addWidget(self.stop_btn)
        
        reset_view_btn = QPushButton("Reset View")
        reset_view_btn.clicked.connect(self.view3d.reset_view)
        controls.addWidget(reset_view_btn)
        
        layout.addLayout(controls)
        
        # Job info
        self.job_info = QLabel("No job selected")
        self.job_info.setStyleSheet("padding: 10px; background: #2a2a3a;")
        layout.addWidget(self.job_info)
        
        return panel
    
    def _create_settings_dock(self) -> None:
        """Create the settings dock widget."""
        dock = QDockWidget("Settings", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)
        
        # Serial settings
        serial_group = QGroupBox("Serial Connection")
        serial_layout = QFormLayout(serial_group)
        
        # Mock mode toggle
        self.mock_check = QCheckBox("Mock Mode (no hardware)")
        self.mock_check.setChecked(True)
        self.mock_check.setToolTip("Enable mock mode to test without physical hardware")
        self.mock_check.stateChanged.connect(self._on_mock_mode_changed)
        serial_layout.addRow(self.mock_check)
        
        # Port selection
        self.port_combo = QComboBox()
        self.port_combo.setToolTip("Serial port (e.g., /dev/ttyUSB0 on Linux, COM3 on Windows)")
        self._refresh_ports()
        serial_layout.addRow("Port:", self.port_combo)
        
        refresh_ports_btn = QPushButton("Refresh Ports")
        refresh_ports_btn.clicked.connect(self._refresh_ports)
        serial_layout.addRow(refresh_ports_btn)
        
        # Baud rate
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("115200")
        serial_layout.addRow("Baud Rate:", self.baud_combo)
        
        # Connect button
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._toggle_connection)
        serial_layout.addRow(self.connect_btn)
        
        # Connection status
        self.conn_status = QLabel("Disconnected")
        self.conn_status.setStyleSheet("color: orange;")
        serial_layout.addRow("Status:", self.conn_status)
        
        layout.addWidget(serial_group)
        
        # Mapping settings
        mapping_group = QGroupBox("Mapping Settings")
        mapping_layout = QFormLayout(mapping_group)
        
        self.feedrate_spin = QSpinBox()
        self.feedrate_spin.setRange(1, 1000)
        self.feedrate_spin.setValue(50)
        self.feedrate_spin.setSuffix(" mm/s")
        mapping_layout.addRow("Feedrate:", self.feedrate_spin)
        
        layout.addWidget(mapping_group)
        
        layout.addStretch()
        
        dock.setWidget(settings_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    
    def _refresh_ports(self) -> None:
        """Refresh available serial ports."""
        self.port_combo.clear()
        ports = list_serial_ports()
        for port in ports:
            self.port_combo.addItem(f"{port['port']} - {port['description']}", port['port'])
        
        if not ports:
            self.port_combo.addItem("No ports found", "")
    
    def _refresh_job_list(self) -> None:
        """Refresh the job list from database."""
        self.job_list.clear()
        jobs = self._db.get_all_jobs()
        
        for job in jobs:
            item = QListWidgetItem(f"{job.name} ({job.status})")
            item.setData(Qt.ItemDataRole.UserRole, job.id)
            self.job_list.addItem(item)
        
        logger.info(f"Loaded {len(jobs)} jobs from database")
    
    def _create_new_job(self) -> None:
        """Open dialog to create a new job."""
        dialog = CreateJobDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_job_data()
            
            # Create job in database
            job = self._db.create_job(
                name=data["name"],
                filename=data["filename"],
                planner_params=data["planner_config"].to_dict()
            )
            
            # Store geometry
            geometry = data["geometry"]
            self._db.add_geometry(job.id, geometry.get_vertices_list())
            
            logger.info(f"Created job: {job.name} (id={job.id})")
            self.statusBar().showMessage(f"Created job: {job.name}")
            
            # Refresh and select
            self._refresh_job_list()
            self._load_job(job.id, geometry)
    
    def _delete_selected_job(self) -> None:
        """Delete the selected job."""
        item = self.job_list.currentItem()
        if not item:
            return
        
        job_id = item.data(Qt.ItemDataRole.UserRole)
        
        if confirm(self, "Delete Job", "Are you sure you want to delete this job?"):
            self._db.delete_job(job_id)
            self._refresh_job_list()
            self.view3d.clear_geometry()
            self._current_job = None
            self._current_geometry = None
            self._current_path = None
            self._update_job_info()
            self.statusBar().showMessage("Job deleted")
    
    def _on_job_selected(self, item: QListWidgetItem) -> None:
        """Handle job selection."""
        job_id = item.data(Qt.ItemDataRole.UserRole)
        self._load_job(job_id)
    
    def _load_job(self, job_id: str, geometry: Optional[GeometryData] = None) -> None:
        """Load a job and display its geometry."""
        job = self._db.get_job(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            return
        
        self._current_job = job
        
        # Load geometry from database if not provided
        if geometry is None:
            vertices = self._db.get_geometry(job_id)
            if vertices:
                import numpy as np
                self._current_geometry = GeometryData(
                    vertices=np.array(vertices),
                    edges=np.array([]).reshape(0, 2),  # Edges not stored
                    metadata={"source": "database"},
                    source="database"
                )
            else:
                self._current_geometry = None
        else:
            self._current_geometry = geometry
        
        # Update 3D view
        if self._current_geometry:
            self.view3d.set_geometry(
                self._current_geometry.vertices,
                self._current_geometry.edges
            )
        else:
            self.view3d.clear_geometry()
        
        # Load waypoints if available
        waypoints = self._db.get_waypoints(job_id)
        if waypoints:
            self._current_path = [(w[1], w[2], w[3]) for w in waypoints]
            # Set path visualization (would need index mapping)
        else:
            self._current_path = None
        
        self._update_job_info()
        self._update_button_states()
        
        logger.info(f"Loaded job: {job.name}")
    
    def _update_job_info(self) -> None:
        """Update the job info display."""
        if self._current_job:
            info = f"Job: {self._current_job.name}\n"
            info += f"Status: {self._current_job.status}\n"
            
            if self._current_geometry:
                info += f"Vertices: {self._current_geometry.vertex_count}\n"
            
            if self._current_path:
                info += f"Waypoints: {len(self._current_path)}\n"
            
            self.job_info.setText(info)
        else:
            self.job_info.setText("No job selected")
    
    def _update_button_states(self) -> None:
        """Update button enabled states."""
        has_job = self._current_job is not None
        has_geometry = self._current_geometry is not None
        has_path = self._current_path is not None
        is_connected = self._serial.is_connected()
        
        self.plan_btn.setEnabled(has_job and has_geometry)
        self.start_btn.setEnabled(has_job and has_path and is_connected)
        self.stop_btn.setEnabled(is_connected)
    
    def _plan_path(self) -> None:
        """Compute path for current job."""
        if not self._current_job or not self._current_geometry:
            return
        
        # Get planner config from job
        params = self._current_job.get_planner_params()
        config = PlannerConfig.from_dict(params) if params else PlannerConfig()
        
        # Plan path
        planner = PathPlanner(config)
        result = planner.plan(self._current_geometry)
        
        self._current_path = result.get_waypoints_list()
        
        # Store in database
        self._db.add_waypoints(self._current_job.id, self._current_path)
        self._db.update_job_status(self._current_job.id, "planned")
        
        # Update UI
        self._current_job = self._db.get_job(self._current_job.id)
        self._update_job_info()
        self._update_button_states()
        
        self.statusBar().showMessage(
            f"Path planned: {result.waypoint_count} waypoints, "
            f"total distance: {result.total_distance:.1f} mm"
        )
        
        logger.info(f"Path planned: {result.waypoint_count} waypoints")
    
    def _start_mapping(self) -> None:
        """Start the mapping process."""
        if not self._current_job or not self._current_path:
            return
        
        if not self._serial.is_connected():
            show_error(self, "Not Connected", "Please connect to controller first.")
            return
        
        # Clear visited markers
        self.view3d.clear_visited()
        
        # Send MAP command
        success = self._serial.send_map_command(
            job_id=self._current_job.id,
            path=self._current_path,
            feedrate=self.feedrate_spin.value()
        )
        
        if success:
            self._db.update_job_status(self._current_job.id, "mapping")
            self.statusBar().showMessage("Mapping started...")
            logger.info("Mapping started")
        else:
            show_error(self, "Send Failed", "Failed to send MAP command.")
    
    def _stop_mapping(self) -> None:
        """Stop the current mapping operation."""
        self._serial.send_stop()
        self.statusBar().showMessage("Stop command sent")
    
    def _toggle_connection(self) -> None:
        """Toggle serial connection."""
        if self._serial.is_connected():
            self._serial.disconnect()
        else:
            if self.mock_check.isChecked():
                self._serial.set_mock_mode(True)
            else:
                self._serial.set_mock_mode(False)
                port_data = self.port_combo.currentData()
                if port_data:
                    self._serial.port = port_data
                self._serial.baudrate = int(self.baud_combo.currentText())
            
            self._serial.connect()
    
    def _on_mock_mode_changed(self, state: int) -> None:
        """Handle mock mode toggle."""
        is_mock = state == Qt.CheckState.Checked.value
        self.port_combo.setEnabled(not is_mock)
        self.baud_combo.setEnabled(not is_mock)
        
        if self._serial.is_connected():
            self._serial.disconnect()
            self._serial.set_mock_mode(is_mock)
            self._serial.connect()
    
    @Slot()
    def _on_serial_connected(self) -> None:
        """Handle serial connection."""
        self.conn_status.setText("Connected")
        self.conn_status.setStyleSheet("color: green;")
        self.connect_btn.setText("Disconnect")
        mode = "Mock Mode" if self._serial.mock_mode else f"Port {self._serial.port}"
        self.statusBar().showMessage(f"Connected - {mode}")
        self._update_button_states()
    
    @Slot()
    def _on_serial_disconnected(self) -> None:
        """Handle serial disconnection."""
        self.conn_status.setText("Disconnected")
        self.conn_status.setStyleSheet("color: orange;")
        self.connect_btn.setText("Connect")
        self.statusBar().showMessage("Disconnected")
        self._update_button_states()
    
    @Slot(object)
    def _on_validation(self, msg: ValidationMessage) -> None:
        """Handle validation message from controller."""
        if msg.status.value == "VALID":
            self.statusBar().showMessage("Controller: Path validated")
        else:
            self.statusBar().showMessage(f"Controller: Validation failed - {msg.message}")
    
    @Slot(object)
    def _on_position(self, msg: PositionMessage) -> None:
        """Handle position update from controller."""
        # Mark position as visited in 3D view
        self.view3d.mark_position_visited((msg.x, msg.y, msg.z))
    
    @Slot(object)
    def _on_progress(self, msg: ProgressMessage) -> None:
        """Handle progress update from controller."""
        self.statusBar().showMessage(
            f"Mapping: {msg.visited}/{msg.total} ({msg.percentage:.1f}%)"
        )
    
    @Slot(object)
    def _on_complete(self, msg: CompleteMessage) -> None:
        """Handle completion message from controller."""
        self.statusBar().showMessage(
            f"Mapping complete! Duration: {msg.duration_s:.1f}s"
        )
        
        if self._current_job and self._current_job.id == msg.job_id:
            self._db.update_job_status(msg.job_id, "completed")
            self._current_job = self._db.get_job(msg.job_id)
            self._update_job_info()
        
        show_info(
            self,
            "Mapping Complete",
            f"Job completed successfully!\nDuration: {msg.duration_s:.1f} seconds"
        )
    
    def closeEvent(self, event) -> None:
        """Handle window close."""
        self._serial.disconnect()
        super().closeEvent(event)
