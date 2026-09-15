from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db
from auth import verificar_acceso
import models as m

router = APIRouter(prefix="/ui/procedimientos", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("/{codigo}", response_class=HTMLResponse)
def ver_ficha(codigo: str, request: Request, db: Session = Depends(get_db)):
    proc = db.query(m.Procedimiento).filter(m.Procedimiento.codigo == codigo).first()
    pasos = db.query(m.PasoDeProcedimiento).filter(m.PasoDeProcedimiento.procedimiento_id == proc.id).order_by(m.PasoDeProcedimiento.numero).all()
    puestos = [r[0] for r in db.query(m.ProcedimientoPuesto.puesto_codigo).filter(m.ProcedimientoPuesto.procedimiento_id == proc.id)]
    return templates.TemplateResponse(request, "ficha_procedimiento.html", {
        "procedimiento": proc, "pasos": pasos, "puestos": puestos})
