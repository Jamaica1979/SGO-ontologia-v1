"""
Posiciones dentro de un puesto (v3.9) — única fuente de la regla.

Antes la «etapa» (primaria / secundaria) estaba fija en el código para PRD-04 y
PRD-05 y generaba tres filas por planta (primaria, secundaria y «sin etapa").
Ahora las posiciones son un dato del puesto (tabla `posiciones`):

  - Un puesto SIN posiciones se asigna como siempre: persona + planta.
  - Un puesto CON posiciones exige elegir una al asignar. La clave elegida se
    guarda en Asignacion.etapa (nombre de columna heredado).
  - Cada actividad del puesto es común (Actividad.posicion = NULL) o propia de
    una posición. El titular de una posición lleva las comunes + las de su posición.
  - Una asignación sin posición a un puesto que las tiene (dato viejo o cargado
    por API) se considera «sin posición» y cubre el puesto completo.
"""
from sqlalchemy.orm import Session
import models as m

MOMENTOS = [("antes", "Antes de arrancar"), ("durante", "Durante la jornada"),
            ("cierre", "Al cerrar la jornada"), ("falla", "Ante una falla")]
MOMENTO_TXT = dict(MOMENTOS)
SIN_POSICION = "sin_etapa"   # valor interno del ámbito «sin posición» en la cobertura (heredado)

_cache = None   # {puesto_codigo: [(clave, nombre)]} — sólo para mostrar nombres en las plantillas


def invalidar_cache():
    global _cache
    _cache = None


def posiciones_de(db: Session, puesto_codigo, incluir_inactivas=False):
    q = db.query(m.Posicion).filter(m.Posicion.puesto_codigo == puesto_codigo)
    if not incluir_inactivas:
        q = q.filter(m.Posicion.activo == 1)
    return q.order_by(m.Posicion.orden, m.Posicion.id).all()


def mapa_posiciones(db: Session):
    """{puesto_codigo: [clave, ...]} de las posiciones activas, en orden."""
    out = {}
    for p in db.query(m.Posicion).filter(m.Posicion.activo == 1).order_by(m.Posicion.orden, m.Posicion.id):
        out.setdefault(p.puesto_codigo, []).append(p.clave)
    return out


def requiere_posicion(db: Session, puesto_codigo) -> bool:
    if not puesto_codigo:
        return False
    return db.query(m.Posicion).filter(m.Posicion.puesto_codigo == puesto_codigo, m.Posicion.activo == 1).first() is not None


def aplica(posicion_actividad, clave) -> bool:
    """¿Una actividad (por su posición) le corresponde a quien ocupa la posición `clave`?
    Comunes: a todos. Sin clave (asignación sin posición): todas."""
    return not posicion_actividad or not clave or posicion_actividad == clave


def normalizar(valor):
    """Normaliza lo que llega de un formulario: '', 'None', 'sin_etapa' → None."""
    return None if valor in (None, "", "None", SIN_POSICION) else valor


def validar(db: Session, puesto_codigo, clave):
    """Devuelve un mensaje de error o None. Si el puesto tiene posiciones, la clave es
    obligatoria y debe ser una de ellas; si no tiene, la clave tiene que venir vacía."""
    claves = [p.clave for p in posiciones_de(db, puesto_codigo)]
    if claves and not clave:
        nombres = ", ".join(p.nombre for p in posiciones_de(db, puesto_codigo))
        return f"{puesto_codigo} tiene posiciones: hay que indicar cuál ({nombres})."
    if clave and clave not in claves:
        if not claves:
            return None  # puesto sin posiciones: se ignora la clave (la normaliza quien llama)
        return f"La posición «{clave}» no existe en {puesto_codigo}."
    return None


def nombre(puesto_codigo, clave):
    """Nombre visible de una posición (para plantillas). Usa una caché liviana que se
    invalida al editar posiciones. Valores viejos ('primaria') se muestran tal cual."""
    global _cache
    if not clave or clave == SIN_POSICION:
        return "sin posición" if clave == SIN_POSICION else ""
    if _cache is None:
        from database import SessionLocal
        db = SessionLocal()
        try:
            _cache = {}
            for p in db.query(m.Posicion):
                _cache.setdefault(p.puesto_codigo, {})[p.clave] = p.nombre
        finally:
            db.close()
    return _cache.get(puesto_codigo, {}).get(clave) or str(clave).capitalize()


def registrar_en(templates):
    """Expone los helpers a una instancia de Jinja2Templates."""
    from ficha_puesto import lineas
    templates.env.globals.update(pos_nombre=nombre, MOMENTO_TXT=MOMENTO_TXT, MOMENTOS=MOMENTOS)
    templates.env.filters["lineas"] = lineas
