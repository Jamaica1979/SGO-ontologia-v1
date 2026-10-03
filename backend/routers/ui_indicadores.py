from datetime import date
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db, log_historial, to_dict
from auth import verificar_acceso
from functions import calcular_semaforo, _umbral_parseable
import models as m

router = APIRouter(prefix="/ui/indicadores", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _periodo_actual():
    return date.today().strftime("%Y-%m")


def _form_ctx(db, indicador=None, error=None, valores=None):
    return {"indicador": indicador, "error": error, "valores": valores,
            "puestos": db.query(m.Puesto).filter(m.Puesto.vigente == 1).order_by(m.Puesto.codigo).all()}


# el orden importa: '/nuevo' tiene que registrarse antes que '/{codigo}'
@router.get("/nuevo", response_class=HTMLResponse)
def nuevo_indicador_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "form_indicador.html", _form_ctx(db))


@router.post("", response_class=HTMLResponse)
def crear_indicador(request: Request, db: Session = Depends(get_db),
                     codigo: str = Form(...), nombre: str = Form(...), area: str = Form(...),
                     formula: str = Form(None), frecuencia: str = Form(None), fuente_dato: str = Form(None),
                     responsable_carga_puesto_codigo: str = Form(None), responsable_uso_puesto_codigo: str = Form(None),
                     umbral_verde: str = Form(None), umbral_amarillo: str = Form(None), umbral_rojo: str = Form(None)):
    if db.query(m.Indicador).filter(m.Indicador.codigo == codigo).first():
        return templates.TemplateResponse(request, "form_indicador.html", _form_ctx(db,
            error=f"Ya existe un indicador con el código {codigo}.",
            valores={"codigo": codigo, "nombre": nombre, "area": area, "formula": formula, "frecuencia": frecuencia,
                     "fuente_dato": fuente_dato, "responsable_carga_puesto_codigo": responsable_carga_puesto_codigo,
                     "responsable_uso_puesto_codigo": responsable_uso_puesto_codigo, "umbral_verde": umbral_verde,
                     "umbral_amarillo": umbral_amarillo, "umbral_rojo": umbral_rojo}))
    i = m.Indicador(codigo=codigo, nombre=nombre, area=area, formula=formula, frecuencia=frecuencia,
                     fuente_dato=fuente_dato, responsable_carga_puesto_codigo=responsable_carga_puesto_codigo or None,
                     responsable_uso_puesto_codigo=responsable_uso_puesto_codigo or None,
                     umbral_verde=umbral_verde, umbral_amarillo=umbral_amarillo, umbral_rojo=umbral_rojo)
    db.add(i)
    db.flush()
    log_historial(db, "indicadores", i.id, "CrearIndicador", despues=to_dict(i))
    db.commit()
    return RedirectResponse(f"/ui/indicadores/{codigo}", status_code=303)


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


@router.get("/{codigo}/editar", response_class=HTMLResponse)
def editar_indicador_form(codigo: str, request: Request, db: Session = Depends(get_db)):
    ind = db.query(m.Indicador).filter(m.Indicador.codigo == codigo).first()
    return templates.TemplateResponse(request, "form_indicador.html", _form_ctx(db, indicador=ind))


@router.post("/{codigo}/editar", response_class=HTMLResponse)
def editar_indicador(codigo: str, request: Request, db: Session = Depends(get_db),
                      nombre: str = Form(...), area: str = Form(...), formula: str = Form(None),
                      frecuencia: str = Form(None), fuente_dato: str = Form(None),
                      responsable_carga_puesto_codigo: str = Form(None), responsable_uso_puesto_codigo: str = Form(None),
                      umbral_verde: str = Form(None), umbral_amarillo: str = Form(None), umbral_rojo: str = Form(None)):
    ind = db.query(m.Indicador).filter(m.Indicador.codigo == codigo).first()
    antes = to_dict(ind)
    ind.nombre, ind.area, ind.formula = nombre, area, formula
    ind.frecuencia, ind.fuente_dato = frecuencia, fuente_dato
    ind.responsable_carga_puesto_codigo = responsable_carga_puesto_codigo or None
    ind.responsable_uso_puesto_codigo = responsable_uso_puesto_codigo or None
    ind.umbral_verde, ind.umbral_amarillo, ind.umbral_rojo = umbral_verde, umbral_amarillo, umbral_rojo
    log_historial(db, "indicadores", ind.id, "EditarIndicador", antes=antes, despues=to_dict(ind))
    db.commit()
    return RedirectResponse(f"/ui/indicadores/{codigo}", status_code=303)


@router.post("/{codigo}/baja")
def dar_de_baja(codigo: str, db: Session = Depends(get_db)):
    ind = db.query(m.Indicador).filter(m.Indicador.codigo == codigo).first()
    antes = to_dict(ind)
    ind.activo = 0
    log_historial(db, "indicadores", ind.id, "DarDeBajaIndicador", antes=antes, despues=to_dict(ind))
    db.commit()
    return RedirectResponse(f"/ui/indicadores/{codigo}", status_code=303)


@router.post("/{codigo}/alta")
def dar_de_alta(codigo: str, db: Session = Depends(get_db)):
    ind = db.query(m.Indicador).filter(m.Indicador.codigo == codigo).first()
    antes = to_dict(ind)
    ind.activo = 1
    log_historial(db, "indicadores", ind.id, "DarDeAltaIndicador", antes=antes, despues=to_dict(ind))
    db.commit()
    return RedirectResponse(f"/ui/indicadores/{codigo}", status_code=303)


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
