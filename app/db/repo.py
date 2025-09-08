# =============================================
# File: app/db/repo.py
# Purpose: DB repository bootstrap: configure engine from DB_URL (default SQLite) and expose init_db() to create tables.
# =============================================

from sqlmodel import SQLModel, Session, create_engine
import os

DB_URL = os.getenv("DB_URL", "sqlite:///./app.db")
engine = create_engine(DB_URL, echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)

# call on startup elsewhere if needed
