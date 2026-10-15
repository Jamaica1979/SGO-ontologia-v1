"""Migración de DATOS de la v3.7 (se corre una sola vez; es idempotente).

  1. Personas: alta de las que faltan y corrección/completado de las existentes, según
     la planilla PERSONAL_CANTERA.xlsx (13/10/2026). Cruce hecho a mano, uno por uno.
  2. ADP-03 absorbe a PRD-07 (que se da de baja). Sin renumerar actividades.
  3. Aplicabilidad por planta: ADP-02 en Eldorado y tareas de planta remota de ADP-01 / ADP-03.
  4. Formularios: F-08.1 Parte de perforación como parte del F-08; plazo del F-08 a las 9 h.
  5. Ajustes de contenido de las reuniones del 1 y 6 de octubre (act. 138, 140, 141, 127, P-07).
  6. Reinicio de asignaciones: se finalizan TODAS (nada se borra) y se archivan los perfiles individuales.

Uso:  python scripts/datos_v3_7.py   → aplica sobre backend/cantera.db (hacer copia antes)
"""
import sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import SessionLocal, log_historial, to_dict   # noqa: E402
import models as m                                           # noqa: E402

HOY = "2026-10-13"
ELD, SB, CG, SA = 1, 2, 3, 4
UOCRA, COMERCIO = 1, 2

# (id existente | None, apellido, nombre, apodo, legajo, cuil, ingreso, sector, cargo, planta, convenio si es alta)
PERSONAL = [
    # ── Eldorado / Campo Grande (planilla "PERSONAL CANTERA POR SUCURSAL")
    (None, "Belaver", "Pedro Aroldo", None, "1", "20-13421189-0", "1983-09-01", "Taller", "Ayudante de taller", ELD, UOCRA),
    (None, "Griebeler", "Artemio", None, "3", "20-21639566-3", "2008-05-05", "Sereno", "Sereno", ELD, UOCRA),
    (11, "Rivas", "Sergio Cristian", None, "4", "20-30706777-4", "2011-01-06", "Martillo hidráulico", "Maquinista", ELD, None),
    (None, "González", "Félix del Pilar", None, "5", "20-24532304-3", "2011-04-01", "Taller", "Mecánico", ELD, UOCRA),
    (9, "Brest", "Esteban José", None, "8", "20-28829365-2", "2012-10-15", "Perforador", "Operador perforador", ELD, None),
    (12, "Baez", "Ángel Gabriel", None, "9", "20-33280816-9", "2013-05-02", "Taller", "Taller", ELD, None),
    (8, "Muschalek", "José Carlos", None, "11", "20-23348072-0", "2013-08-01", "Taller", "Mecánico", ELD, None),
    (None, "Dos Santos", "César", None, "12", "23-35012174-9", "2013-10-01", "Taller", "Ayudante de taller", ELD, UOCRA),
    (14, "Bobadilla", "Leandro Andrés", None, "13", "20-30903416-4", "2014-02-17", "Chofer externo", "Chofer de camión", ELD, None),
    (None, "Baez", "Ramón Alfredo", None, "14", "20-31122201-6", "2014-04-01", "Secundario", "Operador", CG, UOCRA),
    (10, "Dorr", "Diego Alejandro", None, "18", "20-38777004-7", "2017-09-04", "Secundario", "Operador secundario", ELD, None),
    (None, "Morel", "Mario E.", None, "29", "20-30615427-4", "2022-02-14", "Playa de voladuras", "Maquinista / chofer de camión", ELD, UOCRA),
    (13, "Ríos", "Edgardo Daniel", None, "30", "20-31034658-7", "2022-02-14", "Playa de acopio", "Maquinista", ELD, None),
    (15, "Cabrera", "Javier David", None, "37", "20-42302741-0", "2022-07-25", "Secundario", "Ayudante secundario", ELD, None),
    (None, "Benítez", "Gabriel Armando", None, "52", "20-31381613-4", "2023-10-02", "Chofer externo", "Chofer de camión / compras", ELD, UOCRA),
    (None, "Gómez", "Juan Javier", None, "59", "20-25315652-0", "2024-02-01", "Playa de voladuras", "Maquinista", CG, UOCRA),
    (33, "Goritz", "Federico Edmundo", None, None, "20-33852940-7", "2025-07-07", "Acondicionamiento de terreno", "Ayudante de armado de planta", CG, None),
    (34, "Goritz", "Maximiliano Alfredo", None, None, "20-40193684-0", "2025-11-03", "Acondicionamiento de terreno", "Ayudante de armado de planta", CG, None),
    (7, "Morla", "Daniel Desiderio", None, "100", "20-20382436-0", "1992-05-02", "Adm. cat. D", None, ELD, None),
    (None, "Christiansen", "María Laura", None, "104", "27-54535699-1", "2019-03-01", "Adm. cat. E", None, ELD, COMERCIO),
    (6, "Steffler", "Jonathan Estiven", None, "105", "20-32418160-2", "2020-02-07", "Adm. cat. A", None, ELD, None),
    (5, "Steffler", "Edith Estela", None, "109", "27-37117068-0", "2023-02-08", "Adm. cat. A", None, ELD, None),
    (4, "Ratzlau", "Roberto Carlos", "Cholín", "111", "20-26907796-5", "2023-05-02", "Adm. cat. A", None, ELD, None),
    (16, "Gómez", "Rodrigo Álvaro Natalio", None, "112", "20-29357142-3", "2023-06-02", "Adm. cat. A", None, ELD, None),
    (1, "Christiansen", "Eliseo Pedro", None, "200", "20-11612849-8", None, "Presidente", None, ELD, None),
    (2, "Christiansen", "Eduardo Eliseo", "Tiki", "201", "20-27797455-0", None, "Vicepresidente", None, ELD, None),
    (3, "Christiansen", "Ian Adolfo", None, "102", "20-33589799-5", None, "Vicepresidente", None, ELD, None),
    # ── San Borgita (planilla "san borjita": sin CUIL ni fecha de ingreso; sólo cargo/descripción)
    (18, "Alvarez", "Carlos", "Carlitos", None, None, None, "Oficina", "Encargado de Administración, Encargado de Ventas y Facturaciones", SB, None),
    (19, "Alvarenga", "Pablo", None, None, None, None, "Oficina", "Atención al cliente, facturación, control y gestión de pagos (administrativo)", SB, None),
    (17, "Barrios", "Guillermo", None, None, None, None, "Planta", "Encargado de producción, encargado de planta, manejo de personal, compras administrativas", SB, None),
    (20, "Espinoza", "Omar Javier", None, None, None, None, "Oficina", "Atención al cliente, facturación, control y gestión de pagos (administrativo)", SB, None),
    (24, "Faleiro", "Roque A.", None, None, None, None, "Playa", "Playero — maquinista, cargas de materiales para ventas", SB, None),
    (30, "Fernández", "Julio Alfredo", None, None, None, None, "Taller", "Manejo y control de combustibles, ayudante mecánico y mantenimientos", SB, None),
    (31, "Leguiza", "Lucas Gabriel", None, None, None, None, "Planta", "Ayudante de planta — limpieza del sector secundario, tareas diarias de mantenimiento", SB, None),
    (29, "Lloret", "Marcelo A.", None, None, None, None, "Taller", "Mecánico, mantenimiento de máquinas industriales y de planta, chofer", SB, None),
    (25, "López", "Jorge Daniel", None, None, None, None, "Playa", "Maquinista — carga de materiales a camiones", SB, None),
    (27, "Miranda", "Juan Carlos", None, None, None, None, "Transporte", "Chofer de camión — transporta materiales para la producción", SB, None),
    (23, "Ponce", "Rodrigo Alexis", None, None, None, None, "Perforación", "Perforista — ayudante de voladuras (explosivos)", SB, None),
    (32, "Ramírez", "Darío", None, None, None, None, "Planta", "Ayudante de planta — limpieza del sector primario, mantenimiento diario, electricista", SB, None),
    (28, "Rebollo", "Gabriel", None, None, None, None, "Transporte", "Chofer de camión — transporta materiales para la producción", SB, None),
    (21, "Sosa", "Claudio Ramón", None, None, None, None, "Planta", "Oficial — operador de planta trituradora (secundario y terciario)", SB, None),
    (26, "Vera", "Mauricio", None, None, None, None, "Playa", "Oficial y maquinista — carga de materiales a camiones", SB, None),
    (22, "Verdún López", "Benito", None, None, None, None, "Planta", "Oficial — operador de planta trituradora (primario)", SB, None),
]


def personas(db):
    res = {"nuevas": [], "actualizadas": []}
    for (pid, ape, nom, apodo, leg, cuil, ing, sector, cargo, planta, conv) in PERSONAL:
        if pid is None:
            p = db.query(m.Persona).filter(m.Persona.apellido == ape, m.Persona.nombre == nom).first()
            if p:
                pid = p.id
        if pid is None:
            p = m.Persona(nombre=nom, apellido=ape, convenio_id=conv, activo=1,
                          estado_legajo="completo" if leg else "incompleto")
            db.add(p)
            db.flush()
            antes = None
            res["nuevas"].append(f"{ape}, {nom}")
        else:
            p = db.query(m.Persona).get(pid)
            antes = to_dict(p)
            res["actualizadas"].append(f"{ape}, {nom}")
        p.apellido, p.nombre = ape, nom
        if apodo:
            p.apodo = apodo
        if leg:
            p.legajo = leg
        if cuil:
            p.cuit = cuil
        if ing:
            p.fecha_ingreso = ing
        p.sector, p.cargo_nomina, p.planta_base_id = sector, cargo, planta
        log_historial(db, "personas", p.id, "AltaPersona" if antes is None else "ActualizarPersona (planilla 13/10/2026)",
                      antes=antes, despues=to_dict(p))
    return res


def _act(db, codigo):
    return db.query(m.Actividad).filter(m.Actividad.codigo == codigo).first()


def fusionar_bascula(db):
    adp03 = db.query(m.Puesto).filter(m.Puesto.codigo == "ADP-03").first()
    prd07 = db.query(m.Puesto).filter(m.Puesto.codigo == "PRD-07").first()
    antes = to_dict(adp03)
    adp03.nombre = "Operador de Báscula"
    adp03.area = "Comercial"
    adp03.proposito = "Ejecutar el proceso completo de báscula, pesaje, guía minera y despacho, como parte de la función de ventas de la planta"
    adp03.limites_autoridad = "Sin autoridad de aprobación"
    log_historial(db, "puestos", adp03.id, "FusionarPuestos (ADP-03 absorbe PRD-07)", antes=antes, despues=to_dict(adp03))
    if prd07.vigente:
        a = to_dict(prd07)
        prd07.vigente = 0
        log_historial(db, "puestos", prd07.id, "DarDeBajaPuesto (absorbido por ADP-03)", antes=a, despues=to_dict(prd07))
    # sin renumerar: las ACT-164..169 duplican a las ACT-092..097; sólo la 170 no tiene equivalente
    for dup, orig in zip(range(164, 170), range(92, 98)):
        x = _act(db, f"ACT-{dup:03d}")
        if x.activo:
            a = to_dict(x)
            x.activo = 0
            x.notas = f"Dada de baja el 13/10/2026: duplicaba a ACT-{orig:03d} al fusionarse PRD-07 en ADP-03."
            log_historial(db, "actividades", x.id, "DarDeBajaActividad (fusión PRD-07 → ADP-03)", antes=a, despues=to_dict(x))
    x = _act(db, "ACT-170")
    if x.puesto_codigo != "ADP-03":
        a = to_dict(x)
        x.puesto_codigo, x.nivel = "ADP-03", "N2"
        x.notas = "Proviene de PRD-07 (fusionado en ADP-03 el 13/10/2026)."
        log_historial(db, "actividades", x.id, "ReubicarActividad (PRD-07 → ADP-03)", antes=a, despues=to_dict(x))
    # actividad nueva: en Eldorado la báscula envía el F-03 directo a Administración
    if not _act(db, "ACT-171"):
        n = m.Actividad(codigo="ACT-171", descripcion="Enviar el F-03 de cierre de báscula al Jefe de Administración antes de las 18:00",
                        area="Comercial", nivel="N2", competencia="Reporte operativo", es_critica=1, frecuencia="Diaria",
                        puesto_codigo="ADP-03", funcion_organizacional_id=1, activo=1,
                        notas="Nueva (reunión del 6/10/2026): en Eldorado la báscula no pasa por el administrativo de planta. No aplica en plantas donde ADP-01 reenvía el F-03.")
        db.add(n)
        db.flush()
        log_historial(db, "actividades", n.id, "CrearActividad", despues=to_dict(n))
    # relaciones y mecanismos de PRD-07 → ADP-03
    R = m.RelacionReporte
    def existe(p, r, t):
        return db.query(R).filter(R.puesto_codigo == p, R.relacionado_codigo == r, R.tipo == t).first()
    for rel in db.query(R).filter(R.puesto_codigo == "PRD-07").all():
        if rel.tipo == "funcional" and rel.relacionado_codigo == "PRD-05" and not existe("ADP-03", "PRD-05", "funcional"):
            rel.puesto_codigo = "ADP-03"
        else:
            db.delete(rel)
    for rel in db.query(R).filter(R.relacionado_codigo == "PRD-07").all():
        if existe(rel.puesto_codigo, "ADP-03", rel.tipo):
            db.delete(rel)
        else:
            rel.relacionado_codigo = "ADP-03"
    for mp in db.query(m.MecanismoPuesto).filter(m.MecanismoPuesto.puesto_codigo == "PRD-07").all():
        mp.puesto_codigo = "ADP-03"
    f3 = db.query(m.Formulario).filter(m.Formulario.codigo == "F-03").first()
    if f3 and f3.emisor and "PRD-07" in f3.emisor:
        f3.emisor = "ADP-03"


def aplicabilidad(db):
    def poner(planta, motivo, puesto=None, act=None, reparte=0):
        from aplicabilidad import guardar_aplicabilidad
        if act:
            guardar_aplicabilidad(db, planta, "no_aplica", motivo, actividad_id=_act(db, act).id)
        else:
            guardar_aplicabilidad(db, planta, "se_reparte" if reparte else "no_aplica", motivo, puesto_codigo=puesto)
    poner(ELD, "Puesto de planta remota; en la sede no se justifica por ahora", puesto="ADP-02", reparte=1)
    for a, mot in (("ACT-082", "Tarea de planta remota (sobre semanal a sede)"),
                   ("ACT-083", "Tarea de planta remota (novedades del personal local)"),
                   ("ACT-085", "Tarea de planta remota (reunión mensual de gestión)"),
                   ("ACT-078", "En Eldorado la báscula envía el F-03 directo a Administración, sin reenvío")):
        poner(ELD, mot, act=a)
    for pl in (SB, CG, SA):  # en las plantas con esquema San Borgita, ADP-01 reenvía el F-03
        poner(pl, "Sólo Eldorado: allí el F-03 va directo a Administración", act="ACT-171")


def formularios(db):
    F = m.Formulario
    f8 = db.query(F).filter(F.codigo == "F-08").first()
    f8.emisor = "PRD-01 (Jefe de Planta), que consolida los partes por sector"
    f8.receptor = "DIR-03, a las 9:00 del día siguiente"
    log_historial(db, "formularios", f8.id, "EditarFormulario (reunión 1 y 6/10/2026)", despues={"emisor": f8.emisor, "receptor": f8.receptor})
    if not db.query(F).filter(F.codigo == "F-08.1").first():
        p = F(codigo="F-08.1", nombre="Parte de perforación", origen="Físico/Planilla", emisor="PRD-03 (Perforista)",
              receptor="PRD-01 (Jefe de Planta)", frecuencia="A definir (diario o semanal)", formulario_padre_id=f8.id,
              estructura=("Fecha | fecha | sí\nPlanta | texto | sí\nPerforista | texto | sí\n"
                          "Horómetro de la máquina | número | sí | tiene vida útil y service propios\n"
                          "Horómetro del martillo | número | sí | tiene vida útil y cambio de aceite propios\n"
                          "Metros perforados | número | sí\nProfundidad de cada pozo | número por pozo | sí\n"
                          "Novedades y anomalías | texto | no\nFallas de la perforadora | texto | no\n"
                          "NOTA: modelo propuesto a partir de la reunión del 6/10/2026; validar con el perforista y tomar como base el parte semanal del sur"))
        db.add(p)
        db.flush()
        log_historial(db, "formularios", p.id, "CrearFormulario", despues={"codigo": "F-08.1", "padre": "F-08"})
        proc = db.query(m.Procedimiento).filter(m.Procedimiento.codigo == "P-03").first()
        if proc:
            db.add(m.ProcedimientoFormulario(procedimiento_id=proc.id, formulario_id=p.id))


def contenido(db):
    def cambiar(codigo, **campos):
        x = _act(db, codigo)
        a = to_dict(x)
        for k, v in campos.items():
            setattr(x, k, v)
        log_historial(db, "actividades", x.id, "AjusteDeContenido (reuniones 1 y 6/10/2026)", antes=a, despues=to_dict(x))
    cambiar("ACT-138", descripcion="Registrar la profundidad de cada pozo perforado en el Parte de perforación (F-08.1)")
    cambiar("ACT-141", descripcion="Registrar novedades y anomalías detectadas en el Parte de perforación (F-08.1)")
    cambiar("ACT-140", puesto_codigo="PRD-01", area="Producción", nivel="N4",
            descripcion="Registrar y rendir los sobrantes de explosivos al polvorín inmediatamente después de cada voladura",
            notas="Pasó del Perforista (PRD-03) al Jefe de Planta el 13/10/2026: es quien coordina la voladura.")
    cambiar("ACT-127", descripcion="Completar y enviar el parte diario F-08, que consolida los partes por sector, antes de las 9:00 del día siguiente")
    p7 = db.query(m.Procedimiento).filter(m.Procedimiento.codigo == "P-07").first()
    a = to_dict(p7)
    p7.descripcion = p7.descripcion.replace("al Gerente de Producción antes de las 18:00",
                                            "al Gerente de Producción antes de las 9:00 del día siguiente")
    p7.descripcion = p7.descripcion.replace("Registrar todo lo que ocurrió", "Registrar (lo carga el Jefe de Planta, consolidando los partes por sector) todo lo que ocurrió", 1)
    log_historial(db, "procedimientos", p7.id, "AjusteDeContenido (reuniones 1 y 6/10/2026)", antes=a, despues=to_dict(p7))


def reiniciar_asignaciones(db):
    n = 0
    for a in db.query(m.Asignacion).filter(m.Asignacion.estado.in_(["activa", "transicion"])).all():
        antes = to_dict(a)
        a.estado, a.fecha_fin_real = "finalizada", HOY
        a.condicion_salida = "Reinicio de asignaciones v3.7 (13/10/2026): se recarga a mano desde cero"
        log_historial(db, "asignaciones", a.id, "ReinicioDeAsignaciones", antes=antes, despues=to_dict(a))
        n += 1
    for pf in db.query(m.Perfil).filter(m.Perfil.origen == "individual", m.Perfil.estado != "archivado").all():
        pf.estado = "archivado"
        log_historial(db, "perfiles", pf.id, "ArchivarPerfil (reinicio v3.7)")
    return n


def main(ruta_db=None):
    db = SessionLocal()
    try:
        r = personas(db)
        fusionar_bascula(db)
        aplicabilidad(db)
        formularios(db)
        contenido(db)
        n = reiniciar_asignaciones(db)
        db.commit()
        print(f"Personas nuevas: {len(r['nuevas'])} · actualizadas: {len(r['actualizadas'])} · asignaciones finalizadas: {n}")
        print("Nuevas:", "; ".join(r["nuevas"]))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
