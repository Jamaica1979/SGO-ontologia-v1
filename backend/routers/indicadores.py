from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, to_dict, log_historial
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/api/indicadores", tags=["Indicador"], dependencies=[Depends(verificar_acceso)])


@router.get("")
def listar(area: str = None, activo: bool = True, db: Session = Depends(get_db)):
    q = db.query(m.Indicador)
    if activo:
        q = q.filter(m.Indicador.activo == 1)
    if area:
        q = q.filter(m.Indicador.area == area)
    return [to_dict(i) for i in q.order_by(m.Indicador.codigo).all()]


@router.get("/{codigo}")
def obtener(codigo: str, db: Session = Depends(get_db)):
    i = db.query(m.Indicador).filter(m.Indicador.codigo == codigo).first()
    if not i:
        raise HTTPException(404, "Indicador no encontrado")
    return to_dict(i)


@router.post("")
def crear(body: dict, db: Session = Depends(get_db)):
    if db.query(m.Indicador).filter(m.Indicador.codigo == body["codigo"]).first():
        raise HTTPException(409, "Ya existe un indicador con ese código")
    i = m.Indicador(codigo=body["codigo"], nombre=body["nombre"], area=body["area"], formula=body.get("formula"),
                     frecuencia=body.get("frecuencia"), fuente_dato=body.get("fuente_dato"),
                     responsable_carga_puesto_codigo=body.get("responsable_carga_puesto_codigo"),
                     responsable_uso_puesto_codigo=body.get("responsable_uso_puesto_codigo"),
                     umbral_verde=body.get("umbral_verde"), umbral_amarillo=body.get("umbral_amarillo"),
                     umbral_rojo=body.get("umbral_rojo"))
    db.add(i)
    db.flush()
    log_historial(db, "indicadores", i.id, "CrearIndicador", despues=to_dict(i))
    db.commit()
    return to_dict(i)


@router.put("/{codigo}")
def actualizar(codigo: str, body: dict, db: Session = Depends(get_db)):
    i = db.query(m.Indicador).filter(m.Indicador.codigo == codigo).first()
    if not i:
        raise HTTPException(404, "Indicador no encontrado")
    antes = to_dict(i)
    for campo in ("nombre", "area", "formula", "frecuencia", "fuente_dato", "responsable_carga_puesto_codigo",
                  "responsable_uso_puesto_codigo", "umbral_verde", "umbral_amarillo", "umbral_rojo", "activo"):
        if campo in body:
            setattr(i, campo, body[campo])
    log_historial(db, "indicadores", i.id, "EditarIndicador", antes=antes, despues=to_dict(i))
    db.commit()
    return to_dict(i)
