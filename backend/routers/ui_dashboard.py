from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db
from auth import verificar_acceso
from functions import calcular_cobertura, resumen_cobertura, bandeja_de_pendientes, detectar_alertas, calcular_riesgo_dependencia
from routers.ui_shared import asignar_o_reasignar
import models as m

router = APIRouter(prefix="/ui/dashboard", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _ctx(db: Session):
    filas = calcular_cobertura(db)
    plantas = db.query(m.Planta).all()
    por_planta = []
    for pl in plantas:
        fs = [f for f in filas if f["planta_id"] == pl.id]
        cub = len([f for f in fs if f["estado"] in ("cubierta", "cubierta_sin_etapa")])
        por_planta.append({"planta_id": pl.id, "planta": pl.nombre, "total": len(fs), "cubiertas": cub})
    general = resumen_cobertura(filas)
    pendientes = bandeja_de_pendientes(db)
    return {
        "general": general, "por_planta": por_planta, "pendientes": pendientes,
        "alertas": detectar_alertas(db), "riesgos": calcular_riesgo_dependencia(db),
        "personas": db.query(m.Persona).filter(m.Persona.activo == 1).order_by(m.Persona.apellido).all(),
        "plantas": plantas,
    }


@router.get("", response_class=HTMLResponse)
def ver(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "dashboard.html", _ctx(db))


@router.post("/asignar", response_class=HTMLResponse)
def asignar(request: Request, db: Session = Depends(get_db),
            puesto_codigo: str = Form(...), planta_id: int = Form(...), etapa: str = Form(None),
            persona_id: int = Form(...), permitir_conflicto: bool = Form(False)):
    etapa = etapa if etapa and etapa != "None" else None
    ok, conflictos = asignar_o_reasignar(db, puesto_codigo, planta_id, etapa, persona_id, permitir_conflicto)
    if not ok:
        return templates.TemplateResponse(request, "_cobertura_conflicto.html", {
            "puesto_codigo": puesto_codigo, "planta_id": planta_id, "etapa": etapa, "persona_id": persona_id,
            "conflictos": conflictos, "accion_url": "/ui/dashboard/asignar"})
    fila = next((f for f in calcular_cobertura(db, puesto_codigo=puesto_codigo) if f["planta_id"] == planta_id and f["etapa"] == etapa), None)
    return templates.TemplateResponse(request, "_cobertura_fila.html", {
        "f": fila, "mostrar_puesto": True, "mostrar_planta": True, "accion_url": "/ui/dashboard/asignar",
        "personas": db.query(m.Persona).filter(m.Persona.activo == 1).order_by(m.Persona.apellido).all(),
        "plantas": db.query(m.Planta).all()})
