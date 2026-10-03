from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, to_dict, log_historial
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/api/puestos", tags=["Puesto"], dependencies=[Depends(verificar_acceso)])


@router.get("")
def listar(area: str = None, vigente: bool = True, db: Session = Depends(get_db)):
    q = db.query(m.Puesto)
    if vigente:
        q = q.filter(m.Puesto.vigente == 1)
    if area:
        q = q.filter(m.Puesto.area == area)
    return [to_dict(p) for p in q.order_by(m.Puesto.codigo).all()]


@router.get("/{codigo}")
def obtener(codigo: str, db: Session = Depends(get_db)):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    if not p:
        raise HTTPException(404, "Puesto no encontrado")
    return to_dict(p)


@router.post("")
def crear(body: dict, db: Session = Depends(get_db)):
    if db.query(m.Puesto).filter(m.Puesto.codigo == body["codigo"]).first():
        raise HTTPException(409, "Ya existe un puesto con ese código")
    p = m.Puesto(codigo=body["codigo"], nombre=body["nombre"], area=body["area"], nivel=body["nivel"],
                 cardinalidad_esperada=body.get("cardinalidad_esperada", "unica_en_la_empresa"),
                 proposito=body.get("proposito"), limites_autoridad=body.get("limites_autoridad"),
                 convenio_id=body.get("convenio_id"))
    db.add(p)
    db.flush()
    log_historial(db, "puestos", p.id, "CrearPuesto", despues=to_dict(p))
    db.commit()
    return to_dict(p)


@router.put("/{codigo}")
def actualizar(codigo: str, body: dict, db: Session = Depends(get_db)):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    if not p:
        raise HTTPException(404, "Puesto no encontrado")
    antes = to_dict(p)
    for campo in ("nombre", "area", "nivel", "cardinalidad_esperada", "proposito", "limites_autoridad", "convenio_id", "vigente"):
        if campo in body:
            setattr(p, campo, body[campo])
    log_historial(db, "puestos", p.id, "EditarPuesto", antes=antes, despues=to_dict(p))
    db.commit()
    return to_dict(p)


@router.get("/{codigo}/relaciones")
def relaciones(codigo: str, db: Session = Depends(get_db)):
    """Link Type relaciones_reporte — separado en jerárquico y funcional (Caso 1)."""
    filas = db.query(m.RelacionReporte).filter(m.RelacionReporte.puesto_codigo == codigo).all()
    return {
        "reporta_jerarquicamente_a": [r.relacionado_codigo for r in filas if r.tipo == "jerarquico"],
        "coordina_funcionalmente_con": [r.relacionado_codigo for r in filas if r.tipo == "funcional"],
    }
