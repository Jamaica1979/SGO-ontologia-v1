from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db, log_historial
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/ui/formularios", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


# el orden importa: '/nuevo' tiene que registrarse antes que '/{codigo}'
@router.get("/nuevo", response_class=HTMLResponse)
def nuevo_formulario_form(request: Request):
    return templates.TemplateResponse(request, "form_formulario.html", {"formulario": None})


@router.post("", response_class=HTMLResponse)
def crear_formulario(request: Request, db: Session = Depends(get_db),
                      codigo: str = Form(...), nombre: str = Form(...), origen: str = Form(None),
                      emisor: str = Form(None), receptor: str = Form(None), frecuencia: str = Form(None)):
    if db.query(m.Formulario).filter(m.Formulario.codigo == codigo).first():
        return templates.TemplateResponse(request, "form_formulario.html", {
            "formulario": None, "error": f"Ya existe un formulario con el código {codigo}.",
            "valores": {"codigo": codigo, "nombre": nombre, "origen": origen, "emisor": emisor,
                        "receptor": receptor, "frecuencia": frecuencia}})
    f = m.Formulario(codigo=codigo, nombre=nombre, origen=origen, emisor=emisor, receptor=receptor, frecuencia=frecuencia)
    db.add(f)
    db.flush()
    log_historial(db, "formularios", f.id, "CrearFormulario", despues={"codigo": codigo, "nombre": nombre})
    db.commit()
    return RedirectResponse(f"/ui/formularios/{codigo}", status_code=303)


@router.get("/{codigo}", response_class=HTMLResponse)
def ver_ficha(codigo: str, request: Request, db: Session = Depends(get_db)):
    f = db.query(m.Formulario).filter(m.Formulario.codigo == codigo).first()
    procedimientos = (db.query(m.Procedimiento)
                      .join(m.ProcedimientoFormulario, m.ProcedimientoFormulario.procedimiento_id == m.Procedimiento.id)
                      .filter(m.ProcedimientoFormulario.formulario_id == f.id).order_by(m.Procedimiento.codigo).all())
    mecanismos = (db.query(m.Mecanismo)
                  .join(m.MecanismoFormulario, m.MecanismoFormulario.mecanismo_id == m.Mecanismo.id)
                  .filter(m.MecanismoFormulario.formulario_id == f.id).order_by(m.Mecanismo.codigo).all())
    return templates.TemplateResponse(request, "ficha_formulario.html", {
        "formulario": f, "procedimientos": procedimientos, "mecanismos": mecanismos})


@router.get("/{codigo}/editar", response_class=HTMLResponse)
def editar_formulario_form(codigo: str, request: Request, db: Session = Depends(get_db)):
    f = db.query(m.Formulario).filter(m.Formulario.codigo == codigo).first()
    return templates.TemplateResponse(request, "form_formulario.html", {"formulario": f})


@router.post("/{codigo}/editar", response_class=HTMLResponse)
def editar_formulario(codigo: str, request: Request, db: Session = Depends(get_db),
                       nombre: str = Form(...), origen: str = Form(None),
                       emisor: str = Form(None), receptor: str = Form(None), frecuencia: str = Form(None)):
    f = db.query(m.Formulario).filter(m.Formulario.codigo == codigo).first()
    antes = {"nombre": f.nombre, "origen": f.origen, "emisor": f.emisor, "receptor": f.receptor, "frecuencia": f.frecuencia}
    f.nombre, f.origen, f.emisor, f.receptor, f.frecuencia = nombre, origen, emisor, receptor, frecuencia
    log_historial(db, "formularios", f.id, "EditarFormulario", antes=antes,
                  despues={"nombre": nombre, "origen": origen, "emisor": emisor, "receptor": receptor, "frecuencia": frecuencia})
    db.commit()
    return RedirectResponse(f"/ui/formularios/{codigo}", status_code=303)


@router.post("/{codigo}/eliminar")
def eliminar_formulario(codigo: str, db: Session = Depends(get_db)):
    f = db.query(m.Formulario).filter(m.Formulario.codigo == codigo).first()
    log_historial(db, "formularios", f.id, "EliminarFormulario",
                  antes={"codigo": f.codigo, "nombre": f.nombre, "origen": f.origen,
                         "emisor": f.emisor, "receptor": f.receptor, "frecuencia": f.frecuencia})
    db.query(m.ProcedimientoFormulario).filter(m.ProcedimientoFormulario.formulario_id == f.id).delete()
    db.query(m.MecanismoFormulario).filter(m.MecanismoFormulario.formulario_id == f.id).delete()
    db.delete(f)
    db.commit()
    return RedirectResponse("/ui/listado/formularios", status_code=303)
