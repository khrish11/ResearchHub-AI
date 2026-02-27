from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv
from pathlib import Path
import re

load_dotenv()

# Normalize SQLite path: anchor to backend directory for default/relative URLs
_db_env = os.getenv("DATABASE_URL")
if _db_env:
    if _db_env.startswith("sqlite:///./"):
        _rel = _db_env.replace("sqlite:///./", "")
        _abs = (Path(__file__).resolve().parent / _rel).resolve()
        DATABASE_URL = f"sqlite:///{_abs.as_posix()}"
    elif _db_env.startswith("sqlite:///"):
        # Normalize relative sqlite paths (e.g. sqlite:///researchhub.db) to
        # backend directory so data is stable across different start commands.
        _raw = _db_env.replace("sqlite:///", "", 1)
        _is_windows_abs = bool(re.match(r"^[a-zA-Z]:[\\/]", _raw))
        _path_obj = Path(_raw)
        if _path_obj.is_absolute() or _is_windows_abs:
            DATABASE_URL = _db_env
        else:
            _abs = (Path(__file__).resolve().parent / _raw).resolve()
            DATABASE_URL = f"sqlite:///{_abs.as_posix()}"
    else:
        DATABASE_URL = _db_env
else:
    _abs_default = (Path(__file__).resolve().parent / "researchhub.db").resolve()
    DATABASE_URL = f"sqlite:///{_abs_default.as_posix()}"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
