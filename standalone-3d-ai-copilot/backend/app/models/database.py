from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DBZone(Base):
    __tablename__ = "zones"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    status = Column(String, default="NORMAL")
    boundaries = Column(JSON, nullable=True)

class DBMachine(Base):
    __tablename__ = "machines"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    zone_id = Column(String, index=True)
    status = Column(String, default="NORMAL")
    parameters = Column(JSON, nullable=False)
    uptime_hours = Column(Integer, default=1200)
    last_maintenance = Column(String, default="2026-09-01T08:00:00Z")
    position = Column(JSON, nullable=True)

class DBSensor(Base):
    __tablename__ = "sensors"
    id = Column(String, primary_key=True, index=True)
    type = Column(String, index=True)
    zone_id = Column(String, index=True)
    machine_id = Column(String, nullable=True)
    unit = Column(String)
    current_value = Column(Float, default=0.0)
    status = Column(String, default="INFO")
    last_updated = Column(DateTime, default=datetime.utcnow)
    threshold_warning = Column(Float, nullable=True)
    threshold_critical = Column(Float, nullable=True)

class DBWorker(Base):
    __tablename__ = "workers"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String)
    zone_id = Column(String, index=True)
    status = Column(String, default="ON_SITE")
    entry_time = Column(String)
    working_hours_today = Column(Float, default=0.0)
    ppe = Column(JSON)
    position = Column(JSON, nullable=True)

class DBCamera(Base):
    __tablename__ = "cameras"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    zone_id = Column(String, index=True)
    status = Column(String, default="ONLINE")
    feed_url = Column(String, nullable=True)
    detected_objects = Column(JSON, default=list)
    last_event = Column(String, nullable=True)

class DBIncident(Base):
    __tablename__ = "incidents"
    id = Column(String, primary_key=True, index=True)
    type = Column(String, index=True)
    severity = Column(String, default="WARNING")
    confidence = Column(Float, default=0.85)
    zone_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    affected_assets = Column(JSON, default=list)
    affected_workers = Column(JSON, default=list)
    evidence = Column(JSON, default=list)
    ai_reasoning = Column(Text)
    recommended_actions = Column(JSON, default=list)
    status = Column(String, default="ACTIVE")

class DBAction(Base):
    __tablename__ = "actions"
    id = Column(String, primary_key=True, index=True)
    incident_id = Column(String, nullable=True)
    action_type = Column(String, nullable=False)
    target = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    risk_level = Column(String, default="MEDIUM")
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, default="recommendation_agent")
    authorized_by = Column(String, nullable=True)
    authorized_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    verification = Column(JSON, nullable=True)

class DBRisk(Base):
    __tablename__ = "risks"
    id = Column(String, primary_key=True, index=True)
    type = Column(String, nullable=False)
    zone_id = Column(String, index=True)
    severity = Column(String, default="WARNING")
    probability = Column(Float, default=0.5)
    impact = Column(String)
    contributing_factors = Column(JSON, default=list)
    assessed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="ACTIVE")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
