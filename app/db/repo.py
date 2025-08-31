from sqlmodel import SQLModel, Session, create_engine
import os

DB_URL = os.getenv("DB_URL", "sqlite:///./app.db")
engine = create_engine(DB_URL, echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)

# call on startup elsewhere if needed
