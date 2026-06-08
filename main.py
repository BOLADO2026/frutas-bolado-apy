from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
from uuid import uuid4
from datetime import datetime
import json
import tempfile

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PyPDF2 import PdfReader, PdfWriter


BASE_URL = "https://frutas-bolado-apy.onrender.com"

ROOT = Path(__file__).parent
PLANTILLA_PATH = ROOT / "PLANTILLA" / "PLANTILLA_BOLADO_DEFINITIVA_IMPRIMIR.pdf"
COORD_PATH = ROOT / "COORDENADAS" / "coordenadas_bolado_v3.json"
OUTPUT_DIR = ROOT / "tmp_pdfs"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="FRUTAS BOLADO API")


class LineaPedido(BaseModel):
    articulo: str
    bultos: Optional[str] = ""
    precio: Optional[str] = ""


class PedidoPDF(BaseModel):
    cliente: str
    codigo: Optional[str] = ""
    numero_pedido: Optional[str] = ""
    fecha_entrega: str
    registro: str
    lineas: List[LineaPedido]
    observaciones: Optional[List[str]] = []


def cargar_coord():
    if not COORD_PATH.exists():
        raise HTTPException(status_code=500, detail="No existe coordenadas_bolado_v3.json")
    with open(COORD_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validar_base():
    if not PLANTILLA_PATH.exists():
        raise HTTPException(status_code=500, detail="No existe plantilla oficial")
    if not COORD_PATH.exists():
        raise HTTPException(status_code=500, detail="No existe mapa de coordenadas")


def generar_pdf_archivo(pedido: PedidoPDF, output_path: Path):
    validar_base()
    coord = cargar_coord()

    max_lineas = int(coord.get("MAX_LINEAS", 28))
    lineas = pedido.lineas

    if not lineas:
        raise HTTPException(status_code=400, detail="Pedido sin líneas")

    observaciones = pedido.observaciones or []
    if len(observaciones) > 3:
        raise HTTPException(status_code=400, detail="Máximo 3 líneas de observaciones")

    paginas = [lineas[i:i + max_lineas] for i in range(0, len(lineas), max_lineas)]

    writer = PdfWriter()

    for pagina_lineas in paginas:
        overlay_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        overlay_path = Path(overlay_tmp.name)
        overlay_tmp.close()

        c = canvas.Canvas(str(overlay_path), pagesize=A4)

        c.setFont("Helvetica-Bold", 10.8)
        c.drawString(coord["CLIENTE_X"], coord["CLIENTE_Y"], pedido.cliente)

        if pedido.codigo:
            c.setFont("Helvetica-Bold", 10.5)
            c.drawString(coord["TCODIGO_X"], coord["TCODIGO_Y"], pedido.codigo)

        if pedido.numero_pedido:
            c.setFont("Helvetica", 9)
            c.drawString(coord["NPEDIDO_X"], coord["NPEDIDO_Y"], pedido.numero_pedido)

        for idx, linea in enumerate(pagina_lineas):
            y = coord["LINEA_INICIAL_Y"] - (idx * coord["SALTO_LINEA"])

            c.setFont("Helvetica-Bold", 7.35)
            c.drawString(coord["ARTICULO_X"], y, linea.articulo or "")

            c.setFont("Helvetica-Bold", 7.35)
            c.drawString(coord["BULTOS_X"], y, linea.bultos or "")

            if linea.precio:
                c.setFont("Helvetica-Bold", 7.15)
                c.drawString(coord["PRECIO_X"], y, linea.precio)

        obs_coords = [
            ("OBS_1_X", "OBS_1_Y"),
            ("OBS_2_X", "OBS_2_Y"),
            ("OBS_3_X", "OBS_3_Y"),
        ]

        c.setFont("Helvetica-Bold", 7.8)
        for obs, (x_key, y_key) in zip(observaciones, obs_coords):
            c.drawString(coord[x_key], coord[y_key], obs)

        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(coord["FECHA_ENTREGA_X"], coord["FECHA_ENTREGA_Y"], pedido.fecha_entrega)

        c.setFont("Helvetica", 7.8)
        c.drawString(coord["REGISTRO_X"], coord["REGISTRO_Y"], pedido.registro)

        c.save()

        plantilla_reader = PdfReader(str(PLANTILLA_PATH))
        overlay_reader = PdfReader(str(overlay_path))

        base_page = plantilla_reader.pages[0]
        base_page.merge_page(overlay_reader.pages[0])
        writer.add_page(base_page)

        overlay_path.unlink(missing_ok=True)

    with open(output_path, "wb") as f:
        writer.write(f)


@app.get("/health")
def health():
    return {
        "ok": True,
        "plantilla": PLANTILLA_PATH.exists(),
        "coordenadas": COORD_PATH.exists()
    }


@app.post("/generar-pdf")
def generar_pdf(pedido: PedidoPDF):
    filename = f"pedido_{uuid4().hex}.pdf"
    output_path = OUTPUT_DIR / filename
    generar_pdf_archivo(pedido, output_path)
    return FileResponse(
        path=str(output_path),
        media_type="application/pdf",
        filename=filename
    )


@app.post("/generar-pdf-link")
def generar_pdf_link(pedido: PedidoPDF):
    filename = f"pedido_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}.pdf"
    output_path = OUTPUT_DIR / filename

    generar_pdf_archivo(pedido, output_path)

    return JSONResponse({
        "ok": True,
        "filename": filename,
        "download_url": f"{BASE_URL}/descargar/{filename}"
    })


@app.get("/descargar/{filename}")
def descargar(filename: str):
    safe_name = Path(filename).name
    file_path = OUTPUT_DIR / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=safe_name
    )
