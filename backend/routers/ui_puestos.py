from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import date
from database import get_db, log_historial, to_dict
from auth import verificar_acceso
from functions import calcular_dias_para_extincion, calcular_cobertura
from routers.ui_shared import asignar_o_reasignar
import models as m

router = APIRouter(prefix="/ui/puestos", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _form_ctx(db, puesto=None, error=None, valores=None):
    return {"puesto": puesto, "error": error, "valores": valores,
            "convenios": db.query(m.ConvenioColectivo).order_by(m.ConvenioColectivo.codigo).all()}


# el orden importa: '/nuevo' tiene que registrarse antes que '/{codigo}'
@router.get("/nuevo", response_class=HTMLResponse)
def nuevo_puesto_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "form_puesto.html", _form_ctx(db))


@router.post("", response_class=HTMLResponse)
def crear_puesto(request: Request, db: Session = Depends(get_db),
                  codigo: str = Form(...), nombre: str = Form(...), area: str = Form(...), nivel: str = Form(...),
                  cardinalidad_esperada: str = Form("unica_en_la_empresa"), proposito: str = Form(None),
                  limites_autoridad: str = Form(None), convenio_id: str = Form(None)):
    if db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first():
        return templates.TemplateResponse(request, "form_puesto.html", _form_ctx(db, error=f"Ya existe un puesto con el código {codigo}.",
            valores={"codigo": codigo, "nombre": nombre, "area": area, "nivel": nivel,
                     "cardinalidad_esperada": cardinalidad_esperada, "proposito": proposito,
                     "limites_autoridad": limites_autoridad, "convenio_id": convenio_id}))
    p = m.Puesto(codigo=codigo, nombre=nombre, area=area, nivel=nivel, cardinalidad_esperada=cardinalidad_esperada,
                 proposito=proposito, limites_autoridad=limites_autoridad, convenio_id=convenio_id or None)
    db.add(p)
    db.flush()
    log_historial(db, "puestos", p.id, "CrearPuesto", despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/puestos/{codigo}", status_code=303)


def _ctx(db: Session, codigo: str):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    relaciones = db.query(m.RelacionReporte).filter(m.RelacionReporte.puesto_codigo == codigo).all()
    actividades = db.query(m.Actividad).filter(m.Actividad.puesto_codigo == codigo, m.Actividad.activo == 1).all()
    ocupantes = calcular_cobertura(db, puesto_codigo=codigo)
    mecs = db.query(m.MecanismoPuesto).filter(m.MecanismoPuesto.puesto_codigo == codigo).all()
    rol_transicion = db.query(m.RolDeTransicion).filter(m.RolDeTransicion.puesto_id == p.id, m.RolDeTransicion.estado == "vigente").first()
    return {
        "puesto": p, "convenio": p.convenio,
        "reporta_a": [r.relacionado_codigo for r in relaciones if r.tipo == "jerarquico"],
        "coordina_con": [r.relacionado_codigo for r in relaciones if r.tipo == "funcional"],
        "actividades": actividades, "ocupantes": ocupantes,
        "mecanismos": [{"mecanismo_codigo": mp.mecanismo.codigo, "rol": mp.rol} for mp in mecs],
        "rol_transicion": ({**{k: v for k, v in vars(rol_transicion).items() if not k.startswith("_")},
                            "dias_para_extincion": calcular_dias_para_extincion(rol_transicion.fecha_estimada_extincion)}
                           if rol_transicion else None),
        "personas": db.query(m.Persona).filter(m.Persona.activo == 1).order_by(m.Persona.apellido).all(),
        "plantas": db.query(m.Planta).all(),
    }


@router.get("/{codigo}", response_class=HTMLResponse)
def ver_ficha(codigo: str, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "ficha_puesto.html", _ctx(db, codigo))


@router.get("/{codigo}/editar", response_class=HTMLResponse)
def editar_puesto_form(codigo: str, request: Request, db: Session = Depends(get_db)):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    return templates.TemplateResponse(request, "form_puesto.html", _form_ctx(db, puesto=p))


@router.post("/{codigo}/editar", response_class=HTMLResponse)
def editar_puesto(codigo: str, request: Request, db: Session = Depends(get_db),
                   nombre: str = Form(...), area: str = Form(...), nivel: str = Form(...),
                   cardinalidad_esperada: str = Form("unica_en_la_empresa"), proposito: str = Form(None),
                   limites_autoridad: str = Form(None), convenio_id: str = Form(None)):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    antes = to_dict(p)
    p.nombre, p.area, p.nivel = nombre, area, nivel
    p.cardinalidad_esperada, p.proposito, p.limites_autoridad = cardinalidad_esperada, proposito, limites_autoridad
    p.convenio_id = convenio_id or None
    log_historial(db, "puestos", p.id, "EditarPuesto", antes=antes, despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/puestos/{codigo}", status_code=303)


@router.post("/{codigo}/baja")
def dar_de_baja(codigo: str, db: Session = Depends(get_db)):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    antes = to_dict(p)
    p.vigente = 0
    log_historial(db, "puestos", p.id, "DarDeBajaPuesto", antes=antes, despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/puestos/{codigo}", status_code=303)


@router.post("/{codigo}/alta")
def dar_de_alta(codigo: str, db: Session = Depends(get_db)):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    antes = to_dict(p)
    p.vigente = 1
    log_historial(db, "puestos", p.id, "DarDeAltaPuesto", antes=antes, despues=to_dict(p))
    db.commit()
    return RedirectResponse(f"/ui/puestos/{codigo}", status_code=303)


@router.get("/{codigo}/pdf")
def exportar_pdf(codigo: str, db: Session = Depends(get_db)):
    from xhtml2pdf import pisa
    import io
    ctx = _ctx(db, codigo)
    ctx["fecha"] = date.today().strftime("%d/%m/%Y")
    html = templates.get_template("pdf_ficha_puesto.html").render(**ctx)
    buf = io.BytesIO()
    pisa.CreatePDF(html, dest=buf)
    return Response(content=buf.getvalue(), media_type="application/pdf",
                     headers={"Content-Disposition": f'inline; filename="Ficha_{codigo}.pdf"'})


@router.post("/{codigo}/asignar", response_class=HTMLResponse)
def asignar(codigo: str, request: Request, db: Session = Depends(get_db),
            planta_id: int = Form(...), etapa: str = Form(None), persona_id: int = Form(...),
            permitir_conflicto: bool = Form(False)):
    etapa = etapa if etapa and etapa != "None" else None
    ok, conflictos = asignar_o_reasignar(db, codigo, planta_id, etapa, persona_id, permitir_conflicto)
    if not ok:
        return templates.TemplateResponse(request, "_cobertura_conflicto.html", {
            "puesto_codigo": codigo, "planta_id": planta_id, "etapa": etapa, "persona_id": persona_id,
            "conflictos": conflictos, "accion_url": f"/ui/puestos/{codigo}/asignar"})
    fila = next((f for f in calcular_cobertura(db, puesto_codigo=codigo) if f["planta_id"] == planta_id and f["etapa"] == etapa), None)
    return templates.TemplateResponse(request, "_cobertura_fila.html", {
        "f": fila, "mostrar_puesto": False, "mostrar_planta": True, "accion_url": f"/ui/puestos/{codigo}/asignar",
        "personas": db.query(m.Persona).filter(m.Persona.activo == 1).order_by(m.Persona.apellido).all(),
        "plantas": db.query(m.Planta).all()})


@router.post("/{codigo}/extinguir-transicion", response_class=HTMLResponse)
def extinguir_transicion(codigo: str, request: Request, db: Session = Depends(get_db)):
    """Action Type: ExtinguirRolDeTransicion — cierra formalmente un rol
    transitorio (ej. TRS-01) una vez que se completó la condición de extinción."""
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    rol = db.query(m.RolDeTransicion).filter(m.RolDeTransicion.puesto_id == p.id, m.RolDeTransicion.estado == "vigente").first()
    if rol:
        antes = to_dict(rol)
        rol.estado = "extinguido"
        log_historial(db, "roles_transicion", rol.id, "ExtinguirRolDeTransicion", antes=antes)
        db.commit()
    return templates.TemplateResponse(request, "_rol_transicion_extinguido.html", {})
