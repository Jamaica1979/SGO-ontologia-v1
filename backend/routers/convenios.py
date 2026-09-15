from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, to_dict
from auth import verificar_acceso
import models as m

router = APIRouter(tags=["ConvenioColectivo / FuncionOrganizacional"], dependencies=[Depends(verificar_acceso)])


@router.get("/api/convenios")
def listar_convenios(db: Session = Depends(get_db)):
    return [to_dict(c) for c in db.query(m.ConvenioColectivo).all()]


@router.get("/api/funciones-organizacionales")
def listar_funciones(db: Session = Depends(get_db)):
    funciones = db.query(m.FuncionOrganizacional).all()
    out = []
    for f in funciones:
        puestos = [pf.puesto_codigo for pf in db.query(m.PuestoFuncion).filter(m.PuestoFuncion.funcion_id == f.id)]
        out.append({**to_dict(f), "puestos": puestos})
    return out
