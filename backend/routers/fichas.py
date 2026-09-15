from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, to_dict
from auth import verificar_acceso
from functions import calcular_cobertura, calcular_dias_para_extincion
import models as m

router = APIRouter(prefix="/api/fichas", tags=["Fichas"], dependencies=[Depends(verificar_acceso)])


@router.get("/persona/{persona_id}")
def ficha_persona(persona_id: int, db: Session = Depends(get_db)):
    p = db.query(m.Persona).get(persona_id)
    if not p:
        raise HTTPException(404, "Persona no encontrada")

    asigs = db.query(m.Asignacion).filter(m.Asignacion.persona_id == persona_id,
                                           m.Asignacion.estado.in_(["activa", "transicion"])).all()
    coberturas = [{
        "asignacion_id": a.id,
        "puesto_codigo": a.puesto_codigo, "puesto_nombre": a.puesto.nombre if a.puesto else None,
        "perfil_id": a.perfil_id, "perfil_nombre": a.perfil.nombre if a.perfil else None,
        "planta": a.planta.nombre, "etapa": a.etapa, "estado": a.estado,
    } for a in asigs]

    habilitaciones = [{**to_dict(h), "tipo_nombre": h.tipo_capacitacion_id and db.query(m.TipoDeCapacitacion).get(h.tipo_capacitacion_id).nombre}
                       for h in db.query(m.HabilitacionDePersona).filter(m.HabilitacionDePersona.persona_id == persona_id)]

    # capacitaciones pendientes: actividades cubiertas por esta persona -> tipo requerido -> ¿tiene habilitación de ese tipo?
    tipos_que_tiene = set(h.tipo_capacitacion_id for h in db.query(m.HabilitacionDePersona).filter(m.HabilitacionDePersona.persona_id == persona_id))
    actividad_ids = set()
    for a in asigs:
        if a.puesto_codigo:
            actividad_ids |= set(r[0] for r in db.query(m.Actividad.id).filter(m.Actividad.puesto_codigo == a.puesto_codigo))
        if a.perfil_id:
            actividad_ids |= set(r[0] for r in db.query(m.PerfilActividad.actividad_id).filter(m.PerfilActividad.perfil_id == a.perfil_id))
    pendientes = []
    if actividad_ids:
        reqs = db.query(m.ActividadCapacitacion).filter(m.ActividadCapacitacion.actividad_id.in_(actividad_ids),
                                                          m.ActividadCapacitacion.obligatoria == 1).all()
        vistos = set()
        for r in reqs:
            if r.tipo_capacitacion_id not in tipos_que_tiene and r.tipo_capacitacion_id not in vistos:
                vistos.add(r.tipo_capacitacion_id)
                tipo = db.query(m.TipoDeCapacitacion).get(r.tipo_capacitacion_id)
                pendientes.append({"tipo_capacitacion_id": tipo.id, "nombre": tipo.nombre})

    alertas = []
    if p.estado_legajo != "completo":
        alertas.append({"tipo": "legajo", "mensaje": f"Legajo {p.estado_legajo}"})
    for h in habilitaciones:
        if h.get("estado") == "vencida":
            alertas.append({"tipo": "habilitacion", "mensaje": f"{h['tipo_nombre']} vencida"})

    return {"persona": to_dict(p), "coberturas": coberturas, "habilitaciones": habilitaciones,
            "capacitaciones_pendientes": pendientes, "alertas": alertas}


@router.get("/puesto/{codigo}")
def ficha_puesto(codigo: str, db: Session = Depends(get_db)):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    if not p:
        raise HTTPException(404, "Puesto no encontrado")

    relaciones = db.query(m.RelacionReporte).filter(m.RelacionReporte.puesto_codigo == codigo).all()
    actividades = db.query(m.Actividad).filter(m.Actividad.puesto_codigo == codigo, m.Actividad.activo == 1).all()
    ocupantes = calcular_cobertura(db, puesto_codigo=codigo)
    mecanismos = db.query(m.MecanismoPuesto).filter(m.MecanismoPuesto.puesto_codigo == codigo).all()
    rol_transicion = db.query(m.RolDeTransicion).filter(m.RolDeTransicion.puesto_id == p.id, m.RolDeTransicion.estado == "vigente").first()

    return {
        "puesto": to_dict(p),
        "convenio": to_dict(p.convenio) if p.convenio else None,
        "reporta_jerarquicamente_a": [r.relacionado_codigo for r in relaciones if r.tipo == "jerarquico"],
        "coordina_funcionalmente_con": [r.relacionado_codigo for r in relaciones if r.tipo == "funcional"],
        "actividades": [to_dict(a) for a in actividades],
        "ocupantes_por_planta": ocupantes,
        "mecanismos": [{"mecanismo_id": mp.mecanismo_id, "mecanismo_codigo": mp.mecanismo.codigo,
                        "mecanismo_nombre": mp.mecanismo.nombre, "rol": mp.rol} for mp in mecanismos],
        "rol_transicion": ({**to_dict(rol_transicion),
                            "dias_para_extincion": calcular_dias_para_extincion(rol_transicion.fecha_estimada_extincion)}
                           if rol_transicion else None),
    }


@router.get("/planta/{planta_id}")
def ficha_planta(planta_id: int, db: Session = Depends(get_db)):
    pl = db.query(m.Planta).get(planta_id)
    if not pl:
        raise HTTPException(404, "Planta no encontrada")

    cobertura = [f for f in calcular_cobertura(db, planta_id=planta_id) if f["planta_id"] == planta_id]
    total = len(cobertura)
    cubiertas = len([f for f in cobertura if f["estado"] in ("cubierta", "cubierta_sin_etapa")])

    return {
        "planta": to_dict(pl),
        "resumen": {"total": total, "cubiertas": cubiertas, "pct_cobertura": round(100 * cubiertas / total, 1) if total else 0},
        "cobertura": cobertura,
    }
