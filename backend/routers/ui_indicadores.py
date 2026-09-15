from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db, log_historial
from auth import verificar_acceso
from functions import calcular_semaforo, _umbral_parseable
import models as m

router = APIRouter(prefix="/ui/indicadores", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _ctx(db: Session, codigo: str):
    ind = db.query(m.Indicador).filter(m.Indicador.codigo == codigo).first()
    meds = db.query(m.MedicionDeIndicador).filter(m.MedicionDeIndicador.indicador_id == ind.id).order_by(m.MedicionDeIndicador.periodo.desc()).all()
    mediciones = [{"periodo": med.periodo, "valor": med.valor,
                   "semaforo": calcular_semaforo(med.valor, ind.umbral_verde, ind.umbral_amarillo, ind.umbral_rojo)}
                  for med in meds]
    es_cualitativo = not (_umbral_parseable(ind.umbral_verde) and _umbral_parseable(ind.umbral_amarillo) and _umbral_parseable(ind.umbral_rojo))
    return {"indicador": ind, "mediciones": mediciones, "es_cualitativo": es_cualitativo}


@router.get("/{codigo}", response_class=HTMLResponse)
def ver_ficha(codigo: str, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "ficha_indicador.html", _ctx(db, codigo))


@router.post("/{codigo}/medicion", response_class=HTMLResponse)
def cargar_medicion(codigo: str, request: Request, db: Session = Depends(get_db),
                     periodo: str = Form(...), valor: str = Form(...)):
    ind = db.query(m.Indicador).filter(m.Indicador.codigo == codigo).first()
    if not ind:
        raise HTTPException(404, "Indicador no encontrado")
    existente = db.query(m.MedicionDeIndicador).filter(m.MedicionDeIndicador.indicador_id == ind.id,
                                                         m.MedicionDeIndicador.periodo == periodo).first()
    if existente:
        existente.valor = valor
        log_historial(db, "mediciones_indicador", existente.id, "CargarMedicionDeIndicador", despues={"valor": valor, "periodo": periodo})
    else:
        nueva = m.MedicionDeIndicador(indicador_id=ind.id, periodo=periodo, valor=valor)
        db.add(nueva)
        db.flush()
        log_historial(db, "mediciones_indicador", nueva.id, "CargarMedicionDeIndicador", despues={"valor": valor, "periodo": periodo})
    db.commit()
    return templates.TemplateResponse(request, "_indicador_mediciones.html", _ctx(db, codigo))
