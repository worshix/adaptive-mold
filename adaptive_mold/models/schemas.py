"""Pydantic schemas for serial protocol messages.

Defines message types for communication between the PC and controller.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CommandType(str, Enum):
    """Command types sent from PC to controller."""
    MAP = "MAP"
    STOP = "STOP"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    STATUS = "STATUS"


class MessageType(str, Enum):
    """Message types received from controller."""
    VALIDATION = "VALIDATION"
    POS = "POS"
    PROGRESS = "PROGRESS"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"


class ValidationStatus(str, Enum):
    """Validation status from controller."""
    VALID = "VALID"
    INVALID = "INVALID"
    ERROR = "ERROR"


# ============ PC -> Controller Messages ============

class MapMeta(BaseModel):
    """Metadata for MAP command."""
    units: str = "mm"
    feedrate: float = 50.0


class MapCommand(BaseModel):
    """MAP command sent to controller to start mapping."""
    cmd: str = Field(default="MAP", pattern="^MAP$")
    job_id: str
    path: list[list[float]]  # List of [x, y, z] coordinates
    meta: MapMeta = Field(default_factory=MapMeta)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return self.model_dump_json()


class StopCommand(BaseModel):
    """STOP command to halt current operation."""
    cmd: str = Field(default="STOP", pattern="^STOP$")
    
    def to_json(self) -> str:
        return self.model_dump_json()


class StatusCommand(BaseModel):
    """STATUS command to query controller state."""
    cmd: str = Field(default="STATUS", pattern="^STATUS$")
    
    def to_json(self) -> str:
        return self.model_dump_json()


# ============ Controller -> PC Messages ============

class ValidationMessage(BaseModel):
    """Validation response from controller."""
    type: str = Field(default="VALIDATION", pattern="^VALIDATION$")
    status: ValidationStatus
    message: Optional[str] = None


class PositionMessage(BaseModel):
    """Position update from controller during mapping."""
    type: str = Field(default="POS", pattern="^POS$")
    pos: list[float]  # [x, y, z]
    t: int  # Timestamp (Unix epoch milliseconds)
    
    @property
    def x(self) -> float:
        return self.pos[0] if len(self.pos) > 0 else 0.0
    
    @property
    def y(self) -> float:
        return self.pos[1] if len(self.pos) > 1 else 0.0
    
    @property
    def z(self) -> float:
        return self.pos[2] if len(self.pos) > 2 else 0.0


class ProgressMessage(BaseModel):
    """Progress update from controller."""
    type: str = Field(default="PROGRESS", pattern="^PROGRESS$")
    visited: int
    total: int
    
    @property
    def percentage(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.visited / self.total) * 100


class CompleteMessage(BaseModel):
    """Completion message from controller."""
    type: str = Field(default="COMPLETE", pattern="^COMPLETE$")
    job_id: str
    duration_s: float


class ErrorMessage(BaseModel):
    """Error message from controller."""
    type: str = Field(default="ERROR", pattern="^ERROR$")
    code: str
    message: str


def parse_controller_message(data: dict) -> ValidationMessage | PositionMessage | ProgressMessage | CompleteMessage | ErrorMessage:
    """Parse a message from the controller.
    
    Args:
        data: Dictionary from JSON message
        
    Returns:
        Parsed message object
        
    Raises:
        ValueError: If message type is unknown
    """
    msg_type = data.get("type")
    
    if msg_type == "VALIDATION":
        return ValidationMessage(**data)
    elif msg_type == "POS":
        return PositionMessage(**data)
    elif msg_type == "PROGRESS":
        return ProgressMessage(**data)
    elif msg_type == "COMPLETE":
        return CompleteMessage(**data)
    elif msg_type == "ERROR":
        return ErrorMessage(**data)
    else:
        raise ValueError(f"Unknown message type: {msg_type}")
