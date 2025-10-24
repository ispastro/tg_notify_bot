from sqlalchemy import (
    Column, BIGINT,Integer, String, Boolean, DateTime, ForeignKey, Enum, Table, Text
)


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
    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(BIGINT, unique=True, nullable=False)

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

    created_at = Column(DateTime, default=datetime.utcnow)

    admin_id = Column(Integer, ForeignKey("users.id"))

    admin = relationship("User", backref="schedules_created")

    batches = relationship(
        "Batch",
        secondary=schedule_batch_association,
        back_populates="schedules"
    )
