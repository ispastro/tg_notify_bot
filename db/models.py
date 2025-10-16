from sqlalchemy import Column , Integer , String, Boolean,DateTime, Enum, ForeignKey, Table
from sqlalchemy.orm  import  declarative_base, relationship
from datetime import datetime
import enum
Base = declarative_base()

class ScheduleType(enum.Enum):
      custom= "custom"
      weekly= "weekly"
      monthly= "monthly"

Schedule_batch = Table(
     "schedule_batch",
      Base.metadata,
      Column("schedule_id", ForeignKey("schedules.id"), primary_key=True),
      Column("batch_name", ForeignKey("batches.name"), primary_key=True),

)



class User(Base):
     __tablename__ = "users"
     id = Column(Integer, primary_key=True, index=True)
     user_id = Column(Integer , unique=True, nullable =False)
     username = Column(String, nullable=True)
     is_admin = Column(Boolean, default =False)
     batch = Column(String , nullable =False  )
     join_date = Column(DateTime, default=datetime.utcnow)


class Schedule(Base):
   __tablename__ ="schedules"
   id = Column(Integer, primary_key =True , index=True)
   batch = Column(String , nullable = False )
   message = Column(String, nullable = False )
   created_at = Column(DateTime, default = datetime.utcnow)
      
class Batch(Base):
     __tablename__="batches"
     name =Column(String, primary_key=True)
     users=relationship("Schedule", secondary=Schedule_batch, batch_populates="batches")
     

