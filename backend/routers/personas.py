from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, to_dict
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/api/personas", tags=["Persona"], dependencies=[Depends(verificar_acceso)])


@router.get("")
def listar(activo: bool = True, db: Session = Depends(get_db)):
    q = db.query(m.Persona)
    if activo:
        q = q.filter(m.Persona.activo == 1)
    return [to_dict(p) for p in q.order_by(m.Persona.apellido).all()]


@router.get("/{persona_id}")
def obtener(persona_id: int, db: Session = Depends(get_db)):
    p = db.query(m.Persona).get(persona_id)
    if not p:
        raise HTTPException(404, "Persona no encontrada")
    return to_dict(p)


@router.post("")
def crear(body: dict, db: Session = Depends(get_db)):
    p = m.Persona(nombre=body["nombre"], apellido=body["apellido"], legajo=body.get("legajo"),
                  cuit=body.get("cuit"), convenio_id=body.get("convenio_id"),
                  antiguedad_anos=body.get("antiguedad_anos"),
                  estado_legajo=body.get("estado_legajo", "completo" if body.get("legajo") else "sin_legajo"),
                  notas=body.get("notas"))
    db.add(p)
    db.commit()
    return to_dict(p)


@router.put("/{persona_id}")
def actualizar(persona_id: int, body: dict, db: Session = Depends(get_db)):
    p = db.query(m.Persona).get(persona_id)
    if not p:
        raise HTTPException(404, "Persona no encontrada")
    for campo in ("nombre", "apellido", "legajo", "cuit", "convenio_id", "antiguedad_anos", "estado_legajo", "notas", "activo"):
        if campo in body:
            setattr(p, campo, body[campo])
    db.commit()
    return to_dict(p)
