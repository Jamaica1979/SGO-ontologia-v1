from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db, log_historial
from auth import verificar_acceso
from functions import calcular_cobertura
from routers.asignaciones import actividades_de_asignacion, es_sede_unica, conflictos_exclusividad
import models as m

router = APIRouter(prefix="/ui", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _ficha_persona_ctx(db: Session, persona_id: int):
    p = db.query(m.Persona).get(persona_id)
    asigs = db.query(m.Asignacion).filter(m.Asignacion.persona_id == persona_id,
                                           m.Asignacion.estado.in_(["activa", "transicion"])).all()
    coberturas = [{
        "asignacion_id": a.id, "puesto_codigo": a.puesto_codigo,
        "puesto_nombre": a.puesto.nombre if a.puesto else None,
        "perfil_nombre": a.perfil.nombre if a.perfil else None,
        "planta": a.planta.nombre, "etapa": a.etapa, "estado": a.estado,
    } for a in asigs]

    tipos_que_tiene = set(h.tipo_capacitacion_id for h in db.query(m.HabilitacionDePersona).filter(m.HabilitacionDePersona.persona_id == persona_id))
    actividad_ids = set()
    for a in asigs:
        actividad_ids |= actividades_de_asignacion(db, a.puesto_codigo, a.perfil_id)
    pendientes = []
    if actividad_ids:
        vistos = set()
        for r in db.query(m.ActividadCapacitacion).filter(m.ActividadCapacitacion.actividad_id.in_(actividad_ids), m.ActividadCapacitacion.obligatoria == 1):
            if r.tipo_capacitacion_id not in tipos_que_tiene and r.tipo_capacitacion_id not in vistos:
                vistos.add(r.tipo_capacitacion_id)
                pendientes.append({"nombre": db.query(m.TipoDeCapacitacion).get(r.tipo_capacitacion_id).nombre})

    alertas = []
    if p.estado_legajo != "completo":
        alertas.append({"mensaje": f"Legajo {p.estado_legajo}"})

    return {
        "persona": p, "iniciales": (p.nombre[:1] + p.apellido[:1]).upper(),
        "convenio_nombre": p.convenio.nombre if p.convenio else None,
        "coberturas": coberturas, "capacitaciones_pendientes": pendientes, "alertas": alertas,
        "puestos": db.query(m.Puesto).filter(m.Puesto.vigente == 1).order_by(m.Puesto.codigo).all(),
        "plantas": db.query(m.Planta).all(),
    }


@router.get("/personas/{persona_id}", response_class=HTMLResponse)
def ver_ficha(persona_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = _ficha_persona_ctx(db, persona_id)
    return templates.TemplateResponse(request, "ficha_persona.html", ctx)


@router.get("/buscar", response_class=HTMLResponse)
def buscar(q: str, request: Request, db: Session = Depends(get_db)):
    resultados = db.query(m.Persona).filter(
        (m.Persona.nombre.ilike(f"%{q}%")) | (m.Persona.apellido.ilike(f"%{q}%"))
    ).filter(m.Persona.activo == 1).all()
    return templates.TemplateResponse(request, "buscar.html", {"q": q, "resultados": resultados})


@router.post("/personas/{persona_id}/asignaciones/nueva", response_class=HTMLResponse)
def nueva_asignacion(persona_id: int, request: Request, db: Session = Depends(get_db),
                      puesto_codigo: str = Form(...), planta_id: int = Form(...),
                      etapa: str = Form(None), permitir_conflicto: bool = Form(False)):
    etapa = etapa or None
    if puesto_codigo in ("PRD-04", "PRD-05") and not etapa:
        return templates.TemplateResponse(request, "_conflicto.html", {
            "persona_id": persona_id, "puesto_codigo": puesto_codigo, "planta_id": planta_id, "etapa": etapa,
            "conflictos": [{"persona": "—", "puesto_codigo": puesto_codigo, "etapa": None,
                             "actividades_en_conflicto": ["Falta indicar la etapa: primaria o secundaria"]}],
        })

    cubiertas = actividades_de_asignacion(db, puesto_codigo, None)
    scope_planta = None if es_sede_unica(db, puesto_codigo=puesto_codigo) else planta_id
    conflictos = conflictos_exclusividad(db, scope_planta, cubiertas, etapa=etapa, excluir_persona_id=persona_id)

    if conflictos and not permitir_conflicto:
        return templates.TemplateResponse(request, "_conflicto.html", {
            "persona_id": persona_id, "puesto_codigo": puesto_codigo, "planta_id": planta_id, "etapa": etapa,
            "conflictos": conflictos,
        })

    nueva = m.Asignacion(persona_id=persona_id, puesto_codigo=puesto_codigo, planta_id=planta_id,
                         etapa=etapa, estado="activa")
    db.add(nueva)
    db.flush()
    log_historial(db, "asignaciones", nueva.id, "AsignarPersonaAPuesto",
                  despues={"puesto_codigo": puesto_codigo, "planta_id": planta_id, "etapa": etapa, "persona_id": persona_id})
    db.commit()
    ctx = _ficha_persona_ctx(db, persona_id)
    return templates.TemplateResponse(request, "_asignacion_creada.html", ctx)


@router.delete("/asignaciones/{asignacion_id}", response_class=HTMLResponse)
def finalizar(asignacion_id: int, request: Request, db: Session = Depends(get_db)):
    a = db.query(m.Asignacion).get(asignacion_id)
    persona_id = a.persona_id
    a.estado = "finalizada"
    log_historial(db, "asignaciones", a.id, "FinalizarAsignacion")
    db.commit()
    ctx = _ficha_persona_ctx(db, persona_id)
    return templates.TemplateResponse(request, "_coberturas.html", ctx)
