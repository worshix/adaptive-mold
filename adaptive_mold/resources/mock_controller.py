"""Mock controller for testing without hardware.

This script simulates an Arduino/hardware controller that receives
MAP commands and sends back position updates.

Can run as:
1. Standalone CLI (reads from stdin, writes to stdout)
2. Pseudo-serial using socat/pty

Usage:
    # Standalone mode (for testing protocol):
    python -m adaptive_mold.resources.mock_controller
    
    # With socat for pseudo-serial (Linux):
    socat -d -d pty,raw,echo=0 pty,raw,echo=0
    # Then run mock_controller connected to one pty, and the app to the other
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Optional

try:
    from loguru import logger
except ImportError:
    # Fallback if loguru not available
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("mock_controller")


@dataclass
class ControllerConfig:
    """Configuration for mock controller."""
    
    update_rate: float = 20.0  # Position updates per second
    bounding_box_min: tuple[float, float, float] = (-100, -100, -100)
    bounding_box_max: tuple[float, float, float] = (100, 100, 100)
    validate_bounds: bool = True
    
    def is_in_bounds(self, pos: list[float]) -> bool:
        """Check if position is within bounding box."""
        if not self.validate_bounds:
            return True
        if len(pos) < 3:
            return False
        return (
            self.bounding_box_min[0] <= pos[0] <= self.bounding_box_max[0] and
            self.bounding_box_min[1] <= pos[1] <= self.bounding_box_max[1] and
            self.bounding_box_min[2] <= pos[2] <= self.bounding_box_max[2]
        )


class MockController:
    """Simulates hardware controller behavior."""
    
    def __init__(self, config: Optional[ControllerConfig] = None):
        """Initialize controller.
        
        Args:
            config: Controller configuration
        """
        self.config = config or ControllerConfig()
        self._running = False
        self._current_job: Optional[str] = None
    
    def send_message(self, msg: dict) -> None:
        """Send a message (JSON line to stdout).
        
        Args:
            msg: Message dictionary
        """
        line = json.dumps(msg)
        print(line, flush=True)
        logger.debug(f"TX: {line}")
    
    def handle_command(self, cmd: dict) -> None:
        """Handle an incoming command.
        
        Args:
            cmd: Command dictionary
        """
        cmd_type = cmd.get("cmd", "").upper()
        
        if cmd_type == "MAP":
            self._handle_map(cmd)
        elif cmd_type == "STOP":
            self._handle_stop()
        elif cmd_type == "STATUS":
            self._handle_status()
        else:
            self.send_message({
                "type": "ERROR",
                "code": "UNKNOWN_CMD",
                "message": f"Unknown command: {cmd_type}"
            })
    
    def _handle_map(self, cmd: dict) -> None:
        """Handle MAP command."""
        job_id = cmd.get("job_id", "unknown")
        path = cmd.get("path", [])
        meta = cmd.get("meta", {})
        
        logger.info(f"Received MAP command: job={job_id}, waypoints={len(path)}")
        
        # Validate path
        if not path:
            self.send_message({
                "type": "VALIDATION",
                "status": "INVALID",
                "message": "Empty path"
            })
            return
        
        # Check bounds
        if self.config.validate_bounds:
            for i, pos in enumerate(path):
                if not self.config.is_in_bounds(pos):
                    self.send_message({
                        "type": "VALIDATION",
                        "status": "INVALID",
                        "message": f"Waypoint {i} out of bounds: {pos}"
                    })
                    return
        
        # Send VALID response
        self.send_message({
            "type": "VALIDATION",
            "status": "VALID"
        })
        
        # Simulate mapping
        self._current_job = job_id
        self._running = True
        
        self._simulate_mapping(job_id, path, meta)
    
    def _simulate_mapping(self, job_id: str, path: list, meta: dict) -> None:
        """Simulate the mapping process.
        
        Args:
            job_id: Job identifier
            path: List of waypoints
            meta: Metadata (feedrate, units)
        """
        interval = 1.0 / self.config.update_rate
        start_time = time.time()
        
        logger.info(f"Starting mapping simulation: {len(path)} waypoints at {self.config.update_rate} Hz")
        
        for i, waypoint in enumerate(path):
            if not self._running:
                logger.info("Mapping interrupted")
                return
            
            # Send position update
            self.send_message({
                "type": "POS",
                "pos": waypoint,
                "t": int(time.time() * 1000)
            })
            
            # Send progress every 10 waypoints or at end
            if (i + 1) % 10 == 0 or i == len(path) - 1:
                self.send_message({
                    "type": "PROGRESS",
                    "visited": i + 1,
                    "total": len(path)
                })
            
            time.sleep(interval)
        
        # Send completion
        duration = time.time() - start_time
        self.send_message({
            "type": "COMPLETE",
            "job_id": job_id,
            "duration_s": round(duration, 2)
        })
        
        self._running = False
        self._current_job = None
        logger.info(f"Mapping complete: {duration:.2f}s")
    
    def _handle_stop(self) -> None:
        """Handle STOP command."""
        logger.info("Received STOP command")
        self._running = False
        self.send_message({
            "type": "PROGRESS",
            "visited": 0,
            "total": 0
        })
    
    def _handle_status(self) -> None:
        """Handle STATUS command."""
        self.send_message({
            "type": "STATUS",
            "running": self._running,
            "job_id": self._current_job
        })
    
    def run_stdin_loop(self) -> None:
        """Run the controller reading from stdin."""
        logger.info("Mock Controller started - reading from stdin")
        logger.info("Send JSON commands (one per line), e.g.:")
        logger.info('  {"cmd":"MAP","job_id":"test","path":[[0,0,0],[10,10,10]]}')
        
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    cmd = json.loads(line)
                    logger.debug(f"RX: {line}")
                    self.handle_command(cmd)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    self.send_message({
                        "type": "ERROR",
                        "code": "PARSE_ERROR",
                        "message": str(e)
                    })
        except KeyboardInterrupt:
            logger.info("Controller stopped")


def main() -> int:
    """Main entry point for mock controller CLI."""
    parser = argparse.ArgumentParser(
        description="Mock controller for Adaptive Mold testing"
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=20.0,
        help="Position update rate in Hz (default: 20)"
    )
    parser.add_argument(
        "--no-bounds",
        action="store_true",
        help="Disable bounds checking"
    )
    parser.add_argument(
        "--bounds-min",
        type=float,
        nargs=3,
        default=[-100, -100, -100],
        metavar=("X", "Y", "Z"),
        help="Minimum bounds (default: -100 -100 -100)"
    )
    parser.add_argument(
        "--bounds-max",
        type=float,
        nargs=3,
        default=[100, 100, 100],
        metavar=("X", "Y", "Z"),
        help="Maximum bounds (default: 100 100 100)"
    )
    
    args = parser.parse_args()
    
    config = ControllerConfig(
        update_rate=args.rate,
        bounding_box_min=tuple(args.bounds_min),
        bounding_box_max=tuple(args.bounds_max),
        validate_bounds=not args.no_bounds
    )
    
    controller = MockController(config)
    controller.run_stdin_loop()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
