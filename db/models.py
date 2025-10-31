# db/models.py — ULTIMATE VERSION
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Table, Text
)
from sqlalchemy.dialects.postgresql import BIGINT
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class ScheduleType(enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

schedule_batch_association = Table(
    "schedule_batch_association",
    Base.metadata,
    Column("schedule_id", ForeignKey("schedules.id"), primary_key=True),
    Column("batch_id", ForeignKey("batches.id"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)  # Internal DB ID
    user_id = Column(BIGINT, unique=True, nullable=False)  # Telegram ID
    username = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)
    join_date = Column(DateTime, default=datetime.utcnow)
    batch = relationship("Batch", back_populates="users")

class Batch(Base):
    __tablename__ = "batches"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    users = relationship("User", back_populates="batch")
    schedules = relationship(
        "Schedule",
        secondary=schedule_batch_association,
        back_populates="batches"
    )

class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(Integer, primary_key=True)
    message = Column(Text, nullable=False)
    type = Column(Enum(ScheduleType), nullable=False)
    cron_expr = Column(String, nullable=True)      # e.g., "0 9 * * 1"
    next_run = Column(DateTime, nullable=True)     # When to send next
    created_at = Column(DateTime, default=datetime.utcnow)
    admin_id = Column(BIGINT, nullable=False)      # ← Telegram ID
    is_active = Column(Boolean, default=True)
    batches = relationship(
        "Batch",
        secondary=schedule_batch_association,
        back_populates="schedules"
    )