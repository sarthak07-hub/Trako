from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

def utc_now() -> datetime:
    """Return naive UTC datetime across Python 3.12+ without deprecation warnings."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

# Normalize database URL
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    # Ensure psycopg v3 dialect is specified for SQLAlchemy
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

is_sqlite = db_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
