from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/ui/historial", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("", response_class=HTMLResponse)
def ver(request: Request, tabla: str = None, db: Session = Depends(get_db)):
    q = db.query(m.Historial).order_by(m.Historial.id.desc())
    if tabla:
        q = q.filter(m.Historial.tabla == tabla)
    eventos = q.limit(200).all()
    tablas = [r[0] for r in db.query(m.Historial.tabla).distinct()]
    return templates.TemplateResponse(request, "historial.html", {
        "eventos": eventos, "tablas": tablas, "tabla_filtro": tabla})
