from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db, log_historial, to_dict
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/ui/procedimientos", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


# el orden importa: '/nuevo' tiene que registrarse antes que '/{codigo}'
@router.get("/nuevo", response_class=HTMLResponse)
def nuevo_procedimiento_form(request: Request):
    return templates.TemplateResponse(request, "form_procedimiento.html", {"procedimiento": None})


@router.post("", response_class=HTMLResponse)
def crear_procedimiento(request: Request, db: Session = Depends(get_db),
                         codigo: str = Form(...), nombre: str = Form(...), area: str = Form(...),
                         nivel_riesgo: str = Form("medio"), descripcion: str = Form(None),
                         tiene_nivel_urgente: bool = Form(False), tiene_nivel_emergencia: bool = Form(False)):
    if db.query(m.Procedimiento).filter(m.Procedimiento.codigo == codigo).first():
        return templates.TemplateResponse(request, "form_procedimiento.html", {
            "procedimiento": None, "error": f"Ya existe un procedimiento con el código {codigo}.",
            "valores": {"codigo": codigo, "nombre": nombre, "area": area, "nivel_riesgo": nivel_riesgo,
                        "descripcion": descripcion, "tiene_nivel_urgente": tiene_nivel_urgente,
                        "tiene_nivel_emergencia": tiene_nivel_emergencia}})
    p = m.Procedimiento(codigo=codigo, nombre=nombre, area=area, nivel_riesgo=nivel_riesgo, descripcion=descripcion,
                         tiene_nivel_urgente=1 if tiene_nivel_urgente else 0,
                         tiene_nivel_emergencia=1 if tiene_nivel_emergencia else 0)
    db.add(p)
    db.flush()
    log_historial(db, "procedimientos", p.id, "CrearProcedimiento", despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/procedimientos/{codigo}", status_code=303)


@router.get("/{codigo}", response_class=HTMLResponse)
def ver_ficha(codigo: str, request: Request, db: Session = Depends(get_db)):
    proc = db.query(m.Procedimiento).filter(m.Procedimiento.codigo == codigo).first()
    pasos = db.query(m.PasoDeProcedimiento).filter(m.PasoDeProcedimiento.procedimiento_id == proc.id).order_by(m.PasoDeProcedimiento.numero).all()
    puestos = [r[0] for r in db.query(m.ProcedimientoPuesto.puesto_codigo).filter(m.ProcedimientoPuesto.procedimiento_id == proc.id)]
    formularios = (db.query(m.Formulario)
                   .join(m.ProcedimientoFormulario, m.ProcedimientoFormulario.formulario_id == m.Formulario.id)
                   .filter(m.ProcedimientoFormulario.procedimiento_id == proc.id).order_by(m.Formulario.codigo).all())
    return templates.TemplateResponse(request, "ficha_procedimiento.html", {
        "procedimiento": proc, "pasos": pasos, "puestos": puestos, "formularios": formularios})


@router.get("/{codigo}/editar", response_class=HTMLResponse)
def editar_procedimiento_form(codigo: str, request: Request, db: Session = Depends(get_db)):
    proc = db.query(m.Procedimiento).filter(m.Procedimiento.codigo == codigo).first()
    return templates.TemplateResponse(request, "form_procedimiento.html", {"procedimiento": proc})


@router.post("/{codigo}/editar", response_class=HTMLResponse)
def editar_procedimiento(codigo: str, request: Request, db: Session = Depends(get_db),
                          nombre: str = Form(...), area: str = Form(...), nivel_riesgo: str = Form("medio"),
                          descripcion: str = Form(None), tiene_nivel_urgente: bool = Form(False),
                          tiene_nivel_emergencia: bool = Form(False)):
    proc = db.query(m.Procedimiento).filter(m.Procedimiento.codigo == codigo).first()
    antes = to_dict(proc)
    proc.nombre, proc.area, proc.nivel_riesgo = nombre, area, nivel_riesgo
    proc.descripcion = descripcion
    proc.tiene_nivel_urgente = 1 if tiene_nivel_urgente else 0
    proc.tiene_nivel_emergencia = 1 if tiene_nivel_emergencia else 0
    log_historial(db, "procedimientos", proc.id, "EditarProcedimiento", antes=antes, despues=to_dict(proc))
    db.commit()
    return RedirectResponse(f"/ui/procedimientos/{codigo}", status_code=303)


@router.post("/{codigo}/baja")
def dar_de_baja(codigo: str, db: Session = Depends(get_db)):
    proc = db.query(m.Procedimiento).filter(m.Procedimiento.codigo == codigo).first()
    antes = to_dict(proc)
    proc.vigente = 0
    log_historial(db, "procedimientos", proc.id, "DarDeBajaProcedimiento", antes=antes, despues=to_dict(proc))
    db.commit()
    return RedirectResponse(f"/ui/procedimientos/{codigo}", status_code=303)


@router.post("/{codigo}/alta")
def dar_de_alta(codigo: str, db: Session = Depends(get_db)):
    proc = db.query(m.Procedimiento).filter(m.Procedimiento.codigo == codigo).first()
    antes = to_dict(proc)
    proc.vigente = 1
    log_historial(db, "procedimientos", proc.id, "DarDeAltaProcedimiento", antes=antes, despues=to_dict(proc))
    db.commit()
    return RedirectResponse(f"/ui/procedimientos/{codigo}", status_code=303)
