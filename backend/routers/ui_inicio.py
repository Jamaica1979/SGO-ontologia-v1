"""Página de inicio: puerta de entrada agrupada por tema, con unos pocos números vivos."""
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db
from auth import verificar_acceso
from functions import calcular_cobertura, resumen_cobertura, bandeja_de_pendientes, detectar_alertas, calcular_riesgo_dependencia
import models as m

router = APIRouter(prefix="/ui", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("/inicio", response_class=HTMLResponse)
def inicio(request: Request, db: Session = Depends(get_db)):
    general = resumen_cobertura(calcular_cobertura(db))
    n = lambda q: q.count()  # noqa: E731
    return templates.TemplateResponse(request, "inicio.html", {
        "general": general,
        "pendientes": bandeja_de_pendientes(db)["total_abiertos"],
        "alertas": len(detectar_alertas(db)),
        "sin_respaldo": calcular_riesgo_dependencia(db)["sin_mitigacion"],
        "n_puestos": n(db.query(m.Puesto).filter(m.Puesto.vigente == 1)),
        "n_personas": n(db.query(m.Persona).filter(m.Persona.activo == 1)),
        "n_plantas": n(db.query(m.Planta)),
        "n_actividades": n(db.query(m.Actividad).filter(m.Actividad.activo == 1)),
        "n_procedimientos": n(db.query(m.Procedimiento).filter(m.Procedimiento.vigente == 1)),
        "n_mecanismos": n(db.query(m.Mecanismo)),
        "n_formularios": n(db.query(m.Formulario).filter(m.Formulario.formulario_padre_id.is_(None))),
        "n_indicadores": n(db.query(m.Indicador)),
    })
