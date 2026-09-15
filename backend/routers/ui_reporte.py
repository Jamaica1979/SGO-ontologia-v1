from datetime import date
from fastapi import APIRouter, Depends, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db
from auth import verificar_acceso
from functions import calcular_semaforo
import models as m

router = APIRouter(prefix="/ui/reporte", dependencies=[Depends(verificar_acceso)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("/pdf")
def exportar_pdf(periodo: str = None, db: Session = Depends(get_db)):
    """El reporte mensual de indicadores — mismo dato que MC-10, en el formato
    que se lleva a la reunión de Dirección (MC-09). No es una pantalla nueva,
    es una salida distinta de la ficha de Indicador, con todos juntos."""
    from xhtml2pdf import pisa
    import io
    periodo = periodo or date.today().strftime("%Y-%m")
    indicadores = db.query(m.Indicador).filter(m.Indicador.activo == 1).order_by(m.Indicador.codigo).all()
    filas = []
    for ind in indicadores:
        med = db.query(m.MedicionDeIndicador).filter(m.MedicionDeIndicador.indicador_id == ind.id,
                                                       m.MedicionDeIndicador.periodo == periodo).first()
        filas.append({
            "codigo": ind.codigo, "nombre": ind.nombre, "area": ind.area,
            "valor": med.valor if med else None,
            "semaforo": calcular_semaforo(med.valor, ind.umbral_verde, ind.umbral_amarillo, ind.umbral_rojo) if med else None,
        })
    html = templates.get_template("pdf_reporte_mensual.html").render(
        periodo=periodo, filas=filas, fecha=date.today().strftime("%d/%m/%Y"))
    buf = io.BytesIO()
    pisa.CreatePDF(html, dest=buf)
    return Response(content=buf.getvalue(), media_type="application/pdf",
                     headers={"Content-Disposition": f'inline; filename="Reporte_{periodo}.pdf"'})
