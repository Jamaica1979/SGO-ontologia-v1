(function () {
  const NODE_W = 190, NODE_H = 64, H_GAP = 26, V_GAP = 80;
  const AREA_COLOR = {
    "Dirección": "#7F6000", "Producción": "#0A2640", "Administración": "#1B3A5C",
    "Comercial": "#8A5A00", "Mantenimiento": "#5A6B7A",
  };

  const svgNS = "http://www.w3.org/2000/svg";
  let arbol = null, modo = "teorico", collapsed = new Set(), viewport, canvas, svg;
  let scale = 1, tx = 0, ty = 0;

  function el(tag, attrs, parent) {
    const e = document.createElementNS(svgNS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  // ── layout: primera pasada calcula ancho de cada subárbol, segunda asigna x absoluto ──
  function medir(nodo, profundidad) {
    nodo._depth = profundidad;
    const sinHijos = collapsed.has(nodo.codigo) || nodo.hijos.length === 0;
    if (sinHijos) { nodo._width = NODE_W; return nodo._width; }
    let total = 0;
    for (const h of nodo.hijos) total += medir(h, profundidad + 1) + H_GAP;
    total -= H_GAP;
    nodo._width = Math.max(NODE_W, total);
    return nodo._width;
  }
  function ubicar(nodo, xCentro) {
    nodo._x = xCentro; nodo._y = nodo._depth * (NODE_H + V_GAP);
    if (collapsed.has(nodo.codigo) || nodo.hijos.length === 0) return;
    let cursor = xCentro - nodo._width / 2;
    for (const h of nodo.hijos) {
      ubicar(h, cursor + h._width / 2);
      cursor += h._width + H_GAP;
    }
  }

  function todosLosNodos(nodo, out) {
    out.push(nodo);
    if (!collapsed.has(nodo.codigo)) nodo.hijos.forEach(h => todosLosNodos(h, out));
    return out;
  }

  function recalcularYdibujar(primeraVez) {
    medir(arbol, 0);
    ubicar(arbol, 0);
    const nodos = todosLosNodos(arbol, []);
    const grupos = {};
    canvas.querySelectorAll(".og-grupo").forEach(g => grupos[g.dataset.codigo] = g);

    // conexiones: se redibujan siempre, son baratas
    let lineas = canvas.querySelector(".og-lineas");
    if (!lineas) { lineas = el("g", { class: "og-lineas" }); canvas.insertBefore(lineas, canvas.firstChild); }
    lineas.innerHTML = "";
    nodos.forEach(n => {
      if (collapsed.has(n.codigo)) return;
      n.hijos.forEach(h => {
        const x1 = n._x, y1 = n._y + NODE_H, x2 = h._x, y2 = h._y;
        const my = (y1 + y2) / 2;
        el("path", { d: `M${x1},${y1} L${x1},${my} L${x2},${my} L${x2},${y2}`, class: "og-linea" }, lineas);
      });
    });

    const vistos = new Set();
    nodos.forEach(n => {
      vistos.add(n.codigo);
      let g = grupos[n.codigo];
      if (!g) {
        g = el("g", { class: "og-grupo", "data-codigo": n.codigo, transform: `translate(${n._x - NODE_W / 2},${n._y})` }, canvas);
        const tieneHijos = n.hijos.length > 0;
        const colorArea = AREA_COLOR[n.area] || "#6B7785";
        const vac = modo === "real" && n.vacante;
        const rect = el("rect", { width: NODE_W, height: NODE_H, rx: 8, class: "og-caja" + (vac ? " og-vacante" : "") }, g);
        el("rect", { width: 5, height: NODE_H, class: "og-franja", fill: colorArea }, g);
        const t1 = el("text", { x: 14, y: 22, class: "og-codigo" }, g); t1.textContent = n.codigo;
        const t2 = el("text", { x: 14, y: 38, class: "og-nombre" }, g); t2.textContent = n.nombre;
        if (modo === "real") {
          const t3 = el("text", { x: 14, y: 54, class: vac ? "og-vacante-txt" : "og-ocupante" }, g);
          t3.textContent = vac ? "vacante" : n.ocupantes.join(", ");
        }
        if (tieneHijos) {
          const btn = el("g", { class: "og-toggle", transform: `translate(${NODE_W - 20},${NODE_H / 2})` }, g);
          el("circle", { r: 9, class: "og-toggle-circulo" }, btn);
          const signo = el("text", { class: "og-toggle-signo", "text-anchor": "middle", dy: 4 }, btn);
          signo.textContent = collapsed.has(n.codigo) ? "+" : "–";
          btn.style.cursor = "pointer";
          btn.addEventListener("click", (ev) => { ev.stopPropagation(); toggle(n.codigo); });
        }
        g.addEventListener("click", () => abrirFicha(n.codigo));
        g.style.cursor = "pointer";
        g.style.opacity = primeraVez ? 1 : 0;
      }
      g.style.transition = "transform .35s ease, opacity .35s ease";
      requestAnimationFrame(() => {
        g.setAttribute("transform", `translate(${n._x - NODE_W / 2},${n._y})`);
        g.style.opacity = 1;
      });
      const signo = g.querySelector(".og-toggle-signo");
      if (signo) signo.textContent = collapsed.has(n.codigo) ? "+" : "–";
    });
    // sacar los nodos que quedaron plegados (ya no visibles)
    Object.keys(grupos).forEach(codigo => {
      if (!vistos.has(codigo)) {
        const g = grupos[codigo];
        g.style.transition = "opacity .25s ease";
        g.style.opacity = 0;
        setTimeout(() => g.remove(), 250);
      }
    });

    if (primeraVez) ajustarVista();
  }

  function toggle(codigo) {
    if (collapsed.has(codigo)) collapsed.delete(codigo); else collapsed.add(codigo);
    recalcularYdibujar(false);
  }

  function abrirFicha(codigo) { window.open(`/ui/puestos/${codigo}`, "_blank"); }

  function aplicarTransform() {
    canvas.setAttribute("transform", `translate(${tx},${ty}) scale(${scale})`);
  }

  function ajustarVista() {
    const bbox = canvas.getBBox();
    const vw = viewport.clientWidth, vh = viewport.clientHeight;
    scale = Math.min(vw / (bbox.width + 120), vh / (bbox.height + 120), 1.1);
    tx = vw / 2 - (bbox.x + bbox.width / 2) * scale;
    ty = 40 - bbox.y * scale;
    aplicarTransform();
  }

  function initZoomPan() {
    let arrastrando = false, ax = 0, ay = 0;
    viewport.addEventListener("wheel", (e) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.1 : 0.9;
      const rect = viewport.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const nuevaScale = Math.min(Math.max(scale * factor, 0.15), 2.5);
      tx = mx - ((mx - tx) / scale) * nuevaScale;
      ty = my - ((my - ty) / scale) * nuevaScale;
      scale = nuevaScale;
      aplicarTransform();
    }, { passive: false });
    viewport.addEventListener("mousedown", (e) => { arrastrando = true; ax = e.clientX; ay = e.clientY; viewport.style.cursor = "grabbing"; });
    window.addEventListener("mousemove", (e) => {
      if (!arrastrando) return;
      tx += e.clientX - ax; ty += e.clientY - ay; ax = e.clientX; ay = e.clientY;
      aplicarTransform();
    });
    window.addEventListener("mouseup", () => { arrastrando = false; viewport.style.cursor = "grab"; });
  }

  window.OrganigramaSGO = {
    async cargar(nuevoModo, plantaId) {
      modo = nuevoModo;
      collapsed = new Set();
      const url = `/api/organigrama?modo=${modo}` + (plantaId ? `&planta_id=${plantaId}` : "");
      const r = await fetch(url);
      arbol = await r.json();
      canvas.innerHTML = "";
      recalcularYdibujar(true);
    },
    init(viewportEl) {
      viewport = viewportEl;
      svg = el("svg", { width: "100%", height: "100%" }, viewport);
      viewport.appendChild(svg);
      canvas = el("g", { class: "og-canvas" }, svg);
      viewport.style.cursor = "grab";
      initZoomPan();
    },
    zoomIn() { scale = Math.min(scale * 1.2, 2.5); aplicarTransform(); },
    zoomOut() { scale = Math.max(scale * 0.8, 0.15); aplicarTransform(); },
    ajustarVista,
  };
})();
