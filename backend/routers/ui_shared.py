"""Helper compartido: la Action de asignar-o-reasignar un puesto en una planta,
usada desde la ficha de Puesto, la ficha de Planta y la bandeja de pendientes
del Dashboard. Un solo lugar, tres pantallas lo llaman."""
from sqlalchemy.orm import Session
from database import log_historial
from routers.asignaciones import (es_sede_unica, conflictos_exclusividad, asignaciones_vigentes_de_puesto,
                                  cesiones_de, heredar_cesiones, actividades_de_asignacion)
import models as m


def asignar_o_reasignar(db: Session, puesto_codigo: str, planta_id: int, etapa: str, persona_id_nuevo: int,
                         permitir_conflicto: bool = False, sumar: bool = False):
    """Devuelve (ok: bool, conflictos: list). Si ok=False, no se escribió nada.
    sumar=True agrega otra persona al puesto sin finalizar a quien ya está (puestos con
    dotación de varias personas por planta, como el Operador de Frente)."""
    from posiciones import normalizar, requiere_posicion, validar
    etapa = normalizar(etapa) if requiere_posicion(db, puesto_codigo) else None
    from aplicabilidad import mensaje_puesto_no_aplica
    msg = mensaje_puesto_no_aplica(db, puesto_codigo, planta_id) or validar(db, puesto_codigo, etapa)
    if msg:  # el puesto no existe en esa planta (o falta la posición): mismo formato de aviso que un conflicto
        return False, [{"persona": "—", "puesto_codigo": puesto_codigo, "etapa": None, "actividades_en_conflicto": [msg]}]
    actividad_ids = actividades_de_asignacion(db, puesto_codigo, None, None, planta_id, etapa)
    scope_planta = None if es_sede_unica(db, puesto_codigo=puesto_codigo) else planta_id
    anteriores = [] if sumar else asignaciones_vigentes_de_puesto(db, puesto_codigo, planta_id, etapa)
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
    log_historial(db, "asignaciones", nueva.id, "AsignarPersonaAPuesto" + (" (suma)" if sumar else ""),
                  despues={"puesto_codigo": puesto_codigo, "planta_id": planta_id, "etapa": etapa, "persona_id": persona_id_nuevo})
    db.commit()
    return True, []
