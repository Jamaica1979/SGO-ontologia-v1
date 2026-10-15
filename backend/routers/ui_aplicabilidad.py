"""Marcar qué puestos y actividades NO aplican en una planta (v3.7). Un solo endpoint
que usan las fichas de Puesto y de Actividad."""
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from auth import verificar_acceso
from aplicabilidad import guardar_aplicabilidad
import models as m

router = APIRouter(prefix="/ui/aplicabilidad", dependencies=[Depends(verificar_acceso)])


@router.post("/guardar")
def guardar(db: Session = Depends(get_db), planta_id: int = Form(...), modo: str = Form(...), motivo: str = Form(""),
            puesto_codigo: str = Form(""), actividad_id: str = Form(""), volver: str = Form("/ui/dashboard")):
    if modo not in ("aplica", "se_reparte", "no_aplica"):
        raise HTTPException(400, "Modo inválido")
    if bool(puesto_codigo) == bool(actividad_id):
        raise HTTPException(400, "Indicá un puesto O una actividad")
    if not db.query(m.Planta).get(planta_id):
        raise HTTPException(404, "Planta no encontrada")
    guardar_aplicabilidad(db, planta_id, modo, motivo.strip() or None, puesto_codigo or None,
                          int(actividad_id) if actividad_id else None)
    db.commit()
    if not volver.startswith("/ui/"):
        volver = "/ui/dashboard"
    return RedirectResponse(volver, status_code=303)
