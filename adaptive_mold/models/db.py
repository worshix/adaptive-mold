"""SQLAlchemy database setup and models for Adaptive Mold.

Models:
- Job: Main job record with metadata
- JobGeometry: Vertices extracted from STEP file
- Waypoint: Computed path waypoints for a job
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class Job(Base):
    """Job record storing metadata about a mapping job."""
    
    __tablename__ = "jobs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(50), default="created")  # created, planning, mapping, completed, error
    planner_params = Column(Text, nullable=True)  # JSON string for planner configuration
    
    # Relationships
    geometries = relationship("JobGeometry", back_populates="job", cascade="all, delete-orphan")
    waypoints = relationship("Waypoint", back_populates="job", cascade="all, delete-orphan")
    
    def get_planner_params(self) -> dict:
        """Get planner params as dictionary."""
        if self.planner_params:
            return json.loads(self.planner_params)
        return {}
    
    def set_planner_params(self, params: dict) -> None:
        """Set planner params from dictionary."""
        self.planner_params = json.dumps(params)
    
    def __repr__(self) -> str:
        return f"<Job(id={self.id}, name={self.name}, status={self.status})>"


class JobGeometry(Base):
    """Vertex data extracted from STEP file for a job."""
    
    __tablename__ = "job_geometries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    vertex_index = Column(Integer, nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float, nullable=False)
    
    # Relationship
    job = relationship("Job", back_populates="geometries")
    
    def __repr__(self) -> str:
        return f"<JobGeometry(job_id={self.job_id}, idx={self.vertex_index}, pos=({self.x}, {self.y}, {self.z}))>"


class Waypoint(Base):
    """Waypoint in the computed path for a job."""
    
    __tablename__ = "waypoints"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    index = Column(Integer, nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float, nullable=False)
    visited = Column(Boolean, default=False)
    
    # Relationship
    job = relationship("Job", back_populates="waypoints")
    
    def __repr__(self) -> str:
        return f"<Waypoint(job_id={self.job_id}, idx={self.index}, pos=({self.x}, {self.y}, {self.z}), visited={self.visited})>"


class Database:
    """Database manager for Adaptive Mold."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Default to data directory in project root
            project_root = Path(__file__).parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "adaptive_mold.db")
        
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
    def create_tables(self) -> None:
        """Create all database tables."""
        Base.metadata.create_all(self.engine)
    
    def drop_tables(self) -> None:
        """Drop all database tables."""
        Base.metadata.drop_all(self.engine)
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
    
    def create_job(
        self, 
        name: str, 
        filename: Optional[str] = None,
        planner_params: Optional[dict] = None
    ) -> Job:
        """Create a new job.
        
        Args:
            name: Job name
            filename: Source STEP filename
            planner_params: Dictionary of planner configuration
            
        Returns:
            Created Job instance
        """
        with self.get_session() as session:
            job = Job(name=name, filename=filename)
            if planner_params:
                job.set_planner_params(planner_params)
            session.add(job)
            session.commit()
            session.refresh(job)
            # Expunge to use outside session
            session.expunge(job)
            return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        with self.get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                session.expunge(job)
            return job
    
    def get_all_jobs(self) -> list[Job]:
        """Get all jobs ordered by creation date."""
        with self.get_session() as session:
            jobs = session.query(Job).order_by(Job.created_at.desc()).all()
            for job in jobs:
                session.expunge(job)
            return jobs
    
    def update_job_status(self, job_id: str, status: str) -> Optional[Job]:
        """Update job status."""
        with self.get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = status
                session.commit()
                session.refresh(job)
                session.expunge(job)
            return job
    
    def add_geometry(self, job_id: str, vertices: list[tuple[float, float, float]]) -> None:
        """Add geometry vertices to a job.
        
        Args:
            job_id: Job ID
            vertices: List of (x, y, z) tuples
        """
        with self.get_session() as session:
            for idx, (x, y, z) in enumerate(vertices):
                geom = JobGeometry(job_id=job_id, vertex_index=idx, x=x, y=y, z=z)
                session.add(geom)
            session.commit()
    
    def get_geometry(self, job_id: str) -> list[tuple[float, float, float]]:
        """Get geometry vertices for a job.
        
        Returns:
            List of (x, y, z) tuples ordered by vertex_index
        """
        with self.get_session() as session:
            geometries = (
                session.query(JobGeometry)
                .filter(JobGeometry.job_id == job_id)
                .order_by(JobGeometry.vertex_index)
                .all()
            )
            return [(g.x, g.y, g.z) for g in geometries]
    
    def add_waypoints(self, job_id: str, waypoints: list[tuple[float, float, float]]) -> None:
        """Add waypoints to a job.
        
        Args:
            job_id: Job ID
            waypoints: List of (x, y, z) tuples in order
        """
        with self.get_session() as session:
            # Clear existing waypoints
            session.query(Waypoint).filter(Waypoint.job_id == job_id).delete()
            
            for idx, (x, y, z) in enumerate(waypoints):
                wp = Waypoint(job_id=job_id, index=idx, x=x, y=y, z=z, visited=False)
                session.add(wp)
            session.commit()
    
    def get_waypoints(self, job_id: str) -> list[tuple[int, float, float, float, bool]]:
        """Get waypoints for a job.
        
        Returns:
            List of (index, x, y, z, visited) tuples
        """
        with self.get_session() as session:
            waypoints = (
                session.query(Waypoint)
                .filter(Waypoint.job_id == job_id)
                .order_by(Waypoint.index)
                .all()
            )
            return [(w.index, w.x, w.y, w.z, w.visited) for w in waypoints]
    
    def mark_waypoint_visited(self, job_id: str, index: int) -> None:
        """Mark a waypoint as visited."""
        with self.get_session() as session:
            waypoint = (
                session.query(Waypoint)
                .filter(Waypoint.job_id == job_id, Waypoint.index == index)
                .first()
            )
            if waypoint:
                waypoint.visited = True
                session.commit()
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job and all associated data."""
        with self.get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                session.delete(job)
                session.commit()
                return True
            return False


# Global database instance (initialized on first import)
_db: Optional[Database] = None


def get_database() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
        _db.create_tables()
    return _db


def init_database(db_path: Optional[str] = None) -> Database:
    """Initialize the database with a custom path."""
    global _db
    _db = Database(db_path)
    _db.create_tables()
    return _db
