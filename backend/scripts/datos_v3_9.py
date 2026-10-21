"""Migración de DATOS de la v3.9 — fichas de puestos de producción (20/10/2026).
Se corre una sola vez; es idempotente (si se corre de nuevo, no duplica nada).

Fuente: «Fichas de puestos de producción» (20/10/2026). Decisiones del cliente:
posición como dato del puesto; códigos PRD-05 = Frente, PRD-08 = Acopio y Despacho,
PRD-09 = Ayudante de Planta; las contradicciones con lo cargado quedan como (provisorio).

  1. Puestos: PRD-04 pasa a «Operador de Planta de Trituración» con dos posiciones
     (Primario / Secundario y Terciario); PRD-05 pasa a «Operador de Carga y Acarreo de
     Frente»; se crean PRD-08 «Operador de Acopio y Despacho» y PRD-09 «Ayudante de Planta»
     (opcional: aplica en Eldorado y San Borgita, donde la nómina tiene ayudantes; no en Campo Grande ni Santa Ana).
  2. Actividades: ACT-143 a 156 se dan de baja (reemplazadas por las fichas); ACT-157
     (combustible) pasa al Jefe de Planta, que la cede al pañolero o designado; nuevas
     ACT-172 a 215, con momento de la jornada y posición. Sin renumerar.
  3. Procedimientos: P-02 y P-05 reescritos, P-06 (carga al cliente) pasa a PRD-08,
     nota provisoria en P-01; nuevos P-18 Bloqueo y etiquetado y P-19 Reglas comunes.
  4. Formularios: F-08.2 Parte de trituración y F-08.3 Parte de carga y acarreo (partes
     del F-08), modelo del F-11 con la firma de recepción; formularios de cada puesto.
  5. Relaciones y traspasos (Anexo B).

Uso:  python scripts/datos_v3_9.py   → aplica sobre backend/cantera.db (hacer copia antes)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import SessionLocal, log_historial, to_dict   # noqa: E402
import models as m                                           # noqa: E402

FECHA = "20/10/2026"
ELD, SB, CG, SA = 1, 2, 3, 4
UOCRA = 1
PROV = " (provisorio)"
NOTA_BAJA = f"Dada de baja el {FECHA}: reemplazada por las fichas de puestos de producción (v3.9)."

# ───────────────────────── puestos ─────────────────────────

PUESTOS = {
    "PRD-04": dict(
        nombre="Operador de Planta de Trituración", area="Producción", nivel="N1",
        proposito="Operar el circuito completo de trituración como una sola cadena, elaborar el producto que programó "
                  "el Jefe de Planta y mantener el circuito en marcha y seguro.",
        dotacion="Dos por planta, una por posición",
        reemplaza_a="El actual Operador de Trituración",
        alcance_inicio="Material recibido en la tolva",
        alcance_fin="Producto clasificado caído al pie de cada cinta",
        equipos=None,
        limites_autoridad="No destraba ni limpia con el equipo en marcha ni sin bloqueo y etiquetado.\n"
                          "No arranca sin haber inspeccionado su posición ni sin avisar al compañero.\n"
                          "No opera con protecciones retiradas ni con paradas de emergencia inhabilitadas.",
        medicion_desempeno="Horas de marcha sobre horas programadas.\n"
                           "Horas de parada por equipo de origen y por motivo.\n"
                           "Producto dentro de la granulometría programada.\n"
                           "Partes entregados completos y a tiempo.",
        notas_ficha="Un puesto, dos posiciones: el circuito (scalper, trituradora primaria, secundaria y terciaria, cintas y "
                    "zarandas de clasificación) funciona como una cadena; si se detiene un equipo, se detiene todo lo que está "
                    "antes. Cada operador es titular de una posición y está habilitado en la otra, para cubrir ausencias.\n"
                    "Autoridad (provisorio): cualquiera de las dos posiciones puede detener el circuito ante un riesgo de "
                    "seguridad. Solo la posición Primario da la señal de descarga al frente.\n"
                    "Las cintas intermedias entre ambas posiciones se asignan a una de las dos según el recorrido real de "
                    "cada planta (a validar).\n"
                    "Si en una planta una misma persona cubre las dos posiciones, se le asignan ambas, cada una con sus tareas y registros.",
    ),
    "PRD-05": dict(
        nombre="Operador de Carga y Acarreo de Frente", area="Producción", nivel="N1",
        proposito="Alimentar al primario con material volado, del tamaño y al ritmo que la trituración puede procesar, "
                  "sin exponerse ni exponer a otros al riesgo de la voladura.",
        dotacion="Según planta (a validar)",
        reemplaza_a="La parte de frente del actual Operador de Carga y Acarreo",
        alcance_inicio="Cuando el responsable de voladura autoriza el reingreso al frente",
        alcance_fin="Cuando el material está descargado en la tolva del primario, con la señal del operador de trituración",
        equipos="Excavadora o pala cargadora de frente (a validar)\nCamiones volcadores de acarreo (a validar)\n"
                "Martillo rompedor, si la planta lo tiene (a validar)",
        limites_autoridad="No ingresa al frente después de una voladura sin autorización.\n"
                          "No descarga en la tolva sin la señal del operador del primario.\n"
                          "No distribuye ni registra el combustible: lo recibe y firma.\n"
                          "No opera un equipo con una falla de seguridad.",
        medicion_desempeno="Horas de parada del primario por falta de material.\n"
                           "Viajes por hora de equipo trabajada.\n"
                           "Litros de combustible por hora de horómetro, por equipo.\n"
                           "Partes entregados completos y a tiempo.",
        notas_ficha="Es titular de los equipos que se le asignen: responde por el control previo, el registro de horas del "
                    "equipo y el aviso de fallas (reglas comunes, P-19).",
    ),
    "PRD-08": dict(
        nombre="Operador de Acopio y Despacho", area="Producción", nivel="N1",
        cardinalidad_esperada="una_por_planta_activa", convenio_id=UOCRA,
        proposito="Mantener los productos terminados ordenados, separados y disponibles, y cargar a cada cliente lo que "
                  "pidió, en la cantidad correcta y sin mezclar productos.",
        dotacion="Uno por planta (a validar)",
        reemplaza_a="La parte de playa del actual Operador de Carga y Acarreo",
        alcance_inicio="Cuando el producto clasificado cae al pie de cada cinta",
        alcance_fin="Cuando el camión del cliente está cargado según la orden de carga de Báscula",
        equipos="Pala cargadora frontal (a validar si la de acopio es la misma que carga para despacho)",
        limites_autoridad="No carga un camión sin orden de carga de Báscula.\n"
                          "No mezcla productos en un acopio.\n"
                          "Báscula le indica qué y cuánto cargar, pero no le da órdenes de trabajo: sigue reportando al "
                          "Jefe de Planta. La cantidad la mide la balanza.\n"
                          "No distribuye ni registra combustible. Esta tarea, que hoy realiza el maquinista de la playa con "
                          "la pala y un tanque, sale del puesto (reglas comunes, P-19).",
        medicion_desempeno="Correcciones de carga indicadas por Báscula, sobre camiones despachados.\n"
                           "Reclamos de clientes por producto mezclado o equivocado.\n"
                           "Tiempo de espera de los camiones para cargar.\n"
                           "Litros de combustible por hora de horómetro.",
        notas_ficha="Pendiente: definir el destino del material fino que separa el scalper, que puede ser un producto para "
                    "acopio o un descarte (a validar).",
    ),
    "PRD-09": dict(
        nombre="Ayudante de Planta", area="Producción", nivel="N1",
        cardinalidad_esperada="una_por_planta_activa", convenio_id=UOCRA,
        proposito="Mantener limpios los equipos y el entorno del circuito de trituración para que los operadores puedan "
                  "concentrarse en la marcha de la planta.",
        dotacion="Según planta (a validar). Existe solo en las plantas cuyo tamaño lo justifique; donde no exista, sus "
                 "tareas las realizan los operadores de trituración.",
        limites_autoridad="No opera equipos.\n"
                          "Trabaja solo sobre equipos detenidos, bloqueados y etiquetados (P-18).\n"
                          "No retira protecciones.",
        notas_ficha="Puesto opcional (a validar por la Dirección, Anexo C): aplica en Eldorado y San Borgita, donde la nómina "
                    "ya tiene ayudantes de planta; figura como «no aplica» en Campo Grande y Santa Ana. Se cambia desde "
                    "«Aplicabilidad por planta».",
    ),
}

POSICIONES = [
    # (puesto, clave, nombre, orden, inicio, fin, equipos)
    ("PRD-04", "primario", "Primario", 1, "Material recibido en la tolva",
     "Material triturado sale del primario por la cinta hacia el secundario (a validar)",
     "Tolva (a validar)\nAlimentador (a validar)\nScalper: zaranda previa que separa el material fino antes del primario (a validar)\n"
     "Trituradora primaria (a validar)"),
    ("PRD-04", "secundario", "Secundario y Terciario", 2, "Material recibido desde la cinta del primario",
     "Producto clasificado caído al pie de cada cinta",
     "Trituradoras secundaria y terciaria (a validar)\nZarandas (a validar)\nCintas de clasificación (a validar)"),
]

# ───────────────────────── actividades ─────────────────────────
# (código, puesto, posición, momento, orden, crítica, frecuencia, competencia, descripción)
ACTIVIDADES = [
    # Ficha 1 — Operador de Carga y Acarreo de Frente
    ("ACT-172", "PRD-05", None, "antes", 1, 1, "Diaria", "Verificación de equipos",
     "Realizar el control previo de cada equipo a su cargo: niveles, neumáticos u orugas, frenos, luces y pérdidas. "
     "El control no se anota; si encuentra una falla, la informa" + PROV),
    ("ACT-173", "PRD-05", None, "antes", 2, 1, "En cada voladura", "Seguridad en voladura",
     "Reingresar al frente solo con la autorización expresa del responsable de voladura"),
    ("ACT-174", "PRD-05", None, "durante", 3, 1, "Diaria", "Operación de equipos pesados",
     "Cargar el material volado según la secuencia que indique el Jefe de Planta, separando los bolones (bloques "
     "demasiado grandes para entrar en la boca del primario)"),
    ("ACT-175", "PRD-05", None, "durante", 4, 0, "Diaria", "Operación de martillo rompedor",
     "Reducir los bolones con el martillo rompedor antes de enviarlos a la tolva, si la planta cuenta con ese equipo (a validar)"),
    ("ACT-176", "PRD-05", None, "durante", 5, 1, "Diaria", "Operación de equipos pesados",
     "Acarrear y descargar en la tolva del primario solo con la señal del operador de trituración"),
    ("ACT-177", "PRD-05", None, "durante", 6, 0, "Diaria", "Coordinación operativa",
     "Acordar con el operador del primario el ritmo de alimentación, para evitar paradas por falta de material o por sobrecarga"),
    ("ACT-178", "PRD-05", None, "durante", 7, 1, "En cada voladura", "Seguridad en voladura",
     "Antes de cada voladura, retirar del frente los equipos y personas a su cargo y avisar al responsable de voladura "
     "que el frente está despejado (provisorio: la forma de confirmarlo la define el responsable de voladura)"),
    ("ACT-179", "PRD-05", None, "durante", 8, 0, "Diaria", "Reporte operativo",
     "Anotar en el parte todo lo que agregue a un equipo, por ejemplo «agregué 5 litros de aceite al motor»"),
    ("ACT-180", "PRD-05", None, "cierre", 9, 1, "Diaria", "Reporte operativo",
     "Completar el parte con horas trabajadas, lectura del horómetro (el contador de horas de uso del equipo), viajes o "
     "ciclos y combustible recibido, y entregarlo en la oficina al retirarse"),
    ("ACT-181", "PRD-05", None, "falla", 10, 1, "Eventual", "Comunicación operativa",
     "Informar de inmediato al Jefe de Taller local y no operar un equipo con una falla de seguridad hasta que sea liberado" + PROV),
    # Ficha 2 — Operador de Planta de Trituración: tareas de ambas posiciones
    ("ACT-182", "PRD-04", None, "antes", 1, 1, "Diaria", "Verificación de equipos",
     "Inspeccionar los equipos de su posición: trituradoras, cintas, rodillos, empalmes, alineación, mallas, protecciones "
     "y paradas de emergencia. La inspección no se anota; si encuentra una falla, la informa" + PROV),
    ("ACT-183", "PRD-04", None, "antes", 2, 1, "Diaria", "Coordinación operativa",
     "Avisar al compañero de la otra posición antes de arrancar"),
    ("ACT-184", "PRD-04", None, "antes", 3, 1, "Diaria", "Operación de trituradora",
     "Arrancar el circuito en la secuencia establecida, de atrás hacia adelante (P-02)"),
    ("ACT-185", "PRD-04", None, "durante", 4, 1, "Diaria", "Operación de trituradora",
     "Vigilar temperatura, ruido y vibración de los equipos de su posición"),
    ("ACT-186", "PRD-04", None, "durante", 5, 1, "Eventual", "Seguridad laboral",
     "Destrabar o limpiar solo con el equipo detenido, bloqueado y etiquetado (P-18)"),
    ("ACT-187", "PRD-04", None, "durante", 6, 1, "Diaria", "Reporte operativo",
     "Registrar cada parada en el momento en que ocurre, con el equipo que la originó y el motivo: falta de material, "
     "falla de equipo, atasco u otro"),
    ("ACT-188", "PRD-04", None, "durante", 7, 0, "Diaria", "Reporte operativo",
     "Anotar en el parte todo lo que agregue a un equipo"),
    ("ACT-189", "PRD-04", None, "cierre", 8, 1, "Diaria", "Operación de trituradora",
     "Detener el circuito en la secuencia establecida, cortando primero la alimentación (P-02)"),
    ("ACT-190", "PRD-04", None, "cierre", 9, 0, "Diaria", "Mantenimiento básico",
     "Realizar la lubricación y limpieza diaria de su posición"),
    ("ACT-191", "PRD-04", None, "cierre", 10, 1, "Diaria", "Reporte operativo",
     "Completar y firmar su sección del parte de trituración y entregarlo en la oficina al retirarse"),
    ("ACT-192", "PRD-04", None, "falla", 11, 1, "Eventual", "Comunicación operativa",
     "Informar de inmediato al Jefe de Taller local y no operar con protecciones retiradas ni con paradas de emergencia "
     "inhabilitadas" + PROV),
    # posición Primario
    ("ACT-193", "PRD-04", "primario", "durante", 12, 1, "Diaria", "Operación de trituradora",
     "Regular la alimentación y dar al operador de frente la señal para descargar en la tolva"),
    ("ACT-194", "PRD-04", "primario", "durante", 13, 1, "Diaria", "Operación de trituradora",
     "Vigilar el scalper, la boca del primario y los bolones; indicar al frente que suspenda la descarga cuando el "
     "primario no pueda recibir material"),
    ("ACT-195", "PRD-04", "primario", "durante", 14, 0, "Diaria", "Operación de trituradora",
     "Ajustar la abertura del primario según el programa del Jefe de Planta"),
    # posición Secundario y Terciario
    ("ACT-196", "PRD-04", "secundario", "durante", 15, 1, "Diaria", "Operación de trituradora",
     "Ajustar las aberturas del secundario y del terciario y las mallas de las zarandas según el producto programado"),
    ("ACT-197", "PRD-04", "secundario", "durante", 16, 1, "Diaria", "Control de calidad",
     "Controlar la granulometría (el tamaño de la piedra) del producto que sale por cada cinta"),
    ("ACT-198", "PRD-04", "secundario", "durante", 17, 0, "Diaria", "Operación de trituradora",
     "Vigilar derrames, desalineación y atascamientos en las cintas de clasificación y en las zarandas"),
    ("ACT-199", "PRD-04", "secundario", "durante", 18, 0, "Diaria", "Coordinación operativa",
     "Avisar al operador de acopio qué producto sale por cada cinta"),
    # Ficha 3 — Operador de Acopio y Despacho
    ("ACT-200", "PRD-08", None, "antes", 1, 1, "Diaria", "Verificación de equipos",
     "Realizar el control previo de la pala cargadora. El control no se anota; si encuentra una falla, la informa" + PROV),
    ("ACT-201", "PRD-08", None, "durante", 2, 1, "Diaria", "Operación de equipos pesados",
     "Retirar el material del pie de cinta y trasladarlo a la playa de acopio, separado por producto"),
    ("ACT-202", "PRD-08", None, "durante", 3, 1, "Diaria", "Gestión de acopios",
     "Mantener los acopios ordenados, señalizados y sin mezcla entre productos"),
    ("ACT-203", "PRD-08", None, "durante", 4, 1, "Diaria", "Despacho",
     "Cargar los camiones de clientes según la orden de carga emitida por Báscula, con el producto y la cantidad indicados"),
    ("ACT-204", "PRD-08", None, "durante", 5, 0, "Eventual", "Despacho",
     "Corregir excesos o faltantes de carga cuando Báscula lo indique"),
    ("ACT-205", "PRD-08", None, "durante", 6, 0, "Eventual", "Coordinación operativa",
     "Cuando no haya despacho ni material para retirar, realizar las tareas que asigne el Jefe de Planta (orden de "
     "playa, limpieza, apoyo a otros tramos)"),
    ("ACT-206", "PRD-08", None, "durante", 7, 0, "Diaria", "Reporte operativo",
     "Anotar en el parte todo lo que agregue a la pala"),
    ("ACT-207", "PRD-08", None, "cierre", 8, 1, "Diaria", "Reporte operativo",
     "Completar el parte con horas trabajadas, horómetro, movimientos de material por producto y combustible recibido, "
     "y entregarlo en la oficina al retirarse"),
    ("ACT-208", "PRD-08", None, "falla", 9, 1, "Eventual", "Comunicación operativa",
     "Informar de inmediato al Jefe de Taller local y no operar la pala con una falla de seguridad" + PROV),
    # Ficha 4 — Ayudante de Planta (opcional)
    ("ACT-209", "PRD-09", None, "durante", 1, 0, "Diaria", "Mantenimiento básico",
     "Limpiar derrames bajo las cintas, las zarandas y las trituradoras"),
    ("ACT-210", "PRD-09", None, "durante", 2, 0, "Diaria", "Mantenimiento básico",
     "Retirar el material acumulado en rodillos y estructuras"),
    ("ACT-211", "PRD-09", None, "durante", 3, 0, "Diaria", "Mantenimiento básico",
     "Apoyar al operador en la lubricación diaria, bajo su indicación"),
    ("ACT-212", "PRD-09", None, "durante", 4, 0, "Eventual", "Comunicación operativa",
     "Informar al operador cualquier anomalía que observe: ruidos, pérdidas, cintas desalineadas"),
    # Jefe de Planta: lo que las fichas le asignan y hoy no tiene (provisorio)
    ("ACT-213", "PRD-01", None, None, None, 1, "Diaria", "Planificación de producción",
     "Fijar el programa diario de producción (producto a elaborar y secuencia de carga en el frente) y comunicarlo a los "
     "puestos de producción" + PROV),
    ("ACT-214", "PRD-01", None, None, None, 1, "Semanal", "Control de combustible",
     "Controlar una vez por semana los litros de combustible entregados contra las horas de horómetro, por equipo" + PROV),
    ("ACT-215", "PRD-01", None, None, None, 0, "Eventual", "Gestión de RRHH",
     "Mantener la matriz de polivalencia de la planta: titular y habilitados de cada equipo (a validar: requiere el "
     "inventario de equipos)"),
]

# ───────────────────────── procedimientos ─────────────────────────
# pasos: (número, título, descripción, puesto responsable | None, texto responsable | None, documento)
P02_PASOS = [
    (1, "Inspeccionar la posición", "Cada operador inspecciona los equipos de su posición antes de arrancar. No se anota; "
        "si encuentra una falla, la informa al Jefe de Taller local (provisorio).", "PRD-04", None, "—"),
    (2, "Avisar al compañero", "Avisar al operador de la otra posición antes de arrancar.", "PRD-04", None, "—"),
    (3, "Arranque de atrás hacia adelante", "Cintas de producto, zarandas, terciario, secundario, cintas intermedias, "
        "primario, scalper y, por último, alimentador. Así ningún equipo recibe material mientras el siguiente está "
        "detenido (provisorio: a validar por el Jefe de Planta).", "PRD-04", None, "—"),
    (4, "Operación", "Vigilar temperatura, ruido y vibración; registrar cada parada en el momento, con el equipo que la "
        "originó y el motivo. Destrabar o limpiar sólo con el equipo detenido, bloqueado y etiquetado (P-18).",
        "PRD-04", None, "F-08.2"),
    (5, "Parada cortando primero la alimentación", "Alimentador, scalper, primario, vaciado de cintas, secundario, "
        "terciario y zarandas. Si el circuito recircula material, se agrega un paso de vaciado (a validar).",
        "PRD-04", None, "—"),
    (6, "Lubricación, limpieza y parte", "Lubricación y limpieza diaria de cada posición. Cada operador completa y firma "
        "su sección del Parte de trituración y lo entrega en la oficina al retirarse.", "PRD-04", None, "F-08.2"),
]
P05_PASOS = [
    (1, "Control previo del equipo", "Niveles, neumáticos u orugas, frenos, luces y pérdidas. No se anota; si hay una "
        "falla, se informa al Jefe de Taller local (provisorio).", "PRD-05", None, "—"),
    (2, "Reingreso al frente", "Sólo con la autorización expresa del responsable de voladura.", "PRD-05", None, "—"),
    (3, "Cargar y separar bolones", "Según la secuencia que indica el Jefe de Planta; los bolones se reducen con el "
        "martillo rompedor si la planta lo tiene.", "PRD-05", None, "—"),
    (4, "Descargar en la tolva con señal", "Sólo con la señal del operador del primario; el ritmo de alimentación se "
        "acuerda directamente entre ambos.", None, "PRD-05 ↔ PRD-04 (posición Primario)", "—"),
    (5, "Registrar en el parte", "Horas, horómetro, viajes o ciclos, combustible recibido y lo agregado a los equipos, en "
        "el Parte de carga y acarreo; se entrega en la oficina al retirarse.", "PRD-05", None, "F-08.3"),
]
P18 = dict(codigo="P-18", nombre="Bloqueo y etiquetado antes de intervenir un equipo", area="Producción", nivel_riesgo="alto",
           descripcion="Propósito: que nadie toque, destrabe, limpie o repare un equipo que pueda ponerse en marcha.\n\n"
                       "Alcance: todos los equipos de las plantas. Si intervienen varias personas, cada una coloca su "
                       "candado; el equipo no se arranca hasta que se retire el último.")
P18_PASOS = [
    (1, "Cortar la energía", "Cortar la energía del equipo desde su tablero o llave de corte.", None, "Quien interviene", "—"),
    (2, "Bloquear con candado propio", "Bloquear ese corte con un candado propio, del que solo él tiene la llave.", None, "Quien interviene", "—"),
    (3, "Colocar la tarjeta", "Colocar una tarjeta con su nombre y la fecha.", None, "Quien interviene", "Tarjeta"),
    (4, "Verificar que no arranca", "Intentar arrancar el equipo para verificar que no arranca.", None, "Quien interviene", "—"),
    (5, "Liberar y avisar", "Al terminar, retirar herramientas y personas, sacar su propio candado y tarjeta y avisar "
        "antes de volver a arrancar.", None, "Quien interviene", "—"),
]
P19 = dict(codigo="P-19", nombre="Reglas comunes a los puestos de producción", area="Producción", nivel_riesgo="medio",
           descripcion="Reglas que forman parte de cada ficha de producción y se entregan junto con ella (Anexo A de las "
                       "fichas de puestos de producción, 20/10/2026).")
P19_PASOS = [
    (1, "Un titular por cada equipo", "Cada equipo tiene un operador titular, que responde por el control previo, el "
        "registro de horas y el aviso de fallas. Además hay operadores habilitados, que pueden reemplazarlo. Quiénes son "
        "titulares y quiénes están habilitados se registra en la matriz de polivalencia de la planta, que mantiene el "
        "Jefe de Planta.", None, "Todos los puestos de producción", "—"),
    (2, "Combustible (provisorio)", "Quien consume el combustible no lo distribuye ni lo registra. Distribuye y registra la "
        "entrega por equipo: el pañolero o la persona que designe el Jefe de Planta. Transporta el tanque hasta los equipos "
        "sobre orugas: quien maneja la pala con el tanque (transporta, pero no registra). Recibe y firma los litros: el "
        "titular del equipo. Controla litros entregados contra horas de horómetro, por equipo: el Jefe de Planta, una vez "
        "por semana.", None, "Pañolero o designado · titular del equipo · PRD-01", "F-11"),
    (3, "Lubricantes y aditivos (provisorio)", "Quien agrega aceite, refrigerante u otro fluido a un equipo lo anota en su "
        "parte, con el equipo, el producto y la cantidad. El pañolero, o quien se designe, coteja esas anotaciones con la "
        "planilla de aceite y combustible. Falta definir quién está autorizado a cargar lubricante: el operador, el "
        "mecánico o ambos.", None, "Todos los puestos de producción", "Parte de cada puesto"),
    (4, "Fallas de equipo", "Toda falla se informa de inmediato al Jefe de Taller local. Un equipo con una falla de "
        "seguridad no se opera hasta que el Jefe de Taller local lo libere (provisorio: antes se informaba al Jefe de "
        "Planta).", None, "Todos → PRD-06", "—"),
    (5, "Bloqueo y etiquetado", "Antes de tocar, destrabar, limpiar o reparar un equipo, quien interviene sigue el "
        "procedimiento P-18.", None, "Quien interviene", "—"),
    (6, "Paradas", "Toda parada del circuito se registra en el momento, con el equipo que la originó y el motivo: falta "
        "de material, falla de equipo, atasco u otro. No se completa al final de la jornada de memoria.",
        None, "Todos los puestos de producción", "F-08.2"),
    (7, "Parte diario", "Cada operador entrega su parte en papel al terminar la jornada, en la oficina de planta. El Jefe "
        "de Planta los revisa, los consolida en el parte diario de planta y los carga en el sistema antes de las 9 del "
        "día siguiente.", None, "Todos → PRD-01", "F-08"),
]

# ───────────────────────── formularios ─────────────────────────

F082 = dict(codigo="F-08.2", nombre="Parte de trituración", origen="Físico/Planilla",
            emisor="PRD-04 (cada posición firma su sección)",
            receptor="PRD-01 (Jefe de Planta), en la oficina de planta al terminar la jornada",
            frecuencia="Diaria (uno por planta y jornada)",
            estructura="Fecha | fecha | sí\nPlanta | texto | sí\nOperador de la posición Primario | texto | sí\n"
                       "Operador de la posición Secundario y Terciario | texto | sí\n"
                       "Horas de marcha | número | sí | por posición\nHorómetro | número | sí | por equipo que lo tenga\n"
                       "Paradas | lista | sí | hora, equipo que la originó, motivo (falta de material, falla de equipo, atasco u otro) y duración; se anota en el momento\n"
                       "Lo agregado a los equipos | texto | no | equipo, producto y cantidad\n"
                       "Firma de cada operador | firma | sí | uno por sección\n"
                       "NOTA: formulario provisorio, a crear como parte del parte diario de planta (fichas de producción 20/10/2026)")
F083 = dict(codigo="F-08.3", nombre="Parte de carga y acarreo", origen="Físico/Planilla",
            emisor="PRD-05 (sección frente) y PRD-08 (sección acopio y despacho)",
            receptor="PRD-01 (Jefe de Planta), en la oficina de planta al terminar la jornada",
            frecuencia="Diaria",
            estructura="Fecha | fecha | sí\nPlanta | texto | sí\nOperador | texto | sí\n"
                       "Sección | opción | sí | Frente / Acopio y despacho\nEquipo | texto | sí\n"
                       "Horas trabajadas | número | sí\nHorómetro inicial y final | número | sí\n"
                       "Viajes o ciclos | número | sí | sección frente\n"
                       "Movimientos de material por producto | lista | sí | sección acopio y despacho\n"
                       "Combustible recibido (litros) | número | sí\n"
                       "Lo agregado al equipo | texto | no | equipo, producto y cantidad\nFirma | firma | sí\n"
                       "NOTA: formulario provisorio: un parte con una sección para frente y otra para acopio y despacho (fichas de producción 20/10/2026)")
F11_ESTRUCTURA = ("Fecha | fecha | sí\nEquipo | texto | sí\nHorómetro al cargar | número | sí\nLitros entregados | número | sí\n"
                  "Quién distribuye | texto | sí | pañolero o designado por el Jefe de Planta\n"
                  "Firma del titular del equipo (recepción) | firma | sí | provisorio\n"
                  "NOTA: provisorio (20/10/2026): la firma de recepción del titular se agrega como columna del F-11 en lugar de un formulario aparte")

# (puesto, formulario, rol, para qué, cuándo y a quién, orden)
FORM_PUESTO = [
    ("PRD-05", "F-08.3", "completa", "Registrar horas, horómetro, viajes, combustible recibido y lo agregado a los equipos (sección frente)",
     "En papel, al terminar la jornada, en la oficina de planta", 1),
    ("PRD-05", "F-11", "completa", "Firmar la recepción de los litros que recibió cada equipo (provisorio)",
     "En el momento de la carga, a quien distribuye", 2),
    ("PRD-04", "F-08.2", "completa", "Registrar horas de marcha, horómetro, paradas con equipo y motivo, y lo agregado a los equipos",
     "En papel, al terminar la jornada, en la oficina de planta; cada operador firma su sección", 1),
    ("PRD-08", "F-08.3", "completa", "Registrar horas, horómetro, movimientos por producto, combustible recibido y lo agregado a la pala (sección acopio y despacho)",
     "En papel, al terminar la jornada, en la oficina de planta", 1),
    ("PRD-08", "F-11", "completa", "Firmar la recepción de los litros recibidos (provisorio)",
     "En el momento de la carga, a quien distribuye", 2),
    ("PRD-03", "F-08.1", "completa", "Registrar horómetros de máquina y martillo, metros y profundidad de cada pozo, novedades",
     "A definir (diario o semanal), al Jefe de Planta", 1),
    ("PRD-01", "F-08", "consolida", "Consolidar los partes de cada operador en el parte diario de planta",
     "Cargado en el sistema antes de las 9 del día siguiente, para la Dirección (DIR-03)", 1),
    ("PRD-01", "F-08.1", "recibe", "Parte de perforación", "Del perforista", 2),
    ("PRD-01", "F-08.2", "recibe", "Parte de trituración", "De los operadores de trituración, al terminar la jornada", 3),
    ("PRD-01", "F-08.3", "recibe", "Parte de carga y acarreo", "De los operadores de frente y de acopio, al terminar la jornada", 4),
    ("PRD-01", "F-11", "recibe", "Control semanal de litros entregados contra horas de horómetro (provisorio)",
     "Una vez por semana", 5),
]

# ───────────────────────── relaciones y traspasos ─────────────────────────

RELACIONES = [  # (puesto, relacionado, tipo) que tienen que existir
    ("PRD-08", "PRD-01", "jerarquico"), ("PRD-08", "ADP-03", "funcional"), ("PRD-08", "PRD-04", "funcional"),
    ("PRD-08", "PRD-06", "funcional"), ("PRD-09", "PRD-04", "jerarquico"), ("PRD-09", "PRD-01", "funcional"),
    ("PRD-01", "PRD-08", "funcional"), ("PRD-04", "PRD-08", "funcional"), ("PRD-05", "PRD-06", "funcional"),
    ("ADP-03", "PRD-08", "funcional"),
]
RELACIONES_FUERA = [("PRD-05", "ADP-03", "funcional"), ("ADP-03", "PRD-05", "funcional")]  # la báscula ahora habla con Acopio

VOLADURA = "Responsable de voladura (provisorio: a definir si es el Perforista o el Jefe de Planta)"
TRASPASOS = [
    # (de_puesto, de_texto, a_puesto, a_texto, qué entrega, señal)
    (None, VOLADURA, "PRD-05", None, "Autorización para reingresar al frente", "Autorización expresa"),
    ("PRD-05", None, None, VOLADURA, "Frente despejado (equipos y personas retirados)", "Aviso antes de cada voladura (provisorio)"),
    ("PRD-05", None, "PRD-04", "Operador de Planta de Trituración, posición Primario", "Material volado en la tolva",
     "Señal del operador del primario"),
    ("PRD-04", "Trituración, posición Primario", "PRD-04", "Trituración, posición Secundario y Terciario",
     "Material triturado por cinta", "Aviso mutuo antes de arrancar o detener"),
    ("PRD-04", "Trituración, posición Secundario y Terciario", "PRD-08", None, "Producto por cinta",
     "Aviso de qué producto sale por cada cinta"),
    ("ADP-03", None, "PRD-08", None, "Orden de carga con producto y cantidad", "Sin orden, no se carga"),
    ("PRD-01", None, "PRD-05", None, "Producto a elaborar y secuencia de carga en el frente", "Programa diario"),
    ("PRD-01", None, "PRD-04", None, "Producto a elaborar", "Programa diario"),
    ("PRD-01", None, "PRD-08", None, "Producto a elaborar", "Programa diario"),
    (None, "Pañolero o designado por el Jefe de Planta (provisorio)", "PRD-05", None, "Combustible",
     "Registro de entrega firmado por el titular (provisorio)"),
    (None, "Pañolero o designado por el Jefe de Planta (provisorio)", "PRD-08", None, "Combustible",
     "Registro de entrega firmado por el titular (provisorio)"),
    ("PRD-05", None, "PRD-01", None, "Parte de la jornada", "Al terminar la jornada, en la oficina"),
    ("PRD-04", None, "PRD-01", None, "Parte de la jornada (cada posición firma su sección)", "Al terminar la jornada, en la oficina"),
    ("PRD-08", None, "PRD-01", None, "Parte de la jornada", "Al terminar la jornada, en la oficina"),
    ("PRD-01", None, "DIR-03", "Dirección", "Parte diario de planta consolidado (F-08)", "Cargado en el sistema antes de las 9 del día siguiente"),
]


# ═══════════════════════ aplicación ═══════════════════════

def _log_si_cambio(db, tabla, obj, accion, antes):
    """Registra en el Historial sólo si algo cambió (así correr el script dos veces no ensucia el Historial)."""
    despues = to_dict(obj)
    limpiar = lambda d: {k: v for k, v in (d or {}).items() if k not in ("updated_at", "created_at")}
    if limpiar(antes) != limpiar(despues):
        log_historial(db, tabla, obj.id, accion, antes=antes, despues=despues)


def _act(db, codigo):
    return db.query(m.Actividad).filter(m.Actividad.codigo == codigo).first()


def _puesto(db, codigo):
    return db.query(m.Puesto).filter(m.Puesto.codigo == codigo).first()


def _form(db, codigo):
    return db.query(m.Formulario).filter(m.Formulario.codigo == codigo).first()


def _proc(db, codigo):
    return db.query(m.Procedimiento).filter(m.Procedimiento.codigo == codigo).first()


def puestos(db):
    for cod, campos in PUESTOS.items():
        p = _puesto(db, cod)
        antes = to_dict(p) if p else None
        if not p:
            p = m.Puesto(codigo=cod, vigente=1)
            db.add(p)
        for k, v in campos.items():
            setattr(p, k, v)
        db.flush()
        _log_si_cambio(db, "puestos", p, "CrearPuesto (fichas de producción)" if antes is None else "EditarPuesto (fichas de producción)", antes)
    for (pc, clave, nombre, orden, ini, fin, eq) in POSICIONES:
        x = db.query(m.Posicion).filter(m.Posicion.puesto_codigo == pc, m.Posicion.clave == clave).first()
        antes = to_dict(x) if x else None
        if not x:
            x = m.Posicion(puesto_codigo=pc, clave=clave)
            db.add(x)
        x.nombre, x.orden, x.alcance_inicio, x.alcance_fin, x.equipos, x.activo = nombre, orden, ini, fin, eq, 1
        db.flush()
        _log_si_cambio(db, "posiciones", x, "CrearPosicion (fichas de producción)" if antes is None else "EditarPosicion (fichas de producción)", antes)


def actividades(db):
    # bajas: ACT-143..156 (la 157, combustible, se reubica en el Jefe de Planta)
    for n in range(143, 157):
        x = _act(db, f"ACT-{n:03d}")
        if x and x.activo:
            a = to_dict(x)
            x.activo, x.notas = 0, NOTA_BAJA
            log_historial(db, "actividades", x.id, "DarDeBajaActividad (fichas de producción)", antes=a, despues=to_dict(x))
    x = _act(db, "ACT-157")
    if x and x.puesto_codigo != "PRD-01":
        a = to_dict(x)
        x.puesto_codigo, x.nivel = "PRD-01", "N4"
        x.descripcion = ("Distribuir el combustible a los equipos y registrar la entrega por equipo en el F-11, con la firma "
                         "del titular; la realiza el pañolero o la persona que designe el Jefe de Planta" + PROV)
        x.notas = (f"Pasó del Operador de Carga y Acarreo al Jefe de Planta el {FECHA}: quien consume el combustible no lo "
                   "distribuye ni lo registra. El Jefe de Planta la cede al pañolero o designado (reparto del puesto).")
        log_historial(db, "actividades", x.id, "ReubicarActividad (PRD-05 → PRD-01, fichas de producción)", antes=a, despues=to_dict(x))
    for (cod, puesto, pos, momento, orden, crit, frec, comp, desc) in ACTIVIDADES:
        x = _act(db, cod)
        nivel = "N4" if puesto == "PRD-01" else "N1"
        if x:
            continue  # idempotente: si ya existe no se pisa (pudo haberse editado a mano)
        x = m.Actividad(codigo=cod, descripcion=desc, area="Producción", nivel=nivel, competencia=comp, es_critica=crit,
                        frecuencia=frec, puesto_codigo=puesto, posicion=pos, momento=momento, orden=orden, activo=1,
                        notas=f"Fichas de puestos de producción ({FECHA}).")
        db.add(x)
        db.flush()
        log_historial(db, "actividades", x.id, "CrearActividad (fichas de producción)", despues=to_dict(x))


def _pasos(db, proc, pasos):
    """Reemplaza el texto de los pasos por número (actualiza los que existen, agrega los que faltan)."""
    for (num, tit, desc, resp, resp_txt, doc) in pasos:
        s = db.query(m.PasoDeProcedimiento).filter(m.PasoDeProcedimiento.procedimiento_id == proc.id,
                                                   m.PasoDeProcedimiento.numero == num).first()
        if not s:
            s = m.PasoDeProcedimiento(procedimiento_id=proc.id, numero=num)
            db.add(s)
        s.titulo, s.descripcion, s.responsable_puesto_codigo, s.responsable_texto_original, s.documento = tit, desc, resp, resp_txt, doc


def _vincular_proc(db, proc, puesto, rol="ejecuta"):
    if not db.get(m.ProcedimientoPuesto, (proc.id, puesto)):
        db.add(m.ProcedimientoPuesto(procedimiento_id=proc.id, puesto_codigo=puesto, rol=rol))


def _desvincular_proc(db, proc, puesto):
    x = db.get(m.ProcedimientoPuesto, (proc.id, puesto))
    if x:
        db.delete(x)


def _proc_form(db, proc, fcod):
    f = _form(db, fcod)
    if f and not db.get(m.ProcedimientoFormulario, (proc.id, f.id)):
        db.add(m.ProcedimientoFormulario(procedimiento_id=proc.id, formulario_id=f.id))


def formularios(db):
    f8 = _form(db, "F-08")
    for datos in (F082, F083):
        f = _form(db, datos["codigo"])
        if not f:
            f = m.Formulario(**datos, formulario_padre_id=f8.id)
            db.add(f)
            db.flush()
            log_historial(db, "formularios", f.id, "CrearFormulario (fichas de producción)", despues={"codigo": f.codigo, "padre": "F-08"})
    f11 = _form(db, "F-11")
    if f11 and not f11.estructura:
        f11.estructura = F11_ESTRUCTURA
        f11.emisor = "Pañolero o designado por el Jefe de Planta (provisorio)"
        log_historial(db, "formularios", f11.id, "EditarFormulario (fichas de producción)", despues={"estructura": "modelo con firma de recepción"})
    db.flush()
    for (pc, fcod, rol, para, cuando, orden) in FORM_PUESTO:
        f = _form(db, fcod)
        if not f:
            continue
        x = db.query(m.PuestoFormulario).filter(m.PuestoFormulario.puesto_codigo == pc, m.PuestoFormulario.formulario_id == f.id,
                                                m.PuestoFormulario.rol == rol).first()
        if not x:
            x = m.PuestoFormulario(puesto_codigo=pc, formulario_id=f.id, rol=rol)
            db.add(x)
        x.para_que, x.cuando, x.orden = para, cuando, orden


def procedimientos(db):
    p01 = _proc(db, "P-01")
    nota = ("\n\nProvisorio (20/10/2026): las fichas de puestos de producción proponen que el control previo de los equipos "
            "de producción no se anote (si hay una falla, se informa) y que las fallas se informen al Jefe de Taller local. "
            "Falta decidir si el checklist registrado se mantiene para otros equipos o se elimina.")
    if p01 and "Provisorio (20/10/2026)" not in (p01.descripcion or ""):
        a = to_dict(p01)
        p01.descripcion = (p01.descripcion or "") + nota
        log_historial(db, "procedimientos", p01.id, "AjusteDeContenido (fichas de producción)", antes=a, despues=to_dict(p01))

    p02 = _proc(db, "P-02")
    a = to_dict(p02)
    p02.descripcion = ("Propósito: estandarizar la secuencia de arranque y parada del circuito de trituración para proteger los "
                       "equipos y garantizar la calidad del producto. Se arranca desde el final del circuito hacia el principio "
                       "y se detiene cortando primero la alimentación: así ningún equipo recibe material mientras el siguiente "
                       "está detenido.\n\nAlcance: circuito de trituración de cada planta: scalper, trituradora primaria, "
                       "secundaria y terciaria, cintas y zarandas de clasificación. Lo ejecutan las dos posiciones del Operador "
                       "de Planta de Trituración.")
    _pasos(db, p02, P02_PASOS)
    _proc_form(db, p02, "F-08.2")
    _log_si_cambio(db, "procedimientos", p02, "AjusteDeContenido (fichas de producción)", a)

    p05 = _proc(db, "P-05")
    a = to_dict(p05)
    p05.nombre = "Carga, acarreo y alimentación del primario"
    p05.descripcion = ("Propósito: alimentar al primario con material volado, del tamaño y al ritmo que la trituración puede "
                       "procesar, sin exponerse ni exponer a otros al riesgo de la voladura.\n\nAlcance: desde que el "
                       "responsable de voladura autoriza el reingreso al frente hasta que el material está descargado en la "
                       "tolva del primario. La carga a clientes desde la playa de acopio pasó a P-06 (Operador de Acopio y "
                       "Despacho).")
    _pasos(db, p05, P05_PASOS)
    _desvincular_proc(db, p05, "PRD-04")
    _proc_form(db, p05, "F-08.3")
    _log_si_cambio(db, "procedimientos", p05, "AjusteDeContenido (fichas de producción)", a)

    p06 = _proc(db, "P-06")
    paso4 = db.query(m.PasoDeProcedimiento).filter(m.PasoDeProcedimiento.procedimiento_id == p06.id, m.PasoDeProcedimiento.numero == 4).first()
    if paso4:
        paso4.titulo = "Carga del material"
        paso4.descripcion = ("El Operador de Acopio y Despacho carga el producto y la cantidad de la orden de carga de Báscula; "
                             "sin orden no se carga. Corrige excesos o faltantes cuando Báscula lo indica.")
        paso4.responsable_puesto_codigo, paso4.responsable_texto_original = "PRD-08", None
    _desvincular_proc(db, p06, "PRD-05")
    _vincular_proc(db, p06, "PRD-08")

    for datos, pasos in ((P18, P18_PASOS), (P19, P19_PASOS)):
        pr = _proc(db, datos["codigo"])
        if not pr:
            pr = m.Procedimiento(**datos, vigente=1)
            db.add(pr)
            db.flush()
            log_historial(db, "procedimientos", pr.id, "CrearProcedimiento (fichas de producción)", despues=to_dict(pr))
        _pasos(db, pr, pasos)
        for pc in ("PRD-04", "PRD-05", "PRD-08", "PRD-09"):
            _vincular_proc(db, pr, pc)
    p19 = _proc(db, "P-19")
    _vincular_proc(db, p19, "PRD-01")
    for fcod in ("F-08", "F-11"):
        _proc_form(db, p19, fcod)
    p05_ = _proc(db, "P-05")
    _vincular_proc(db, p05_, "PRD-05")
    _vincular_proc(db, p02, "PRD-04")


def relaciones(db):
    R = m.RelacionReporte
    for (p, r, t) in RELACIONES:
        if not db.query(R).filter(R.puesto_codigo == p, R.relacionado_codigo == r, R.tipo == t).first():
            db.add(R(puesto_codigo=p, relacionado_codigo=r, tipo=t))
    for (p, r, t) in RELACIONES_FUERA:
        x = db.query(R).filter(R.puesto_codigo == p, R.relacionado_codigo == r, R.tipo == t).first()
        if x:
            log_historial(db, "relaciones_reporte", x.id, "QuitarRelacion (fichas de producción)", antes={"puesto": p, "relacionado": r, "tipo": t})
            db.delete(x)


def traspasos(db):
    T = m.Traspaso
    for i, (dp, dt, ap, at, que, senal) in enumerate(TRASPASOS, start=1):
        ya = db.query(T).filter(T.de_puesto_codigo == dp, T.a_puesto_codigo == ap, T.que_entrega == que,
                                T.de_texto == dt, T.a_texto == at).first()
        if not ya:
            x = T(de_puesto_codigo=dp, de_texto=dt, a_puesto_codigo=ap, a_texto=at, que_entrega=que, senal=senal, orden=i)
            db.add(x)
            db.flush()
            log_historial(db, "traspasos", x.id, "CrearTraspaso (fichas de producción)", despues=to_dict(x))


def aplicabilidad(db):
    from aplicabilidad import guardar_aplicabilidad
    # Ayudante de Planta (opcional): aplica donde la nómina ya tiene ayudantes de planta (Eldorado y San Borgita)
    for pl in (ELD, SB):
        guardar_aplicabilidad(db, pl, "aplica", puesto_codigo="PRD-09")
    for pl in (CG, SA):
        guardar_aplicabilidad(db, pl, "no_aplica", "Puesto opcional: se habilita cuando la Dirección decida que el tamaño de la planta lo justifica",
                              puesto_codigo="PRD-09")


def _migrar_esquema():
    """Por si la base todavía no tiene el esquema v3.9: aplica las migraciones de Alembic antes de usar el ORM."""
    from alembic.config import Config
    from alembic import command
    from database import DB_PATH
    base = Path(__file__).resolve().parents[1]
    cfg = Config()
    cfg.set_main_option("script_location", str(base / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")
    command.upgrade(cfg, "head")


def main():
    _migrar_esquema()
    db = SessionLocal()
    try:
        puestos(db)
        db.flush()
        actividades(db)
        formularios(db)
        db.flush()
        procedimientos(db)
        relaciones(db)
        traspasos(db)
        aplicabilidad(db)
        db.commit()
        n_act = db.query(m.Actividad).filter(m.Actividad.codigo.in_([a[0] for a in ACTIVIDADES])).count()
        print(f"Fichas de producción aplicadas: {len(PUESTOS)} puestos, {len(POSICIONES)} posiciones, {n_act} actividades nuevas, "
              f"{db.query(m.Traspaso).count()} traspasos, {db.query(m.PuestoFormulario).count()} vínculos puesto-formulario.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    from posiciones import invalidar_cache
    invalidar_cache()


if __name__ == "__main__":
    main()
