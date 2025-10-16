from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
engine = create_engine(DATABASE_URL)

Sessionlocal  = sessionmaker(autoflush=False , autocommit=False , bind=engine)

db = Sessionlocal()


def get_db():
    try:
        yield db
    finally:
        db.close()    
