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
def nuevo_formulario_form(request: Request, db: Session = Depends(get_db), padre: str = None):
    return templates.TemplateResponse(request, "form_formulario.html", _ctx_form(db, valores={"padre_codigo": padre} if padre else None))


def _ctx_form(db, formulario=None, error=None, valores=None):
    """Los formularios que pueden ser 'padre': los que no son parte de otro (un solo nivel de anidado)."""
    q = db.query(m.Formulario).filter(m.Formulario.formulario_padre_id.is_(None))
    if formulario:
        q = q.filter(m.Formulario.id != formulario.id)
    padre_actual = None
    if formulario and formulario.formulario_padre_id:
        pf = db.query(m.Formulario).get(formulario.formulario_padre_id)
        padre_actual = pf.codigo if pf else None
    return {"formulario": formulario, "error": error, "valores": valores,
            "posibles_padres": q.order_by(m.Formulario.codigo).all(), "padre_actual": padre_actual}


def _padre_id(db, padre_codigo):
    if not padre_codigo:
        return None
    pf = db.query(m.Formulario).filter(m.Formulario.codigo == padre_codigo).first()
    return pf.id if pf else None


@router.post("", response_class=HTMLResponse)
def crear_formulario(request: Request, db: Session = Depends(get_db),
                      codigo: str = Form(...), nombre: str = Form(...), origen: str = Form(None),
                      emisor: str = Form(None), receptor: str = Form(None), frecuencia: str = Form(None),
                      padre_codigo: str = Form(""), estructura: str = Form("")):
    if db.query(m.Formulario).filter(m.Formulario.codigo == codigo).first():
        return templates.TemplateResponse(request, "form_formulario.html", _ctx_form(
            db, error=f"Ya existe un formulario con el código {codigo}.",
            valores={"codigo": codigo, "nombre": nombre, "origen": origen, "emisor": emisor,
                     "receptor": receptor, "frecuencia": frecuencia, "padre_codigo": padre_codigo, "estructura": estructura}))
    f = m.Formulario(codigo=codigo, nombre=nombre, origen=origen, emisor=emisor, receptor=receptor, frecuencia=frecuencia,
                     formulario_padre_id=_padre_id(db, padre_codigo), estructura=estructura.strip() or None)
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
    padre = db.query(m.Formulario).get(f.formulario_padre_id) if f.formulario_padre_id else None
    partes = db.query(m.Formulario).filter(m.Formulario.formulario_padre_id == f.id).order_by(m.Formulario.codigo).all()
    campos, nota_modelo = [], None
    for linea in (f.estructura or "").splitlines():
        if linea.strip().upper().startswith("NOTA:"):
            nota_modelo = linea.strip()
        elif linea.strip():
            c = [x.strip() for x in linea.split("|")]
            campos.append({"campo": c[0], "tipo": c[1] if len(c) > 1 else "", "obligatorio": c[2] if len(c) > 2 else "", "nota": c[3] if len(c) > 3 else ""})
    return templates.TemplateResponse(request, "ficha_formulario.html", {
        "formulario": f, "procedimientos": procedimientos, "mecanismos": mecanismos,
        "padre": padre, "partes": partes, "campos": campos, "nota_modelo": nota_modelo})


@router.get("/{codigo}/editar", response_class=HTMLResponse)
def editar_formulario_form(codigo: str, request: Request, db: Session = Depends(get_db)):
    f = db.query(m.Formulario).filter(m.Formulario.codigo == codigo).first()
    return templates.TemplateResponse(request, "form_formulario.html", _ctx_form(db, formulario=f))


@router.post("/{codigo}/editar", response_class=HTMLResponse)
def editar_formulario(codigo: str, request: Request, db: Session = Depends(get_db),
                       nombre: str = Form(...), origen: str = Form(None),
                       emisor: str = Form(None), receptor: str = Form(None), frecuencia: str = Form(None),
                       padre_codigo: str = Form(""), estructura: str = Form("")):
    f = db.query(m.Formulario).filter(m.Formulario.codigo == codigo).first()
    padre_id = _padre_id(db, padre_codigo)
    if padre_id == f.id or (padre_id and db.query(m.Formulario).filter(m.Formulario.formulario_padre_id == f.id).first()):
        return templates.TemplateResponse(request, "form_formulario.html", _ctx_form(
            db, formulario=f, error="Un formulario que ya tiene partes no puede ser parte de otro (se admite un solo nivel).",
            valores={"nombre": nombre, "origen": origen, "emisor": emisor, "receptor": receptor, "frecuencia": frecuencia,
                     "padre_codigo": padre_codigo, "estructura": estructura}))
    antes = {"nombre": f.nombre, "origen": f.origen, "emisor": f.emisor, "receptor": f.receptor, "frecuencia": f.frecuencia,
             "formulario_padre_id": f.formulario_padre_id, "estructura": f.estructura}
    f.nombre, f.origen, f.emisor, f.receptor, f.frecuencia = nombre, origen, emisor, receptor, frecuencia
    f.formulario_padre_id, f.estructura = padre_id, estructura.strip() or None
    log_historial(db, "formularios", f.id, "EditarFormulario", antes=antes,
                  despues={"nombre": nombre, "origen": origen, "emisor": emisor, "receptor": receptor, "frecuencia": frecuencia,
                           "formulario_padre_id": padre_id, "estructura": f.estructura})
    db.commit()
    return RedirectResponse(f"/ui/formularios/{codigo}", status_code=303)


@router.post("/{codigo}/eliminar")
def eliminar_formulario(codigo: str, db: Session = Depends(get_db)):
    f = db.query(m.Formulario).filter(m.Formulario.codigo == codigo).first()
    # sus partes no se pierden: pasan a ser formularios independientes
    db.query(m.Formulario).filter(m.Formulario.formulario_padre_id == f.id).update({"formulario_padre_id": None})
    log_historial(db, "formularios", f.id, "EliminarFormulario",
                  antes={"codigo": f.codigo, "nombre": f.nombre, "origen": f.origen,
                         "emisor": f.emisor, "receptor": f.receptor, "frecuencia": f.frecuencia})
    db.query(m.ProcedimientoFormulario).filter(m.ProcedimientoFormulario.formulario_id == f.id).delete()
    db.query(m.MecanismoFormulario).filter(m.MecanismoFormulario.formulario_id == f.id).delete()
    db.delete(f)
    db.commit()
    return RedirectResponse("/ui/listado/formularios", status_code=303)
