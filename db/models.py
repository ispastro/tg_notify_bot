from sqlalchemy import Column , Integer , String, Boolean,DateTime
from sqlalchemy.ext.declarative  import  declarative_base 
from datetime import datetime
Base = declarative_base()

class User(Base):
     __tablename__ = "users"
     id = Column(Integer, primary_key=True, index=True)
     user_id = Column(Integer , unique=True, nullabel =False)
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
      
