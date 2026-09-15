# Cantera Eldorado — SGO v3 (ontología por objetos)

Reconstrucción completa del sistema sobre el modelo de ontología (Object Types /
Link Types / Action Types / Functions) definido en `Ontologia_Cantera_Eldorado_v2.md`.
No es una actualización de la v2 — es una base nueva, con los datos migrados
automáticamente desde ahí.

## Estado del proyecto — importante antes de usarlo

**Construido y probado (Etapas 1 a 5):**
- Esquema físico completo (24 tablas) + migración verificada desde la base v2 (cero pérdida de datos)
- Backend organizado por Object Type, con las Actions: `AsignarPersonaAPuesto`, `FinalizarAsignacion`, `ReasignarPuesto`, `AsignarActividadSuelta`, `RegistrarCumplimientoDeMecanismo`, `CargarMedicionDeIndicador`
- **Siete fichas de objeto**, todas conectadas entre sí por links reales: Persona, Puesto, Planta, Actividad, Mecanismo, Procedimiento, Indicador
- **Listados** de los siete tipos de objeto — la navegación ya no depende de saber un código de memoria
- **Dashboard** con el resumen general, la bandeja de pendientes priorizada, Alertas y Riesgo de dependencia
- **Historial de auditoría** conectado en todas las Actions — quién cambió qué y cuándo
- Semáforo de KPIs calculado al vuelo, incluso para los indicadores cualitativos (se resuelve por coincidencia exacta de texto contra el umbral, sin necesitar que nadie elija un color a mano)

**Afuera a propósito:**
- Comparador de puestos — decisión de Jamaica, cada Puesto ya tiene ficha propia y navegable

**Pendiente (no forma parte de esta entrega):**
- Login individual con roles
- Exportar a PDF
- Datos por completar: TRS-01 (puesto absorbente y fecha), etapa de los 4 casos reales de Trituración en San Borgita, confirmar si ADM-06 en Eldorado es un hueco real, la diferencia de 1 indicador contra el informe, la descripción general de los 17 procedimientos (Parte V del manual)
- 42 de 97 pasos de procedimiento con responsabilidad conjunta o secuencial, sin un solo responsable — quedan con el texto original, no se fuerza a un solo puesto

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

La base (`cantera.db`) ya viene con el esquema nuevo y los datos migrados — no hace falta correr nada de Alembic ni el script de migración para usarlo tal cual.

## Estructura

```
app/
  backend/
    main.py            → arma la app y conecta todos los routers
    models.py           → los 24 Object Types / Junction Objects / Link Types
    database.py          → conexión SQLAlchemy
    functions.py          → cálculos que se corren al vuelo (cobertura, riesgo, alertas, semáforo)
    migrar_datos.py        → el script que migró los datos desde cantera_v2_origen.db (ya ejecutado, queda de referencia)
    cantera.db             → la base con el esquema nuevo, ya poblada
    cantera_v2_origen.db    → la base v2 original, sin tocar — por si hace falta volver a migrar algo
    alembic/                → migraciones de esquema
    routers/
      plantas.py, puestos.py, personas.py, actividades.py, convenios.py,
      mecanismos.py, asignaciones.py, fichas.py, dashboard.py   → API JSON (/api/...)
      ui_personas.py, ui_puestos.py, ui_plantas.py, ui_dashboard.py, ui_shared.py  → páginas htmx (/ui/...)
    templates/          → las páginas y fragmentos htmx
    static/             → CSS y htmx (empaquetado local, no depende de un CDN)
  requirements.txt
```

## Navegación

- `/ui/dashboard` — resumen general, bandeja de pendientes, alertas, riesgo de dependencia
- `/ui/listado/{puestos|personas|plantas|actividades|mecanismos|procedimientos|indicadores}` — listados, con links a cada ficha
- `/ui/personas/{id}`, `/ui/puestos/{codigo}`, `/ui/plantas/{id}`, `/ui/actividades/{codigo}`, `/ui/mecanismos/{codigo}`, `/ui/procedimientos/{codigo}`, `/ui/indicadores/{codigo}` — la ficha de cada objeto
- `/api/...` — toda la API JSON, documentada automáticamente en `/docs`

## Llevarlo a red (Render + GitHub)

Ver las instrucciones que te pasó la consultoría junto con este archivo — el resumen corto es: actualizar el repo de GitHub con este contenido, y Render lo redespliega solo si ya está conectado a ese repo. Si es la primera vez, hay que crear el Web Service en Render apuntando a `app/backend` como raíz, con el comando de arranque `uvicorn main:app --host 0.0.0.0 --port $PORT`, y cargar las variables de entorno `ADMIN_USER` / `ADMIN_PASS`.
