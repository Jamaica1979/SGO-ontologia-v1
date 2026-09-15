from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/ui/listado", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _render(request, titulo, items):
    return templates.TemplateResponse(request, "listado.html", {"titulo": titulo, "items": items})


@router.get("/puestos", response_class=HTMLResponse)
def puestos(request: Request, db: Session = Depends(get_db)):
    items = [{"principal": f"{p.codigo} — {p.nombre}", "sub": p.area, "href": f"/ui/puestos/{p.codigo}"}
              for p in db.query(m.Puesto).filter(m.Puesto.vigente == 1).order_by(m.Puesto.codigo)]
    return _render(request, "Puestos", items)


@router.get("/personas", response_class=HTMLResponse)
def personas(request: Request, db: Session = Depends(get_db)):
    items = [{"principal": f"{p.nombre} {p.apellido}", "sub": p.legajo and f"Legajo {p.legajo}" or "Sin legajo",
              "href": f"/ui/personas/{p.id}", "tag": None if p.estado_legajo == "completo" else p.estado_legajo,
              "tag_clase": "warn"}
             for p in db.query(m.Persona).filter(m.Persona.activo == 1).order_by(m.Persona.apellido)]
    return _render(request, "Personas", items)


@router.get("/plantas", response_class=HTMLResponse)
def plantas(request: Request, db: Session = Depends(get_db)):
    items = [{"principal": p.nombre, "sub": p.notas, "href": f"/ui/plantas/{p.id}",
              "tag": p.estado, "tag_clase": "ok" if p.estado in ("activa", "piloto") else "warn"}
             for p in db.query(m.Planta)]
    return _render(request, "Plantas", items)


@router.get("/actividades", response_class=HTMLResponse)
def actividades(request: Request, db: Session = Depends(get_db)):
    items = [{"principal": f"{a.codigo} — {a.descripcion}", "sub": f"{a.area} · {a.puesto_codigo or 'sin puesto'}",
              "href": f"/ui/actividades/{a.codigo}", "tag": "crítica" if a.es_critica else None, "tag_clase": "crit"}
             for a in db.query(m.Actividad).filter(m.Actividad.activo == 1).order_by(m.Actividad.codigo)]
    return _render(request, "Catálogo de actividades", items)


@router.get("/mecanismos", response_class=HTMLResponse)
def mecanismos(request: Request, db: Session = Depends(get_db)):
    items = [{"principal": f"{me.codigo} — {me.nombre}", "sub": me.grupo, "href": f"/ui/mecanismos/{me.codigo}"}
              for me in db.query(m.Mecanismo).filter(m.Mecanismo.vigente == 1).order_by(m.Mecanismo.codigo)]
    return _render(request, "Mecanismos de coordinación", items)


@router.get("/procedimientos", response_class=HTMLResponse)
def procedimientos(request: Request, db: Session = Depends(get_db)):
    items = [{"principal": f"{p.codigo} — {p.nombre}", "sub": p.area, "href": f"/ui/procedimientos/{p.codigo}"}
              for p in db.query(m.Procedimiento).order_by(m.Procedimiento.codigo)]
    return _render(request, "Manual de Procedimientos", items)


@router.get("/indicadores", response_class=HTMLResponse)
def indicadores(request: Request, db: Session = Depends(get_db)):
    items = [{"principal": f"{i.codigo} — {i.nombre}", "sub": i.area, "href": f"/ui/indicadores/{i.codigo}"}
              for i in db.query(m.Indicador).filter(m.Indicador.activo == 1).order_by(m.Indicador.codigo)]
    return _render(request, "Tablero de KPIs", items)
