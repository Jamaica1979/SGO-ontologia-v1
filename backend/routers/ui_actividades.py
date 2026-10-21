from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db, log_historial, to_dict
from auth import verificar_acceso
import models as m
from posiciones import MOMENTOS

router = APIRouter(prefix="/ui/actividades", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _form_ctx(db, actividad=None, error=None, valores=None):
    return {"actividad": actividad, "error": error, "valores": valores,
            "puestos": db.query(m.Puesto).filter(m.Puesto.vigente == 1).order_by(m.Puesto.codigo).all(),
            "funciones": db.query(m.FuncionOrganizacional).order_by(m.FuncionOrganizacional.codigo).all(),
            "posiciones": db.query(m.Posicion).filter(m.Posicion.activo == 1).order_by(m.Posicion.puesto_codigo, m.Posicion.orden).all(),
            "momentos": MOMENTOS}


def _validar_posicion(db, puesto_codigo, posicion):
    """La posición tiene que ser del mismo puesto. Devuelve (posicion_normalizada, error)."""
    if not posicion:
        return None, None
    ok = db.query(m.Posicion).filter(m.Posicion.puesto_codigo == puesto_codigo, m.Posicion.clave == posicion).first()
    if not ok:
        return None, f"La posición elegida no pertenece al puesto {puesto_codigo or '(sin puesto)'}."
    return posicion, None


def _int(v):
    try:
        return int(v) if v not in (None, "") else None
    except ValueError:
        return None


# el orden importa: '/nuevo' tiene que registrarse antes que '/{codigo}'
@router.get("/nuevo", response_class=HTMLResponse)
def nueva_actividad_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "form_actividad.html", _form_ctx(db))


@router.post("", response_class=HTMLResponse)
def crear_actividad(request: Request, db: Session = Depends(get_db),
                     codigo: str = Form(...), descripcion: str = Form(...), area: str = Form(...), nivel: str = Form(...),
                     competencia: str = Form(None), es_critica: bool = Form(False), frecuencia: str = Form(None),
                     notas: str = Form(None), puesto_codigo: str = Form(None), funcion_organizacional_id: str = Form(None),
                     posicion: str = Form(None), momento: str = Form(None), orden: str = Form(None)):
    pos, err = _validar_posicion(db, puesto_codigo, posicion)
    if db.query(m.Actividad).filter(m.Actividad.codigo == codigo).first() or err:
        return templates.TemplateResponse(request, "form_actividad.html", _form_ctx(db,
            error=err or f"Ya existe una actividad con el código {codigo}.",
            valores={"codigo": codigo, "descripcion": descripcion, "area": area, "nivel": nivel,
                     "competencia": competencia, "es_critica": es_critica, "frecuencia": frecuencia,
                     "notas": notas, "puesto_codigo": puesto_codigo, "funcion_organizacional_id": funcion_organizacional_id,
                     "posicion": posicion, "momento": momento, "orden": orden}))
    a = m.Actividad(codigo=codigo, descripcion=descripcion, area=area, nivel=nivel, competencia=competencia,
                     es_critica=1 if es_critica else 0, frecuencia=frecuencia, notas=notas,
                     puesto_codigo=puesto_codigo or None, funcion_organizacional_id=funcion_organizacional_id or None,
                     posicion=pos, momento=momento or None, orden=_int(orden))
    db.add(a)
    db.flush()
    log_historial(db, "actividades", a.id, "CrearActividad", despues=to_dict(a))
    db.commit()
    return RedirectResponse(f"/ui/actividades/{codigo}", status_code=303)


@router.get("/{codigo}", response_class=HTMLResponse)
def ver_ficha(codigo: str, request: Request, db: Session = Depends(get_db)):
    a = db.query(m.Actividad).filter(m.Actividad.codigo == codigo).first()
    puesto = db.query(m.Puesto).filter(m.Puesto.codigo == a.puesto_codigo).first() if a.puesto_codigo else None

    responsables = []
    activas = db.query(m.Asignacion).filter(m.Asignacion.estado.in_(["activa", "transicion"])).all()
    cedidas = set((r.asignacion_id, r.actividad_id) for r in db.query(m.ActividadCedida))
    for asig in activas:
        cubre = False
        if asig.puesto_codigo == a.puesto_codigo and a.puesto_codigo:
            cubre = (asig.id, a.id) not in cedidas   # si el titular la cedió, no la lleva él
        elif asig.perfil_id:
            if db.query(m.PerfilActividad).filter(m.PerfilActividad.perfil_id == asig.perfil_id, m.PerfilActividad.actividad_id == a.id).first():
                cubre = True
        if cubre:
            responsables.append({"persona_id": asig.persona_id, "persona": f"{asig.persona.nombre} {asig.persona.apellido}",
                                  "planta": asig.planta.nombre, "via": "perfil" if asig.perfil_id else "puesto"})

    caps = [db.query(m.TipoDeCapacitacion).get(r.tipo_capacitacion_id).nombre
            for r in db.query(m.ActividadCapacitacion).filter(m.ActividadCapacitacion.actividad_id == a.id)]

    return templates.TemplateResponse(request, "ficha_actividad.html", {
        "actividad": a, "puesto_nombre": puesto.nombre if puesto else None,
        "responsables": responsables, "capacitaciones": caps,
        "aplicabilidad": __import__("aplicabilidad").filas_aplicabilidad(db, actividad_id=a.id),
    })


@router.get("/{codigo}/editar", response_class=HTMLResponse)
def editar_actividad_form(codigo: str, request: Request, db: Session = Depends(get_db)):
    a = db.query(m.Actividad).filter(m.Actividad.codigo == codigo).first()
    return templates.TemplateResponse(request, "form_actividad.html", _form_ctx(db, actividad=a))


@router.post("/{codigo}/editar", response_class=HTMLResponse)
def editar_actividad(codigo: str, request: Request, db: Session = Depends(get_db),
                      descripcion: str = Form(...), area: str = Form(...), nivel: str = Form(...),
                      competencia: str = Form(None), es_critica: bool = Form(False), frecuencia: str = Form(None),
                      notas: str = Form(None), puesto_codigo: str = Form(None), funcion_organizacional_id: str = Form(None),
                      posicion: str = Form(None), momento: str = Form(None), orden: str = Form(None)):
    a = db.query(m.Actividad).filter(m.Actividad.codigo == codigo).first()
    pos, err = _validar_posicion(db, puesto_codigo, posicion)
    if err:
        return templates.TemplateResponse(request, "form_actividad.html", _form_ctx(db, actividad=a, error=err))
    antes = to_dict(a)
    a.descripcion, a.area, a.nivel = descripcion, area, nivel
    a.competencia, a.es_critica, a.frecuencia = competencia, 1 if es_critica else 0, frecuencia
    a.notas = notas
    a.puesto_codigo = puesto_codigo or None
    a.funcion_organizacional_id = funcion_organizacional_id or None
    a.posicion, a.momento, a.orden = pos, momento or None, _int(orden)
    log_historial(db, "actividades", a.id, "EditarActividad", antes=antes, despues=to_dict(a))
    db.commit()
    return RedirectResponse(f"/ui/actividades/{codigo}", status_code=303)


@router.post("/{codigo}/baja")
def dar_de_baja(codigo: str, db: Session = Depends(get_db)):
    a = db.query(m.Actividad).filter(m.Actividad.codigo == codigo).first()
    antes = to_dict(a)
    a.activo = 0
    log_historial(db, "actividades", a.id, "DarDeBajaActividad", antes=antes, despues=to_dict(a))
    db.commit()
    return RedirectResponse(f"/ui/actividades/{codigo}", status_code=303)


@router.post("/{codigo}/alta")
def dar_de_alta(codigo: str, db: Session = Depends(get_db)):
    a = db.query(m.Actividad).filter(m.Actividad.codigo == codigo).first()
    antes = to_dict(a)
    a.activo = 1
    log_historial(db, "actividades", a.id, "DarDeAltaActividad", antes=antes, despues=to_dict(a))
    db.commit()
    return RedirectResponse(f"/ui/actividades/{codigo}", status_code=303)
