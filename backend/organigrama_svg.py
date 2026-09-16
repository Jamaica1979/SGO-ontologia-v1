"""
Renderiza el árbol organizacional a SVG directamente en Python — sin
navegador de por medio. Usa el mismo algoritmo de layout que static/organigrama.js
(mismas constantes, mismo criterio de posicionamiento), pero siempre con el
árbol completo desplegado, porque un PDF no tiene un lector plegando ramas.
Se eligió este camino en vez de capturar la página con un navegador headless
para no depender de Chromium en el deploy (pesado e innecesario para un PDF).
"""
NODE_W, NODE_H, H_GAP, V_GAP = 190, 64, 26, 80
AREA_COLOR = {"Dirección": "#7F6000", "Producción": "#0A2640", "Administración": "#1B3A5C",
              "Comercial": "#8A5A00", "Mantenimiento": "#5A6B7A"}


def _medir(nodo, profundidad):
    nodo["_depth"] = profundidad
    if not nodo["hijos"]:
        nodo["_width"] = NODE_W
        return nodo["_width"]
    total = sum(_medir(h, profundidad + 1) + H_GAP for h in nodo["hijos"]) - H_GAP
    nodo["_width"] = max(NODE_W, total)
    return nodo["_width"]


def _ubicar(nodo, x_centro):
    nodo["_x"], nodo["_y"] = x_centro, nodo["_depth"] * (NODE_H + V_GAP)
    if not nodo["hijos"]:
        return
    cursor = x_centro - nodo["_width"] / 2
    for h in nodo["hijos"]:
        _ubicar(h, cursor + h["_width"] / 2)
        cursor += h["_width"] + H_GAP


def _todos(nodo, out):
    out.append(nodo)
    for h in nodo["hijos"]:
        _todos(h, out)
    return out


def _esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def renderizar_svg(arbol: dict, modo: str) -> str:
    _medir(arbol, 0)
    _ubicar(arbol, 0)
    nodos = _todos(arbol, [])
    min_x = min(n["_x"] - n["_width"] / 2 for n in nodos) - 20
    max_x = max(n["_x"] + n["_width"] / 2 for n in nodos) + 20
    max_y = max(n["_y"] for n in nodos) + NODE_H + 20
    ancho, alto = max_x - min_x, max_y

    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x} 0 {ancho} {alto}" '
              f'width="{ancho}" height="{alto}" font-family="Helvetica,Arial,sans-serif">',
              '<rect x="{}" y="0" width="{}" height="{}" fill="white"/>'.format(min_x, ancho, alto)]

    # líneas de conexión primero, para que queden detrás de las cajas
    for n in nodos:
        for h in n["hijos"]:
            x1, y1, x2, y2 = n["_x"], n["_y"] + NODE_H, h["_x"], h["_y"]
            my = (y1 + y2) / 2
            partes.append(f'<path d="M{x1},{y1} L{x1},{my} L{x2},{my} L{x2},{y2}" '
                          f'stroke="#C7D0DA" stroke-width="1.5" fill="none"/>')

    for n in nodos:
        x, y = n["_x"] - NODE_W / 2, n["_y"]
        vac = modo == "real" and n.get("vacante")
        color_area = AREA_COLOR.get(n["area"], "#6B7785")
        if vac:
            caja = f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="8" fill="#FBEAEA" stroke="#B0413E" stroke-width="1.5" stroke-dasharray="4,3"/>'
        else:
            caja = (f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="8" fill="white" '
                    f'stroke="#DDE4EC" stroke-width="1.5"/>')
        partes.append(caja)
        partes.append(f'<rect x="{x}" y="{y}" width="5" height="{NODE_H}" fill="{color_area}"/>')
        partes.append(f'<text x="{x+14}" y="{y+22}" font-size="12" font-weight="bold" fill="#0A2640">{_esc(n["codigo"])}</text>')
        partes.append(f'<text x="{x+14}" y="{y+38}" font-size="11" fill="#1A1A1A">{_esc(n["nombre"])}</text>')
        if modo == "real":
            texto = "vacante" if vac else _esc(", ".join(n.get("ocupantes", [])))[:34]
            color_txt = "#B0413E" if vac else "#6B7785"
            peso = "bold" if vac else "normal"
            partes.append(f'<text x="{x+14}" y="{y+54}" font-size="11" fill="{color_txt}" font-weight="{peso}">{texto}</text>')

    partes.append("</svg>")
    return "".join(partes)
