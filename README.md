# Cantera Eldorado — SGO v3 (ontología por objetos)

Reconstrucción completa del sistema sobre el modelo de ontología (Object Types /
Link Types / Action Types / Functions) definido en `Ontologia_Cantera_Eldorado_v2.md`.
No es una actualización de la v2 — es una base nueva, con los datos migrados
automáticamente desde ahí.

## Estado del proyecto — importante antes de usarlo

**Construido y probado (Etapas 1 a 5, más historial, acciones sueltas y PDF):**
- Esquema físico completo (24 tablas) + migración verificada desde la base v2 (cero pérdida de datos)
- Backend organizado por Object Type, con las Actions: `AsignarPersonaAPuesto`, `FinalizarAsignacion`, `ReasignarPuesto`, `AsignarActividadSuelta`, `RegistrarCumplimientoDeMecanismo`, `CargarMedicionDeIndicador`, `ExtinguirRolDeTransicion`, `ConfirmarHabilitacion`
- **Ocho fichas de objeto**, todas conectadas entre sí por links reales: Persona, Puesto, Planta, Actividad, Mecanismo, Procedimiento, Indicador, Formulario
- **Listados** de los ocho tipos de objeto, más un **buscador** que cubre personas, puestos, actividades, mecanismos, plantas y formularios
- **Dashboard** con el resumen general, la bandeja de pendientes priorizada, Alertas y Riesgo de dependencia
- **Historial de auditoría**, con pantalla propia (`/ui/historial`) filtrable por tabla
- **Exportar a PDF**: la ficha de cualquier Puesto, el Reporte mensual de indicadores completo, y el Organigrama (teórico o real, por planta)
- **Organigrama interactivo** (`/ui/organigrama`): árbol con zoom, paneo y ramas plegables, en dos modos — Teórico (la estructura del manual) y Real (quién ocupa cada puesto hoy, por planta, con las vacantes resaltadas). El PDF se genera sin depender de un navegador en el servidor — el árbol se recalcula en Python puro (`organigrama_svg.py`) y se convierte con svglib, liviano para desplegar en Render
- **Actividades sueltas de otro puesto, desde la ficha de Persona** (2 de octubre de 2026): en "Agregar una nueva cobertura" ahora hay un selector de modo — *Puesto completo* (como antes) o *Actividades sueltas de otro puesto*. En el segundo modo se elige el puesto de origen, aparecen sus actividades como casilleros para tildar, y al confirmar se ejecuta `AsignarActividadSuelta` (Opción B): crea o reutiliza el Perfil personal "Ajustes individuales — {Nombre}" de esa persona y le vincula las actividades elegidas, sin tocar su puesto formal. Maneja conflictos de exclusividad igual que el modo de puesto completo. Cargado con el primer caso real: Tiki (DIR-02) + las 7 actividades de Tesorería y Pagos (ADM-04) — es el caso TRANS-02 de la planilla de roles de transición.
- **Formulario como objeto propio de la ontología** (2 de octubre de 2026): nuevo Object Type `Formulario` (tabla `formularios`, migración Alembic) con dos Link Types nuevos — `ProcedimientoFormulario` y `MecanismoFormulario` — que conectan cada formulario con los procedimientos y mecanismos que lo generan o usan. Ficha propia (`/ui/formularios/{codigo}`) con alta, edición y baja completas (es el único objeto del sistema que admite borrado físico real, porque es metadata simple sin historia encadenada — cada alta, edición y baja queda igual registrada en el Historial de auditoría). Pestaña "Formularios" agregada a la navegación principal y a las fichas de Procedimiento y Mecanismo. Cargado con los 11 formularios reales (F-01 a F-11) y sus vínculos reales con procedimientos y mecanismos, tomados de la planilla.
- **CRUD completo con baja lógica para los 7 objetos principales** (3 de octubre de 2026): Puesto, Actividad, Planta, Persona, Mecanismo, Procedimiento e Indicador ahora tienen pantalla propia de **alta** (botón "+ Nuevo..." en cada listado), **edición** (botón "Editar" en la ficha) y **baja** (botón "Dar de baja" en la ficha, con confirmación). A diferencia de Formulario, acá **nunca se borra físicamente un registro** — dar de baja cambia el campo de estado propio de cada objeto (`vigente`, `activo` o `estado` según el caso) y el registro sigue existiendo, con su historial completo, pudiendo **reactivarse** con el botón "Dar de alta". Los listados muestran por defecto solo los vigentes, con un link "Ver también dados de baja" para mostrar todos (los dados de baja aparecen atenuados y con la etiqueta **BAJA**). Procedimiento necesitó una migración nueva (columna `vigente`) porque era el único de los 7 sin ningún campo de estado. De paso se completó el registro en el Historial de auditoría de `crear`/`editar` para Puesto, Actividad, Planta y Persona, que ya existían en la API pero no quedaban auditados. Mecanismo, Procedimiento e Indicador no tenían API de alta/edición hasta ahora — se agregó (`/api/mecanismos`, `/api/procedimientos` nuevo, `/api/indicadores` nuevo).
- **Descripción general (Propósito y Alcance) de los 17 procedimientos** (3 de octubre de 2026): cargada en el campo `descripcion` de cada Procedimiento, tomada de la Parte V de la planilla. La ficha ya no muestra el cartel de "pendiente" y respeta el salto de línea entre Propósito y Alcance.
- **Nombre del indicador KPI-F04 corregido** (3 de octubre de 2026): "Margen bruto por planta" → "Margen bruto por planta (%)", para que coincida con la planilla. Sin cambios en fórmula, umbrales ni responsables.
- **Reparto de actividades y reportes por persona** (5 de octubre de 2026): 
  - *Cesiones (Opción A)*: la persona titular conserva su puesto y las actividades que se pasan a otra quedan registradas como "cedidas" en su asignación (tabla nueva `actividades_cedidas`, migración `4afec79fdaed`). Las actividades efectivas de un titular = las del puesto menos las cedidas; quien las recibe las lleva en su perfil individual. El organigrama no cambia. Las cesiones se heredan si el puesto cambia de titular.
  - *Ficha de Persona*: sección "Actividades a cargo" (propias del puesto, cedidas, y sueltas con su puesto de origen); contador "N de M" y casillero "todas" al elegir actividades sueltas; opción de asignar "el resto" a otra persona; botón "Asignar el puesto sin esas actividades" ante un conflicto.
  - *Reparto por puesto* (`/ui/reparto/{puesto}`): una fila por actividad con quién la lleva (del puesto, trasladada, doble cobertura o sin responsable) y un selector para moverla; botón "asignar las sin responsable a...".
  - *Reportes* (`/ui/reportes`): detalle por persona (HTML y Excel), tablero de cobertura por puesto (HTML y Excel, con las actividades sin cubrir) y **Ficha de reestructuración en PDF** por persona.
  - *Impacto de una salida*: antes de finalizar una cobertura o dar de baja a una persona se muestran las actividades que quedarían sin responsable y se reasignan en el mismo paso. Nada se borra; un perfil individual sin asignaciones se archiva.
  - *Migración automática*: al arrancar, la app aplica las migraciones pendientes de Alembic.

**Afuera a propósito:**
- Comparador de puestos — decisión de Jamaica, cada Puesto ya tiene ficha propia y navegable

**Recodificación de puestos (2 de octubre de 2026) — aplicada:**
Se migró `cantera.db` a la codificación vigente según `Cantera_Eldorado_Inventario.xlsx`: ADM-06/06-A/06-B pasaron a ADP-01/02/03 (nueva serie, Administrativos de Planta Tipo), ADM-07/08/09 bajaron a ADM-06/07/08, PRD-02 (Jefe de Planta) pasó a PRD-01, PRD-06-C (Jefe de Taller Central) pasó a PRD-02, y TRS-01 pasó a TRANS-01. Cambio 1 a 1, sin altas ni bajas de puesto — remapeado en todas las tablas que referencian `puesto_codigo` (incluidas menciones embebidas en texto libre). El Historial de auditoría no se tocó — queda con los códigos vigentes al momento de cada hecho. Backup de la base previa a la migración: `cantera_pre_recodificacion_2026-10-02.db`. Verificado: 0 códigos huérfanos, conteos de todas las tablas idénticos antes/después, servidor, fichas, organigrama y exportación a PDF probados tras la migración.

De la misma planilla quedaron resueltos dos pendientes que estaban sin datos: los 11 formularios (F-01 a F-11, ya cargados con pestaña propia — Fase 2) y los 6 roles de transición completos (TRANS-01 a TRANS-06 — TRANS-01 es el único puesto formal; TRANS-02 ya cargado como caso real de Fase 1, TRANS-03 a TRANS-06 pendientes a criterio de Jamaica).

**Pendiente:**
- Login individual con roles — pausado por ahora a pedido del cliente
- Cargar los casos reales de actividades sueltas y puestos vacantes (TRANS-03 a TRANS-06, ADP-01 en Eldorado, etapa de los 4 casos de Trituración en San Borgita) — a cargo del equipo de Cantera Eldorado desde las pantallas ya construidas
- Revisar y actualizar el texto de las actividades de 7 puestos (ADM-05, ADM-06, ADM-08, ADP-03, PRD-05, PRD-06, PRD-07) contra la versión más nueva de la planilla — el detalle fila por fila está en el documento "Revisión de actividades — sistema vs. planilla (Fase 4)" guardado en el proyecto; es una decisión de contenido, no de carga mecánica
- 42 de 97 pasos de procedimiento con responsabilidad conjunta o secuencial, sin un solo responsable — quedan con el texto original, no se fuerza a un solo puesto (decisión ya tomada, no es una tarea abierta)

## Cómo correrlo local

```
cd app
python -m venv venv
venv\Scripts\activate        (Windows)
source venv/bin/activate     (Mac/Linux)
pip install -r requirements.txt
cd backend
python -m uvicorn main:app --reload --port 8000
```

Abrir **http://localhost:8000** — redirige directo al Dashboard.
Usuario/clave: `eldorado` / `cantera2026` (los mismos de siempre; se pueden cambiar con las variables de entorno `ADMIN_USER` / `ADMIN_PASS`).

La base (`cantera.db`) ya viene con el esquema nuevo y los datos migrados — **Importante:** si ya cargaste datos propios en tu `cantera.db` (local o en Render), NO la reemplaces con la del zip: copiá solo el código. La app aplica sola la migración nueva al arrancar; conviene hacer una copia de seguridad antes. No hace falta correr nada de Alembic ni el script de migración para usarlo tal cual.

## Estructura

```
app/
  backend/
    main.py            → arma la app y conecta todos los routers
    models.py           → los 24 Object Types / Junction Objects / Link Types
    database.py          → conexión SQLAlchemy
    reparto.py             → servicio de reparto: cesiones, traslados, cobertura por puesto, impacto de salidas
    functions.py          → cálculos que se corren al vuelo (cobertura, riesgo, alertas, semáforo)
    migrar_datos.py        → el script que migró los datos desde cantera_v2_origen.db (ya ejecutado, queda de referencia)
    cantera.db             → la base con el esquema nuevo, ya poblada
    cantera_v2_origen.db    → la base v2 original, sin tocar — por si hace falta volver a migrar algo
    alembic/                → migraciones de esquema
    routers/
      plantas.py, puestos.py, personas.py, actividades.py, convenios.py,
      mecanismos.py, procedimientos.py, indicadores.py, formularios.py,
      asignaciones.py, fichas.py, dashboard.py   → API JSON (/api/...)
      ui_personas.py, ui_puestos.py, ui_plantas.py, ui_actividades.py, ui_mecanismos.py,
      ui_procedimientos.py, ui_indicadores.py, ui_formularios.py,
      ui_reparto.py, ui_reportes.py, ui_dashboard.py, ui_listados.py, ui_shared.py  → páginas htmx (/ui/...), con
      alta/edición/baja para los 7 objetos principales + Formulario
    templates/          → las páginas y fragmentos htmx
    static/             → CSS y htmx (empaquetado local, no depende de un CDN)
  requirements.txt
```

## Navegación

- `/ui/dashboard` — resumen general, bandeja de pendientes, alertas, riesgo de dependencia
- `/ui/organigrama` — árbol interactivo, teórico o real por planta, con zoom y PDF
- `/ui/listado/{puestos|personas|plantas|actividades|mecanismos|procedimientos|indicadores|formularios}` — listados, con links a cada ficha, botón "+ Nuevo..." y (salvo Formulario) link "Ver también dados de baja"
- `/ui/personas/{id}`, `/ui/puestos/{codigo}`, `/ui/plantas/{id}`, `/ui/actividades/{codigo}`, `/ui/mecanismos/{codigo}`, `/ui/procedimientos/{codigo}`, `/ui/indicadores/{codigo}` — la ficha de cada objeto, con botones Editar / Dar de baja / Dar de alta
- `/ui/{tipo}/nuevo` y `/ui/{tipo}/{id}/editar` — formularios de alta y edición para cada uno de los 7 objetos
- `/ui/reportes` — reportes por persona, cobertura por puesto, exportes Excel y PDF; `/ui/reparto/{puesto}` — reparto de actividades de un puesto
- `/api/...` — toda la API JSON, documentada automáticamente en `/docs`

## Llevarlo a red (Render + GitHub)

Ver las instrucciones que te pasó la consultoría junto con este archivo — el resumen corto es: actualizar el repo de GitHub con este contenido, y Render lo redespliega solo si ya está conectado a ese repo. Si es la primera vez, hay que crear el Web Service en Render apuntando a `app/backend` como raíz, con el comando de arranque `uvicorn main:app --host 0.0.0.0 --port $PORT`, y cargar las variables de entorno `ADMIN_USER` / `ADMIN_PASS`.
