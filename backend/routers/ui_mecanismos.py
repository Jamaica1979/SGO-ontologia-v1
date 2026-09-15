from datetime import date
from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db, to_dict, log_historial
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/ui/mecanismos", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _periodo_actual():
    return date.today().strftime("%Y-%m")


def _ctx(db: Session, codigo: str, periodo: str):
    mec = db.query(m.Mecanismo).filter(m.Mecanismo.codigo == codigo).first()
    puestos_rol = db.query(m.MecanismoPuesto).filter(m.MecanismoPuesto.mecanismo_id == mec.id).all()
    puestos_por_rol = {}
    for pr in puestos_rol:
        puestos_por_rol.setdefault(pr.rol, []).append(pr.puesto_codigo)
    registro_actual = db.query(m.RegistroDeCumplimiento).filter(
        m.RegistroDeCumplimiento.mecanismo_id == mec.id, m.RegistroDeCumplimiento.periodo == periodo).first()
    historial = db.query(m.RegistroDeCumplimiento).filter(m.RegistroDeCumplimiento.mecanismo_id == mec.id,
                                                            m.RegistroDeCumplimiento.periodo != periodo).order_by(m.RegistroDeCumplimiento.periodo.desc()).all()
    return {"mecanismo": mec, "puestos_por_rol": puestos_por_rol, "periodo": periodo,
            "registro_actual": registro_actual, "historial": historial}


@router.get("/{codigo}", response_class=HTMLResponse)
def ver_ficha(codigo: str, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "ficha_mecanismo.html", _ctx(db, codigo, _periodo_actual()))


@router.post("/{codigo}/cumplimiento", response_class=HTMLResponse)
def registrar(codigo: str, request: Request, db: Session = Depends(get_db),
              estado: str = Form(...), causa: str = Form(None), accion_correctiva: str = Form(None),
              registrado_por: str = Form(None)):
    periodo = _periodo_actual()
    mec = db.query(m.Mecanismo).filter(m.Mecanismo.codigo == codigo).first()
    existente = db.query(m.RegistroDeCumplimiento).filter(m.RegistroDeCumplimiento.mecanismo_id == mec.id,
                                                            m.RegistroDeCumplimiento.periodo == periodo).first()
    body = {"estado": estado, "causa": causa, "accion_correctiva": accion_correctiva, "registrado_por": registrado_por}
    if existente:
        antes = to_dict(existente)
        existente.estado, existente.causa = estado, causa
        existente.accion_correctiva, existente.registrado_por = accion_correctiva, registrado_por
        log_historial(db, "registro_cumplimiento", existente.id, "RegistrarCumplimientoDeMecanismo", antes=antes, despues=body)
    else:
        nuevo = m.RegistroDeCumplimiento(mecanismo_id=mec.id, periodo=periodo, estado=estado, causa=causa,
                                          accion_correctiva=accion_correctiva, registrado_por=registrado_por)
        db.add(nuevo)
        db.flush()
        log_historial(db, "registro_cumplimiento", nuevo.id, "RegistrarCumplimientoDeMecanismo", despues=body)
    db.commit()
    ctx = _ctx(db, codigo, periodo)
    return templates.TemplateResponse(request, "_mecanismo_cumplimiento.html", ctx)
