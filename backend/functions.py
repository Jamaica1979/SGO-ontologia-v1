"""
Functions — Sección 6 de la ontología. Cálculos derivados que nunca se
guardan en una columna; se corren cada vez que se consultan.
"""
import re
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
import models as m


# ───────────────────────── calcular_semaforo ─────────────────────────
# Sección 10.4: el semáforo se calcula al vuelo contra el umbral vigente,
# nunca se persiste. PERO: de los 27 indicadores reales, los umbrales tienen
# tres formatos distintos, y no los tres son parseables por una máquina:
#   1) Numéricos con comparador (≥95%, <70%, ≤$1.400/tn, rangos "80-99%") → SÍ
#   2) Referencias a un valor externo ("≥ meta F-07", "≥meta presupuesto") → NO,
#      el valor de la meta no vive en esta base
#   3) Puramente cualitativos ("Creciendo/estable", "Sí con acta") → NO, es
#      juicio humano, no una comparación numérica
# calcular_semaforo() hace lo que SÍ se puede automatizar y devuelve
# 'requiere_criterio' — explícito, no una adivinanza — en los otros dos casos.

def _num(texto):
    """Extrae el primer número de un string en formato AR (punto=miles, coma=decimal),
    ignorando cualquier texto pegado (unidades como '$', '/tn', '%', 'días', etc.)."""
    if texto is None:
        return None
    t = texto.strip()
    match = re.search(r"-?\d[\d.]*(?:,\d+)?", t)
    if not match:
        return None
    numero = match.group().replace(".", "").replace(",", ".")
    try:
        return float(numero)
    except ValueError:
        return None


def _umbral_parseable(umbral):
    """True si el umbral tiene forma numérica reconocible (con o sin comparador/rango)."""
    if not umbral or "meta" in umbral.lower() or "presupuesto" in umbral.lower():
        return False
    return bool(re.search(r"\d", umbral))


def calcular_semaforo(valor: str, umbral_verde: str, umbral_amarillo: str, umbral_rojo: str):
    """Devuelve 'verde'|'amarillo'|'rojo'|'requiere_criterio'.
    Para umbrales cualitativos (ej. 'Creciendo/estable'), si el valor cargado
    coincide EXACTO con uno de los tres textos del umbral, el semáforo también
    se resuelve solo — no hace falta un selector de color aparte, la persona
    elige el texto correcto al cargar y el semáforo sale de ahí."""
    if valor is not None:
        v_strip = valor.strip()
        if v_strip == (umbral_verde or "").strip():
            return "verde"
        if v_strip == (umbral_amarillo or "").strip():
            return "amarillo"
        if v_strip == (umbral_rojo or "").strip():
            return "rojo"

    if not all(_umbral_parseable(u) for u in (umbral_verde, umbral_amarillo, umbral_rojo)):
        return "requiere_criterio"
    v = _num(valor)
    if v is None:
        return "requiere_criterio"

    def cumple(umbral):
        umbral = umbral.strip()
        if "-" in umbral and not umbral.startswith("-"):
            lo, hi = umbral.split("-", 1)
            lo, hi = _num(lo), _num(hi)
            return lo is not None and hi is not None and lo <= v <= hi
        for simbolo, op in [("≥", lambda a, b: a >= b), ("<=", lambda a, b: a <= b),
                             ("≤", lambda a, b: a <= b), (">=", lambda a, b: a >= b),
                             (">", lambda a, b: a > b), ("<", lambda a, b: a < b)]:
            if simbolo in umbral:
                n = _num(umbral.replace(simbolo, ""))
                return n is not None and op(v, n)
        n = _num(umbral)
        return n is not None and v == n

    if cumple(umbral_verde):
        return "verde"
    if cumple(umbral_amarillo):
        return "amarillo"
    if cumple(umbral_rojo):
        return "rojo"
    return "requiere_criterio"


# ───────────────────────── calcular_cobertura ─────────────────────────
# El corazón de la Fase 1, reescrito sobre el esquema nuevo. Puesto XOR
# Perfil (Sección 13.1), etapa (Sección 10.2), cardinalidad_esperada
# reemplaza a es_por_planta (Sección 10.2).

def calcular_cobertura(db: Session, planta_id: int = None, puesto_codigo: str = None):
    puestos_q = db.query(m.Puesto).filter(m.Puesto.vigente == 1)
    if puesto_codigo:
        puestos_q = puestos_q.filter(m.Puesto.codigo == puesto_codigo)
    puestos = puestos_q.all()
    plantas = db.query(m.Planta).all()

    activas = db.query(m.Asignacion).filter(m.Asignacion.estado.in_(["activa", "transicion"])).all()

    def actividades_de(puesto_codigo_, perfil_id_):
        if puesto_codigo_:
            return set(a.id for a in db.query(m.Actividad.id).filter(m.Actividad.puesto_codigo == puesto_codigo_, m.Actividad.activo == 1))
        if perfil_id_:
            return set(r[0] for r in db.query(m.PerfilActividad.actividad_id).filter(m.PerfilActividad.perfil_id == perfil_id_))
        return set()

    filas = []
    for p in puestos:
        act_puesto = {a.id: a for a in db.query(m.Actividad).filter(m.Actividad.puesto_codigo == p.codigo, m.Actividad.activo == 1)}
        if p.cardinalidad_esperada == "una_por_planta_activa":
            scopes = [(pl, e) for pl in plantas for e in
                      (("primaria", "secundaria", "sin_etapa") if p.codigo in ("PRD-04", "PRD-05") else (None,))]
        else:
            scopes = [(None, None)]

        for pl, etapa in scopes:
            pl_id = pl.id if pl else None
            if planta_id and pl_id and pl_id != planta_id:
                continue

            def matchea(a):
                if pl_id is not None and a.planta_id != pl_id:
                    return False
                if etapa == "sin_etapa":
                    return not a.etapa
                if etapa is not None and a.etapa != etapa:
                    return False
                return True

            directas = [a for a in activas if a.puesto_codigo == p.codigo and matchea(a)]
            if etapa == "sin_etapa" and not directas:
                continue
            if directas:
                estado_fila = "cubierta" if etapa != "sin_etapa" else "cubierta_sin_etapa"
                responsables = [{"persona_id": a.persona_id, "persona": f"{a.persona.nombre} {a.persona.apellido}", "via": "puesto"} for a in directas]
                acts_sin = []
            else:
                cubiertas_ids, resp_perfil = set(), []
                for a in activas:
                    if a.perfil_id and matchea(a):
                        de_perfil = actividades_de(None, a.perfil_id)
                        interseccion = set(act_puesto.keys()) & de_perfil
                        if interseccion:
                            cubiertas_ids |= interseccion
                            resp_perfil.append({"persona_id": a.persona_id, "persona": f"{a.persona.nombre} {a.persona.apellido}",
                                                 "via": "perfil", "n_actividades": len(interseccion)})
                acts_sin = [act_puesto[i] for i in act_puesto if i not in cubiertas_ids]
                if not act_puesto:
                    estado_fila = "sin_actividades"
                elif not cubiertas_ids:
                    estado_fila = "sin_asignar"
                elif acts_sin:
                    estado_fila = "parcial"
                else:
                    estado_fila = "cubierta"
                responsables = resp_perfil

            filas.append({
                "puesto_codigo": p.codigo, "puesto_nombre": p.nombre, "area": p.area,
                "planta_id": pl_id, "planta_nombre": pl.nombre if pl else "Sede / toda la empresa",
                "planta_estado": pl.estado if pl else None, "etapa": etapa,
                "estado": estado_fila, "responsables": responsables,
                "n_actividades": len(act_puesto),
                "actividades_sin_asignar": [{"id": a.id, "codigo": a.codigo, "descripcion": a.descripcion, "es_critica": bool(a.es_critica)} for a in acts_sin],
            })
    return filas


def resumen_cobertura(filas):
    total = len(filas)
    cubiertas = len([f for f in filas if f["estado"] in ("cubierta", "cubierta_sin_etapa")])
    parciales = len([f for f in filas if f["estado"] == "parcial"])
    sin_asignar = len([f for f in filas if f["estado"] == "sin_asignar"])
    sin_etapa = len([f for f in filas if f["estado"] == "cubierta_sin_etapa"])
    return {"total": total, "cubiertas": cubiertas, "parciales": parciales,
            "sin_asignar": sin_asignar, "cubiertas_sin_etapa_definida": sin_etapa,
            "pct_cobertura": round(100 * cubiertas / total, 1) if total else 0}


# ───────────────────────── bandeja_de_pendientes ─────────────────────────
# Sección 11: reemplaza la tabla plana por una cola priorizada. Devuelve las
# filas COMPLETAS de calcular_cobertura (no un resumen) para que tanto la API
# JSON como las plantillas de la UI puedan reusarlas — la UI necesita el detalle
# completo (responsables, actividades) para ofrecer la acción de asignar ahí mismo.

def bandeja_de_pendientes(db: Session):
    filas = calcular_cobertura(db)
    plantas = {pl.id: pl for pl in db.query(m.Planta).all()}
    urgente, antes_de_habilitar, dato_incompleto, sede_unica = [], [], [], []
    for f in filas:
        planta = plantas.get(f["planta_id"]) if f["planta_id"] else None
        if f["estado"] == "cubierta_sin_etapa":
            dato_incompleto.append(f)
        elif f["estado"] in ("sin_asignar", "parcial"):
            if planta is None:
                sede_unica.append(f)
            elif planta.estado in ("activa", "piloto"):
                urgente.append(f)
            else:
                antes_de_habilitar.append(f)
    return {
        "total_abiertos": len(urgente) + len(antes_de_habilitar) + len(dato_incompleto) + len(sede_unica),
        "urgente_plantas_activas": urgente,
        "antes_de_habilitar_planta": antes_de_habilitar,
        "dato_por_completar": dato_incompleto,
        "sede_unica_sin_cubrir": sede_unica,
    }


# ───────────────────────── calcular_riesgo_dependencia ─────────────────────────
# Adaptado de la lógica ya validada en v2 (dependencias_criticas), sobre el
# esquema nuevo: personas ya no tiene planta_id propio (se deriva de Asignación),
# notas_alertas se unificó en 'notas'.

def calcular_riesgo_dependencia(db: Session):
    puestos = db.query(m.Puesto).filter(m.Puesto.vigente == 1, m.Puesto.area != "Dirección").all()
    riesgos = []
    for p in puestos:
        n_criticas = db.query(m.Actividad).filter(m.Actividad.puesto_codigo == p.codigo, m.Actividad.es_critica == 1).count()
        if n_criticas == 0:
            continue
        gente = db.query(m.Asignacion).filter(m.Asignacion.puesto_codigo == p.codigo,
                                               m.Asignacion.estado.in_(["activa", "transicion"])).all()
        por_planta = {}
        for a in gente:
            por_planta.setdefault(a.planta_id, []).append(a)
        for planta_id, asigs in por_planta.items():
            activos = [a for a in asigs if a.estado == "activa"]
            en_transicion = [a for a in asigs if a.estado == "transicion"]
            if len(activos) == 1:
                mitigacion = len(en_transicion) > 0
                persona = activos[0].persona
                planta = db.query(m.Planta).get(planta_id)
                riesgos.append({
                    "puesto": p.codigo, "puesto_nombre": p.nombre, "area": p.area,
                    "planta": planta.codigo if planta else None,
                    "persona_id": persona.id, "persona": f"{persona.nombre} {persona.apellido}",
                    "actividades_criticas": n_criticas,
                    "en_mitigacion": mitigacion,
                    "respaldo_en_formacion": f"{en_transicion[0].persona.nombre} {en_transicion[0].persona.apellido}" if mitigacion else None,
                })
    riesgos.sort(key=lambda r: (r["en_mitigacion"], -r["actividades_criticas"]))
    return {"total": len(riesgos), "sin_mitigacion": sum(1 for r in riesgos if not r["en_mitigacion"]),
            "en_mitigacion": sum(1 for r in riesgos if r["en_mitigacion"]), "riesgos": riesgos}


# ───────────────────────── calcular_dias_para_extincion ─────────────────────────

def calcular_dias_para_extincion(fecha_estimada: str):
    if not fecha_estimada:
        return None
    try:
        f = datetime.strptime(fecha_estimada, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (f - date.today()).days


# ───────────────────────── detectar_alerta_legal ─────────────────────────

def detectar_alertas(db: Session):
    alertas = []
    for pe in db.query(m.Persona).filter(m.Persona.activo == 1, m.Persona.estado_legajo != "completo"):
        alertas.append({"tipo": "legajo", "nivel": "amarillo",
                         "mensaje": f"Legajo {pe.estado_legajo} — {pe.nombre} {pe.apellido}"})
    hoy = date.today()
    for h in db.query(m.HabilitacionDePersona):
        if not h.fecha_vencimiento:
            continue
        try:
            f = datetime.strptime(h.fecha_vencimiento, "%Y-%m-%d").date()
        except ValueError:
            continue
        dias = (f - hoy).days
        if dias < 0:
            persona = db.query(m.Persona).get(h.persona_id)
            alertas.append({"tipo": "habilitacion", "nivel": "rojo",
                             "mensaje": f"Habilitación vencida — {persona.nombre} {persona.apellido} (hace {-dias} días)"})
        elif dias <= 30:
            persona = db.query(m.Persona).get(h.persona_id)
            alertas.append({"tipo": "habilitacion", "nivel": "amarillo",
                             "mensaje": f"Habilitación vence en {dias} días — {persona.nombre} {persona.apellido}"})

    filas = calcular_cobertura(db)
    for f in filas:
        if f["estado"] == "sin_asignar" and f["planta_id"]:
            alertas.append({"tipo": "vacante", "nivel": "amarillo",
                             "mensaje": f"Puesto {f['puesto_codigo']} {f['puesto_nombre']} sin asignación en {f['planta_nombre']} ({f['planta_estado']})"})
        elif f["estado"] == "sin_asignar" and not f["planta_id"]:
            alertas.append({"tipo": "vacante", "nivel": "amarillo",
                             "mensaje": f"Puesto {f['puesto_codigo']} {f['puesto_nombre']} sin asignación activa"})
    return alertas
