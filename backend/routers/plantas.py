from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, to_dict, log_historial
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
    if db.query(m.Planta).filter(m.Planta.codigo == body["codigo"]).first():
        raise HTTPException(409, "Ya existe una planta con ese código")
    p = m.Planta(codigo=body["codigo"], nombre=body["nombre"], estado=body.get("estado", "pendiente"), notas=body.get("notas"))
    db.add(p)
    db.flush()
    log_historial(db, "plantas", p.id, "CrearPlanta", despues=to_dict(p))
    db.commit()
    return to_dict(p)


@router.put("/{planta_id}")
def actualizar(planta_id: int, body: dict, db: Session = Depends(get_db)):
    p = db.query(m.Planta).get(planta_id)
    if not p:
        raise HTTPException(404, "Planta no encontrada")
    antes = to_dict(p)
    for campo in ("codigo", "nombre", "estado", "notas"):
        if campo in body:
            setattr(p, campo, body[campo])
    log_historial(db, "plantas", p.id, "EditarPlanta", antes=antes, despues=to_dict(p))
    db.commit()
    return to_dict(p)
