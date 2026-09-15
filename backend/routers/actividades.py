from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, to_dict
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/api/actividades", tags=["Actividad"], dependencies=[Depends(verificar_acceso)])


@router.get("")
def listar(area: str = None, puesto_codigo: str = None, activo: bool = True, db: Session = Depends(get_db)):
    q = db.query(m.Actividad)
    if activo:
        q = q.filter(m.Actividad.activo == 1)
    if area:
        q = q.filter(m.Actividad.area == area)
    if puesto_codigo:
        q = q.filter(m.Actividad.puesto_codigo == puesto_codigo)
    return [to_dict(a) for a in q.order_by(m.Actividad.codigo).all()]


@router.get("/{codigo}")
def obtener(codigo: str, db: Session = Depends(get_db)):
    a = db.query(m.Actividad).filter(m.Actividad.codigo == codigo).first()
    if not a:
        raise HTTPException(404, "Actividad no encontrada")
    return to_dict(a)


@router.post("")
def crear(body: dict, db: Session = Depends(get_db)):
    a = m.Actividad(codigo=body["codigo"], descripcion=body["descripcion"], area=body["area"], nivel=body["nivel"],
                     competencia=body.get("competencia"), es_critica=body.get("es_critica", 0),
                     frecuencia=body.get("frecuencia"), notas=body.get("notas"),
                     puesto_codigo=body.get("puesto_codigo"), funcion_organizacional_id=body.get("funcion_organizacional_id"))
    db.add(a)
    db.commit()
    return to_dict(a)


@router.put("/{codigo}")
def actualizar(codigo: str, body: dict, db: Session = Depends(get_db)):
    a = db.query(m.Actividad).filter(m.Actividad.codigo == codigo).first()
    if not a:
        raise HTTPException(404, "Actividad no encontrada")
    for campo in ("descripcion", "area", "nivel", "competencia", "es_critica", "frecuencia", "notas",
                  "puesto_codigo", "funcion_organizacional_id", "activo"):
        if campo in body:
            setattr(a, campo, body[campo])
    db.commit()
    return to_dict(a)
