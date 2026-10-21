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
from util_texto import personas_ordenadas
from ficha_puesto import armar_ficha
from posiciones import posiciones_de, invalidar_cache
import re
import unicodedata

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
                  limites_autoridad: str = Form(None), convenio_id: str = Form(None),
                  dotacion: str = Form(None), reemplaza_a: str = Form(None),
                  alcance_inicio: str = Form(None), alcance_fin: str = Form(None), equipos: str = Form(None),
                  medicion_desempeno: str = Form(None), notas_ficha: str = Form(None)):
    if db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first():
        return templates.TemplateResponse(request, "form_puesto.html", _form_ctx(db, error=f"Ya existe un puesto con el código {codigo}.",
            valores={"codigo": codigo, "nombre": nombre, "area": area, "nivel": nivel,
                     "cardinalidad_esperada": cardinalidad_esperada, "proposito": proposito,
                     "limites_autoridad": limites_autoridad, "convenio_id": convenio_id}))
    p = m.Puesto(codigo=codigo, nombre=nombre, area=area, nivel=nivel, cardinalidad_esperada=cardinalidad_esperada,
                 proposito=proposito, limites_autoridad=limites_autoridad, convenio_id=convenio_id or None,
                 dotacion=dotacion, reemplaza_a=reemplaza_a, alcance_inicio=alcance_inicio, alcance_fin=alcance_fin,
                 equipos=equipos, medicion_desempeno=medicion_desempeno, notas_ficha=notas_ficha)
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
        "personas": personas_ordenadas(db.query(m.Persona).filter(m.Persona.activo == 1)),
        "plantas": db.query(m.Planta).all(),
        "aplicabilidad": __import__("aplicabilidad").filas_aplicabilidad(db, puesto_codigo=codigo),
        "ficha": armar_ficha(db, codigo),
        "posiciones_todas": posiciones_de(db, codigo, incluir_inactivas=True),
        "formularios_disp": db.query(m.Formulario).order_by(m.Formulario.codigo).all(),
        "procedimientos_disp": db.query(m.Procedimiento).filter(m.Procedimiento.vigente == 1).order_by(m.Procedimiento.codigo).all(),
        "puestos_disp": db.query(m.Puesto).filter(m.Puesto.vigente == 1).order_by(m.Puesto.codigo).all(),
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
                   limites_autoridad: str = Form(None), convenio_id: str = Form(None),
                   dotacion: str = Form(None), reemplaza_a: str = Form(None),
                  alcance_inicio: str = Form(None), alcance_fin: str = Form(None), equipos: str = Form(None),
                  medicion_desempeno: str = Form(None), notas_ficha: str = Form(None)):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    antes = to_dict(p)
    p.nombre, p.area, p.nivel = nombre, area, nivel
    p.cardinalidad_esperada, p.proposito, p.limites_autoridad = cardinalidad_esperada, proposito, limites_autoridad
    p.convenio_id = convenio_id or None
    p.dotacion, p.reemplaza_a = dotacion, reemplaza_a
    p.alcance_inicio, p.alcance_fin, p.equipos = alcance_inicio, alcance_fin, equipos
    p.medicion_desempeno, p.notas_ficha = medicion_desempeno, notas_ficha
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
            permitir_conflicto: bool = Form(False), sumar: bool = Form(False)):
    from posiciones import normalizar
    etapa = normalizar(etapa)
    ok, conflictos = asignar_o_reasignar(db, codigo, planta_id, etapa, persona_id, permitir_conflicto, sumar)
    if not ok:
        return templates.TemplateResponse(request, "_cobertura_conflicto.html", {
            "puesto_codigo": codigo, "planta_id": planta_id, "etapa": etapa, "persona_id": persona_id, "sumar": sumar,
            "conflictos": conflictos, "accion_url": f"/ui/puestos/{codigo}/asignar"})
    fila = next((f for f in calcular_cobertura(db, puesto_codigo=codigo) if f["planta_id"] == planta_id and f["etapa"] == etapa), None)
    return templates.TemplateResponse(request, "_cobertura_fila.html", {
        "f": fila, "mostrar_puesto": False, "mostrar_planta": True, "accion_url": f"/ui/puestos/{codigo}/asignar",
        "personas": personas_ordenadas(db.query(m.Persona).filter(m.Persona.activo == 1)),
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


# ───────────────────────── v3.9: posiciones del puesto ─────────────────────────

def _slug(texto):
    s = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s.split("_y_")[0][:30] or "posicion"


def _volver(codigo, ancla="posiciones"):
    return RedirectResponse(f"/ui/puestos/{codigo}#{ancla}", status_code=303)


@router.get("/{codigo}/posiciones/nueva", response_class=HTMLResponse)
def posicion_nueva_form(codigo: str, request: Request, db: Session = Depends(get_db)):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    return templates.TemplateResponse(request, "form_posicion.html", {"puesto": p, "posicion": None})


@router.post("/{codigo}/posiciones/nueva", response_class=HTMLResponse)
def posicion_crear(codigo: str, request: Request, db: Session = Depends(get_db),
                   nombre: str = Form(...), orden: int = Form(0), descripcion: str = Form(None),
                   alcance_inicio: str = Form(None), alcance_fin: str = Form(None), equipos: str = Form(None)):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    clave, n = _slug(nombre), 2
    base = clave
    while db.query(m.Posicion).filter(m.Posicion.puesto_codigo == codigo, m.Posicion.clave == clave).first():
        clave, n = f"{base}_{n}", n + 1
    x = m.Posicion(puesto_codigo=codigo, clave=clave, nombre=nombre.strip(), orden=orden, descripcion=descripcion,
                   alcance_inicio=alcance_inicio, alcance_fin=alcance_fin, equipos=equipos)
    db.add(x)
    db.flush()
    log_historial(db, "posiciones", x.id, "CrearPosicion", despues=to_dict(x))
    db.commit()
    invalidar_cache()
    return _volver(p.codigo)


@router.get("/{codigo}/posiciones/{pid}/editar", response_class=HTMLResponse)
def posicion_editar_form(codigo: str, pid: int, request: Request, db: Session = Depends(get_db)):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()
    return templates.TemplateResponse(request, "form_posicion.html", {"puesto": p, "posicion": db.query(m.Posicion).get(pid)})


@router.post("/{codigo}/posiciones/{pid}/editar", response_class=HTMLResponse)
def posicion_editar(codigo: str, pid: int, db: Session = Depends(get_db),
                    nombre: str = Form(...), orden: int = Form(0), descripcion: str = Form(None),
                    alcance_inicio: str = Form(None), alcance_fin: str = Form(None), equipos: str = Form(None)):
    x = db.query(m.Posicion).get(pid)
    antes = to_dict(x)
    x.nombre, x.orden, x.descripcion = nombre.strip(), orden, descripcion
    x.alcance_inicio, x.alcance_fin, x.equipos = alcance_inicio, alcance_fin, equipos
    log_historial(db, "posiciones", x.id, "EditarPosicion", antes=antes, despues=to_dict(x))
    db.commit()
    invalidar_cache()
    return _volver(codigo)


@router.post("/{codigo}/posiciones/{pid}/baja", response_class=HTMLResponse)
def posicion_baja(codigo: str, pid: int, request: Request, db: Session = Depends(get_db)):
    x = db.query(m.Posicion).get(pid)
    en_uso = db.query(m.Asignacion).filter(m.Asignacion.puesto_codigo == codigo, m.Asignacion.etapa == x.clave,
                                           m.Asignacion.estado.in_(["activa", "transicion"])).count()
    if en_uso:
        return HTMLResponse(f"<p class='error'>No se puede dar de baja la posición {x.nombre}: tiene {en_uso} asignación(es) activa(s). "
                            f"Finalizalas o reasignalas primero. <a href='/ui/puestos/{codigo}'>Volver</a></p>", status_code=400)
    x.activo = 0
    log_historial(db, "posiciones", x.id, "DarDeBajaPosicion")
    db.commit()
    invalidar_cache()
    return _volver(codigo)


@router.post("/{codigo}/posiciones/{pid}/alta", response_class=HTMLResponse)
def posicion_alta(codigo: str, pid: int, db: Session = Depends(get_db)):
    x = db.query(m.Posicion).get(pid)
    x.activo = 1
    log_historial(db, "posiciones", x.id, "DarDeAltaPosicion")
    db.commit()
    invalidar_cache()
    return _volver(codigo)


# ───────────────────────── v3.9: formularios y procedimientos del puesto ─────────────────────────

@router.post("/{codigo}/formularios", response_class=HTMLResponse)
def vincular_formulario(codigo: str, db: Session = Depends(get_db), formulario_id: int = Form(...),
                        rol: str = Form("completa"), para_que: str = Form(None), cuando: str = Form(None),
                        orden: int = Form(0)):
    if rol not in ("completa", "recibe", "consolida"):
        rol = "completa"
    ya = db.query(m.PuestoFormulario).filter(m.PuestoFormulario.puesto_codigo == codigo, m.PuestoFormulario.formulario_id == formulario_id,
                                             m.PuestoFormulario.rol == rol).first()
    if ya:
        ya.para_que, ya.cuando, ya.orden = para_que, cuando, orden
        log_historial(db, "puesto_formularios", ya.id, "EditarFormularioDePuesto", despues=to_dict(ya))
    else:
        x = m.PuestoFormulario(puesto_codigo=codigo, formulario_id=formulario_id, rol=rol, para_que=para_que, cuando=cuando, orden=orden)
        db.add(x)
        db.flush()
        log_historial(db, "puesto_formularios", x.id, "VincularFormularioAPuesto", despues=to_dict(x))
    db.commit()
    return _volver(codigo, "formularios")


@router.post("/{codigo}/formularios/{vid}/quitar", response_class=HTMLResponse)
def desvincular_formulario(codigo: str, vid: int, db: Session = Depends(get_db)):
    x = db.query(m.PuestoFormulario).get(vid)
    if x and x.puesto_codigo == codigo:
        log_historial(db, "puesto_formularios", x.id, "DesvincularFormularioDePuesto", antes=to_dict(x))
        db.delete(x)   # es un vínculo (Link Type), no un objeto de negocio: queda en el Historial
        db.commit()
    return _volver(codigo, "formularios")


@router.post("/{codigo}/procedimientos", response_class=HTMLResponse)
def vincular_procedimiento(codigo: str, db: Session = Depends(get_db), procedimiento_id: int = Form(...),
                           rol: str = Form("ejecuta")):
    if rol not in ("ejecuta", "aprueba", "recibe"):
        rol = "ejecuta"
    x = db.query(m.ProcedimientoPuesto).get((procedimiento_id, codigo))
    if x:
        x.rol = rol
    else:
        db.add(m.ProcedimientoPuesto(procedimiento_id=procedimiento_id, puesto_codigo=codigo, rol=rol))
    log_historial(db, "procedimiento_puestos", procedimiento_id, "VincularProcedimientoAPuesto",
                  despues={"puesto_codigo": codigo, "rol": rol})
    db.commit()
    return _volver(codigo, "procedimientos")


@router.post("/{codigo}/procedimientos/{proc_id}/quitar", response_class=HTMLResponse)
def desvincular_procedimiento(codigo: str, proc_id: int, db: Session = Depends(get_db)):
    x = db.query(m.ProcedimientoPuesto).get((proc_id, codigo))
    if x:
        log_historial(db, "procedimiento_puestos", proc_id, "DesvincularProcedimientoDePuesto",
                      antes={"puesto_codigo": codigo, "rol": x.rol})
        db.delete(x)
        db.commit()
    return _volver(codigo, "procedimientos")


# ───────────────────────── v3.9: traspasos (quién entrega qué a quién) ─────────────────────────

def _txt(v):
    return (v or "").strip() or None


@router.get("/{codigo}/traspasos/nuevo", response_class=HTMLResponse)
def traspaso_nuevo_form(codigo: str, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "form_traspaso.html", {
        "puesto": db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first(), "traspaso": None,
        "puestos": db.query(m.Puesto).filter(m.Puesto.vigente == 1).order_by(m.Puesto.codigo).all()})


@router.get("/{codigo}/traspasos/{tid}/editar", response_class=HTMLResponse)
def traspaso_editar_form(codigo: str, tid: int, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "form_traspaso.html", {
        "puesto": db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first(), "traspaso": db.query(m.Traspaso).get(tid),
        "puestos": db.query(m.Puesto).filter(m.Puesto.vigente == 1).order_by(m.Puesto.codigo).all()})


@router.post("/{codigo}/traspasos", response_class=HTMLResponse)
def traspaso_guardar(codigo: str, request: Request, db: Session = Depends(get_db), tid: str = Form(None),
                     de_puesto_codigo: str = Form(None), de_texto: str = Form(None),
                     a_puesto_codigo: str = Form(None), a_texto: str = Form(None),
                     que_entrega: str = Form(...), senal: str = Form(None), orden: int = Form(0)):
    de_p, a_p = _txt(de_puesto_codigo), _txt(a_puesto_codigo)
    if not (de_p or _txt(de_texto)) or not (a_p or _txt(a_texto)):
        return HTMLResponse("<p class='error'>Falta indicar quién entrega y quién recibe (un puesto o un texto).</p>", status_code=400)
    if codigo not in (de_p, a_p):
        return HTMLResponse(f"<p class='error'>El traspaso tiene que involucrar a {codigo} como emisor o receptor.</p>", status_code=400)
    x = db.query(m.Traspaso).get(int(tid)) if tid else None
    antes = to_dict(x) if x else None
    if not x:
        x = m.Traspaso()
        db.add(x)
    x.de_puesto_codigo, x.de_texto, x.a_puesto_codigo, x.a_texto = de_p, _txt(de_texto), a_p, _txt(a_texto)
    x.que_entrega, x.senal, x.orden = que_entrega.strip(), _txt(senal), orden
    db.flush()
    log_historial(db, "traspasos", x.id, "EditarTraspaso" if antes else "CrearTraspaso", antes=antes, despues=to_dict(x))
    db.commit()
    return _volver(codigo, "traspasos")


@router.post("/{codigo}/traspasos/{tid}/quitar", response_class=HTMLResponse)
def traspaso_quitar(codigo: str, tid: int, db: Session = Depends(get_db)):
    x = db.query(m.Traspaso).get(tid)
    if x:
        log_historial(db, "traspasos", x.id, "QuitarTraspaso", antes=to_dict(x))
        db.delete(x)   # vínculo entre puestos, no objeto de negocio: queda en el Historial
        db.commit()
    return _volver(codigo, "traspasos")
