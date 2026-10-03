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


def _render(request, titulo, items, nuevo_link=None, toggle_link=None, extra_link=None):
    return templates.TemplateResponse(request, "listado.html", {
        "titulo": titulo, "items": items, "nuevo_link": nuevo_link,
        "toggle_link": toggle_link, "extra_link": extra_link})


@router.get("/puestos", response_class=HTMLResponse)
def puestos(request: Request, ver_baja: bool = False, db: Session = Depends(get_db)):
    q = db.query(m.Puesto)
    if not ver_baja:
        q = q.filter(m.Puesto.vigente == 1)
    items = [{"principal": f"{p.codigo} — {p.nombre}", "sub": p.area, "href": f"/ui/puestos/{p.codigo}",
              "tag": None if p.vigente else "BAJA", "tag_clase": "off", "de_baja": not p.vigente}
             for p in q.order_by(m.Puesto.codigo)]
    return _render(request, "Puestos", items, nuevo_link={"texto": "+ Nuevo puesto", "href": "/ui/puestos/nuevo"},
                   toggle_link={"texto": "Ocultar dados de baja" if ver_baja else "Ver también dados de baja",
                                "href": "/ui/listado/puestos" if ver_baja else "/ui/listado/puestos?ver_baja=1"})


@router.get("/personas", response_class=HTMLResponse)
def personas(request: Request, ver_baja: bool = False, db: Session = Depends(get_db)):
    q = db.query(m.Persona)
    if not ver_baja:
        q = q.filter(m.Persona.activo == 1)
    items = [{"principal": f"{p.nombre} {p.apellido}", "sub": p.legajo and f"Legajo {p.legajo}" or "Sin legajo",
              "href": f"/ui/personas/{p.id}",
              "tag": "BAJA" if not p.activo else (None if p.estado_legajo == "completo" else p.estado_legajo),
              "tag_clase": "off" if not p.activo else "warn", "de_baja": not p.activo}
             for p in q.order_by(m.Persona.apellido)]
    return _render(request, "Personas", items, nuevo_link={"texto": "+ Nueva persona", "href": "/ui/personas/nuevo"},
                   toggle_link={"texto": "Ocultar dados de baja" if ver_baja else "Ver también dados de baja",
                                "href": "/ui/listado/personas" if ver_baja else "/ui/listado/personas?ver_baja=1"})


@router.get("/plantas", response_class=HTMLResponse)
def plantas(request: Request, ver_baja: bool = False, db: Session = Depends(get_db)):
    q = db.query(m.Planta)
    if not ver_baja:
        q = q.filter(m.Planta.estado != "inactiva")
    items = [{"principal": p.nombre, "sub": p.notas, "href": f"/ui/plantas/{p.id}",
              "tag": p.estado, "tag_clase": "ok" if p.estado in ("activa", "piloto") else ("off" if p.estado == "inactiva" else "warn"),
              "de_baja": p.estado == "inactiva"}
             for p in q]
    return _render(request, "Plantas", items, nuevo_link={"texto": "+ Nueva planta", "href": "/ui/plantas/nuevo"},
                   toggle_link={"texto": "Ocultar inactivas" if ver_baja else "Ver también inactivas",
                                "href": "/ui/listado/plantas" if ver_baja else "/ui/listado/plantas?ver_baja=1"})


@router.get("/actividades", response_class=HTMLResponse)
def actividades(request: Request, ver_baja: bool = False, db: Session = Depends(get_db)):
    q = db.query(m.Actividad)
    if not ver_baja:
        q = q.filter(m.Actividad.activo == 1)
    items = [{"principal": f"{a.codigo} — {a.descripcion}", "sub": f"{a.area} · {a.puesto_codigo or 'sin puesto'}",
              "href": f"/ui/actividades/{a.codigo}",
              "tag": "BAJA" if not a.activo else ("crítica" if a.es_critica else None),
              "tag_clase": "off" if not a.activo else "crit", "de_baja": not a.activo}
             for a in q.order_by(m.Actividad.codigo)]
    return _render(request, "Catálogo de actividades", items,
                   nuevo_link={"texto": "+ Nueva actividad", "href": "/ui/actividades/nuevo"},
                   toggle_link={"texto": "Ocultar dadas de baja" if ver_baja else "Ver también dadas de baja",
                                "href": "/ui/listado/actividades" if ver_baja else "/ui/listado/actividades?ver_baja=1"})


@router.get("/mecanismos", response_class=HTMLResponse)
def mecanismos(request: Request, ver_baja: bool = False, db: Session = Depends(get_db)):
    q = db.query(m.Mecanismo)
    if not ver_baja:
        q = q.filter(m.Mecanismo.vigente == 1)
    items = [{"principal": f"{me.codigo} — {me.nombre}", "sub": me.grupo, "href": f"/ui/mecanismos/{me.codigo}",
              "tag": None if me.vigente else "BAJA", "tag_clase": "off", "de_baja": not me.vigente}
             for me in q.order_by(m.Mecanismo.codigo)]
    return _render(request, "Mecanismos de coordinación", items,
                   nuevo_link={"texto": "+ Nuevo mecanismo", "href": "/ui/mecanismos/nuevo"},
                   toggle_link={"texto": "Ocultar dados de baja" if ver_baja else "Ver también dados de baja",
                                "href": "/ui/listado/mecanismos" if ver_baja else "/ui/listado/mecanismos?ver_baja=1"})


@router.get("/procedimientos", response_class=HTMLResponse)
def procedimientos(request: Request, ver_baja: bool = False, db: Session = Depends(get_db)):
    q = db.query(m.Procedimiento)
    if not ver_baja:
        q = q.filter(m.Procedimiento.vigente == 1)
    items = [{"principal": f"{p.codigo} — {p.nombre}", "sub": p.area, "href": f"/ui/procedimientos/{p.codigo}",
              "tag": None if p.vigente else "BAJA", "tag_clase": "off", "de_baja": not p.vigente}
             for p in q.order_by(m.Procedimiento.codigo)]
    return _render(request, "Manual de Procedimientos", items,
                   nuevo_link={"texto": "+ Nuevo procedimiento", "href": "/ui/procedimientos/nuevo"},
                   toggle_link={"texto": "Ocultar dados de baja" if ver_baja else "Ver también dados de baja",
                                "href": "/ui/listado/procedimientos" if ver_baja else "/ui/listado/procedimientos?ver_baja=1"})


@router.get("/formularios", response_class=HTMLResponse)
def formularios(request: Request, db: Session = Depends(get_db)):
    items = [{"principal": f"{f.codigo} — {f.nombre}", "sub": f.origen, "href": f"/ui/formularios/{f.codigo}"}
              for f in db.query(m.Formulario).order_by(m.Formulario.codigo)]
    return _render(request, "Formularios", items, nuevo_link={"texto": "+ Nuevo formulario", "href": "/ui/formularios/nuevo"})


@router.get("/indicadores", response_class=HTMLResponse)
def indicadores(request: Request, ver_baja: bool = False, db: Session = Depends(get_db)):
    q = db.query(m.Indicador)
    if not ver_baja:
        q = q.filter(m.Indicador.activo == 1)
    items = [{"principal": f"{i.codigo} — {i.nombre}", "sub": i.area, "href": f"/ui/indicadores/{i.codigo}",
              "tag": None if i.activo else "BAJA", "tag_clase": "off", "de_baja": not i.activo}
             for i in q.order_by(m.Indicador.codigo)]
    return templates.TemplateResponse(request, "listado.html", {
        "titulo": "Tablero de KPIs", "items": items,
        "nuevo_link": {"texto": "+ Nuevo indicador", "href": "/ui/indicadores/nuevo"},
        "extra_link": {"texto": "⬇ Reporte mensual completo (PDF)", "href": "/ui/reporte/pdf", "target": "_blank"},
        "toggle_link": {"texto": "Ocultar dados de baja" if ver_baja else "Ver también dados de baja",
                         "href": "/ui/listado/indicadores" if ver_baja else "/ui/listado/indicadores?ver_baja=1"}})
