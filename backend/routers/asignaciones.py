from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, to_dict, log_historial
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/api/asignaciones", tags=["Asignacion"], dependencies=[Depends(verificar_acceso)])


# ───────────────────────── helpers compartidos por las Actions ─────────────────────────

def actividades_de_asignacion(db: Session, puesto_codigo, perfil_id, asignacion_id=None):
    """Actividades que una asignación cubre de verdad. Para un Puesto son todas las
    suyas MENOS las cedidas a otra persona (Opción A) — por eso hay que pasar
    asignacion_id cuando se la conoce; sin él se devuelve el puesto completo."""
    if puesto_codigo:
        ids = set(r[0] for r in db.query(m.Actividad.id).filter(m.Actividad.puesto_codigo == puesto_codigo, m.Actividad.activo == 1))
        if asignacion_id:
            ids -= set(r[0] for r in db.query(m.ActividadCedida.actividad_id).filter(m.ActividadCedida.asignacion_id == asignacion_id))
        return ids
    if perfil_id:
        return set(r[0] for r in db.query(m.PerfilActividad.actividad_id).filter(m.PerfilActividad.perfil_id == perfil_id))
    return set()


def es_sede_unica(db: Session, puesto_codigo=None, actividad_ids=None):
    if puesto_codigo:
        p = db.query(m.Puesto).filter(m.Puesto.codigo == puesto_codigo).first()
        return bool(p and p.cardinalidad_esperada == "unica_en_la_empresa")
    if actividad_ids:
        return db.query(m.Actividad).join(m.Puesto, m.Actividad.puesto_codigo == m.Puesto.codigo).filter(
            m.Actividad.id.in_(actividad_ids), m.Puesto.cardinalidad_esperada == "unica_en_la_empresa").first() is not None
    return False


def conflictos_exclusividad(db: Session, planta_id, actividad_ids, etapa=None, excluir_asignacion_id=None, excluir_persona_id=None):
    """La exclusividad es por (actividad, planta, etapa). planta_id=None chequea
    GLOBAL (para puestos de sede única). excluir_persona_id evita que la propia
    cobertura de la misma persona cuente como choque contra sí misma."""
    if not actividad_ids:
        return []
    q = db.query(m.Asignacion).filter(m.Asignacion.estado.in_(["activa", "transicion"]))
    if planta_id is not None:
        q = q.filter(m.Asignacion.planta_id == planta_id)
    conflictos = []
    for a in q.all():
        if excluir_asignacion_id and a.id == excluir_asignacion_id:
            continue
        if excluir_persona_id and a.persona_id == excluir_persona_id:
            continue
        if etapa and a.etapa and etapa != a.etapa:
            continue  # misma planta, línea de producción distinta — no choca
        cubiertas = actividades_de_asignacion(db, a.puesto_codigo, a.perfil_id, a.id)
        choque = cubiertas & actividad_ids
        if choque:
            codigos = [c[0] for c in db.query(m.Actividad.codigo).filter(m.Actividad.id.in_(choque))]
            conflictos.append({"asignacion_id": a.id, "persona": f"{a.persona.nombre} {a.persona.apellido}",
                                "puesto_codigo": a.puesto_codigo, "perfil_id": a.perfil_id, "etapa": a.etapa,
                                "actividades_en_conflicto": codigos})
    return conflictos


def get_or_create_perfil_personal(db: Session, persona_id: int, etapa=None):
    persona = db.query(m.Persona).get(persona_id)
    nombre = f"Ajustes individuales — {persona.nombre} {persona.apellido}" + (f" ({etapa})" if etapa else "")
    existente = db.query(m.Perfil).join(m.Asignacion, m.Asignacion.perfil_id == m.Perfil.id).filter(
        m.Asignacion.persona_id == persona_id, m.Perfil.nombre == nombre,
        m.Asignacion.estado.in_(["activa", "transicion"])).first()
    if existente:
        return existente
    perfil = m.Perfil(nombre=nombre, estado="vigente", origen="individual",
                       descripcion="Generado automáticamente — agrupa actividades sueltas de otros puestos asignadas individualmente a esta persona.")
    db.add(perfil)
    db.flush()  # para tener perfil.id sin cerrar la transacción
    return perfil


def asignaciones_vigentes_de_puesto(db: Session, puesto_codigo, planta_id, etapa=None):
    q = db.query(m.Asignacion).filter(m.Asignacion.puesto_codigo == puesto_codigo, m.Asignacion.planta_id == planta_id,
                                       m.Asignacion.estado.in_(["activa", "transicion"]))
    if etapa:
        q = q.filter(m.Asignacion.etapa == etapa)
    return q.all()


def cesiones_de(db: Session, asignaciones):
    """Unión de las actividades cedidas en un conjunto de asignaciones. Cuando un
    puesto cambia de titular, esas cesiones se heredan: la actividad sigue en manos
    de quien ya la lleva, el nuevo titular recibe el puesto menos esas actividades."""
    ids = [a.id for a in asignaciones]
    if not ids:
        return set()
    return set(r[0] for r in db.query(m.ActividadCedida.actividad_id).filter(m.ActividadCedida.asignacion_id.in_(ids)))


def heredar_cesiones(db: Session, nueva_asignacion, actividad_ids):
    for aid in actividad_ids:
        db.add(m.ActividadCedida(asignacion_id=nueva_asignacion.id, actividad_id=aid))
    if actividad_ids:
        log_historial(db, "actividades_cedidas", nueva_asignacion.id, "HeredarCesiones",
                      despues={"actividad_ids": sorted(actividad_ids)})


# ───────────────────────── lectura ─────────────────────────

@router.get("")
def listar(planta_id: int = None, estado: str = None, db: Session = Depends(get_db)):
    q = db.query(m.Asignacion)
    if planta_id:
        q = q.filter(m.Asignacion.planta_id == planta_id)
    if estado:
        q = q.filter(m.Asignacion.estado == estado)
    out = []
    for a in q.all():
        out.append({
            **to_dict(a),
            "persona": f"{a.persona.nombre} {a.persona.apellido}",
            "puesto_nombre": a.puesto.nombre if a.puesto else None,
            "perfil_nombre": a.perfil.nombre if a.perfil else None,
            "planta_nombre": a.planta.nombre,
        })
    return out


# ───────────────────────── Action: AsignarPersonaAPuesto (o a Perfil) ─────────────────────────

@router.post("")
def asignar_persona_a_puesto(body: dict, permitir_conflicto: bool = False, db: Session = Depends(get_db)):
    puesto_codigo, perfil_id = body.get("puesto_codigo"), body.get("perfil_id")
    if bool(puesto_codigo) == bool(perfil_id):
        raise HTTPException(400, "La asignación va a un Puesto formal O a un Perfil — exactamente uno de los dos.")
    if puesto_codigo in ("PRD-04", "PRD-05") and not body.get("etapa"):
        raise HTTPException(400, f"{puesto_codigo} requiere indicar etapa: 'primaria' o 'secundaria'.")

    cubiertas = actividades_de_asignacion(db, puesto_codigo, perfil_id)
    scope_planta = None if es_sede_unica(db, puesto_codigo=puesto_codigo) else body["planta_id"]
    conflictos = conflictos_exclusividad(db, scope_planta, cubiertas, etapa=body.get("etapa"), excluir_persona_id=body.get("persona_id"))
    if conflictos and not permitir_conflicto:
        raise HTTPException(409, {"mensaje": "Hay actividades que ya tienen responsable activo en esta planta/etapa.",
                                   "conflictos": conflictos})

    a = m.Asignacion(persona_id=body["persona_id"], puesto_codigo=puesto_codigo, perfil_id=perfil_id,
                      planta_id=body["planta_id"], etapa=body.get("etapa"), estado=body.get("estado", "activa"),
                      fecha_inicio=body.get("fecha_inicio"), fecha_fin_estimada=body.get("fecha_fin_estimada"),
                      condicion_salida=body.get("condicion_salida"))
    db.add(a)
    db.flush()
    log_historial(db, "asignaciones", a.id, "AsignarPersonaAPuesto", despues=body)
    db.commit()
    return {"id": a.id, "message": "Asignación creada", "conflictos_aceptados": conflictos or None}


@router.put("/{asignacion_id}")
def actualizar(asignacion_id: int, body: dict, permitir_conflicto: bool = False, db: Session = Depends(get_db)):
    a = db.query(m.Asignacion).get(asignacion_id)
    if not a:
        raise HTTPException(404, "Asignación no encontrada")
    puesto_codigo, perfil_id = body.get("puesto_codigo", a.puesto_codigo), body.get("perfil_id", a.perfil_id)
    if bool(puesto_codigo) == bool(perfil_id):
        raise HTTPException(400, "La asignación va a un Puesto formal O a un Perfil — exactamente uno de los dos.")

    cambia_puesto = puesto_codigo != a.puesto_codigo
    # las cesiones pertenecen al puesto original: si la asignación pasa a otro puesto, no aplican
    cubiertas = actividades_de_asignacion(db, puesto_codigo, perfil_id, None if cambia_puesto else asignacion_id)
    scope_planta = None if es_sede_unica(db, puesto_codigo=puesto_codigo) else body.get("planta_id", a.planta_id)
    conflictos = conflictos_exclusividad(db, scope_planta, cubiertas, etapa=body.get("etapa", a.etapa),
                                          excluir_asignacion_id=asignacion_id, excluir_persona_id=body.get("persona_id", a.persona_id))
    if conflictos and not permitir_conflicto:
        raise HTTPException(409, {"mensaje": "Hay actividades que ya tienen responsable activo en esta planta/etapa.",
                                   "conflictos": conflictos})

    antes = to_dict(a)
    if cambia_puesto:
        db.query(m.ActividadCedida).filter(m.ActividadCedida.asignacion_id == a.id).delete()
    for campo in ("puesto_codigo", "perfil_id", "planta_id", "etapa", "estado", "fecha_inicio", "fecha_fin_estimada", "condicion_salida"):
        if campo in body:
            setattr(a, campo, body[campo])
    log_historial(db, "asignaciones", a.id, "ActualizarAsignacion", antes=antes, despues=body)
    db.commit()
    return {"message": "Asignación actualizada", "conflictos_aceptados": conflictos or None}


# ───────────────────────── Action: FinalizarAsignacion ─────────────────────────

@router.delete("/{asignacion_id}")
def finalizar_asignacion(asignacion_id: int, db: Session = Depends(get_db)):
    a = db.query(m.Asignacion).get(asignacion_id)
    if not a:
        raise HTTPException(404, "Asignación no encontrada")
    from reparto import archivar_perfil_si_huerfano
    antes = to_dict(a)
    a.estado = "finalizada"
    log_historial(db, "asignaciones", a.id, "FinalizarAsignacion", antes=antes)
    db.flush()
    archivar_perfil_si_huerfano(db, a)
    db.commit()
    return {"message": "Asignación finalizada"}


# ───────────────────────── Action: ReasignarPuesto ─────────────────────────

@router.post("/reasignar-puesto")
def reasignar_puesto(body: dict, permitir_conflicto: bool = False, db: Session = Depends(get_db)):
    puesto_codigo, planta_id, etapa = body["puesto_codigo"], body["planta_id"], body.get("etapa")
    actividad_ids = set(r[0] for r in db.query(m.Actividad.id).filter(m.Actividad.puesto_codigo == puesto_codigo))
    scope_planta = None if es_sede_unica(db, puesto_codigo=puesto_codigo) else planta_id
    anteriores = asignaciones_vigentes_de_puesto(db, puesto_codigo, planta_id, etapa)
    heredadas = cesiones_de(db, anteriores)  # ya las lleva otra persona: no son conflicto
    conflictos = [c for c in conflictos_exclusividad(db, scope_planta, actividad_ids - heredadas, etapa=etapa,
                                                       excluir_persona_id=body.get("persona_id_nuevo"))
                  if c["puesto_codigo"] != puesto_codigo]
    if conflictos and not permitir_conflicto:
        raise HTTPException(409, {"mensaje": "Otras actividades de este puesto ya tienen responsable.", "conflictos": conflictos})

    finalizadas = []
    for a in anteriores:
        a.estado = "finalizada"
        log_historial(db, "asignaciones", a.id, "ReasignarPuesto (finaliza anterior)")
        finalizadas.append(a.id)

    nueva = m.Asignacion(persona_id=body["persona_id_nuevo"], puesto_codigo=puesto_codigo, planta_id=planta_id,
                          etapa=etapa, estado="activa", fecha_inicio=body.get("fecha_inicio"))
    db.add(nueva)
    db.flush()
    heredar_cesiones(db, nueva, heredadas)
    log_historial(db, "asignaciones", nueva.id, "ReasignarPuesto (nueva)", despues=body)
    db.commit()
    return {"message": "Puesto reasignado", "asignaciones_finalizadas": finalizadas, "conflictos_aceptados": conflictos or None}


# ───────────────────────── Action: AsignarActividadSuelta (Opción B — Sección 13.1) ─────────────────────────

@router.post("/asignar-actividades")
def asignar_actividad_suelta(body: dict, permitir_conflicto: bool = False, db: Session = Depends(get_db)):
    actividad_ids = set(body.get("actividad_ids") or [])
    if not actividad_ids:
        raise HTTPException(400, "Falta indicar qué actividades asignar.")

    scope_planta = None if es_sede_unica(db, actividad_ids=actividad_ids) else body["planta_id"]
    conflictos = conflictos_exclusividad(db, scope_planta, actividad_ids, etapa=body.get("etapa"), excluir_persona_id=body["persona_id"])
    if conflictos and not permitir_conflicto:
        raise HTTPException(409, {"mensaje": "Alguna de estas actividades ya tiene responsable activo en esta planta/etapa.",
                                   "conflictos": conflictos})

    from reparto import asignar_a_perfil_personal  # import diferido: reparto.py importa de este módulo
    perfil = asignar_a_perfil_personal(db, body["persona_id"], body["planta_id"], body.get("etapa"), actividad_ids)
    db.commit()
    return {"message": "Actividades asignadas", "perfil_id": perfil.id, "conflictos_aceptados": conflictos or None}


# ───────────────────────── Actions de reparto (Opción A) ─────────────────────────

@router.post("/trasladar-actividades")
def trasladar_actividades_api(body: dict, db: Session = Depends(get_db)):
    """Traslada actividades a una persona SIN doble cobertura: si las llevaba el
    titular de un puesto, queda registrada la cesión (el puesto sigue entero); si las
    llevaba otra persona vía perfil, se le quitan. body: actividad_ids, persona_id,
    planta_id (opcional: se deduce), etapa (opcional)."""
    from reparto import trasladar_actividades, planta_por_defecto
    ids = set(body.get("actividad_ids") or [])
    if not ids or not body.get("persona_id"):
        raise HTTPException(400, "Faltan actividad_ids y/o persona_id.")
    persona = db.query(m.Persona).get(body["persona_id"])
    if not persona or not persona.activo:
        raise HTTPException(404, "Persona no encontrada o dada de baja.")
    planta_id = body.get("planta_id") or planta_por_defecto(db, persona.id)
    res = trasladar_actividades(db, ids, persona.id, planta_id, body.get("etapa"))
    db.commit()
    return {"message": "Actividades trasladadas", **res}


@router.post("/devolver-actividades")
def devolver_actividades_api(body: dict, db: Session = Depends(get_db)):
    """Deshace traslados: las actividades vuelven al titular del puesto (o quedan
    sin responsable si el puesto está vacante). body: actividad_ids, planta_id, etapa."""
    from reparto import devolver_a_titular
    ids = set(body.get("actividad_ids") or [])
    if not ids:
        raise HTTPException(400, "Falta actividad_ids.")
    res = devolver_a_titular(db, ids, body.get("planta_id"), body.get("etapa"))
    db.commit()
    return {"message": "Actividades devueltas al titular", **res}
