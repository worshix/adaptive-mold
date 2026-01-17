"""STEP file loader with precision geometry extraction.

Supports two backends:
1. pythonocc-core (OCC) - PREFERRED for precise B-Rep geometry
2. trimesh + cascadio - Fallback, tessellates geometry (loses precision)

Provides vertex and edge extraction from STEP/STP files or JSON fallback.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

# Try to import pythonocc-core (OCC) for precise geometry
try:
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
    from OCC.Core.TopoDS import topods_Edge, topods_Vertex
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GCPnts import GCPnts_UniformAbscissa
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib_Add
    OCC_AVAILABLE = True
    logger.info("pythonocc-core (OCC) available - using precise B-Rep geometry")
except ImportError:
    OCC_AVAILABLE = False
    logger.warning("pythonocc-core not available, will try trimesh fallback")

# Try trimesh as fallback
try:
    import trimesh
    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False
    if not OCC_AVAILABLE:
        logger.warning("Neither OCC nor trimesh available, will use sample geometry only")


@dataclass
class GeometryData:
    """Container for extracted geometry data."""
    
    vertices: np.ndarray  # (N, 3) array of vertex positions
    edges: np.ndarray  # (M, 2) array of vertex indices forming edges
    metadata: dict  # Additional metadata (bounding box, vertex count, etc.)
    source: str  # Source file path or "sample"
    
    @property
    def vertex_count(self) -> int:
        """Number of vertices."""
        return len(self.vertices)
    
    @property
    def edge_count(self) -> int:
        """Number of edges."""
        return len(self.edges)
    
    @property
    def bounding_box(self) -> tuple[np.ndarray, np.ndarray]:
        """Get bounding box as (min_point, max_point)."""
        if len(self.vertices) == 0:
            return np.zeros(3), np.zeros(3)
        return self.vertices.min(axis=0), self.vertices.max(axis=0)
    
    @property
    def bounding_box_size(self) -> np.ndarray:
        """Get bounding box dimensions."""
        min_pt, max_pt = self.bounding_box
        return max_pt - min_pt
    
    @property
    def center(self) -> np.ndarray:
        """Get center of bounding box."""
        min_pt, max_pt = self.bounding_box
        return (min_pt + max_pt) / 2
    
    def get_vertices_list(self) -> list[tuple[float, float, float]]:
        """Get vertices as list of tuples."""
        return [(float(v[0]), float(v[1]), float(v[2])) for v in self.vertices]
    
    def get_edge_vertices(self) -> list[tuple[np.ndarray, np.ndarray]]:
        """Get edges as list of (start_vertex, end_vertex) tuples."""
        return [(self.vertices[e[0]], self.vertices[e[1]]) for e in self.edges]


def load_step(file_path: str | Path) -> GeometryData:
    """Load geometry from a CAD file (STEP, STL, OBJ, PLY, etc.).
    
    Backend priority:
    1. pythonocc-core (OCC) - Precise B-Rep geometry for STEP files
    2. trimesh + cascadio - Tessellated geometry (less precise)
    3. Sample geometry fallback
    
    Args:
        file_path: Path to CAD file
        
    Returns:
        GeometryData containing vertices, edges, and metadata
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}, using sample geometry")
        return load_sample_geometry()
    
    suffix = file_path.suffix.lower()
    
    # For STEP files, try OCC first (precise), then trimesh (tessellated)
    if suffix in ['.step', '.stp']:
        if OCC_AVAILABLE:
            try:
                return _load_step_with_occ(file_path)
            except Exception as e:
                logger.warning(f"OCC failed to load STEP: {e}, trying trimesh fallback")
        
        # Try trimesh+cascadio as fallback
        if TRIMESH_AVAILABLE:
            try:
                return _load_with_trimesh(file_path)
            except Exception as e:
                logger.warning(f"trimesh failed to load STEP: {e}")
        
        logger.error("No STEP loader available, using sample geometry")
        return load_sample_geometry()
    
    # For mesh files (STL, OBJ, etc.), use trimesh
    if TRIMESH_AVAILABLE:
        try:
            return _load_with_trimesh(file_path)
        except Exception as e:
            logger.error(f"Failed to load file: {e}, using sample geometry")
            return load_sample_geometry()
    
    logger.warning("No geometry loader available, using sample geometry")
    return load_sample_geometry()


def _load_step_with_occ(file_path: Path) -> GeometryData:
    """Load STEP file using pythonocc-core for precise B-Rep geometry.
    
    This extracts actual vertices and edges from the B-Rep topology,
    preserving engineering precision.
    
    Args:
        file_path: Path to STEP file
        
    Returns:
        GeometryData with precise geometry
    """
    logger.info(f"Loading STEP with OCC (precise): {file_path}")
    
    # Read STEP file
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(file_path))
    
    if status != IFSelect_RetDone:
        raise RuntimeError(f"Failed to read STEP file: status {status}")
    
    reader.TransferRoots()
    shape = reader.OneShape()
    
    # Extract vertices
    vertex_coords = []
    vertex_map = {}  # Map from OCC vertex hash to index
    
    vertex_explorer = TopExp_Explorer(shape, TopAbs_VERTEX)
    while vertex_explorer.More():
        vertex = topods_Vertex(vertex_explorer.Current())
        pnt = BRep_Tool.Pnt(vertex)
        coord = (pnt.X(), pnt.Y(), pnt.Z())
        
        # Use coordinate tuple as key to avoid duplicates
        coord_key = (round(coord[0], 6), round(coord[1], 6), round(coord[2], 6))
        if coord_key not in vertex_map:
            vertex_map[coord_key] = len(vertex_coords)
            vertex_coords.append(coord)
        
        vertex_explorer.Next()
    
    vertices = np.array(vertex_coords, dtype=np.float64)
    
    # Extract edges
    edge_list = []
    edge_explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    
    while edge_explorer.More():
        edge = topods_Edge(edge_explorer.Current())
        
        try:
            # Get edge curve and sample points along it
            curve = BRepAdaptor_Curve(edge)
            first = curve.FirstParameter()
            last = curve.LastParameter()
            
            # Get start and end points
            start_pnt = curve.Value(first)
            end_pnt = curve.Value(last)
            
            start_coord = (round(start_pnt.X(), 6), round(start_pnt.Y(), 6), round(start_pnt.Z(), 6))
            end_coord = (round(end_pnt.X(), 6), round(end_pnt.Y(), 6), round(end_pnt.Z(), 6))
            
            # Find or add vertices
            if start_coord not in vertex_map:
                vertex_map[start_coord] = len(vertices)
                vertices = np.vstack([vertices, [start_pnt.X(), start_pnt.Y(), start_pnt.Z()]])
            if end_coord not in vertex_map:
                vertex_map[end_coord] = len(vertices)
                vertices = np.vstack([vertices, [end_pnt.X(), end_pnt.Y(), end_pnt.Z()]])
            
            start_idx = vertex_map[start_coord]
            end_idx = vertex_map[end_coord]
            
            if start_idx != end_idx:
                edge_list.append([start_idx, end_idx])
                
        except Exception as e:
            logger.debug(f"Skipping edge: {e}")
        
        edge_explorer.Next()
    
    edges = np.array(edge_list, dtype=np.int64) if edge_list else np.array([]).reshape(0, 2)
    
    # Get bounding box
    bbox = Bnd_Box()
    brepbndlib_Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    
    metadata = {
        "source_file": str(file_path),
        "file_format": file_path.suffix.lower(),
        "loader": "pythonocc-core (precise B-Rep)",
        "vertex_count": len(vertices),
        "edge_count": len(edges),
        "bounding_box_min": [xmin, ymin, zmin],
        "bounding_box_max": [xmax, ymax, zmax],
        "bounding_box_size": [xmax - xmin, ymax - ymin, zmax - zmin],
    }
    
    logger.info(f"OCC loaded {len(vertices)} vertices, {len(edges)} edges (precise B-Rep)")
    
    return GeometryData(
        vertices=vertices,
        edges=edges,
        metadata=metadata,
        source=str(file_path)
    )


def _load_with_trimesh(file_path: Path) -> GeometryData:
    """Load geometry file using trimesh (tessellated, less precise).
    
    Args:
        file_path: Path to CAD/mesh file
        
    Returns:
        GeometryData with tessellated geometry
    """
    logger.info(f"Loading with trimesh (tessellated): {file_path}")
    
    # Try to load with trimesh
    mesh = trimesh.load(str(file_path))
    
    # Handle different return types from trimesh
    if isinstance(mesh, trimesh.Scene):
        # Scene with multiple geometries - combine them
        geometries = list(mesh.geometry.values())
        if not geometries:
            raise ValueError("Empty scene")
        
        all_vertices = []
        all_edges = []
        vertex_offset = 0
        
        for geom in geometries:
            if hasattr(geom, 'vertices') and hasattr(geom, 'edges'):
                all_vertices.append(geom.vertices)
                all_edges.append(geom.edges + vertex_offset)
                vertex_offset += len(geom.vertices)
            elif hasattr(geom, 'vertices') and hasattr(geom, 'faces'):
                # Extract edges from faces
                all_vertices.append(geom.vertices)
                edges = _extract_edges_from_faces(geom.faces)
                all_edges.append(edges + vertex_offset)
                vertex_offset += len(geom.vertices)
        
        if all_vertices:
            vertices = np.vstack(all_vertices)
            edges = np.vstack(all_edges) if all_edges else np.array([]).reshape(0, 2)
        else:
            raise ValueError("No valid geometry found in scene")
            
    elif hasattr(mesh, 'vertices'):
        vertices = mesh.vertices
        
        if hasattr(mesh, 'edges') and len(mesh.edges) > 0:
            edges = mesh.edges
        elif hasattr(mesh, 'faces'):
            edges = _extract_edges_from_faces(mesh.faces)
        else:
            # Create edges from vertices (connect sequential vertices)
            edges = np.array([[i, i + 1] for i in range(len(vertices) - 1)])
    else:
        raise ValueError("Unsupported geometry type")
    
    # Build metadata
    min_pt, max_pt = vertices.min(axis=0), vertices.max(axis=0)
    metadata = {
        "source_file": str(file_path),
        "file_format": file_path.suffix.lower(),
        "loader": "trimesh (tessellated)",
        "vertex_count": len(vertices),
        "edge_count": len(edges),
        "bounding_box_min": min_pt.tolist(),
        "bounding_box_max": max_pt.tolist(),
        "bounding_box_size": (max_pt - min_pt).tolist(),
    }
    
    logger.info(f"trimesh loaded {len(vertices)} vertices, {len(edges)} edges")
    
    return GeometryData(
        vertices=vertices.astype(np.float64),
        edges=edges.astype(np.int64),
        metadata=metadata,
        source=str(file_path)
    )


def _extract_edges_from_faces(faces: np.ndarray) -> np.ndarray:
    """Extract unique edges from face indices.
    
    Args:
        faces: (N, 3) array of face vertex indices (triangles)
        
    Returns:
        (M, 2) array of unique edges
    """
    edges_set = set()
    
    for face in faces:
        for i in range(len(face)):
            v1, v2 = face[i], face[(i + 1) % len(face)]
            # Normalize edge direction to avoid duplicates
            edge = (min(v1, v2), max(v1, v2))
            edges_set.add(edge)
    
    return np.array(list(edges_set), dtype=np.int64)


def load_sample_geometry() -> GeometryData:
    """Load sample geometry from JSON file.
    
    Returns:
        GeometryData with sample cube/wireframe
    """
    sample_path = Path(__file__).parent.parent / "resources" / "sample_geometry.json"
    
    if sample_path.exists():
        return load_geometry_json(sample_path)
    else:
        logger.warning(f"Sample geometry not found at {sample_path}, generating default cube")
        return _generate_default_cube()


def load_geometry_json(file_path: str | Path) -> GeometryData:
    """Load geometry from a JSON file.
    
    Expected JSON format:
    {
        "vertices": [[x, y, z], ...],
        "edges": [[v1, v2], ...],
        "metadata": {...}
    }
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        GeometryData
    """
    file_path = Path(file_path)
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    vertices = np.array(data.get("vertices", []), dtype=np.float64)
    edges = np.array(data.get("edges", []), dtype=np.int64)
    metadata = data.get("metadata", {})
    
    # Add computed metadata if not present
    if "vertex_count" not in metadata:
        metadata["vertex_count"] = len(vertices)
    if "edge_count" not in metadata:
        metadata["edge_count"] = len(edges)
    if len(vertices) > 0:
        min_pt, max_pt = vertices.min(axis=0), vertices.max(axis=0)
        metadata["bounding_box_min"] = min_pt.tolist()
        metadata["bounding_box_max"] = max_pt.tolist()
        metadata["bounding_box_size"] = (max_pt - min_pt).tolist()
    
    logger.info(f"Loaded {len(vertices)} vertices, {len(edges)} edges from {file_path}")
    
    return GeometryData(
        vertices=vertices,
        edges=edges,
        metadata=metadata,
        source=str(file_path)
    )


def _generate_default_cube() -> GeometryData:
    """Generate a default cube wireframe.
    
    Returns:
        GeometryData for a 100x100x100 cube centered at origin
    """
    # Cube vertices (100mm cube centered at origin)
    size = 50.0
    vertices = np.array([
        [-size, -size, -size],  # 0
        [ size, -size, -size],  # 1
        [ size,  size, -size],  # 2
        [-size,  size, -size],  # 3
        [-size, -size,  size],  # 4
        [ size, -size,  size],  # 5
        [ size,  size,  size],  # 6
        [-size,  size,  size],  # 7
    ], dtype=np.float64)
    
    # Cube edges
    edges = np.array([
        # Bottom face
        [0, 1], [1, 2], [2, 3], [3, 0],
        # Top face
        [4, 5], [5, 6], [6, 7], [7, 4],
        # Vertical edges
        [0, 4], [1, 5], [2, 6], [3, 7],
    ], dtype=np.int64)
    
    metadata = {
        "type": "generated_cube",
        "size": size * 2,
        "vertex_count": len(vertices),
        "edge_count": len(edges),
        "bounding_box_min": [-size, -size, -size],
        "bounding_box_max": [size, size, size],
        "bounding_box_size": [size * 2, size * 2, size * 2],
    }
    
    return GeometryData(
        vertices=vertices,
        edges=edges,
        metadata=metadata,
        source="generated"
    )


def save_geometry_json(geometry: GeometryData, file_path: str | Path) -> None:
    """Save geometry to a JSON file.
    
    Args:
        geometry: GeometryData to save
        file_path: Output path
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "vertices": geometry.vertices.tolist(),
        "edges": geometry.edges.tolist(),
        "metadata": geometry.metadata,
    }
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved geometry to {file_path}")
