from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db, log_historial, to_dict
from auth import verificar_acceso
from functions import calcular_cobertura
from routers.asignaciones import actividades_de_asignacion, es_sede_unica, conflictos_exclusividad, get_or_create_perfil_personal
from reparto import (actividades_a_cargo, trasladar_actividades, asignar_a_perfil_personal, planta_por_defecto,
                     archivar_perfil_si_huerfano, cobertura_de_puesto, DEL_PUESTO, SIN_RESPONSABLE)
import models as m

router = APIRouter(prefix="/ui", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _ficha_persona_ctx(db: Session, persona_id: int):
    p = db.query(m.Persona).get(persona_id)
    asigs = db.query(m.Asignacion).filter(m.Asignacion.persona_id == persona_id,
                                           m.Asignacion.estado.in_(["activa", "transicion"])).all()
    a_cargo = actividades_a_cargo(db, persona_id)
    cedidas_por_asig = {b["asignacion_id"]: len(b["cedidas"]) for b in a_cargo["bloques_propios"]}
    coberturas = [{
        "asignacion_id": a.id, "puesto_codigo": a.puesto_codigo,
        "puesto_nombre": a.puesto.nombre if a.puesto else None,
        "perfil_nombre": a.perfil.nombre if a.perfil else None,
        "planta": a.planta.nombre, "planta_id": a.planta_id, "etapa": a.etapa, "estado": a.estado,
        "n_cedidas": cedidas_por_asig.get(a.id, 0),
    } for a in asigs]

    sugerencias = []
    if not coberturas:
        # persona sin coberturas (por ejemplo, recién incorporada): qué hay para cubrir hoy
        sugerencias = [f for f in calcular_cobertura(db) if f["estado"] in ("sin_asignar", "parcial")
                       and (f["planta_estado"] in (None, "activa", "piloto"))][:8]

    tipos_que_tiene = set(h.tipo_capacitacion_id for h in db.query(m.HabilitacionDePersona).filter(m.HabilitacionDePersona.persona_id == persona_id))
    actividad_ids = set()
    for a in asigs:
        actividad_ids |= actividades_de_asignacion(db, a.puesto_codigo, a.perfil_id, a.id)
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
        "habilitaciones": habilitaciones, "a_cargo": a_cargo, "sugerencias": sugerencias,
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
    tiene_coberturas = db.query(m.Asignacion).filter(m.Asignacion.persona_id == persona_id,
                                                      m.Asignacion.estado.in_(["activa", "transicion"])).count()
    if tiene_coberturas:
        # antes de darla de baja hay que ver qué actividades quedan sin cubrir y decidir quién las toma
        return RedirectResponse(f"/ui/personas/{persona_id}/baja-impacto", status_code=303)
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
                      etapa: str = Form(None), permitir_conflicto: bool = Form(False),
                      sin_conflictivas: bool = Form(False)):
    etapa = etapa or None
    if puesto_codigo in ("PRD-04", "PRD-05") and not etapa:
        return templates.TemplateResponse(request, "_conflicto.html", {
            "persona_id": persona_id, "puesto_codigo": puesto_codigo, "planta_id": planta_id, "etapa": etapa,
            "conflictos": [{"persona": "—", "puesto_codigo": puesto_codigo, "etapa": None,
                             "actividades_en_conflicto": ["Falta indicar la etapa: primaria o secundaria"]}],
            "puede_excluir": False,
        })

    cubiertas = actividades_de_asignacion(db, puesto_codigo, None)
    scope_planta = None if es_sede_unica(db, puesto_codigo=puesto_codigo) else planta_id
    conflictos = conflictos_exclusividad(db, scope_planta, cubiertas, etapa=etapa, excluir_persona_id=persona_id)

    # Opción A: si las únicas actividades en conflicto las llevan personas por sus perfiles individuales,
    # se puede asignar el puesto SIN esas actividades (quedan cedidas y siguen con quien las lleva hoy)
    puede_excluir = bool(conflictos) and all(c["puesto_codigo"] is None for c in conflictos)

    if conflictos and not permitir_conflicto and not (sin_conflictivas and puede_excluir):
        return templates.TemplateResponse(request, "_conflicto.html", {
            "persona_id": persona_id, "puesto_codigo": puesto_codigo, "planta_id": planta_id, "etapa": etapa,
            "conflictos": conflictos, "puede_excluir": puede_excluir,
        })

    nueva = m.Asignacion(persona_id=persona_id, puesto_codigo=puesto_codigo, planta_id=planta_id,
                         etapa=etapa, estado="activa")
    db.add(nueva)
    db.flush()
    log_historial(db, "asignaciones", nueva.id, "AsignarPersonaAPuesto",
                  despues={"puesto_codigo": puesto_codigo, "planta_id": planta_id, "etapa": etapa, "persona_id": persona_id})
    aviso = None
    if conflictos and sin_conflictivas and puede_excluir:
        codigos = {cod for c in conflictos for cod in c["actividades_en_conflicto"]}
        ids = [r[0] for r in db.query(m.Actividad.id).filter(m.Actividad.codigo.in_(codigos))]
        for aid in ids:
            db.add(m.ActividadCedida(asignacion_id=nueva.id, actividad_id=aid))
        log_historial(db, "actividades_cedidas", nueva.id, "CederActividad",
                      despues={"actividades": sorted(codigos), "motivo": "ya las lleva otra persona"})
        aviso = f"Puesto asignado sin {len(ids)} actividad{'es' if len(ids) != 1 else ''}: quedan con quien las lleva hoy."
    db.commit()
    ctx = _ficha_persona_ctx(db, persona_id)
    ctx["aviso"] = aviso
    return templates.TemplateResponse(request, "_asignacion_creada.html", ctx)


@router.get("/personas/{persona_id}/actividades-de-puesto", response_class=HTMLResponse)
def actividades_de_puesto_origen(persona_id: int, request: Request, puesto_codigo: str = "", db: Session = Depends(get_db)):
    """Alimenta el checklist de actividades cuando se elige el puesto de origen
    en el modo 'Actividades sueltas' — Opción B / AsignarActividadSuelta. Muestra quién
    lleva hoy cada actividad, para ver el reparto antes de elegir."""
    actividades, hoy, personas = [], {}, []
    requiere_etapa = False
    if puesto_codigo:
        actividades = db.query(m.Actividad).filter(m.Actividad.puesto_codigo == puesto_codigo,
                                                     m.Actividad.activo == 1).order_by(m.Actividad.codigo).all()
        requiere_etapa = puesto_codigo in ("PRD-04", "PRD-05")
        for f in cobertura_de_puesto(db, puesto_codigo)["filas"]:
            nombres = sorted({t["persona"] for t in f["titulares"]})
            hoy[f["actividad"]["id"]] = (f"{len(nombres)} personas" if len(nombres) >= 3 else ", ".join(nombres)) or None
        personas = db.query(m.Persona).filter(m.Persona.activo == 1, m.Persona.id != persona_id).order_by(m.Persona.apellido).all()
    return templates.TemplateResponse(request, "_actividades_checkboxes.html", {
        "actividades": actividades, "requiere_etapa": requiere_etapa, "puesto_codigo": puesto_codigo,
        "hoy": hoy, "personas": personas,
    })


@router.post("/personas/{persona_id}/actividades-sueltas/nueva", response_class=HTMLResponse)
def nueva_actividad_suelta(persona_id: int, request: Request, db: Session = Depends(get_db),
                            planta_id: int = Form(...), etapa: str = Form(None),
                            actividad_ids: list[int] = Form(default=[]), permitir_conflicto: bool = Form(False),
                            trasladar: bool = Form(False), todas_ids: list[int] = Form(default=[]),
                            resto_persona_id: str = Form(None)):
    """Acción AsignarActividadSuelta desde la ficha de Persona. Si alguna actividad ya la lleva
    otra persona, se ofrece TRASLADARLA (el titular del puesto la cede, el puesto sigue entero)
    o, como antes, confirmar la doble cobertura. 'Resto': las actividades del puesto que no se
    marcaron pueden pasar en el mismo paso a otra persona."""
    etapa = etapa or None

    if not actividad_ids:
        ctx = _ficha_persona_ctx(db, persona_id)
        ctx["error_sueltas"] = "Elegí al menos una actividad."
        ctx["modo_default"] = "sueltas"
        return templates.TemplateResponse(request, "_form_nueva_asignacion.html", ctx)

    actividad_ids_set = set(actividad_ids)
    resto_id = int(resto_persona_id) if resto_persona_id else None
    scope_planta = None if es_sede_unica(db, actividad_ids=actividad_ids_set) else planta_id
    resto_ids = set()
    if resto_id and resto_id != persona_id:
        # el 'resto' son las no marcadas que hoy lleva el titular del puesto o nadie; lo que ya lleva
        # una tercera persona por traslado previo no se toca
        origen = db.query(m.Actividad.puesto_codigo).filter(m.Actividad.id.in_(actividad_ids_set)).first()
        if origen and origen[0]:
            cob = cobertura_de_puesto(db, origen[0], scope_planta, etapa)
            libres = {f["actividad"]["id"] for f in cob["filas"] if f["estado"] in (DEL_PUESTO, SIN_RESPONSABLE)}
            resto_ids = (set(todas_ids) & libres) - actividad_ids_set
    conflictos = conflictos_exclusividad(db, scope_planta, actividad_ids_set, etapa=etapa, excluir_persona_id=persona_id)

    if conflictos and not permitir_conflicto and not trasladar:
        return templates.TemplateResponse(request, "_conflicto_sueltas.html", {
            "persona_id": persona_id, "planta_id": planta_id, "etapa": etapa,
            "actividad_ids": actividad_ids, "conflictos": conflictos,
            "todas_ids": todas_ids, "resto_persona_id": resto_persona_id or "",
        })

    partes = []
    if trasladar and conflictos:
        res = trasladar_actividades(db, actividad_ids_set, persona_id, planta_id, etapa)
        if res["cedidas"]:
            partes.append(f"{len(res['cedidas'])} actividad{'es' if len(res['cedidas']) != 1 else ''} cedida{'s' if len(res['cedidas']) != 1 else ''} por el titular del puesto (conserva el resto)")
        if res["retiradas_de_otro_perfil"]:
            partes.append(f"{len(res['retiradas_de_otro_perfil'])} retirada{'s' if len(res['retiradas_de_otro_perfil']) != 1 else ''} de otra persona")
    else:
        asignar_a_perfil_personal(db, persona_id, planta_id, etapa, actividad_ids_set)

    if resto_ids:
        planta_resto = planta_por_defecto(db, resto_id) if scope_planta is None else planta_id
        trasladar_actividades(db, resto_ids, resto_id, planta_resto, etapa)
        resto_p = db.query(m.Persona).get(resto_id)
        partes.append(f"las {len(resto_ids)} restantes pasaron a {resto_p.nombre} {resto_p.apellido}")
    db.commit()

    ctx = _ficha_persona_ctx(db, persona_id)
    ctx["aviso"] = ("Asignadas. " + "; ".join(partes) + ".") if partes else None
    return templates.TemplateResponse(request, "_asignacion_creada.html", ctx)


@router.delete("/asignaciones/{asignacion_id}", response_class=HTMLResponse)
def finalizar(asignacion_id: int, request: Request, db: Session = Depends(get_db)):
    a = db.query(m.Asignacion).get(asignacion_id)
    persona_id = a.persona_id
    a.estado = "finalizada"
    log_historial(db, "asignaciones", a.id, "FinalizarAsignacion")
    db.flush()
    archivar_perfil_si_huerfano(db, a)
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
