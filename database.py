
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase,sessionmaker
from sqlalchemy.ext.declarative import declarative_base


DATABASE_URL = "sqlite:///./ecommerce.db"

engine= create_engine(DATABASE_URL,connect_args={"check_same_thread": False})


SessionLocal=sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()