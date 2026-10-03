from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, to_dict, log_historial
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/api/mecanismos", tags=["Mecanismo"], dependencies=[Depends(verificar_acceso)])


@router.post("")
def crear(body: dict, db: Session = Depends(get_db)):
    if db.query(m.Mecanismo).filter(m.Mecanismo.codigo == body["codigo"]).first():
        raise HTTPException(409, "Ya existe un mecanismo con ese código")
    mec = m.Mecanismo(codigo=body["codigo"], nombre=body["nombre"], grupo=body["grupo"],
                       frecuencia=body.get("frecuencia"), descripcion=body.get("descripcion"),
                       documento=body.get("documento"), emite=body.get("emite"), recibe=body.get("recibe"),
                       estado_relevado=body.get("estado_relevado"))
    db.add(mec)
    db.flush()
    log_historial(db, "mecanismos", mec.id, "CrearMecanismo", despues=to_dict(mec))
    db.commit()
    return to_dict(mec)


@router.put("/{codigo}")
def actualizar(codigo: str, body: dict, db: Session = Depends(get_db)):
    mec = db.query(m.Mecanismo).filter(m.Mecanismo.codigo == codigo).first()
    if not mec:
        raise HTTPException(404, "Mecanismo no encontrado")
    antes = to_dict(mec)
    for campo in ("nombre", "grupo", "frecuencia", "descripcion", "documento", "emite", "recibe", "estado_relevado", "vigente"):
        if campo in body:
            setattr(mec, campo, body[campo])
    log_historial(db, "mecanismos", mec.id, "EditarMecanismo", antes=antes, despues=to_dict(mec))
    db.commit()
    return to_dict(mec)


def _periodo_actual():
    return date.today().strftime("%Y-%m")


@router.get("")
def listar(periodo: str = None, grupo: str = None, db: Session = Depends(get_db)):
    periodo = periodo or _periodo_actual()
    q = db.query(m.Mecanismo).filter(m.Mecanismo.vigente == 1)
    if grupo:
        q = q.filter(m.Mecanismo.grupo == grupo)
    mecs = q.order_by(m.Mecanismo.codigo).all()

    registros = {r.mecanismo_id: r for r in db.query(m.RegistroDeCumplimiento).filter(m.RegistroDeCumplimiento.periodo == periodo)}

    out = []
    for mec in mecs:
        puestos = db.query(m.MecanismoPuesto).filter(m.MecanismoPuesto.mecanismo_id == mec.id).all()
        reg = registros.get(mec.id)
        out.append({
            **to_dict(mec),
            "puestos": [{"puesto_codigo": p.puesto_codigo, "rol": p.rol} for p in puestos],
            "registro": {"estado": reg.estado, "causa": reg.causa, "accion_correctiva": reg.accion_correctiva,
                         "registrado_por": reg.registrado_por} if reg else None,
        })

    resumen = {"periodo": periodo, "total": len(out),
               "cumplido": sum(1 for x in out if x["registro"] and x["registro"]["estado"] == "cumplido"),
               "cumplido_parcial": sum(1 for x in out if x["registro"] and x["registro"]["estado"] == "cumplido_parcial"),
               "no_cumplido": sum(1 for x in out if x["registro"] and x["registro"]["estado"] == "no_cumplido"),
               "sin_registrar": sum(1 for x in out if not x["registro"])}
    por_grupo = {}
    for x in out:
        d = por_grupo.setdefault(x["grupo"], {"grupo": x["grupo"], "total": 0, "registrados": 0})
        d["total"] += 1
        if x["registro"]:
            d["registrados"] += 1

    return {"periodo": periodo, "resumen": resumen, "por_grupo": list(por_grupo.values()), "mecanismos": out}


@router.post("/{codigo}/cumplimiento")
def registrar_cumplimiento_de_mecanismo(codigo: str, body: dict, db: Session = Depends(get_db)):
    """Action Type: RegistrarCumplimientoDeMecanismo — crea un registro nuevo por
    período, nunca sobrescribe uno de un período distinto (Sección 13.2)."""
    if body.get("estado") not in ("cumplido", "cumplido_parcial", "no_cumplido"):
        raise HTTPException(400, "estado debe ser cumplido, cumplido_parcial o no_cumplido")
    mec = db.query(m.Mecanismo).filter(m.Mecanismo.codigo == codigo).first()
    if not mec:
        raise HTTPException(404, "Mecanismo no encontrado")
    periodo = body.get("periodo") or _periodo_actual()
    existente = db.query(m.RegistroDeCumplimiento).filter(
        m.RegistroDeCumplimiento.mecanismo_id == mec.id, m.RegistroDeCumplimiento.periodo == periodo).first()
    if existente:
        antes = to_dict(existente)
        existente.estado = body["estado"]
        existente.causa = body.get("causa")
        existente.accion_correctiva = body.get("accion_correctiva")
        existente.registrado_por = body.get("registrado_por")
        log_historial(db, "registro_cumplimiento", existente.id, "RegistrarCumplimientoDeMecanismo", antes=antes, despues=body)
    else:
        nuevo = m.RegistroDeCumplimiento(mecanismo_id=mec.id, periodo=periodo, estado=body["estado"],
                                          causa=body.get("causa"), accion_correctiva=body.get("accion_correctiva"),
                                          registrado_por=body.get("registrado_por"))
        db.add(nuevo)
        db.flush()
        log_historial(db, "registro_cumplimiento", nuevo.id, "RegistrarCumplimientoDeMecanismo", despues=body)
    db.commit()
    return {"message": "Cumplimiento registrado"}
