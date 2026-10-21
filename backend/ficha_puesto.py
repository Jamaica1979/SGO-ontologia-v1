"""
Ficha de puesto (v3.9) — arma, en un solo lugar, todo lo que le incumbe a quien
ocupa un puesto, en el orden de las fichas de producción:

  identificación · misión · dónde empieza y termina · equipos · tareas por momento
  de la jornada (y por posición) · procedimientos con sus pasos · formularios que
  completa · límites · cómo se mide · mecanismos · indicadores · traspasos.

La usan la ficha de Puesto en pantalla, el PDF del puesto y el PDF por persona.
Para una persona se pasa la posición que ocupa y el conjunto de actividades que
efectivamente lleva (sin las cedidas): así cada uno imprime sólo lo suyo.
"""
from sqlalchemy.orm import Session
import models as m
from posiciones import MOMENTOS, aplica, posiciones_de

ORDEN_MOMENTO = {k: i for i, (k, _) in enumerate(MOMENTOS)}


def lineas(texto):
    """Texto multilínea → lista de renglones (sin viñetas ni vacíos)."""
    if not texto:
        return []
    out = []
    for r in str(texto).splitlines():
        r = r.strip()
        if r.startswith(("- ", "• ", "* ")):
            r = r[2:].strip()
        if r:
            out.append(r)
    return out


def _act(a):
    return {"id": a.id, "codigo": a.codigo, "descripcion": a.descripcion, "es_critica": bool(a.es_critica),
            "frecuencia": a.frecuencia, "posicion": a.posicion, "momento": a.momento, "orden": a.orden}


def _clave_orden(a):
    return (ORDEN_MOMENTO.get(a.momento, 9), a.orden if a.orden is not None else 999, a.codigo)


def agrupar_por_momento(acts):
    """[(titulo_momento | None, [act...])] respetando el orden de la jornada. Si ninguna
    actividad tiene momento, devuelve un solo grupo sin título."""
    acts = sorted(acts, key=_clave_orden)
    if not any(a.momento for a in acts):
        return [(None, [_act(a) for a in acts])] if acts else []
    grupos = []
    for clave, titulo in MOMENTOS + [(None, "Otras tareas")]:
        g = [_act(a) for a in acts if (a.momento if a.momento in ORDEN_MOMENTO else None) == clave]
        if g:
            grupos.append((titulo, g))
    return grupos


def _etiqueta_puesto(db, cod):
    p = db.query(m.Puesto).filter(m.Puesto.codigo == cod).first()
    return {"codigo": cod, "nombre": p.nombre if p else cod}


def armar_ficha(db: Session, puesto_codigo: str, posicion: str = None, actividad_ids=None, planta_id=None):
    """posicion: clave de la posición que ocupa la persona (None = puesto completo).
    actividad_ids: si se pasa, sólo esas actividades del puesto (las que la persona lleva).
    planta_id: si se pasa, se omiten las actividades que no aplican en esa planta."""
    p = db.query(m.Puesto).filter(m.Puesto.codigo == puesto_codigo).first()
    if not p:
        return None
    posiciones = posiciones_de(db, puesto_codigo)
    pos_obj = next((x for x in posiciones if x.clave == posicion), None) if posicion else None

    rel = db.query(m.RelacionReporte).filter(m.RelacionReporte.puesto_codigo == puesto_codigo).all()
    supervisa = db.query(m.RelacionReporte).filter(m.RelacionReporte.relacionado_codigo == puesto_codigo,
                                                   m.RelacionReporte.tipo == "jerarquico").all()

    # ── actividades ──
    acts = db.query(m.Actividad).filter(m.Actividad.puesto_codigo == puesto_codigo, m.Actividad.activo == 1).all()
    if planta_id is not None:
        from aplicabilidad import excluidas_en_planta
        excl = excluidas_en_planta(db, planta_id)
        acts = [a for a in acts if a.id not in excl]
    if actividad_ids is not None:
        acts = [a for a in acts if a.id in actividad_ids]
    if posicion:
        acts = [a for a in acts if aplica(a.posicion, posicion)]

    bloques_tareas = []   # [{"titulo": str|None, "grupos": [(momento, [acts])]}]
    if posiciones:
        comunes = [a for a in acts if not a.posicion]
        if comunes:
            bloques_tareas.append({"titulo": "Tareas de todas las posiciones" if not posicion else "Tareas comunes del puesto",
                                   "grupos": agrupar_por_momento(comunes)})
        for x in posiciones:
            if posicion and x.clave != posicion:
                continue
            propias = [a for a in acts if a.posicion == x.clave]
            if propias:
                bloques_tareas.append({"titulo": f"Tareas propias de la posición {x.nombre}",
                                       "grupos": agrupar_por_momento(propias)})
        huerfanas = [a for a in acts if a.posicion and a.posicion not in {x.clave for x in posiciones}]
        if huerfanas:
            bloques_tareas.append({"titulo": "Otras tareas", "grupos": agrupar_por_momento(huerfanas)})
    elif acts:
        bloques_tareas.append({"titulo": None, "grupos": agrupar_por_momento(acts)})

    # ── procedimientos: vinculados al puesto o donde algún paso es suyo ──
    proc_ids = {r.procedimiento_id: r.rol for r in db.query(m.ProcedimientoPuesto).filter(m.ProcedimientoPuesto.puesto_codigo == puesto_codigo)}
    for r in db.query(m.PasoDeProcedimiento.procedimiento_id).filter(m.PasoDeProcedimiento.responsable_puesto_codigo == puesto_codigo):
        proc_ids.setdefault(r[0], "ejecuta")
    procedimientos = []
    if proc_ids:
        for pr in db.query(m.Procedimiento).filter(m.Procedimiento.id.in_(proc_ids.keys()), m.Procedimiento.vigente == 1).order_by(m.Procedimiento.codigo):
            pasos = db.query(m.PasoDeProcedimiento).filter(m.PasoDeProcedimiento.procedimiento_id == pr.id).order_by(m.PasoDeProcedimiento.numero).all()
            procedimientos.append({
                "codigo": pr.codigo, "nombre": pr.nombre, "descripcion": pr.descripcion, "rol": proc_ids[pr.id],
                "pasos": [{"numero": s.numero, "titulo": s.titulo, "descripcion": s.descripcion,
                           "responsable": s.responsable_puesto_codigo or s.responsable_texto_original,
                           "es_suyo": s.responsable_puesto_codigo == puesto_codigo or
                                      (s.responsable_texto_original and puesto_codigo in (s.responsable_texto_original or ""))}
                          for s in pasos],
            })

    # ── formularios del puesto ──
    formularios = []
    for pf in db.query(m.PuestoFormulario).filter(m.PuestoFormulario.puesto_codigo == puesto_codigo).order_by(m.PuestoFormulario.orden, m.PuestoFormulario.id):
        f = pf.formulario
        padre = db.query(m.Formulario).get(f.formulario_padre_id) if f.formulario_padre_id else None
        formularios.append({"id": pf.id, "formulario_id": f.id, "codigo": f.codigo, "nombre": f.nombre, "rol": pf.rol,
                            "para_que": pf.para_que, "cuando": pf.cuando, "padre": padre.codigo if padre else None})

    # ── mecanismos e indicadores ──
    mecanismos = [{"codigo": mp.mecanismo.codigo, "nombre": mp.mecanismo.nombre, "rol": mp.rol,
                   "frecuencia": mp.mecanismo.frecuencia, "descripcion": mp.mecanismo.descripcion}
                  for mp in db.query(m.MecanismoPuesto).filter(m.MecanismoPuesto.puesto_codigo == puesto_codigo)
                  if mp.mecanismo.vigente]
    mecanismos.sort(key=lambda x: x["codigo"])
    indicadores = []
    for i in db.query(m.Indicador).filter(m.Indicador.activo == 1,
                                          (m.Indicador.responsable_carga_puesto_codigo == puesto_codigo) |
                                          (m.Indicador.responsable_uso_puesto_codigo == puesto_codigo)).order_by(m.Indicador.codigo):
        roles = []
        if i.responsable_carga_puesto_codigo == puesto_codigo:
            roles.append("lo carga")
        if i.responsable_uso_puesto_codigo == puesto_codigo:
            roles.append("lo usa")
        indicadores.append({"codigo": i.codigo, "nombre": i.nombre, "formula": i.formula,
                            "frecuencia": i.frecuencia, "rol": " y ".join(roles)})

    # ── traspasos ──
    nombres = {x.codigo: x.nombre for x in db.query(m.Puesto)}

    def _extremo(texto, codigo):
        if texto:
            return texto
        return f"{codigo} {nombres.get(codigo, '')}".strip() if codigo else "—"

    def _tr(t):
        return {"id": t.id, "de": _extremo(t.de_texto, t.de_puesto_codigo), "de_codigo": t.de_puesto_codigo,
                "a": _extremo(t.a_texto, t.a_puesto_codigo), "a_codigo": t.a_puesto_codigo,
                "que_entrega": t.que_entrega, "senal": t.senal}
    recibe = [_tr(t) for t in db.query(m.Traspaso).filter(m.Traspaso.a_puesto_codigo == puesto_codigo).order_by(m.Traspaso.orden, m.Traspaso.id)]
    entrega = [_tr(t) for t in db.query(m.Traspaso).filter(m.Traspaso.de_puesto_codigo == puesto_codigo).order_by(m.Traspaso.orden, m.Traspaso.id)]
    if pos_obj:
        # para quien ocupa una posición, se omiten los traspasos cuyo extremo de este puesto nombra OTRA posición
        otras = [x.nombre for x in posiciones if x.clave != pos_obj.clave]

        def de_otra(texto):
            return bool(texto) and pos_obj.nombre not in texto and any(o in texto for o in otras)
        recibe = [x for x in recibe if not de_otra(x["a"])]
        entrega = [x for x in entrega if not de_otra(x["de"])]
    vistos, todos = set(), []
    for x in recibe + entrega:
        if x["id"] not in vistos:
            vistos.add(x["id"])
            todos.append(x)

    alcance_inicio = (pos_obj.alcance_inicio if pos_obj and pos_obj.alcance_inicio else p.alcance_inicio)
    alcance_fin = (pos_obj.alcance_fin if pos_obj and pos_obj.alcance_fin else p.alcance_fin)
    equipos = lineas(pos_obj.equipos) if pos_obj and pos_obj.equipos else lineas(p.equipos)

    return {
        "puesto": p, "posiciones": posiciones, "posicion": pos_obj,
        "reporta_a": [_etiqueta_puesto(db, r.relacionado_codigo) for r in rel if r.tipo == "jerarquico"],
        "coordina_con": [_etiqueta_puesto(db, r.relacionado_codigo) for r in rel if r.tipo == "funcional"],
        "supervisa_a": [_etiqueta_puesto(db, r.puesto_codigo) for r in supervisa],
        "alcance_inicio": alcance_inicio, "alcance_fin": alcance_fin, "equipos": equipos,
        "bloques_tareas": bloques_tareas, "n_actividades": len(acts),
        "procedimientos": procedimientos, "formularios": formularios,
        "limites": lineas(p.limites_autoridad), "medicion": lineas(p.medicion_desempeno),
        "notas": lineas(p.notas_ficha),
        "mecanismos": mecanismos, "indicadores": indicadores,
        "traspasos_recibe": recibe, "traspasos_entrega": entrega, "traspasos": todos,
    }
