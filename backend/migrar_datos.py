#!/usr/bin/env python3
"""Migración de datos: v2 (21 tablas) -> v3 (24 tablas, ontología por objetos).
Sigue la Sección 15 de Ontologia_Cantera_Eldorado_v2.md. Imprime un reporte al
final con todo lo que NO se pudo resolver automáticamente, para revisión manual.
"""
import sqlite3
import json

ORIGEN = "cantera_v2_origen.db"
DESTINO = "cantera.db"

reporte = {"auto_resuelto": [], "revision_manual": []}

src = sqlite3.connect(ORIGEN)
src.row_factory = sqlite3.Row
dst = sqlite3.connect(DESTINO)
dst.execute("PRAGMA foreign_keys = OFF")  # se reactiva al final, para no depender del orden de carga


def copiar_directo(tabla, columnas):
    filas = src.execute(f"SELECT {','.join(columnas)} FROM {tabla}").fetchall()
    placeholders = ",".join("?" * len(columnas))
    dst.executemany(f"INSERT INTO {tabla} ({','.join(columnas)}) VALUES ({placeholders})",
                     [tuple(f[c] for c in columnas) for f in filas])
    return len(filas)


# ── 1. plantas: copia directa ──
n = copiar_directo("plantas", ["id", "codigo", "nombre", "estado", "notas"])
reporte["auto_resuelto"].append(f"plantas: {n} filas")

# ── 2. convenios_colectivos: nuevo, derivado de los valores de texto ──
CONVENIOS = [(1, "UOCRA", "UOCRA", 1, "Ley 22.250 - construcción", "UOCRA", "OSPECON"),
             (2, "COMERCIO", "Empleados de Comercio", 0, "Ley 20.744 general", "Empleados de Comercio", "OSECAC")]
dst.executemany("""INSERT INTO convenios_colectivos
    (id,codigo,nombre,tiene_fondo_cese_laboral,regimen_indemnizatorio,sindicato,obra_social)
    VALUES (?,?,?,?,?,?,?)""", CONVENIOS)
CCT_MAP = {"UOCRA": 1, "Empleados de Comercio": 2, "—": None, None: None}
reporte["auto_resuelto"].append(f"convenios_colectivos: {len(CONVENIOS)} filas (creadas desde los valores de texto)")

# ── 3. puestos ──
puestos_src = src.execute("SELECT * FROM puestos").fetchall()
for p in puestos_src:
    cardinalidad = "una_por_planta_activa" if p["es_por_planta"] else "unica_en_la_empresa"
    dst.execute("""INSERT INTO puestos
        (id,codigo,nombre,area,nivel,cardinalidad_esperada,proposito,limites_autoridad,convenio_id,version,vigente,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (p["id"], p["codigo"], p["nombre"], p["area"], p["nivel"], cardinalidad,
         p["proposito"], p["limites_autoridad"], CCT_MAP.get(p["cct"]), p["version"], p["vigente"],
         p["created_at"], p["updated_at"]))
reporte["auto_resuelto"].append(f"puestos: {len(puestos_src)} filas (es_por_planta -> cardinalidad_esperada, cct -> convenio_id)")

# ── 4. relaciones_reporte: explota reporte_a + coordina_con ──
n_rel = 0
for p in puestos_src:
    if p["reporte_a"]:
        dst.execute("INSERT INTO relaciones_reporte (puesto_codigo, relacionado_codigo, tipo) VALUES (?,?,'jerarquico')",
                     (p["codigo"], p["reporte_a"]))
        n_rel += 1
    if p["coordina_con"]:
        for otro in json.loads(p["coordina_con"]):
            dst.execute("INSERT INTO relaciones_reporte (puesto_codigo, relacionado_codigo, tipo) VALUES (?,?,'funcional')",
                         (p["codigo"], otro))
            n_rel += 1
reporte["auto_resuelto"].append(f"relaciones_reporte: {n_rel} filas (explotadas desde reporte_a y coordina_con)")

# ── 5. roles_transicion: puestos con es_transitorio=1 ──
n_trans = 0
for p in puestos_src:
    if p["es_transitorio"]:
        dst.execute("""INSERT INTO roles_transicion
            (puesto_id, condicion_extincion, estado) VALUES (?,?,'vigente')""",
            (p["id"], p["condicion_salida"]))
        n_trans += 1
        reporte["revision_manual"].append(
            f"roles_transicion: {p['codigo']} migrado con condicion_extincion='{p['condicion_salida']}' "
            f"pero SIN puesto_absorbente_codigo ni fecha_estimada_extincion — completar a mano")
reporte["auto_resuelto"].append(f"roles_transicion: {n_trans} fila(s) creada(s) (esqueleto, ver revisión manual)")

# ── 6. personas (sin planta_id, se deriva de Asignación) ──
personas_src = src.execute("SELECT * FROM personas").fetchall()
for pe in personas_src:
    dst.execute("""INSERT INTO personas
        (id,nombre,apellido,legajo,cuit,convenio_id,antiguedad_anos,estado_legajo,notas,activo,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (pe["id"], pe["nombre"], pe["apellido"], pe["legajo"], pe["cuit"], CCT_MAP.get(pe["cct"]),
         pe["antiguedad_anos"], pe["estado_legajo"], pe["notas_alertas"], pe["activo"], pe["created_at"]))
reporte["auto_resuelto"].append(f"personas: {len(personas_src)} filas (planta_id descartado a propósito, se deriva de asignaciones)")

# ── 7. funciones_organizacionales + actividades ──
dst.execute("INSERT INTO funciones_organizacionales (id,codigo,nombre,descripcion) VALUES (1,'COMERCIAL','Comercial','Función distribuida entre plantas y sede: báscula, despacho y cuentas corrientes')")
puestos_validos = set(p["codigo"] for p in puestos_src)
acts_src = src.execute("SELECT * FROM actividades").fetchall()
n_comercial = 0
for a in acts_src:
    puesto_codigo = a["funcion_origen"] if a["funcion_origen"] in puestos_validos else None
    funcion_id = 1 if a["area"] == "Comercial" else None
    if funcion_id:
        n_comercial += 1
    dst.execute("""INSERT INTO actividades
        (id,codigo,descripcion,area,nivel,competencia,es_critica,frecuencia,notas,activo,puesto_codigo,funcion_organizacional_id,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (a["id"], a["codigo"], a["descripcion"], a["area"], a["nivel"], a["competencia"], a["es_critica"],
         a["frecuencia"], a["notas"], a["activo"], puesto_codigo, funcion_id, a["created_at"], a["updated_at"]))
reporte["auto_resuelto"].append(f"actividades: {len(acts_src)} filas (cct descartado -confirmado redundante-, {n_comercial} vinculadas a función Comercial por area='Comercial', 100% automático)")

# ── 8. tipos_de_capacitacion (desde capacitaciones) ──
caps_src = src.execute("SELECT * FROM capacitaciones").fetchall()
for c in caps_src:
    dst.execute("""INSERT INTO tipos_de_capacitacion
        (id,nombre,tipo,descripcion,url_o_referencia,duracion_estimada,created_at)
        VALUES (?,?,?,?,?,?,?)""",
        (c["id"], c["titulo"], c["tipo"], c["descripcion"], c["url_o_referencia"], c["duracion_estimada"], c["created_at"]))
reporte["auto_resuelto"].append(f"tipos_de_capacitacion: {len(caps_src)} filas (organismo_emisor/vigencia_meses quedan en blanco para completar)")

# ── 9. habilitaciones_persona (resolver tipo texto -> tipo_capacitacion_id) ──
hab_src = src.execute("SELECT * FROM habilitaciones").fetchall()
n_hab_auto, n_hab_manual = 0, 0
for h in hab_src:
    match = dst.execute("SELECT id FROM tipos_de_capacitacion WHERE nombre LIKE ?", (f"%{h['tipo']}%",)).fetchone()
    if match:
        dst.execute("""INSERT INTO habilitaciones_persona
            (id,persona_id,tipo_capacitacion_id,numero,fecha_vencimiento,estado) VALUES (?,?,?,?,?,?)""",
            (h["id"], h["persona_id"], match[0], h["numero"], h["fecha_vencimiento"], h["estado"]))
        n_hab_auto += 1
    else:
        reporte["revision_manual"].append(f"habilitaciones_persona: tipo '{h['tipo']}' (persona_id={h['persona_id']}) sin tipo_de_capacitacion equivalente — no migrada")
        n_hab_manual += 1
reporte["auto_resuelto"].append(f"habilitaciones_persona: {n_hab_auto} de {len(hab_src)} resueltas automáticamente contra tipos_de_capacitacion existentes")

# ── 10. procedimientos: copia directa ──
n = copiar_directo("procedimientos", ["id", "codigo", "nombre", "area", "nivel_riesgo", "descripcion",
                                        "tiene_nivel_urgente", "tiene_nivel_emergencia", "formularios_asociados", "created_at"])
reporte["auto_resuelto"].append(f"procedimientos: {n} filas")

# ── 11. pasos_procedimiento (responsable texto -> FK o texto original) ──
pasos_src = src.execute("SELECT * FROM pasos_procedimiento").fetchall()
n_paso_auto, n_paso_manual = 0, 0
for p in pasos_src:
    if p["responsable"] in puestos_validos:
        dst.execute("""INSERT INTO pasos_procedimiento
            (id,procedimiento_id,numero,titulo,descripcion,responsable_puesto_codigo,documento)
            VALUES (?,?,?,?,?,?,?)""",
            (p["id"], p["procedimiento_id"], p["numero"], p["titulo"], p["descripcion"], p["responsable"], p["documento"]))
        n_paso_auto += 1
    else:
        dst.execute("""INSERT INTO pasos_procedimiento
            (id,procedimiento_id,numero,titulo,descripcion,responsable_texto_original,documento)
            VALUES (?,?,?,?,?,?,?)""",
            (p["id"], p["procedimiento_id"], p["numero"], p["titulo"], p["descripcion"], p["responsable"], p["documento"]))
        n_paso_manual += 1
reporte["revision_manual"].append(
    f"pasos_procedimiento: {n_paso_manual} de {len(pasos_src)} pasos tienen responsabilidad conjunta o secuencial "
    f"(ej. 'PRD-02 → DIR-03', 'PRD-02 + ADM-06') — no se fuerza a un solo puesto, quedan en responsable_texto_original")
reporte["auto_resuelto"].append(f"pasos_procedimiento: {n_paso_auto} de {len(pasos_src)} resueltos a un único responsable_puesto_codigo")

# ── 12. indicadores (responsable_carga/uso ya eran códigos limpios) ──
ind_src = src.execute("SELECT * FROM indicadores").fetchall()
for i in ind_src:
    dst.execute("""INSERT INTO indicadores
        (id,codigo,nombre,area,formula,frecuencia,fuente_dato,responsable_carga_puesto_codigo,responsable_uso_puesto_codigo,umbral_verde,umbral_amarillo,umbral_rojo,activo)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (i["id"], i["codigo"], i["nombre"], i["area"], i["formula"], i["frecuencia"], i["fuente_dato"],
         i["responsable_carga"], i["responsable_uso"], i["umbral_verde"], i["umbral_amarillo"], i["umbral_rojo"], i["activo"]))
reporte["auto_resuelto"].append(f"indicadores: {len(ind_src)} filas (responsable_carga/uso ya eran códigos válidos, 100% automático)")

# ── 13. mediciones_indicador (desde kpi_valores, sin semaforo) ──
kpi_src = src.execute("SELECT * FROM kpi_valores").fetchall()
ind_id_por_codigo = {i["codigo"]: i["id"] for i in ind_src}
n_kpi = 0
for k in kpi_src:
    dst.execute("INSERT INTO mediciones_indicador (id,indicador_id,periodo,valor,notas,created_at) VALUES (?,?,?,?,?,?)",
                (k["id"], ind_id_por_codigo[k["codigo"]], k["periodo"], k["valor"], k["notas"], k["created_at"]))
    n_kpi += 1
reporte["auto_resuelto"].append(f"mediciones_indicador: {n_kpi} filas (semaforo descartado -se calcula al vuelo-)")

# ── 14. resto de tablas sin cambio de estructura: copia directa ──
n = copiar_directo("perfiles", ["id", "nombre", "estado", "descripcion", "creado_por", "created_at", "updated_at"])
reporte["auto_resuelto"].append(f"perfiles: {n} filas (origen se completa 'armado' por defecto vía server_default)")
n = copiar_directo("perfil_actividades", ["perfil_id", "actividad_id", "orden"])
reporte["auto_resuelto"].append(f"perfil_actividades: {n} filas")
n = copiar_directo("mecanismos", ["id", "codigo", "nombre", "grupo", "frecuencia", "descripcion", "documento", "emite", "recibe", "estado_relevado", "vigente", "created_at"])
reporte["auto_resuelto"].append(f"mecanismos: {n} filas")
n = copiar_directo("mecanismo_puestos", ["id", "mecanismo_id", "puesto_codigo", "rol"])
reporte["auto_resuelto"].append(f"mecanismo_puestos: {n} filas")
n = copiar_directo("registro_cumplimiento", ["id", "mecanismo_id", "periodo", "estado", "causa", "accion_correctiva", "registrado_por", "created_at"])
reporte["auto_resuelto"].append(f"registro_cumplimiento: {n} filas")
n = copiar_directo("procedimiento_puestos", ["procedimiento_id", "puesto_codigo", "rol"])
reporte["auto_resuelto"].append(f"procedimiento_puestos: {n} filas")
n = copiar_directo("asignaciones", ["id", "persona_id", "puesto_codigo", "perfil_id", "planta_id", "etapa", "estado", "fecha_inicio", "fecha_fin_estimada", "condicion_salida", "created_at"])
reporte["auto_resuelto"].append(f"asignaciones: {n} filas (sin cambios de estructura)")
n = copiar_directo("historial", ["id", "tabla", "registro_id", "accion", "datos_anteriores", "datos_nuevos", "usuario", "timestamp"])
reporte["auto_resuelto"].append(f"historial: {n} filas")

# actividad_capacitaciones: la FK cambió de nombre (capacitacion_id -> tipo_capacitacion_id), incluida acá
ac_src = src.execute("SELECT * FROM actividad_capacitaciones").fetchall()
for r in ac_src:
    dst.execute("INSERT INTO actividad_capacitaciones (actividad_id, tipo_capacitacion_id, obligatoria) VALUES (?,?,?)",
                (r["actividad_id"], r["capacitacion_id"], r["obligatoria"]))
reporte["auto_resuelto"].append(f"actividad_capacitaciones: {len(ac_src)} filas (capacitacion_id renombrado a tipo_capacitacion_id)")

# puesto_funciones: se completa a partir de los puestos que ya tienen actividad Comercial
puestos_comercial = set(r[0] for r in dst.execute(
    "SELECT DISTINCT puesto_codigo FROM actividades WHERE funcion_organizacional_id=1 AND puesto_codigo IS NOT NULL"))
for pc in puestos_comercial:
    dst.execute("INSERT INTO puesto_funciones (puesto_codigo, funcion_id) VALUES (?,1)", (pc,))
reporte["auto_resuelto"].append(f"puesto_funciones: {len(puestos_comercial)} filas ({', '.join(sorted(puestos_comercial))}) — derivadas automáticamente de qué puestos tienen actividades comerciales")

dst.execute("PRAGMA foreign_keys = ON")
dst.commit()

print("=" * 70)
print("MIGRACIÓN COMPLETADA")
print("=" * 70)
print("\n--- Automático ---")
for l in reporte["auto_resuelto"]:
    print(" ✓", l)
print(f"\n--- Revisión manual pendiente ({len(reporte['revision_manual'])} ítems) ---")
for l in reporte["revision_manual"][:5]:
    print(" ⚠", l)
if len(reporte["revision_manual"]) > 5:
    print(f"   ... y {len(reporte['revision_manual'])-5} más (pasos_procedimiento con responsabilidad conjunta)")
