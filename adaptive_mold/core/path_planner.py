"""Path planner for computing waypoint sequences from geometry.

Implements greedy nearest-neighbor and edge-sampling strategies.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
from loguru import logger
from scipy.spatial.distance import cdist

from adaptive_mold.core.step_loader import GeometryData


class PlannerMode(str, Enum):
    """Path planning strategy."""
    GREEDY = "greedy"  # Greedy nearest-neighbor
    EDGE_SAMPLE = "edge_sample"  # Sample points along edges


@dataclass
class PlannerConfig:
    """Configuration for path planner."""
    
    mode: PlannerMode = PlannerMode.GREEDY
    edge_sample_spacing: float = 5.0  # mm between samples on edges
    start_point: Optional[tuple[float, float, float]] = None  # Starting position
    include_vertices: bool = True  # Include original vertices in path
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        # Handle both enum and string mode values
        mode_value = self.mode.value if isinstance(self.mode, PlannerMode) else self.mode
        return {
            "mode": mode_value,
            "edge_sample_spacing": self.edge_sample_spacing,
            "start_point": self.start_point,
            "include_vertices": self.include_vertices,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PlannerConfig":
        """Create from dictionary."""
        return cls(
            mode=PlannerMode(data.get("mode", "greedy")),
            edge_sample_spacing=data.get("edge_sample_spacing", 5.0),
            start_point=data.get("start_point"),
            include_vertices=data.get("include_vertices", True),
        )


@dataclass
class PathResult:
    """Result of path planning."""
    
    waypoints: np.ndarray  # (N, 3) array of ordered waypoints
    total_distance: float  # Total path length
    config: PlannerConfig  # Configuration used
    
    @property
    def waypoint_count(self) -> int:
        """Number of waypoints."""
        return len(self.waypoints)
    
    def get_waypoints_list(self) -> list[tuple[float, float, float]]:
        """Get waypoints as list of tuples."""
        return [(float(w[0]), float(w[1]), float(w[2])) for w in self.waypoints]
    
    def get_path_segments(self) -> list[tuple[np.ndarray, np.ndarray]]:
        """Get path as list of (start, end) segments."""
        segments = []
        for i in range(len(self.waypoints) - 1):
            segments.append((self.waypoints[i], self.waypoints[i + 1]))
        return segments


class PathPlanner:
    """Path planner for geometry waypoint sequencing."""
    
    def __init__(self, config: Optional[PlannerConfig] = None):
        """Initialize planner.
        
        Args:
            config: Planner configuration
        """
        self.config = config or PlannerConfig()
    
    def plan(self, geometry: GeometryData) -> PathResult:
        """Compute an ordered path through the geometry.
        
        Args:
            geometry: Input geometry data
            
        Returns:
            PathResult with ordered waypoints
        """
        logger.info(f"Planning path with mode={self.config.mode.value}")
        
        if self.config.mode == PlannerMode.GREEDY:
            return self._plan_greedy(geometry)
        elif self.config.mode == PlannerMode.EDGE_SAMPLE:
            return self._plan_edge_sample(geometry)
        else:
            raise ValueError(f"Unknown planner mode: {self.config.mode}")
    
    def _plan_greedy(self, geometry: GeometryData) -> PathResult:
        """Greedy nearest-neighbor path planning.
        
        Starts from start_point (or first vertex) and always moves to
        the nearest unvisited vertex.
        
        Args:
            geometry: Input geometry
            
        Returns:
            PathResult with greedy path
        """
        vertices = geometry.vertices
        n = len(vertices)
        
        if n == 0:
            return PathResult(
                waypoints=np.array([]).reshape(0, 3),
                total_distance=0.0,
                config=self.config
            )
        
        if n == 1:
            return PathResult(
                waypoints=vertices.copy(),
                total_distance=0.0,
                config=self.config
            )
        
        # Compute distance matrix
        dist_matrix = cdist(vertices, vertices)
        
        # Find starting vertex
        if self.config.start_point is not None:
            start_pt = np.array(self.config.start_point).reshape(1, 3)
            distances_to_start = cdist(start_pt, vertices)[0]
            current = np.argmin(distances_to_start)
        else:
            current = 0
        
        # Greedy nearest-neighbor
        visited = np.zeros(n, dtype=bool)
        order = [current]
        visited[current] = True
        total_distance = 0.0
        
        for _ in range(n - 1):
            # Find nearest unvisited
            distances = dist_matrix[current].copy()
            distances[visited] = np.inf
            nearest = np.argmin(distances)
            
            total_distance += distances[nearest]
            order.append(nearest)
            visited[nearest] = True
            current = nearest
        
        waypoints = vertices[order]
        
        logger.info(f"Greedy path: {n} waypoints, total distance: {total_distance:.2f}")
        
        return PathResult(
            waypoints=waypoints,
            total_distance=total_distance,
            config=self.config
        )
    
    def _plan_edge_sample(self, geometry: GeometryData) -> PathResult:
        """Edge-sampling path planning.
        
        Samples points along edges at fixed spacing, then orders them
        using greedy nearest-neighbor.
        
        Args:
            geometry: Input geometry
            
        Returns:
            PathResult with sampled path
        """
        vertices = geometry.vertices
        edges = geometry.edges
        spacing = self.config.edge_sample_spacing
        
        # Collect all sample points
        samples = []
        
        # Optionally include original vertices
        if self.config.include_vertices:
            samples.extend(vertices.tolist())
        
        # Sample along edges
        for edge in edges:
            v1 = vertices[edge[0]]
            v2 = vertices[edge[1]]
            
            edge_length = np.linalg.norm(v2 - v1)
            if edge_length < spacing:
                # Edge too short, just use midpoint
                if not self.config.include_vertices:
                    samples.append(((v1 + v2) / 2).tolist())
            else:
                # Sample at regular intervals
                n_samples = int(edge_length / spacing)
                for i in range(1, n_samples):
                    t = i / n_samples
                    point = v1 + t * (v2 - v1)
                    samples.append(point.tolist())
        
        if not samples:
            return PathResult(
                waypoints=np.array([]).reshape(0, 3),
                total_distance=0.0,
                config=self.config
            )
        
        # Remove duplicates (within tolerance)
        samples_array = np.array(samples)
        samples_array = _remove_duplicate_points(samples_array, tolerance=spacing / 10)
        
        # Apply greedy ordering to samples
        temp_geom = GeometryData(
            vertices=samples_array,
            edges=np.array([]).reshape(0, 2),
            metadata={},
            source="sampled"
        )
        
        # Use greedy planner for ordering
        greedy_config = PlannerConfig(
            mode=PlannerMode.GREEDY,
            start_point=self.config.start_point,
        )
        greedy_planner = PathPlanner(greedy_config)
        result = greedy_planner._plan_greedy(temp_geom)
        
        logger.info(f"Edge-sample path: {len(result.waypoints)} waypoints, "
                    f"spacing={spacing}mm, total distance: {result.total_distance:.2f}")
        
        # Update config to reflect actual mode used
        return PathResult(
            waypoints=result.waypoints,
            total_distance=result.total_distance,
            config=self.config
        )


def _remove_duplicate_points(points: np.ndarray, tolerance: float = 0.01) -> np.ndarray:
    """Remove duplicate points within tolerance.
    
    Args:
        points: (N, 3) array of points
        tolerance: Distance threshold for duplicates
        
    Returns:
        Array with duplicates removed
    """
    if len(points) <= 1:
        return points
    
    # Simple O(n^2) approach - fine for prototype
    keep = [True] * len(points)
    
    for i in range(len(points)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(points)):
            if not keep[j]:
                continue
            if np.linalg.norm(points[i] - points[j]) < tolerance:
                keep[j] = False
    
    return points[keep]


def compute_path_length(waypoints: np.ndarray) -> float:
    """Compute total length of a path.
    
    Args:
        waypoints: (N, 3) array of waypoints
        
    Returns:
        Total path length
    """
    if len(waypoints) <= 1:
        return 0.0
    
    diffs = np.diff(waypoints, axis=0)
    distances = np.linalg.norm(diffs, axis=1)
    return float(np.sum(distances))


def find_nearest_waypoint(
    position: tuple[float, float, float],
    waypoints: np.ndarray,
    tolerance: float = 1.0
) -> Optional[int]:
    """Find the index of the nearest waypoint to a position.
    
    Args:
        position: (x, y, z) position
        waypoints: (N, 3) array of waypoints
        tolerance: Maximum distance to consider a match
        
    Returns:
        Index of nearest waypoint within tolerance, or None
    """
    if len(waypoints) == 0:
        return None
    
    pos = np.array(position).reshape(1, 3)
    distances = cdist(pos, waypoints)[0]
    min_idx = np.argmin(distances)
    
    if distances[min_idx] <= tolerance:
        return int(min_idx)
    return None
