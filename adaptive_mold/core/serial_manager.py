"""Serial communication manager for controller communication.

Provides both real serial (pyserial) and mock serial implementations.
"""

import json
import threading
import time
from abc import ABC, abstractmethod
from queue import Empty, Queue
from typing import Callable, Optional

import serial
import serial.tools.list_ports
from loguru import logger
from PySide6.QtCore import QObject, Signal

from adaptive_mold.models.schemas import (
    CompleteMessage,
    ErrorMessage,
    MapCommand,
    MapMeta,
    PositionMessage,
    ProgressMessage,
    ValidationMessage,
    parse_controller_message,
)


class SerialManagerBase(ABC):
    """Abstract base class for serial managers."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the serial port.
        
        Returns:
            True if connection successful
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from serial port."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected."""
        pass
    
    @abstractmethod
    def send_map_command(
        self,
        job_id: str,
        path: list[tuple[float, float, float]],
        units: str = "mm",
        feedrate: float = 50.0
    ) -> bool:
        """Send MAP command to controller.
        
        Args:
            job_id: Job identifier
            path: List of (x, y, z) waypoints
            units: Unit system
            feedrate: Movement speed
            
        Returns:
            True if send successful
        """
        pass
    
    @abstractmethod
    def send_stop(self) -> bool:
        """Send STOP command."""
        pass
    
    @abstractmethod
    def set_message_callback(
        self,
        callback: Callable[[dict], None]
    ) -> None:
        """Set callback for received messages.
        
        Args:
            callback: Function to call with parsed message dict
        """
        pass


class RealSerialManager(SerialManagerBase):
    """Real serial port communication using pyserial."""
    
    def __init__(self, port: str = "", baudrate: int = 115200, timeout: float = 1.0):
        """Initialize serial manager.
        
        Args:
            port: Serial port name (e.g., '/dev/ttyUSB0', 'COM3')
            baudrate: Baud rate
            timeout: Read timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        
        self._serial: Optional[serial.Serial] = None
        self._read_thread: Optional[threading.Thread] = None
        self._running = False
        self._message_callback: Optional[Callable[[dict], None]] = None
        self._buffer = ""
    
    def connect(self) -> bool:
        if not self.port:
            logger.error("No port specified")
            return False
        
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            self._running = True
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            logger.info(f"Connected to {self.port} at {self.baudrate} baud")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to {self.port}: {e}")
            return False
    
    def disconnect(self) -> None:
        self._running = False
        if self._read_thread:
            self._read_thread.join(timeout=2.0)
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None
        logger.info("Disconnected from serial port")
    
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open
    
    def send_map_command(
        self,
        job_id: str,
        path: list[tuple[float, float, float]],
        units: str = "mm",
        feedrate: float = 50.0
    ) -> bool:
        if not self.is_connected():
            logger.error("Not connected")
            return False
        
        cmd = MapCommand(
            job_id=job_id,
            path=[[p[0], p[1], p[2]] for p in path],
            meta=MapMeta(units=units, feedrate=feedrate)
        )
        
        return self._send_json(cmd.model_dump())
    
    def send_stop(self) -> bool:
        return self._send_json({"cmd": "STOP"})
    
    def set_message_callback(self, callback: Callable[[dict], None]) -> None:
        self._message_callback = callback
    
    def _send_json(self, data: dict) -> bool:
        """Send JSON data to serial port."""
        if not self.is_connected():
            return False
        
        try:
            message = json.dumps(data) + "\n"
            self._serial.write(message.encode('utf-8'))
            self._serial.flush()
            logger.debug(f"Sent: {message.strip()}")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to send: {e}")
            return False
    
    def _read_loop(self) -> None:
        """Background thread for reading serial data."""
        while self._running and self._serial and self._serial.is_open:
            try:
                if self._serial.in_waiting:
                    data = self._serial.read(self._serial.in_waiting).decode('utf-8', errors='ignore')
                    self._buffer += data
                    self._process_buffer()
                else:
                    time.sleep(0.01)
            except serial.SerialException as e:
                logger.error(f"Serial read error: {e}")
                break
            except Exception as e:
                logger.error(f"Read loop error: {e}")
    
    def _process_buffer(self) -> None:
        """Process buffered data for complete JSON messages."""
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                logger.debug(f"Received: {data}")
                if self._message_callback:
                    self._message_callback(data)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON: {line} - {e}")


class MockSerialManager(SerialManagerBase):
    """Mock serial manager for testing without hardware.
    
    Simulates controller behavior internally.
    """
    
    def __init__(self, simulation_speed: float = 20.0):
        """Initialize mock manager.
        
        Args:
            simulation_speed: Simulated positions per second
        """
        self.simulation_speed = simulation_speed
        
        self._connected = False
        self._message_callback: Optional[Callable[[dict], None]] = None
        self._simulation_thread: Optional[threading.Thread] = None
        self._running = False
        self._command_queue: Queue = Queue()
    
    def connect(self) -> bool:
        self._connected = True
        self._running = True
        self._simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._simulation_thread.start()
        logger.info("Mock serial connected")
        return True
    
    def disconnect(self) -> None:
        self._running = False
        if self._simulation_thread:
            self._simulation_thread.join(timeout=2.0)
        self._connected = False
        logger.info("Mock serial disconnected")
    
    def is_connected(self) -> bool:
        return self._connected
    
    def send_map_command(
        self,
        job_id: str,
        path: list[tuple[float, float, float]],
        units: str = "mm",
        feedrate: float = 50.0
    ) -> bool:
        if not self._connected:
            return False
        
        self._command_queue.put({
            "cmd": "MAP",
            "job_id": job_id,
            "path": path,
            "meta": {"units": units, "feedrate": feedrate}
        })
        logger.debug(f"Mock: Queued MAP command for job {job_id} with {len(path)} waypoints")
        return True
    
    def send_stop(self) -> bool:
        if not self._connected:
            return False
        self._command_queue.put({"cmd": "STOP"})
        return True
    
    def set_message_callback(self, callback: Callable[[dict], None]) -> None:
        self._message_callback = callback
    
    def _emit_message(self, data: dict) -> None:
        """Send message to callback."""
        logger.debug(f"Mock -> App: {data}")
        if self._message_callback:
            self._message_callback(data)
    
    def _simulation_loop(self) -> None:
        """Background thread simulating controller behavior."""
        while self._running:
            try:
                cmd = self._command_queue.get(timeout=0.1)
            except Empty:
                continue
            
            if cmd.get("cmd") == "MAP":
                self._simulate_mapping(cmd)
            elif cmd.get("cmd") == "STOP":
                logger.info("Mock: Received STOP command")
                # Could interrupt mapping here
    
    def _simulate_mapping(self, cmd: dict) -> None:
        """Simulate the mapping process."""
        job_id = cmd["job_id"]
        path = cmd["path"]
        
        logger.info(f"Mock: Starting mapping simulation for job {job_id}")
        
        # Send VALID response
        time.sleep(0.1)
        self._emit_message({
            "type": "VALIDATION",
            "status": "VALID"
        })
        
        # Simulate movement through waypoints
        start_time = time.time()
        interval = 1.0 / self.simulation_speed
        
        for i, waypoint in enumerate(path):
            if not self._running:
                break
            
            # Position update
            self._emit_message({
                "type": "POS",
                "pos": list(waypoint) if isinstance(waypoint, tuple) else waypoint,
                "t": int(time.time() * 1000)
            })
            
            # Progress update every 10 waypoints
            if (i + 1) % 10 == 0 or i == len(path) - 1:
                self._emit_message({
                    "type": "PROGRESS",
                    "visited": i + 1,
                    "total": len(path)
                })
            
            time.sleep(interval)
        
        # Send completion
        duration = time.time() - start_time
        self._emit_message({
            "type": "COMPLETE",
            "job_id": job_id,
            "duration_s": duration
        })
        
        logger.info(f"Mock: Mapping complete for job {job_id} in {duration:.1f}s")


class SerialSignals(QObject):
    """Qt signals for serial events."""
    
    connected = Signal()
    disconnected = Signal()
    validation_received = Signal(object)  # ValidationMessage
    position_received = Signal(object)  # PositionMessage
    progress_received = Signal(object)  # ProgressMessage
    complete_received = Signal(object)  # CompleteMessage
    error_received = Signal(object)  # ErrorMessage


class SerialController(QObject):
    """High-level serial controller with Qt signals.
    
    Wraps SerialManagerBase implementations and emits Qt signals
    for UI integration.
    """
    
    def __init__(self, mock_mode: bool = True, parent: Optional[QObject] = None):
        """Initialize controller.
        
        Args:
            mock_mode: If True, use MockSerialManager
            parent: Qt parent object
        """
        super().__init__(parent)
        
        self.signals = SerialSignals()
        self.mock_mode = mock_mode
        
        self._manager: Optional[SerialManagerBase] = None
        self._port = ""
        self._baudrate = 115200
    
    @property
    def port(self) -> str:
        return self._port
    
    @port.setter
    def port(self, value: str) -> None:
        self._port = value
    
    @property
    def baudrate(self) -> int:
        return self._baudrate
    
    @baudrate.setter
    def baudrate(self, value: int) -> None:
        self._baudrate = value
    
    def set_mock_mode(self, enabled: bool) -> None:
        """Enable or disable mock mode."""
        was_connected = self.is_connected()
        if was_connected:
            self.disconnect()
        self.mock_mode = enabled
        if was_connected:
            self.connect()
    
    def connect(self) -> bool:
        """Connect using current settings."""
        if self._manager:
            self.disconnect()
        
        if self.mock_mode:
            self._manager = MockSerialManager()
        else:
            self._manager = RealSerialManager(
                port=self._port,
                baudrate=self._baudrate
            )
        
        self._manager.set_message_callback(self._on_message)
        
        if self._manager.connect():
            self.signals.connected.emit()
            return True
        return False
    
    def disconnect(self) -> None:
        """Disconnect from controller."""
        if self._manager:
            self._manager.disconnect()
            self._manager = None
            self.signals.disconnected.emit()
    
    def is_connected(self) -> bool:
        """Check connection status."""
        return self._manager is not None and self._manager.is_connected()
    
    def send_map_command(
        self,
        job_id: str,
        path: list[tuple[float, float, float]],
        units: str = "mm",
        feedrate: float = 50.0
    ) -> bool:
        """Send MAP command."""
        if not self._manager:
            return False
        return self._manager.send_map_command(job_id, path, units, feedrate)
    
    def send_stop(self) -> bool:
        """Send STOP command."""
        if not self._manager:
            return False
        return self._manager.send_stop()
    
    def _on_message(self, data: dict) -> None:
        """Handle incoming message from controller."""
        try:
            msg = parse_controller_message(data)
            
            if isinstance(msg, ValidationMessage):
                self.signals.validation_received.emit(msg)
            elif isinstance(msg, PositionMessage):
                self.signals.position_received.emit(msg)
            elif isinstance(msg, ProgressMessage):
                self.signals.progress_received.emit(msg)
            elif isinstance(msg, CompleteMessage):
                self.signals.complete_received.emit(msg)
            elif isinstance(msg, ErrorMessage):
                self.signals.error_received.emit(msg)
                
        except ValueError as e:
            logger.warning(f"Unknown message type: {e}")


def list_serial_ports() -> list[dict]:
    """List available serial ports.
    
    Returns:
        List of dicts with 'port', 'description', 'hwid' keys
    """
    ports = []
    for port in serial.tools.list_ports.comports():
        ports.append({
            "port": port.device,
            "description": port.description,
            "hwid": port.hwid
        })
    return ports
