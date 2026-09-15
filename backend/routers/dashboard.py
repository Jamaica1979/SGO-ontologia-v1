from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from auth import verificar_acceso
from functions import calcular_cobertura, resumen_cobertura, detectar_alertas, bandeja_de_pendientes as _bandeja
import models as m

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"], dependencies=[Depends(verificar_acceso)])


@router.get("/resumen")
def resumen(db: Session = Depends(get_db)):
    filas = calcular_cobertura(db)
    plantas = db.query(m.Planta).all()
    por_planta = []
    for pl in plantas:
        fs = [f for f in filas if f["planta_id"] == pl.id]
        cub = len([f for f in fs if f["estado"] in ("cubierta", "cubierta_sin_etapa")])
        por_planta.append({"planta_id": pl.id, "planta": pl.nombre, "estado": pl.estado,
                            "total": len(fs), "cubiertas": cub})
    return {"general": resumen_cobertura(filas), "por_planta": por_planta}


@router.get("/pendientes")
def bandeja_de_pendientes(db: Session = Depends(get_db)):
    """Sección 11: reemplaza la tabla plana de Distribución de actividades por
    una cola corta, priorizada. La lógica vive en functions.py, compartida con
    la UI (Etapa 4) para que ambas muestren siempre lo mismo."""
    return _bandeja(db)


@router.get("/alertas")
def alertas(db: Session = Depends(get_db)):
    al = detectar_alertas(db)
    return {"total": len(al), "alertas": al}
