from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, to_dict, log_historial
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/api/procedimientos", tags=["Procedimiento"], dependencies=[Depends(verificar_acceso)])


@router.get("")
def listar(area: str = None, vigente: bool = True, db: Session = Depends(get_db)):
    q = db.query(m.Procedimiento)
    if vigente:
        q = q.filter(m.Procedimiento.vigente == 1)
    if area:
        q = q.filter(m.Procedimiento.area == area)
    return [to_dict(p) for p in q.order_by(m.Procedimiento.codigo).all()]


@router.get("/{codigo}")
def obtener(codigo: str, db: Session = Depends(get_db)):
    p = db.query(m.Procedimiento).filter(m.Procedimiento.codigo == codigo).first()
    if not p:
        raise HTTPException(404, "Procedimiento no encontrado")
    return to_dict(p)


@router.post("")
def crear(body: dict, db: Session = Depends(get_db)):
    if db.query(m.Procedimiento).filter(m.Procedimiento.codigo == body["codigo"]).first():
        raise HTTPException(409, "Ya existe un procedimiento con ese código")
    p = m.Procedimiento(codigo=body["codigo"], nombre=body["nombre"], area=body["area"],
                         nivel_riesgo=body.get("nivel_riesgo", "medio"), descripcion=body.get("descripcion"),
                         tiene_nivel_urgente=body.get("tiene_nivel_urgente", 1),
                         tiene_nivel_emergencia=body.get("tiene_nivel_emergencia", 1))
    db.add(p)
    db.flush()
    log_historial(db, "procedimientos", p.id, "CrearProcedimiento", despues=to_dict(p))
    db.commit()
    return to_dict(p)


@router.put("/{codigo}")
def actualizar(codigo: str, body: dict, db: Session = Depends(get_db)):
    p = db.query(m.Procedimiento).filter(m.Procedimiento.codigo == codigo).first()
    if not p:
        raise HTTPException(404, "Procedimiento no encontrado")
    antes = to_dict(p)
    for campo in ("nombre", "area", "nivel_riesgo", "descripcion", "tiene_nivel_urgente", "tiene_nivel_emergencia", "vigente"):
        if campo in body:
            setattr(p, campo, body[campo])
    log_historial(db, "procedimientos", p.id, "EditarProcedimiento", antes=antes, despues=to_dict(p))
    db.commit()
    return to_dict(p)
