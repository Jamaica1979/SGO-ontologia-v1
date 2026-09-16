from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from auth import verificar_acceso
from functions import construir_arbol_organizacional
import models as m

router = APIRouter(prefix="/api/organigrama", tags=["Organigrama"], dependencies=[Depends(verificar_acceso)])


@router.get("")
def organigrama(modo: str = "teorico", planta_id: int = None, db: Session = Depends(get_db)):
    return construir_arbol_organizacional(db, modo=modo, planta_id=planta_id)
