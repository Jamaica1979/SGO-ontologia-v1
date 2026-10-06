"""
Reparto de actividades (Opción A) — lógica compartida por la API y las pantallas.

Modelo: una persona puede llevar actividades de dos maneras.
  1) Vía un Puesto: lleva todas las actividades del puesto, MENOS las que tenga
     cedidas (tabla actividades_cedidas, colgada de su Asignación al puesto).
  2) Vía su Perfil individual ("Ajustes individuales — Nombre"): actividades
     sueltas de otros puestos.
Ceder una actividad = registrar la cesión en la asignación del titular del
puesto + agregarla al perfil individual de quien la recibe. El titular conserva
su puesto (el organigrama no cambia) y la excepción queda a la vista.

Nada de acá borra registros de negocio: finalizar es un cambio de estado, y las
cesiones o actividades sueltas que se retiran quedan registradas en el Historial.
"""
from collections import defaultdict
from sqlalchemy.orm import Session
from database import log_historial
from routers.asignaciones import actividades_de_asignacion, get_or_create_perfil_personal
import models as m

ACTIVAS = ["activa", "transicion"]
SIN_RESPONSABLE, DEL_PUESTO, TRASLADADA, DOBLE = "sin_responsable", "del_puesto", "trasladada", "doble"


# ───────────────────────── utilidades ─────────────────────────

def _activas(db: Session):
    return db.query(m.Asignacion).filter(m.Asignacion.estado.in_(ACTIVAS)).all()


def _nombre(p):
    return f"{p.nombre} {p.apellido}".strip()


def _matchea(asig, planta_id, etapa):
    """Mismo criterio que conflictos_exclusividad: planta_id=None es ámbito global
    (puestos de sede única); si ambos tienen etapa y difieren, no son el mismo ámbito."""
    if planta_id is not None and asig.planta_id != planta_id:
        return False
    if etapa and asig.etapa and etapa != asig.etapa:
        return False
    return True


def _ambito_planta(puesto, planta_id):
    """Los puestos de sede única no se acotan por planta."""
    if puesto is None or puesto.cardinalidad_esperada == "unica_en_la_empresa":
        return None
    return planta_id


def cedidas_por_asignacion(db: Session):
    out = defaultdict(set)
    for r in db.query(m.ActividadCedida):
        out[r.asignacion_id].add(r.actividad_id)
    return out


def planta_por_defecto(db: Session, persona_id: int):
    """Planta para crear el perfil individual de alguien cuando el puesto de origen es de sede
    única y no hay una planta elegida: la de su cobertura actual, o si no tiene, la primera."""
    a = db.query(m.Asignacion).filter(m.Asignacion.persona_id == persona_id,
                                       m.Asignacion.estado.in_(ACTIVAS)).order_by(m.Asignacion.id).first()
    if a:
        return a.planta_id
    pl = db.query(m.Planta).order_by(m.Planta.id).first()
    return pl.id if pl else None


def _act(a):
    return {"id": a.id, "codigo": a.codigo, "descripcion": a.descripcion,
            "es_critica": bool(a.es_critica), "frecuencia": a.frecuencia}


# ───────────────────────── acciones ─────────────────────────

def asignar_a_perfil_personal(db: Session, persona_id, planta_id, etapa, actividad_ids):
    """Suma actividades al Perfil individual de la persona (lo crea con su cobertura si
    hace falta). Es el mecanismo de AsignarActividadSuelta, extraído para compartirlo."""
    actividad_ids = set(actividad_ids)
    perfil = get_or_create_perfil_personal(db, persona_id, etapa)
    ya = db.query(m.Asignacion).filter(m.Asignacion.persona_id == persona_id, m.Asignacion.perfil_id == perfil.id,
                                        m.Asignacion.planta_id == planta_id, m.Asignacion.estado.in_(ACTIVAS)).first()
    if not ya:
        nueva = m.Asignacion(persona_id=persona_id, perfil_id=perfil.id, planta_id=planta_id, etapa=etapa, estado="activa")
        db.add(nueva)
        db.flush()
        log_historial(db, "asignaciones", nueva.id, "AsignarActividadSuelta (nueva cobertura)",
                      despues={"planta_id": planta_id, "etapa": etapa, "persona_id": persona_id})
    existentes = set(r[0] for r in db.query(m.PerfilActividad.actividad_id).filter(m.PerfilActividad.perfil_id == perfil.id))
    for aid in actividad_ids - existentes:
        db.add(m.PerfilActividad(perfil_id=perfil.id, actividad_id=aid))
    db.flush()
    log_historial(db, "perfil_actividades", perfil.id, "AsignarActividadSuelta", despues={"actividad_ids": sorted(actividad_ids)})
    return perfil


def _limpiar_perfiles_vacios(db: Session, asignaciones_perfil):
    """Si a un perfil individual se le retiraron todas las actividades, su cobertura
    deja de tener sentido: se finaliza y el perfil se archiva (no se borra)."""
    for a in asignaciones_perfil:
        quedan = db.query(m.PerfilActividad).filter(m.PerfilActividad.perfil_id == a.perfil_id).count()
        if quedan == 0 and a.estado in ACTIVAS:
            a.estado = "finalizada"
            log_historial(db, "asignaciones", a.id, "FinalizarAsignacion (perfil sin actividades)")
            if a.perfil:
                a.perfil.estado = "archivado"
                log_historial(db, "perfiles", a.perfil_id, "ArchivarPerfil (sin actividades)")


def archivar_perfil_si_huerfano(db: Session, asignacion):
    """Al finalizar la cobertura de un perfil individual, si ninguna otra asignación activa
    lo usa, el perfil se archiva (sus actividades quedan como historia, nada se borra)."""
    if not asignacion.perfil_id or not asignacion.perfil or asignacion.perfil.origen != "individual":
        return
    otras = db.query(m.Asignacion).filter(m.Asignacion.perfil_id == asignacion.perfil_id, m.Asignacion.id != asignacion.id,
                                           m.Asignacion.estado.in_(ACTIVAS)).count()
    if otras == 0 and asignacion.perfil.estado != "archivado":
        asignacion.perfil.estado = "archivado"
        log_historial(db, "perfiles", asignacion.perfil_id, "ArchivarPerfil (cobertura finalizada)")


def trasladar_actividades(db: Session, actividad_ids, persona_destino_id, planta_id, etapa=None):
    """Pasa las actividades a una persona SIN dejar doble cobertura.
    - Si las llevaba el titular de un puesto: se registra la cesión (el puesto sigue entero).
    - Si las llevaba otra persona vía perfil individual: se le retiran.
    - Si el destino es el propio titular del puesto: se le devuelven (se quita la cesión).
    - En cualquier otro caso se suman al perfil individual del destino."""
    actividad_ids = set(actividad_ids)
    puestos = {p.codigo: p for p in db.query(m.Puesto)}
    acts = db.query(m.Actividad).filter(m.Actividad.id.in_(actividad_ids)).all()
    activas = _activas(db)
    res = {"cedidas": [], "devueltas": [], "retiradas_de_otro_perfil": [], "asignadas": []}
    perfiles_tocados = []
    a_perfil = []

    for act in acts:
        scope = _ambito_planta(puestos.get(act.puesto_codigo), planta_id)
        es_titular_destino = False
        for a in activas:
            if not _matchea(a, scope, etapa):
                continue
            if a.puesto_codigo and a.puesto_codigo == act.puesto_codigo:
                cesion = db.query(m.ActividadCedida).get((a.id, act.id))
                if a.persona_id == persona_destino_id:
                    es_titular_destino = True
                    if cesion:
                        db.delete(cesion)
                        res["devueltas"].append(act.codigo)
                        log_historial(db, "actividades_cedidas", a.id, "DevolverActividadATitular", antes={"actividad": act.codigo})
                elif not cesion:
                    db.add(m.ActividadCedida(asignacion_id=a.id, actividad_id=act.id))
                    res["cedidas"].append(act.codigo)
                    log_historial(db, "actividades_cedidas", a.id, "CederActividad",
                                  despues={"actividad": act.codigo, "a_persona_id": persona_destino_id})
            elif a.perfil_id and a.persona_id != persona_destino_id:
                pa = db.query(m.PerfilActividad).get((a.perfil_id, act.id))
                if pa:
                    db.delete(pa)
                    perfiles_tocados.append(a)
                    res["retiradas_de_otro_perfil"].append(act.codigo)
                    log_historial(db, "perfil_actividades", a.perfil_id, "RetirarActividadDePerfil",
                                  antes={"actividad": act.codigo, "persona_id": a.persona_id})
        db.flush()
        if es_titular_destino:
            # el destino ya la lleva por su puesto; si además la tenía suelta, se evita la doble cobertura
            for a in activas:
                if a.perfil_id and a.persona_id == persona_destino_id and _matchea(a, scope, etapa):
                    pa = db.query(m.PerfilActividad).get((a.perfil_id, act.id))
                    if pa:
                        db.delete(pa)
                        perfiles_tocados.append(a)
            db.flush()
        else:
            a_perfil.append(act.id)

    if a_perfil:
        asignar_a_perfil_personal(db, persona_destino_id, planta_id, etapa, a_perfil)
        res["asignadas"] = [a.codigo for a in acts if a.id in a_perfil]
    db.flush()
    _limpiar_perfiles_vacios(db, perfiles_tocados)
    return res


def devolver_a_titular(db: Session, actividad_ids, planta_id=None, etapa=None):
    """Deshace los traslados: se quita la cesión y se retira la actividad de cualquier perfil
    individual. Queda con el titular del puesto, o sin responsable si el puesto está vacante."""
    puestos = {p.codigo: p for p in db.query(m.Puesto)}
    acts = db.query(m.Actividad).filter(m.Actividad.id.in_(set(actividad_ids))).all()
    activas = _activas(db)
    res = {"devueltas": [], "retiradas_de_perfil": []}
    perfiles_tocados = []
    for act in acts:
        scope = _ambito_planta(puestos.get(act.puesto_codigo), planta_id)
        for a in activas:
            if not _matchea(a, scope, etapa):
                continue
            if a.puesto_codigo and a.puesto_codigo == act.puesto_codigo:
                cesion = db.query(m.ActividadCedida).get((a.id, act.id))
                if cesion:
                    db.delete(cesion)
                    res["devueltas"].append(act.codigo)
                    log_historial(db, "actividades_cedidas", a.id, "DevolverActividadATitular", antes={"actividad": act.codigo})
            elif a.perfil_id:
                pa = db.query(m.PerfilActividad).get((a.perfil_id, act.id))
                if pa:
                    db.delete(pa)
                    perfiles_tocados.append(a)
                    res["retiradas_de_perfil"].append(act.codigo)
                    log_historial(db, "perfil_actividades", a.perfil_id, "RetirarActividadDePerfil",
                                  antes={"actividad": act.codigo, "persona_id": a.persona_id})
        db.flush()
    _limpiar_perfiles_vacios(db, perfiles_tocados)
    return res


# ───────────────────────── reparto de un puesto ─────────────────────────

def cobertura_de_puesto(db: Session, puesto_codigo: str, planta_id=None, etapa=None):
    """Quién lleva cada actividad de un puesto en un ámbito (planta/etapa)."""
    puesto = db.query(m.Puesto).filter(m.Puesto.codigo == puesto_codigo).first()
    scope = _ambito_planta(puesto, planta_id)
    acts = db.query(m.Actividad).filter(m.Actividad.puesto_codigo == puesto_codigo,
                                         m.Actividad.activo == 1).order_by(m.Actividad.codigo).all()
    asigs = [a for a in _activas(db) if _matchea(a, scope, etapa)]
    ced = cedidas_por_asignacion(db)
    perfil = defaultdict(set)
    for r in db.query(m.PerfilActividad):
        perfil[r.perfil_id].add(r.actividad_id)

    titulares_puesto = [{"persona_id": a.persona_id, "persona": _nombre(a.persona), "asignacion_id": a.id}
                        for a in asigs if a.puesto_codigo == puesto_codigo]
    filas = []
    for act in acts:
        titulares, cedida = [], False
        for a in asigs:
            if a.puesto_codigo == puesto_codigo:
                if act.id in ced.get(a.id, ()):
                    cedida = True
                else:
                    titulares.append({"persona_id": a.persona_id, "persona": _nombre(a.persona), "via": "puesto"})
            elif a.perfil_id and act.id in perfil[a.perfil_id]:
                titulares.append({"persona_id": a.persona_id, "persona": _nombre(a.persona), "via": "perfil"})
        vias = {t["via"] for t in titulares}
        if not titulares:
            estado = SIN_RESPONSABLE
        elif vias == {"puesto"}:
            estado = DEL_PUESTO      # puede haber varios titulares: en PRD-05, por ejemplo, es lo normal
        elif vias == {"perfil"}:
            estado = TRASLADADA
        else:
            estado = DOBLE           # la lleva un titular del puesto Y alguien por perfil: doble cobertura real
        filas.append({"actividad": _act(act), "titulares": titulares, "cedida": cedida, "estado": estado})
    return {
        "puesto": puesto, "titulares_puesto": titulares_puesto, "filas": filas,
        "n_total": len(filas),
        "n_sin_responsable": sum(1 for f in filas if f["estado"] == SIN_RESPONSABLE),
        "n_trasladadas": sum(1 for f in filas if f["estado"] == TRASLADADA),
        "n_doble": sum(1 for f in filas if f["estado"] == DOBLE),
    }


# ───────────────────────── lo que tiene a cargo cada persona ─────────────────────────

class _Datos:
    """Carga una sola vez todo lo necesario para armar reportes sin una consulta por persona."""
    def __init__(self, db: Session):
        self.puestos = {p.codigo: p for p in db.query(m.Puesto)}
        self.plantas = {p.id: p for p in db.query(m.Planta)}
        self.personas = {p.id: p for p in db.query(m.Persona)}
        self.acts = {}
        self.por_puesto = defaultdict(list)
        for a in db.query(m.Actividad).filter(m.Actividad.activo == 1).order_by(m.Actividad.codigo):
            self.acts[a.id] = a
            self.por_puesto[a.puesto_codigo].append(a)
        self.asigs = _activas(db)
        self.ced = cedidas_por_asignacion(db)
        self.perfil = defaultdict(set)
        for r in db.query(m.PerfilActividad):
            self.perfil[r.perfil_id].add(r.actividad_id)

    def quienes_llevan_suelta(self, actividad_id, scope_planta, etapa):
        return [_nombre(self.personas[x.persona_id]) for x in self.asigs
                if x.perfil_id and actividad_id in self.perfil[x.perfil_id] and _matchea(x, scope_planta, etapa)]

    def titulares_de_puesto(self, puesto_codigo, planta_id):
        scope = _ambito_planta(self.puestos.get(puesto_codigo), planta_id)
        return [_nombre(self.personas[x.persona_id]) for x in self.asigs
                if x.puesto_codigo == puesto_codigo and _matchea(x, scope, None)]


def resumen_persona(datos: _Datos, persona_id: int):
    p = datos.personas[persona_id]
    propios, recibidos = [], []
    n_propias = n_cedidas = n_recibidas = n_criticas = 0
    puestos_cod, planta_ids = [], []

    for a in sorted((x for x in datos.asigs if x.persona_id == persona_id), key=lambda x: (x.puesto_codigo or "~", x.id)):
        planta_ids.append(a.planta_id)
        if a.puesto_codigo:
            puesto = datos.puestos.get(a.puesto_codigo)
            puestos_cod.append(a.puesto_codigo)
            cedidas_ids = datos.ced.get(a.id, set())
            todas = datos.por_puesto.get(a.puesto_codigo, [])
            propias = [_act(x) for x in todas if x.id not in cedidas_ids]
            scope = _ambito_planta(puesto, a.planta_id)
            cedidas = [{"actividad": _act(x), "a_cargo_de": datos.quienes_llevan_suelta(x.id, scope, a.etapa)}
                       for x in todas if x.id in cedidas_ids]
            n_propias += len(propias)
            n_cedidas += len(cedidas)
            n_criticas += sum(1 for x in propias if x["es_critica"])
            propios.append({"asignacion_id": a.id, "puesto_codigo": a.puesto_codigo,
                            "puesto_nombre": puesto.nombre if puesto else a.puesto_codigo,
                            "planta": datos.plantas[a.planta_id].nombre, "etapa": a.etapa, "estado": a.estado,
                            "total_puesto": len(todas), "propias": propias, "cedidas": cedidas})
        else:
            por_origen = defaultdict(list)
            for aid in datos.perfil.get(a.perfil_id, set()):
                act = datos.acts.get(aid)
                if act:
                    por_origen[act.puesto_codigo].append(act)
            for cod, lista in sorted(por_origen.items(), key=lambda kv: kv[0] or "~"):
                puesto = datos.puestos.get(cod)
                lista.sort(key=lambda x: x.codigo)
                acts = [_act(x) for x in lista]
                n_recibidas += len(acts)
                n_criticas += sum(1 for x in acts if x["es_critica"])
                recibidos.append({"asignacion_id": a.id, "puesto_codigo": cod,
                                  "puesto_nombre": puesto.nombre if puesto else "Sin puesto de origen",
                                  "planta": datos.plantas[a.planta_id].nombre, "etapa": a.etapa,
                                  "titulares": datos.titulares_de_puesto(cod, a.planta_id) if cod else [],
                                  "actividades": acts})
    return {
        "persona_id": p.id, "persona": _nombre(p), "activo": bool(p.activo),
        "puestos": puestos_cod, "planta_ids": sorted(set(planta_ids)),
        "plantas": [datos.plantas[i].nombre for i in sorted(set(planta_ids))],
        "sin_asignacion": not planta_ids,
        "bloques_propios": propios, "bloques_recibidos": recibidos,
        "n_propias": n_propias, "n_recibidas": n_recibidas, "n_cedidas": n_cedidas,
        "n_total": n_propias + n_recibidas, "n_criticas": n_criticas,
    }


def actividades_a_cargo(db: Session, persona_id: int):
    return resumen_persona(_Datos(db), persona_id)


def reporte_personas(db: Session, planta_id=None, incluir_inactivas=False):
    datos = _Datos(db)
    filas = []
    for p in sorted(datos.personas.values(), key=lambda x: ((x.apellido or "").lower(), (x.nombre or "").lower())):
        if not p.activo and not incluir_inactivas:
            continue
        r = resumen_persona(datos, p.id)
        if planta_id and planta_id not in r["planta_ids"]:
            continue
        filas.append(r)
    return filas


# ───────────────────────── impacto de una salida ─────────────────────────

def impacto_de_finalizar(db: Session, asignaciones):
    """Qué actividades quedarían sin nadie que las lleve si se finalizan estas asignaciones."""
    finalizando = {a.id for a in asignaciones}
    datos = _Datos(db)
    restantes = [x for x in datos.asigs if x.id not in finalizando]

    def efectivas(x):
        if x.puesto_codigo:
            return {a.id for a in datos.por_puesto.get(x.puesto_codigo, [])} - datos.ced.get(x.id, set())
        return set(datos.perfil.get(x.perfil_id, set()))

    efectivas_restantes = [(x, efectivas(x)) for x in restantes]
    filas, vistos = [], set()
    for a in asignaciones:
        for aid in sorted(efectivas(a)):
            act = datos.acts.get(aid)
            if not act:
                continue
            puesto = datos.puestos.get(act.puesto_codigo)
            scope = _ambito_planta(puesto, a.planta_id)
            if any(aid in ef and _matchea(x, scope, a.etapa) for x, ef in efectivas_restantes):
                continue
            clave = (aid, a.planta_id, a.etapa)
            if clave in vistos:
                continue
            vistos.add(clave)
            devolvible = [_nombre(datos.personas[x.persona_id]) for x, _ in efectivas_restantes
                          if x.puesto_codigo and x.puesto_codigo == act.puesto_codigo
                          and aid in datos.ced.get(x.id, ()) and _matchea(x, scope, a.etapa)]
            filas.append({"actividad": _act(act), "puesto_codigo": act.puesto_codigo,
                          "puesto_nombre": puesto.nombre if puesto else None,
                          "planta_id": a.planta_id, "etapa": a.etapa,
                          "via": "puesto" if a.puesto_codigo else "perfil",
                          "devolvible_a": devolvible})
    return filas


def finalizar_con_reasignacion(db: Session, asignaciones, destinos):
    """Finaliza las asignaciones y, para cada actividad que quedaría sin cubrir, aplica el
    destino elegido: '' (dejar sin cubrir), '__titular__' (devolver al titular del puesto)
    o el id de una persona. Todo en una sola transacción: lo confirma quien llama."""
    filas = impacto_de_finalizar(db, asignaciones)
    for a in asignaciones:
        a.estado = "finalizada"
        log_historial(db, "asignaciones", a.id, "FinalizarAsignacion")
        db.flush()
        archivar_perfil_si_huerfano(db, a)
    db.flush()
    por_destino = defaultdict(list)
    for f in filas:
        d = str(destinos.get(f["actividad"]["id"], "") or "")
        if d:
            por_destino[(d, f["planta_id"], f["etapa"])].append(f["actividad"]["id"])
    aplicadas = 0
    for (d, planta, etapa), ids in por_destino.items():
        if d == "__titular__":
            devolver_a_titular(db, ids, planta, etapa)
        else:
            trasladar_actividades(db, ids, int(d), planta, etapa)
        aplicadas += len(ids)
    return {"sin_cubrir": len(filas) - aplicadas, "reasignadas": aplicadas}
