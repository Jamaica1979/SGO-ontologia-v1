from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/ui/actividades", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("/{codigo}", response_class=HTMLResponse)
def ver_ficha(codigo: str, request: Request, db: Session = Depends(get_db)):
    a = db.query(m.Actividad).filter(m.Actividad.codigo == codigo).first()
    puesto = db.query(m.Puesto).filter(m.Puesto.codigo == a.puesto_codigo).first() if a.puesto_codigo else None

    responsables = []
    activas = db.query(m.Asignacion).filter(m.Asignacion.estado.in_(["activa", "transicion"])).all()
    for asig in activas:
        cubre = False
        if asig.puesto_codigo == a.puesto_codigo and a.puesto_codigo:
            cubre = True
        elif asig.perfil_id:
            if db.query(m.PerfilActividad).filter(m.PerfilActividad.perfil_id == asig.perfil_id, m.PerfilActividad.actividad_id == a.id).first():
                cubre = True
        if cubre:
            responsables.append({"persona_id": asig.persona_id, "persona": f"{asig.persona.nombre} {asig.persona.apellido}",
                                  "planta": asig.planta.nombre, "via": "perfil" if asig.perfil_id else "puesto"})

    caps = [db.query(m.TipoDeCapacitacion).get(r.tipo_capacitacion_id).nombre
            for r in db.query(m.ActividadCapacitacion).filter(m.ActividadCapacitacion.actividad_id == a.id)]

    return templates.TemplateResponse(request, "ficha_actividad.html", {
        "actividad": a, "puesto_nombre": puesto.nombre if puesto else None,
        "responsables": responsables, "capacitaciones": caps,
    })
