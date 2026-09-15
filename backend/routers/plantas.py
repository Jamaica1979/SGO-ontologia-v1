from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, to_dict
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/api/plantas", tags=["Planta"], dependencies=[Depends(verificar_acceso)])


@router.get("")
def listar(db: Session = Depends(get_db)):
    return [to_dict(p) for p in db.query(m.Planta).order_by(m.Planta.id).all()]


@router.get("/{planta_id}")
def obtener(planta_id: int, db: Session = Depends(get_db)):
    p = db.query(m.Planta).get(planta_id)
    if not p:
        raise HTTPException(404, "Planta no encontrada")
    return to_dict(p)


@router.post("")
def crear(body: dict, db: Session = Depends(get_db)):
    p = m.Planta(codigo=body["codigo"], nombre=body["nombre"], estado=body.get("estado", "pendiente"), notas=body.get("notas"))
    db.add(p)
    db.commit()
    return to_dict(p)


@router.put("/{planta_id}")
def actualizar(planta_id: int, body: dict, db: Session = Depends(get_db)):
    p = db.query(m.Planta).get(planta_id)
    if not p:
        raise HTTPException(404, "Planta no encontrada")
    for campo in ("codigo", "nombre", "estado", "notas"):
        if campo in body:
            setattr(p, campo, body[campo])
    db.commit()
    return to_dict(p)
