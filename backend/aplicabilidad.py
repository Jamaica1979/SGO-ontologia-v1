"""Aplicabilidad por planta (v3.7).

Todo puesto y toda actividad aplica en todas las plantas salvo que la tabla
`exclusiones_planta` diga lo contrario. Este módulo es la única fuente de esa
regla: cobertura, reparto, reportes y alta de asignaciones preguntan acá.

  - exclusión de PUESTO con se_reparte=1 → el puesto no existe en la planta, pero sus
    actividades siguen siendo necesarias: se cubren con actividades sueltas.
  - exclusión de PUESTO con se_reparte=0 → ni el puesto ni sus actividades se necesitan allí.
  - exclusión de ACTIVIDAD → esa actividad no se necesita en esa planta.
"""
from collections import defaultdict
from sqlalchemy.orm import Session
import models as m


def mapa_exclusiones(db: Session):
    """Devuelve (actividades_no_requeridas_por_planta, puestos_excluidos).
       actividades_no_requeridas_por_planta: {planta_id: {actividad_id}}
       puestos_excluidos: {(puesto_codigo, planta_id): {"se_reparte": bool, "motivo": str}}"""
    filas = db.query(m.ExclusionPlanta).all()
    por_puesto = defaultdict(set)
    if any(f.puesto_codigo and not f.se_reparte for f in filas):
        for aid, cod in db.query(m.Actividad.id, m.Actividad.puesto_codigo):
            por_puesto[cod].add(aid)
    act = defaultdict(set)
    puestos = {}
    for f in filas:
        if f.actividad_id:
            act[f.planta_id].add(f.actividad_id)
        elif f.puesto_codigo:
            puestos[(f.puesto_codigo, f.planta_id)] = {"se_reparte": bool(f.se_reparte), "motivo": f.motivo}
            if not f.se_reparte:
                act[f.planta_id] |= por_puesto[f.puesto_codigo]
    return act, puestos


def excluidas_en_planta(db: Session, planta_id):
    """Ids de actividad que NO se necesitan en esa planta."""
    if planta_id is None:
        return set()
    return set(mapa_exclusiones(db)[0].get(planta_id, set()))


def exclusion_de_puesto(db: Session, puesto_codigo, planta_id):
    """None si el puesto aplica en la planta; si no, {"se_reparte", "motivo"}."""
    if planta_id is None:
        return None
    return mapa_exclusiones(db)[1].get((puesto_codigo, planta_id))


def mensaje_puesto_no_aplica(db: Session, puesto_codigo, planta_id):
    """Texto para mostrar al intentar asignar un puesto que no aplica en la planta (o None)."""
    ex = exclusion_de_puesto(db, puesto_codigo, planta_id)
    if not ex:
        return None
    pl = db.query(m.Planta).get(planta_id)
    base = f"El puesto {puesto_codigo} no aplica en {pl.nombre if pl else 'esa planta'}."
    if ex["se_reparte"]:
        return base + " Sus actividades se reparten entre otras personas: asignalas como actividades sueltas."
    return base + " Sus actividades tampoco se necesitan allí."


def filas_aplicabilidad(db: Session, puesto_codigo=None, actividad_id=None):
    """Una fila por planta con el modo vigente: 'aplica' | 'se_reparte' | 'no_aplica' (+ motivo)."""
    filas = []
    q = db.query(m.ExclusionPlanta)
    q = q.filter(m.ExclusionPlanta.puesto_codigo == puesto_codigo) if puesto_codigo else q.filter(m.ExclusionPlanta.actividad_id == actividad_id)
    por_planta = {e.planta_id: e for e in q}
    heredadas = {}
    if actividad_id:  # si el puesto de la actividad no aplica en la planta, la actividad lo hereda
        act = db.query(m.Actividad).get(actividad_id)
        for e in db.query(m.ExclusionPlanta).filter(m.ExclusionPlanta.puesto_codigo == act.puesto_codigo):
            heredadas[e.planta_id] = e
    for pl in db.query(m.Planta).order_by(m.Planta.id):
        e = por_planta.get(pl.id)
        modo = "aplica" if not e else ("se_reparte" if e.se_reparte else "no_aplica")
        filas.append({"planta": pl, "modo": modo, "motivo": e.motivo if e else "", "heredada": heredadas.get(pl.id)})
    return filas


def guardar_aplicabilidad(db: Session, planta_id, modo, motivo=None, puesto_codigo=None, actividad_id=None):
    """Fija el modo ('aplica' quita la excepción). Devuelve True si algo cambió."""
    from database import log_historial
    q = db.query(m.ExclusionPlanta).filter(m.ExclusionPlanta.planta_id == planta_id)
    q = q.filter(m.ExclusionPlanta.puesto_codigo == puesto_codigo) if puesto_codigo else q.filter(m.ExclusionPlanta.actividad_id == actividad_id)
    e = q.first()
    ref = puesto_codigo or f"actividad {actividad_id}"
    if modo == "aplica":
        if not e:
            return False
        log_historial(db, "exclusiones_planta", e.id, "MarcarAplica", antes={"ref": ref, "planta_id": planta_id, "se_reparte": e.se_reparte})
        db.delete(e)
        return True
    se_reparte = 1 if (modo == "se_reparte" and puesto_codigo) else 0
    if e:
        if bool(e.se_reparte) == bool(se_reparte) and (e.motivo or "") == (motivo or ""):
            return False
        e.se_reparte, e.motivo = se_reparte, motivo
        log_historial(db, "exclusiones_planta", e.id, "EditarNoAplica", despues={"ref": ref, "planta_id": planta_id, "modo": modo})
    else:
        e = m.ExclusionPlanta(planta_id=planta_id, puesto_codigo=puesto_codigo, actividad_id=actividad_id,
                               se_reparte=se_reparte, motivo=motivo)
        db.add(e)
        db.flush()
        log_historial(db, "exclusiones_planta", e.id, "MarcarNoAplica", despues={"ref": ref, "planta_id": planta_id, "modo": modo, "motivo": motivo})
    return True
