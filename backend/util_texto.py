"""Orden alfabético que ignora tildes y mayúsculas (SQLite ordena 'Ríos' después de la 'Z')."""
import unicodedata


def sin_tildes(texto) -> str:
    t = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower().strip()


def clave_persona(p):
    return (sin_tildes(p.apellido), sin_tildes(p.nombre))


def personas_ordenadas(query):
    """Recibe un query de Persona (sin order_by) y devuelve la lista por apellido y nombre."""
    return sorted(query.all(), key=clave_persona)
