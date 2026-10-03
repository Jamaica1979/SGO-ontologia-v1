from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, to_dict
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/api/formularios", tags=["Formulario"], dependencies=[Depends(verificar_acceso)])


@router.get("")
def listar(db: Session = Depends(get_db)):
    return [to_dict(f) for f in db.query(m.Formulario).order_by(m.Formulario.codigo).all()]


@router.get("/{codigo}")
def obtener(codigo: str, db: Session = Depends(get_db)):
    f = db.query(m.Formulario).filter(m.Formulario.codigo == codigo).first()
    if not f:
        raise HTTPException(404, "Formulario no encontrado")
    return to_dict(f)


@router.post("")
def crear(body: dict, db: Session = Depends(get_db)):
    if db.query(m.Formulario).filter(m.Formulario.codigo == body["codigo"]).first():
        raise HTTPException(409, "Ya existe un formulario con ese código")
    f = m.Formulario(codigo=body["codigo"], nombre=body["nombre"], origen=body.get("origen"),
                      emisor=body.get("emisor"), receptor=body.get("receptor"), frecuencia=body.get("frecuencia"))
    db.add(f)
    db.commit()
    return to_dict(f)


@router.put("/{codigo}")
def actualizar(codigo: str, body: dict, db: Session = Depends(get_db)):
    f = db.query(m.Formulario).filter(m.Formulario.codigo == codigo).first()
    if not f:
        raise HTTPException(404, "Formulario no encontrado")
    for campo in ("nombre", "origen", "emisor", "receptor", "frecuencia"):
        if campo in body:
            setattr(f, campo, body[campo])
    db.commit()
    return to_dict(f)


@router.delete("/{codigo}")
def eliminar(codigo: str, db: Session = Depends(get_db)):
    f = db.query(m.Formulario).filter(m.Formulario.codigo == codigo).first()
    if not f:
        raise HTTPException(404, "Formulario no encontrado")
    db.query(m.ProcedimientoFormulario).filter(m.ProcedimientoFormulario.formulario_id == f.id).delete()
    db.query(m.MecanismoFormulario).filter(m.MecanismoFormulario.formulario_id == f.id).delete()
    db.delete(f)
    db.commit()
    return {"message": "Formulario eliminado"}
