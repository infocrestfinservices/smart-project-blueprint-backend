import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# Fetch database URL from settings or environment
_url = settings.DATABASE_URL

_engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

if _url.startswith("sqlite"):
    # SQLite configuration for local testing
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL / Supabase Fixes:
    # 1. Fix old "postgres://" protocol if present
    if _url.startswith("postgres://"):
        _url = _url.replace("postgres://", "postgresql://", 1)
    
    # 2. Force SSL mode and explicit 10s connect timeout to avoid hanging requests
    _engine_kwargs["connect_args"] = {
        "sslmode": "require",
        "connect_timeout": 10
    }

engine = create_engine(_url, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()