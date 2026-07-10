from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# Hosted Postgres (Neon/Supabase/Render/etc.) silently drops idle connections,
# after which a pooled connection is dead and the next query fails with
# "server closed the connection unexpectedly". pool_pre_ping checks each
# connection with a lightweight SELECT 1 before use and transparently
# reconnects if it's stale; pool_recycle proactively retires connections that
# have been open too long. SQLite ignores these harmlessly.
_url = settings.DATABASE_URL
_engine_kwargs = {"pool_pre_ping": True, "pool_recycle": 300}
if _url.startswith("sqlite"):
    # SQLite has no real pool; only needs cross-thread access for FastAPI.
    _engine_kwargs = {"connect_args": {"check_same_thread": False}}

engine = create_engine(_url, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()