from datetime import date
from fastapi import APIRouter, Depends, Request, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db
from auth import verificar_acceso
from functions import construir_arbol_organizacional
from organigrama_svg import renderizar_svg
import models as m

router = APIRouter(prefix="/ui/organigrama", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("", response_class=HTMLResponse)
def ver(request: Request, db: Session = Depends(get_db)):
    plantas = db.query(m.Planta).all()
    return templates.TemplateResponse(request, "organigrama.html", {"plantas": plantas})


@router.get("/pdf")
def exportar_pdf(modo: str = "teorico", planta_id: int = None, db: Session = Depends(get_db)):
    """El SVG se genera server-side en Python puro (organigrama_svg.py) — mismo
    layout que dibuja organigrama.js en el navegador, siempre desplegado del
    todo. Se convierte a PDF con svglib + reportlab, sin necesitar un
    navegador headless en el deploy."""
    import io
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas as pdfcanvas
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPDF

    planta_nombre = None
    if planta_id:
        pl = db.query(m.Planta).get(planta_id)
        planta_nombre = pl.nombre if pl else None

    arbol = construir_arbol_organizacional(db, modo=modo, planta_id=planta_id)
    svg_str = renderizar_svg(arbol, modo)
    drawing = svg2rlg(io.StringIO(svg_str))

    pagina = landscape(A4)
    margen = 30
    escala = min((pagina[0] - 2 * margen) / drawing.width, (pagina[1] - 2 * margen - 60) / drawing.height, 1.4)
    drawing.width *= escala; drawing.height *= escala; drawing.scale(escala, escala)

    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=pagina)
    c.setFillColor("#0A2640")
    c.rect(0, pagina[1] - 46, pagina[0], 46, fill=1, stroke=0)
    c.setFillColor("#E0A82E")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20, pagina[1] - 18, "CANTERA ELDORADO S.A. — SISTEMA DE GESTION ORGANIZACIONAL")
    c.setFillColor("#FFFFFF")
    c.setFont("Helvetica-Bold", 14)
    titulo = "Organigrama — Estructura del manual" if modo == "teorico" else f"Organigrama real — {planta_nombre or ''}"
    c.drawString(20, pagina[1] - 36, titulo)
    renderPDF.draw(drawing, c, (pagina[0] - drawing.width) / 2, pagina[1] - 60 - drawing.height)
    c.setFillColor("#6B7785")
    c.setFont("Helvetica", 8)
    c.drawCentredString(pagina[0] / 2, 14, f"Generado el {date.today().strftime('%d/%m/%Y')}")
    c.save()

    return Response(content=buf.getvalue(), media_type="application/pdf",
                     headers={"Content-Disposition": 'inline; filename="Organigrama.pdf"'})
