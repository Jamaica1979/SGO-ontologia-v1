from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db
from auth import verificar_acceso
from functions import calcular_dias_para_extincion, calcular_cobertura
from routers.ui_shared import asignar_o_reasignar
import models as m

router = APIRouter(prefix="/ui/puestos", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _ctx(db: Session, codigo: str):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    relaciones = db.query(m.RelacionReporte).filter(m.RelacionReporte.puesto_codigo == codigo).all()
    actividades = db.query(m.Actividad).filter(m.Actividad.puesto_codigo == codigo, m.Actividad.activo == 1).all()
    ocupantes = calcular_cobertura(db, puesto_codigo=codigo)
    mecs = db.query(m.MecanismoPuesto).filter(m.MecanismoPuesto.puesto_codigo == codigo).all()
    rol_transicion = db.query(m.RolDeTransicion).filter(m.RolDeTransicion.puesto_id == p.id, m.RolDeTransicion.estado == "vigente").first()
    return {
        "puesto": p, "convenio": p.convenio,
        "reporta_a": [r.relacionado_codigo for r in relaciones if r.tipo == "jerarquico"],
        "coordina_con": [r.relacionado_codigo for r in relaciones if r.tipo == "funcional"],
        "actividades": actividades, "ocupantes": ocupantes,
        "mecanismos": [{"mecanismo_codigo": mp.mecanismo.codigo, "rol": mp.rol} for mp in mecs],
        "rol_transicion": ({**{k: v for k, v in vars(rol_transicion).items() if not k.startswith("_")},
                            "dias_para_extincion": calcular_dias_para_extincion(rol_transicion.fecha_estimada_extincion)}
                           if rol_transicion else None),
        "personas": db.query(m.Persona).filter(m.Persona.activo == 1).order_by(m.Persona.apellido).all(),
        "plantas": db.query(m.Planta).all(),
    }


@router.get("/{codigo}", response_class=HTMLResponse)
def ver_ficha(codigo: str, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "ficha_puesto.html", _ctx(db, codigo))


@router.post("/{codigo}/asignar", response_class=HTMLResponse)
def asignar(codigo: str, request: Request, db: Session = Depends(get_db),
            planta_id: int = Form(...), etapa: str = Form(None), persona_id: int = Form(...),
            permitir_conflicto: bool = Form(False)):
    etapa = etapa if etapa and etapa != "None" else None
    ok, conflictos = asignar_o_reasignar(db, codigo, planta_id, etapa, persona_id, permitir_conflicto)
    if not ok:
        return templates.TemplateResponse(request, "_cobertura_conflicto.html", {
            "puesto_codigo": codigo, "planta_id": planta_id, "etapa": etapa, "persona_id": persona_id,
            "conflictos": conflictos, "accion_url": f"/ui/puestos/{codigo}/asignar"})
    fila = next((f for f in calcular_cobertura(db, puesto_codigo=codigo) if f["planta_id"] == planta_id and f["etapa"] == etapa), None)
    return templates.TemplateResponse(request, "_cobertura_fila.html", {
        "f": fila, "mostrar_puesto": False, "mostrar_planta": True, "accion_url": f"/ui/puestos/{codigo}/asignar",
        "personas": db.query(m.Persona).filter(m.Persona.activo == 1).order_by(m.Persona.apellido).all(),
        "plantas": db.query(m.Planta).all()})
