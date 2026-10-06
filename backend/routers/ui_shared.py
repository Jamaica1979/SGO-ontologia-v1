"""Helper compartido: la Action de asignar-o-reasignar un puesto en una planta,
usada desde la ficha de Puesto, la ficha de Planta y la bandeja de pendientes
del Dashboard. Un solo lugar, tres pantallas lo llaman."""
from sqlalchemy.orm import Session
from database import log_historial
from routers.asignaciones import (es_sede_unica, conflictos_exclusividad, asignaciones_vigentes_de_puesto,
                                  cesiones_de, heredar_cesiones)
import models as m


def asignar_o_reasignar(db: Session, puesto_codigo: str, planta_id: int, etapa: str, persona_id_nuevo: int,
                         permitir_conflicto: bool = False):
    """Devuelve (ok: bool, conflictos: list). Si ok=False, no se escribió nada."""
    etapa = etapa if etapa and etapa != "None" else None  # normaliza strings vacíos o literales "None" del form
    actividad_ids = set(r[0] for r in db.query(m.Actividad.id).filter(m.Actividad.puesto_codigo == puesto_codigo))
    scope_planta = None if es_sede_unica(db, puesto_codigo=puesto_codigo) else planta_id
    anteriores = asignaciones_vigentes_de_puesto(db, puesto_codigo, planta_id, etapa)
    heredadas = cesiones_de(db, anteriores)  # las que ya lleva otra persona se heredan, no son conflicto
    conflictos = [c for c in conflictos_exclusividad(db, scope_planta, actividad_ids - heredadas, etapa=etapa,
                                                       excluir_persona_id=persona_id_nuevo)
                  if c["puesto_codigo"] != puesto_codigo]
    if conflictos and not permitir_conflicto:
        return False, conflictos

    for a in anteriores:
        a.estado = "finalizada"
        log_historial(db, "asignaciones", a.id, "ReasignarPuesto (finaliza anterior)")

    nueva = m.Asignacion(persona_id=persona_id_nuevo, puesto_codigo=puesto_codigo, planta_id=planta_id,
                          etapa=etapa, estado="activa")
    db.add(nueva)
    db.flush()
    heredar_cesiones(db, nueva, heredadas)
    log_historial(db, "asignaciones", nueva.id, "AsignarPersonaAPuesto",
                  despues={"puesto_codigo": puesto_codigo, "planta_id": planta_id, "etapa": etapa, "persona_id": persona_id_nuevo})
    db.commit()
    return True, []
