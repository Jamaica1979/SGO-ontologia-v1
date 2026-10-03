from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db, log_historial, to_dict
from auth import verificar_acceso
from functions import calcular_cobertura
from routers.asignaciones import actividades_de_asignacion, es_sede_unica, conflictos_exclusividad, get_or_create_perfil_personal
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

    habilitaciones = [{"id": h.id, "tipo": db.query(m.TipoDeCapacitacion).get(h.tipo_capacitacion_id).nombre,
                       "fecha_vencimiento": h.fecha_vencimiento, "estado": h.estado}
                      for h in db.query(m.HabilitacionDePersona).filter(m.HabilitacionDePersona.persona_id == persona_id)]

    return {
        "persona": p, "iniciales": (p.nombre[:1] + p.apellido[:1]).upper(),
        "convenio_nombre": p.convenio.nombre if p.convenio else None,
        "coberturas": coberturas, "capacitaciones_pendientes": pendientes, "alertas": alertas,
        "habilitaciones": habilitaciones,
        "puestos": db.query(m.Puesto).filter(m.Puesto.vigente == 1).order_by(m.Puesto.codigo).all(),
        "plantas": db.query(m.Planta).all(),
    }


def _form_persona_ctx(db, persona=None, error=None, valores=None):
    return {"persona": persona, "error": error, "valores": valores,
            "convenios": db.query(m.ConvenioColectivo).order_by(m.ConvenioColectivo.codigo).all()}


# el orden importa: '/personas/nuevo' tiene que registrarse antes que '/personas/{persona_id}'
@router.get("/personas/nuevo", response_class=HTMLResponse)
def nueva_persona_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "form_persona.html", _form_persona_ctx(db))


@router.post("/personas", response_class=HTMLResponse)
def crear_persona(request: Request, db: Session = Depends(get_db),
                   nombre: str = Form(...), apellido: str = Form(...), legajo: str = Form(None),
                   cuit: str = Form(None), convenio_id: str = Form(None), antiguedad_anos: str = Form(None),
                   estado_legajo: str = Form("completo"), notas: str = Form(None)):
    p = m.Persona(nombre=nombre, apellido=apellido, legajo=legajo or None, cuit=cuit or None,
                  convenio_id=convenio_id or None, antiguedad_anos=float(antiguedad_anos) if antiguedad_anos else None,
                  estado_legajo=estado_legajo, notas=notas)
    db.add(p)
    db.flush()
    log_historial(db, "personas", p.id, "CrearPersona", despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/personas/{p.id}", status_code=303)


@router.get("/personas/{persona_id}", response_class=HTMLResponse)
def ver_ficha(persona_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = _ficha_persona_ctx(db, persona_id)
    return templates.TemplateResponse(request, "ficha_persona.html", ctx)


@router.get("/personas/{persona_id}/editar", response_class=HTMLResponse)
def editar_persona_form(persona_id: int, request: Request, db: Session = Depends(get_db)):
    p = db.query(m.Persona).get(persona_id)
    return templates.TemplateResponse(request, "form_persona.html", _form_persona_ctx(db, persona=p))


@router.post("/personas/{persona_id}/editar", response_class=HTMLResponse)
def editar_persona(persona_id: int, request: Request, db: Session = Depends(get_db),
                    nombre: str = Form(...), apellido: str = Form(...), legajo: str = Form(None),
                    cuit: str = Form(None), convenio_id: str = Form(None), antiguedad_anos: str = Form(None),
                    estado_legajo: str = Form("completo"), notas: str = Form(None)):
    p = db.query(m.Persona).get(persona_id)
    antes = to_dict(p)
    p.nombre, p.apellido, p.legajo, p.cuit = nombre, apellido, legajo or None, cuit or None
    p.convenio_id = convenio_id or None
    p.antiguedad_anos = float(antiguedad_anos) if antiguedad_anos else None
    p.estado_legajo, p.notas = estado_legajo, notas
    log_historial(db, "personas", p.id, "EditarPersona", antes=antes, despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/personas/{persona_id}", status_code=303)


@router.post("/personas/{persona_id}/baja")
def dar_de_baja_persona(persona_id: int, db: Session = Depends(get_db)):
    p = db.query(m.Persona).get(persona_id)
    antes = to_dict(p)
    p.activo = 0
    log_historial(db, "personas", p.id, "DarDeBajaPersona", antes=antes, despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/personas/{persona_id}", status_code=303)


@router.post("/personas/{persona_id}/alta")
def dar_de_alta_persona(persona_id: int, db: Session = Depends(get_db)):
    p = db.query(m.Persona).get(persona_id)
    antes = to_dict(p)
    p.activo = 1
    log_historial(db, "personas", p.id, "DarDeAltaPersona", antes=antes, despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/personas/{persona_id}", status_code=303)


@router.get("/buscar", response_class=HTMLResponse)
def buscar(q: str, request: Request, db: Session = Depends(get_db)):
    ql = f"%{q}%"
    resultados = []
    for p in db.query(m.Persona).filter((m.Persona.nombre.ilike(ql)) | (m.Persona.apellido.ilike(ql)), m.Persona.activo == 1):
        resultados.append({"principal": f"{p.nombre} {p.apellido}", "sub": "Persona", "href": f"/ui/personas/{p.id}"})
    for pu in db.query(m.Puesto).filter((m.Puesto.codigo.ilike(ql)) | (m.Puesto.nombre.ilike(ql)), m.Puesto.vigente == 1):
        resultados.append({"principal": f"{pu.codigo} — {pu.nombre}", "sub": "Puesto", "href": f"/ui/puestos/{pu.codigo}"})
    for a in db.query(m.Actividad).filter((m.Actividad.codigo.ilike(ql)) | (m.Actividad.descripcion.ilike(ql)), m.Actividad.activo == 1).limit(15):
        resultados.append({"principal": f"{a.codigo} — {a.descripcion}", "sub": "Actividad", "href": f"/ui/actividades/{a.codigo}"})
    for me in db.query(m.Mecanismo).filter((m.Mecanismo.codigo.ilike(ql)) | (m.Mecanismo.nombre.ilike(ql))):
        resultados.append({"principal": f"{me.codigo} — {me.nombre}", "sub": "Mecanismo", "href": f"/ui/mecanismos/{me.codigo}"})
    for pl in db.query(m.Planta).filter(m.Planta.nombre.ilike(ql)):
        resultados.append({"principal": pl.nombre, "sub": "Planta", "href": f"/ui/plantas/{pl.id}"})
    for f in db.query(m.Formulario).filter((m.Formulario.codigo.ilike(ql)) | (m.Formulario.nombre.ilike(ql))):
        resultados.append({"principal": f"{f.codigo} — {f.nombre}", "sub": "Formulario", "href": f"/ui/formularios/{f.codigo}"})
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


@router.get("/personas/{persona_id}/actividades-de-puesto", response_class=HTMLResponse)
def actividades_de_puesto_origen(persona_id: int, request: Request, puesto_codigo: str = "", db: Session = Depends(get_db)):
    """Alimenta el checklist de actividades cuando se elige el puesto de origen
    en el modo 'Actividades sueltas' — Opción B / AsignarActividadSuelta."""
    actividades = []
    requiere_etapa = False
    if puesto_codigo:
        actividades = db.query(m.Actividad).filter(m.Actividad.puesto_codigo == puesto_codigo,
                                                     m.Actividad.activo == 1).order_by(m.Actividad.codigo).all()
        requiere_etapa = puesto_codigo in ("PRD-04", "PRD-05")
    return templates.TemplateResponse(request, "_actividades_checkboxes.html", {
        "actividades": actividades, "requiere_etapa": requiere_etapa, "puesto_codigo": puesto_codigo,
    })


@router.post("/personas/{persona_id}/actividades-sueltas/nueva", response_class=HTMLResponse)
def nueva_actividad_suelta(persona_id: int, request: Request, db: Session = Depends(get_db),
                            planta_id: int = Form(...), etapa: str = Form(None),
                            actividad_ids: list[int] = Form(default=[]), permitir_conflicto: bool = Form(False)):
    """Acción AsignarActividadSuelta (Opción B) desde la ficha de Persona — mismo
    mecanismo que /api/asignaciones/asignar-actividades, pero con formulario HTML
    y manejo de conflictos consistente con el resto de la ficha."""
    etapa = etapa or None

    if not actividad_ids:
        ctx = _ficha_persona_ctx(db, persona_id)
        ctx["error_sueltas"] = "Elegí al menos una actividad."
        ctx["modo_default"] = "sueltas"
        return templates.TemplateResponse(request, "_form_nueva_asignacion.html", ctx)

    actividad_ids_set = set(actividad_ids)
    scope_planta = None if es_sede_unica(db, actividad_ids=actividad_ids_set) else planta_id
    conflictos = conflictos_exclusividad(db, scope_planta, actividad_ids_set, etapa=etapa, excluir_persona_id=persona_id)

    if conflictos and not permitir_conflicto:
        return templates.TemplateResponse(request, "_conflicto_sueltas.html", {
            "persona_id": persona_id, "planta_id": planta_id, "etapa": etapa,
            "actividad_ids": actividad_ids, "conflictos": conflictos,
        })

    perfil = get_or_create_perfil_personal(db, persona_id, etapa)
    ya_asignada = db.query(m.Asignacion).filter(m.Asignacion.persona_id == persona_id,
                                                 m.Asignacion.perfil_id == perfil.id,
                                                 m.Asignacion.planta_id == planta_id,
                                                 m.Asignacion.estado.in_(["activa", "transicion"])).first()
    if not ya_asignada:
        nueva = m.Asignacion(persona_id=persona_id, perfil_id=perfil.id, planta_id=planta_id,
                              etapa=etapa, estado="activa")
        db.add(nueva)
        db.flush()
        log_historial(db, "asignaciones", nueva.id, "AsignarActividadSuelta (nueva cobertura)",
                      despues={"planta_id": planta_id, "etapa": etapa, "persona_id": persona_id})

    existentes = set(r[0] for r in db.query(m.PerfilActividad.actividad_id).filter(m.PerfilActividad.perfil_id == perfil.id))
    for aid in actividad_ids_set - existentes:
        db.add(m.PerfilActividad(perfil_id=perfil.id, actividad_id=aid))
    log_historial(db, "perfil_actividades", perfil.id, "AsignarActividadSuelta", despues={"actividad_ids": list(actividad_ids_set)})
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


@router.post("/personas/{persona_id}/habilitaciones/{habilitacion_id}/confirmar", response_class=HTMLResponse)
def confirmar_habilitacion(persona_id: int, habilitacion_id: int, request: Request, db: Session = Depends(get_db)):
    """Action Type: ConfirmarHabilitacion — pasa una habilitación de
    'pendiente_confirmacion' a 'vigente' una vez verificada."""
    h = db.query(m.HabilitacionDePersona).get(habilitacion_id)
    if h and h.estado == "sin_confirmar":
        log_historial(db, "habilitaciones_persona", h.id, "ConfirmarHabilitacion", antes={"estado": h.estado})
        h.estado = "vigente"
        db.commit()
    ctx = _ficha_persona_ctx(db, persona_id)
    return templates.TemplateResponse(request, "_habilitaciones.html", ctx)
