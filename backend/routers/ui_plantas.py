from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db, log_historial, to_dict
from auth import verificar_acceso
from functions import calcular_cobertura
from routers.ui_shared import asignar_o_reasignar
import models as m

router = APIRouter(prefix="/ui/plantas", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


# el orden importa: '/nuevo' tiene que registrarse antes que '/{planta_id}'
@router.get("/nuevo", response_class=HTMLResponse)
def nueva_planta_form(request: Request):
    return templates.TemplateResponse(request, "form_planta.html", {"planta": None})


@router.post("", response_class=HTMLResponse)
def crear_planta(request: Request, db: Session = Depends(get_db),
                  codigo: str = Form(...), nombre: str = Form(...), estado: str = Form("pendiente"),
                  notas: str = Form(None)):
    if db.query(m.Planta).filter(m.Planta.codigo == codigo).first():
        return templates.TemplateResponse(request, "form_planta.html", {
            "planta": None, "error": f"Ya existe una planta con el código {codigo}.",
            "valores": {"codigo": codigo, "nombre": nombre, "estado": estado, "notas": notas}})
    p = m.Planta(codigo=codigo, nombre=nombre, estado=estado, notas=notas)
    db.add(p)
    db.flush()
    log_historial(db, "plantas", p.id, "CrearPlanta", despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/plantas/{p.id}", status_code=303)


def _ctx(db: Session, planta_id: int):
    pl = db.query(m.Planta).get(planta_id)
    cobertura = [f for f in calcular_cobertura(db, planta_id=planta_id) if f["planta_id"] == planta_id]
    total = len(cobertura)
    cubiertas = len([f for f in cobertura if f["estado"] in ("cubierta", "cubierta_sin_etapa")])
    return {
        "planta": pl, "cobertura": cobertura,
        "resumen": {"total": total, "cubiertas": cubiertas, "pct_cobertura": round(100 * cubiertas / total, 1) if total else 0},
        "personas": db.query(m.Persona).filter(m.Persona.activo == 1).order_by(m.Persona.apellido).all(),
        "plantas": db.query(m.Planta).all(),
    }


@router.get("/{planta_id}", response_class=HTMLResponse)
def ver_ficha(planta_id: int, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "ficha_planta.html", _ctx(db, planta_id))


@router.get("/{planta_id}/editar", response_class=HTMLResponse)
def editar_planta_form(planta_id: int, request: Request, db: Session = Depends(get_db)):
    p = db.query(m.Planta).get(planta_id)
    return templates.TemplateResponse(request, "form_planta.html", {"planta": p})


@router.post("/{planta_id}/editar", response_class=HTMLResponse)
def editar_planta(planta_id: int, request: Request, db: Session = Depends(get_db),
                   codigo: str = Form(...), nombre: str = Form(...), estado: str = Form(...), notas: str = Form(None)):
    p = db.query(m.Planta).get(planta_id)
    antes = to_dict(p)
    p.codigo, p.nombre, p.estado, p.notas = codigo, nombre, estado, notas
    log_historial(db, "plantas", p.id, "EditarPlanta", antes=antes, despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/plantas/{planta_id}", status_code=303)


@router.post("/{planta_id}/baja")
def dar_de_baja(planta_id: int, db: Session = Depends(get_db)):
    p = db.query(m.Planta).get(planta_id)
    antes = to_dict(p)
    p.estado = "inactiva"
    log_historial(db, "plantas", p.id, "DarDeBajaPlanta", antes=antes, despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/plantas/{planta_id}", status_code=303)


@router.post("/{planta_id}/alta")
def dar_de_alta(planta_id: int, db: Session = Depends(get_db)):
    p = db.query(m.Planta).get(planta_id)
    antes = to_dict(p)
    p.estado = "pendiente"
    log_historial(db, "plantas", p.id, "DarDeAltaPlanta", antes=antes, despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/plantas/{planta_id}", status_code=303)


@router.post("/{planta_id}/asignar", response_class=HTMLResponse)
def asignar(planta_id: int, request: Request, db: Session = Depends(get_db),
            puesto_codigo: str = Form(...), etapa: str = Form(None), persona_id: int = Form(...),
            permitir_conflicto: bool = Form(False)):
    etapa = etapa if etapa and etapa != "None" else None
    ok, conflictos = asignar_o_reasignar(db, puesto_codigo, planta_id, etapa, persona_id, permitir_conflicto)
    if not ok:
        return templates.TemplateResponse(request, "_cobertura_conflicto.html", {
            "puesto_codigo": puesto_codigo, "planta_id": planta_id, "etapa": etapa, "persona_id": persona_id,
            "conflictos": conflictos, "accion_url": f"/ui/plantas/{planta_id}/asignar"})
    fila = next((f for f in calcular_cobertura(db, puesto_codigo=puesto_codigo) if f["planta_id"] == planta_id and f["etapa"] == etapa), None)
    return templates.TemplateResponse(request, "_cobertura_fila.html", {
        "f": fila, "mostrar_puesto": True, "mostrar_planta": False, "accion_url": f"/ui/plantas/{planta_id}/asignar",
        "personas": db.query(m.Persona).filter(m.Persona.activo == 1).order_by(m.Persona.apellido).all(),
        "plantas": db.query(m.Planta).all()})
