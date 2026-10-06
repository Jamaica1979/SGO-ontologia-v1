"""Pantallas de reparto de actividades (Opción A):
  - /ui/reparto/{puesto}: una fila por actividad del puesto y quién la lleva; se cambia con un selector.
  - /ui/asignaciones/{id}/finalizar y /ui/personas/{id}/baja-impacto: antes de que alguien deje de llevar
    actividades, se ve cuáles quedan sin cubrir y se reasignan en el mismo paso."""
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db, log_historial, to_dict
from auth import verificar_acceso
from reparto import (cobertura_de_puesto, trasladar_actividades, devolver_a_titular, planta_por_defecto,
                     impacto_de_finalizar, finalizar_con_reasignacion, SIN_RESPONSABLE)
import models as m

router = APIRouter(prefix="/ui", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

ETAPAS = ("primaria", "secundaria")


def _norm(valor):
    return None if valor in (None, "", "None", "sin_etapa") else valor


def _ctx_reparto(db: Session, puesto_codigo: str, planta_id=None, etapa=None):
    puesto = db.query(m.Puesto).filter(m.Puesto.codigo == puesto_codigo).first()
    if not puesto:
        raise HTTPException(404, "Puesto no encontrado")
    por_planta = puesto.cardinalidad_esperada == "una_por_planta_activa"
    plantas = db.query(m.Planta).order_by(m.Planta.id).all()
    if por_planta and not planta_id:
        a = db.query(m.Asignacion).filter(m.Asignacion.puesto_codigo == puesto_codigo,
                                           m.Asignacion.estado.in_(["activa", "transicion"])).order_by(m.Asignacion.id).first()
        planta_id = a.planta_id if a else (plantas[0].id if plantas else None)
    if not por_planta:
        planta_id = None
    etapa = _norm(etapa)
    cob = cobertura_de_puesto(db, puesto_codigo, planta_id, etapa)
    return {
        "puesto": puesto, "por_planta": por_planta, "plantas": plantas, "planta_id": planta_id,
        "requiere_etapa": puesto_codigo in ("PRD-04", "PRD-05"), "etapa": etapa,
        "cob": cob, "etapas": ETAPAS,
        "personas": db.query(m.Persona).filter(m.Persona.activo == 1).order_by(m.Persona.apellido, m.Persona.nombre).all(),
    }


@router.get("/reparto/{puesto_codigo}", response_class=HTMLResponse)
def ver_reparto(puesto_codigo: str, request: Request, planta_id: int = None, etapa: str = None, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "reparto.html", _ctx_reparto(db, puesto_codigo, planta_id, etapa))


@router.post("/reparto/{puesto_codigo}/mover", response_class=HTMLResponse)
def mover_actividad(puesto_codigo: str, request: Request, db: Session = Depends(get_db),
                    actividad_id: int = Form(...), persona_id: str = Form(""),
                    planta_id: str = Form(None), etapa: str = Form(None)):
    planta = int(planta_id) if planta_id else None
    etapa = _norm(etapa)
    if persona_id:
        persona = db.query(m.Persona).get(int(persona_id))
        if not persona or not persona.activo:
            raise HTTPException(404, "Persona no encontrada o dada de baja")
        trasladar_actividades(db, {actividad_id}, persona.id, planta or planta_por_defecto(db, persona.id), etapa)
    else:
        devolver_a_titular(db, {actividad_id}, planta, etapa)
    db.commit()
    return templates.TemplateResponse(request, "_reparto_tabla.html", _ctx_reparto(db, puesto_codigo, planta, etapa))


@router.post("/reparto/{puesto_codigo}/asignar-resto", response_class=HTMLResponse)
def asignar_resto(puesto_codigo: str, request: Request, db: Session = Depends(get_db),
                  persona_id: int = Form(...), planta_id: str = Form(None), etapa: str = Form(None)):
    """Todas las actividades del puesto que hoy no lleva nadie pasan a una persona."""
    planta = int(planta_id) if planta_id else None
    etapa = _norm(etapa)
    persona = db.query(m.Persona).get(persona_id)
    if not persona or not persona.activo:
        raise HTTPException(404, "Persona no encontrada o dada de baja")
    cob = cobertura_de_puesto(db, puesto_codigo, planta, etapa)
    ids = {f["actividad"]["id"] for f in cob["filas"] if f["estado"] == SIN_RESPONSABLE}
    if ids:
        trasladar_actividades(db, ids, persona.id, planta or planta_por_defecto(db, persona.id), etapa)
        db.commit()
    return templates.TemplateResponse(request, "_reparto_tabla.html", _ctx_reparto(db, puesto_codigo, planta, etapa))


# ───────────────────────── impacto de una salida ─────────────────────────

def _pagina_impacto(request, db, asignaciones, persona_que_sale, titulo, intro, accion_url, texto_boton, volver_url):
    filas = impacto_de_finalizar(db, asignaciones)
    return templates.TemplateResponse(request, "impacto_salida.html", {
        "titulo": titulo, "intro": intro, "asignaciones": asignaciones, "filas": filas,
        "accion_url": accion_url, "texto_boton": texto_boton, "volver_url": volver_url,
        "personas": db.query(m.Persona).filter(m.Persona.activo == 1, m.Persona.id != persona_que_sale.id)
                       .order_by(m.Persona.apellido, m.Persona.nombre).all(),
    })


async def _destinos(request: Request):
    form = await request.form()
    return {int(k[5:]): v for k, v in form.items() if k.startswith("dest_")}


@router.get("/asignaciones/{asignacion_id}/finalizar", response_class=HTMLResponse)
def finalizar_form(asignacion_id: int, request: Request, db: Session = Depends(get_db)):
    a = db.query(m.Asignacion).get(asignacion_id)
    if not a:
        raise HTTPException(404, "Asignación no encontrada")
    if a.estado == "finalizada":
        return RedirectResponse(f"/ui/personas/{a.persona_id}", status_code=303)
    nombre = a.puesto.nombre if a.puesto else (a.perfil.nombre if a.perfil else "")
    return _pagina_impacto(
        request, db, [a], a.persona, f"Finalizar cobertura — {a.puesto_codigo or 'perfil individual'} {nombre}",
        f"{a.persona.nombre} {a.persona.apellido} deja de cubrir esto en {a.planta.nombre}. La asignación queda en el historial, no se borra.",
        f"/ui/asignaciones/{asignacion_id}/finalizar", "Finalizar cobertura", f"/ui/personas/{a.persona_id}")


@router.post("/asignaciones/{asignacion_id}/finalizar")
async def finalizar_confirmar(asignacion_id: int, request: Request, db: Session = Depends(get_db)):
    a = db.query(m.Asignacion).get(asignacion_id)
    if not a:
        raise HTTPException(404, "Asignación no encontrada")
    if a.estado != "finalizada":
        finalizar_con_reasignacion(db, [a], await _destinos(request))
        db.commit()
    return RedirectResponse(f"/ui/personas/{a.persona_id}", status_code=303)


@router.get("/personas/{persona_id}/baja-impacto", response_class=HTMLResponse)
def baja_impacto_form(persona_id: int, request: Request, db: Session = Depends(get_db)):
    p = db.query(m.Persona).get(persona_id)
    if not p:
        raise HTTPException(404, "Persona no encontrada")
    asigs = db.query(m.Asignacion).filter(m.Asignacion.persona_id == persona_id,
                                           m.Asignacion.estado.in_(["activa", "transicion"])).all()
    return _pagina_impacto(
        request, db, asigs, p, f"Dar de baja a {p.nombre} {p.apellido}",
        f"Se finalizan sus {len(asigs)} cobertura{'s' if len(asigs) != 1 else ''} y la persona queda dada de baja (se puede reactivar). "
        "Nada se borra: todo queda en el historial.",
        f"/ui/personas/{persona_id}/baja-impacto", "Confirmar la baja", f"/ui/personas/{persona_id}")


@router.post("/personas/{persona_id}/baja-impacto")
async def baja_impacto_confirmar(persona_id: int, request: Request, db: Session = Depends(get_db)):
    p = db.query(m.Persona).get(persona_id)
    if not p:
        raise HTTPException(404, "Persona no encontrada")
    asigs = db.query(m.Asignacion).filter(m.Asignacion.persona_id == persona_id,
                                           m.Asignacion.estado.in_(["activa", "transicion"])).all()
    if asigs:
        finalizar_con_reasignacion(db, asigs, await _destinos(request))
    antes = to_dict(p)
    p.activo = 0
    log_historial(db, "personas", p.id, "DarDeBajaPersona", antes=antes, despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/personas/{persona_id}", status_code=303)
