from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from database import SessionLocal
import models as m

from routers import (plantas, puestos, personas, actividades, convenios, mecanismos, asignaciones, fichas,
                     dashboard, ui_personas, ui_puestos, ui_plantas, ui_dashboard, ui_listados,
                     ui_actividades, ui_mecanismos, ui_procedimientos, ui_indicadores, ui_historial, ui_reporte)

app = FastAPI(title="SGO Cantera Eldorado v3 — por objetos")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

for r in (plantas.router, puestos.router, personas.router, actividades.router, convenios.router,
          mecanismos.router, asignaciones.router, fichas.router, dashboard.router,
          ui_personas.router, ui_puestos.router, ui_plantas.router, ui_dashboard.router, ui_listados.router,
          ui_actividades.router, ui_mecanismos.router, ui_procedimientos.router, ui_indicadores.router,
          ui_historial.router, ui_reporte.router):
    app.include_router(r)


@app.get("/")
def home():
    return RedirectResponse("/ui/dashboard")


@app.get("/api/health")
def health():
    db = SessionLocal()
    counts = {t.__tablename__: db.query(t).count() for t in
              (m.Actividad, m.Puesto, m.Persona, m.Procedimiento, m.Indicador, m.Mecanismo, m.Perfil)}
    db.close()
    return {"status": "ok", "version": "v3-ontologia", "counts": counts}
