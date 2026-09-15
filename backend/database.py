from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

DB_PATH = Path(__file__).parent / "cantera.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _enable_fk(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def to_dict(obj, exclude=("_sa_instance_state",)):
    """Serializa una instancia de modelo SQLAlchemy a dict plano para JSON."""
    if obj is None:
        return None
    return {k: v for k, v in vars(obj).items() if k not in exclude}


def log_historial(db, tabla: str, registro_id, accion: str, antes: dict = None, despues: dict = None, usuario: str = "sistema"):
    """Registra un evento de auditoría. Se usa desde cada Action — no es opcional,
    es parte de completar la Action, no un agregado aparte."""
    import json
    import models as m
    db.add(m.Historial(
        tabla=tabla, registro_id=registro_id or 0, accion=accion,
        datos_anteriores=json.dumps(antes, ensure_ascii=False, default=str) if antes else None,
        datos_nuevos=json.dumps(despues, ensure_ascii=False, default=str) if despues else None,
        usuario=usuario,
    ))
