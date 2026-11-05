"""Conexão com o banco (SQLite no dev, PostgreSQL em produção)."""
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

E_SQLITE = settings.DATABASE_URL.startswith("sqlite")
E_POSTGRES = settings.DATABASE_URL.startswith("postgresql")

if E_SQLITE:
    os.makedirs(settings.DATA_DIR, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30} if E_SQLITE else {},
    pool_pre_ping=True,
)

if E_SQLITE:
    # WAL permite API e worker (processos diferentes) lendo/escrevendo juntos
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401  (registra as tabelas)
    Base.metadata.create_all(engine)
