from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from database import SessionLocal, DB_PATH
import models as m


def _migrar_base():
    """Aplica las migraciones de Alembic pendientes al iniciar. Así, al actualizar el código sobre una
    cantera.db que YA tiene datos cargados, el esquema se completa solo (por ejemplo la tabla de
    actividades cedidas) sin pisar nada. Si falla, la app arranca igual y lo informa en el log."""
    try:
        from alembic.config import Config
        from alembic import command
        base = Path(__file__).parent
        cfg = Config()  # sin archivo .ini: así Alembic no reconfigura el logging de uvicorn
        cfg.set_main_option("script_location", str(base / "alembic"))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")
        command.upgrade(cfg, "head")
    except Exception as e:  # noqa: BLE001
        print(f"[SGO] No se pudieron aplicar las migraciones al iniciar: {e}")


_migrar_base()

from routers import (plantas, puestos, personas, actividades, convenios, mecanismos, asignaciones, fichas,
                     dashboard, ui_personas, ui_puestos, ui_plantas, ui_dashboard, ui_listados,
                     ui_actividades, ui_mecanismos, ui_procedimientos, ui_indicadores, ui_historial, ui_reporte,
                     organigrama, ui_organigrama, formularios, ui_formularios, procedimientos, indicadores,
                     ui_reparto, ui_reportes)

app = FastAPI(title="SGO Cantera Eldorado v3 — por objetos")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

for r in (plantas.router, puestos.router, personas.router, actividades.router, convenios.router,
          mecanismos.router, asignaciones.router, fichas.router, dashboard.router,
          ui_personas.router, ui_puestos.router, ui_plantas.router, ui_dashboard.router, ui_listados.router,
          ui_actividades.router, ui_mecanismos.router, ui_procedimientos.router, ui_indicadores.router,
          ui_historial.router, ui_reporte.router, organigrama.router, ui_organigrama.router,
          formularios.router, ui_formularios.router, procedimientos.router, indicadores.router,
          ui_reparto.router, ui_reportes.router):
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
