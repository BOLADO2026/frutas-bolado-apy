import os
import json
import textwrap
from io import BytesIO
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, Field
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PyPDF2 import PdfReader, PdfWriter


BASE_DIR = Path(__file__).resolve().parent
PLANTILLA = BASE_DIR / "PLANTILLA" / "PLANTILLA_BOLADO_DEFINITIVA_IMPRIMIR.pdf"
COORDENADAS = BASE_DIR / "COORDENADAS" / "coordenadas_bolado_v3.json"

# En Render se configura como variable de entorno.
# Si no existe, la API funciona sin clave durante pruebas.
API_KEY = os.getenv("BOLADO_API_KEY", "")


class LineaPedido(BaseModel):
    articulo: str = Field(..., description="Artículo proveedor completo")
    bultos: str = Field(..., description="Cantidad + formato, por ejemplo 10 KG, 2 UNIDAD, 1 BANDEJA")
    precio: str = Field(..., description="Precio neto unitario en formato español, por ejemplo 1,65")


class Pedido(BaseModel):
    registro: str
    cliente: str
    pedido: str
    fecha_entrega: str
    lineas: List[LineaPedido]
    tcodigo: Optional[str] = ""
    observaciones: Optional[List[str]] = []


class Lote(BaseModel):
    nombre_salida: Optional[str] = "LOTE_BOLADO_GPT.pdf"
    pedidos: List[Pedido]


app = FastAPI(
    title="FRUTAS BOLADO API",
    description="Motor PDF BOLADO: recibe JSON validado por GPT y devuelve PDF sobre plantilla oficial.",
    version="1.0.0",
    servers=[
        {"url": "https://frutas-bolado-apy.onrender.com"}
    ],
)


def verificar_clave(x_api_key: Optional[str]):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key incorrecta")


def cargar_coordenadas():
    if not COORDENADAS.exists():
        raise HTTPException(status_code=500, detail=f"No existe archivo de coordenadas: {COORDENADAS}")
    with open(COORDENADAS, "r", encoding="utf-8") as f:
        return json.load(f)


def draw_articulo(c, texto, x, y):
    partes = textwrap.wrap(str(texto), width=43, break_long_words=False, break_on_hyphens=False)
    if not partes:
        return

    c.setFont("Helvetica-Bold", 7.35)
    c.drawString(x, y, partes[0])

    if len(partes) > 1:
        c.drawString(x, y - 8, partes[1][:43])

    if len(partes) > 2:
        c.setFont("Helvetica-Bold", 6.4)
        c.drawString(x, y - 15, partes[2][:43])


def crear_overlay(pedido: Pedido, lineas, pagina, total_paginas, cfg):
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)

    c.setFont("Helvetica-Bold", 10.80)
    c.drawString(cfg["cliente"][0], cfg["cliente"][1], pedido.cliente[:60])

    c.setFont("Helvetica-Bold", 10.50)
    c.drawString(cfg["tcodigo"][0], cfg["tcodigo"][1], (pedido.tcodigo or "")[:18])

    c.setFont("Helvetica", 9.00)
    c.drawString(cfg["pedido"][0], cfg["pedido"][1], pedido.pedido)

    y = cfg["linea_inicial_y"]
    for linea in lineas:
        draw_articulo(c, linea.articulo, cfg["articulo_x"], y)

        c.setFont("Helvetica-Bold", 7.35)
        c.drawString(cfg["bultos_x"], y, linea.bultos)

        c.setFont("Helvetica-Bold", 7.15)
        c.drawString(cfg["precio_x"], y, linea.precio)

        y -= cfg["salto_linea"]

    if pagina == total_paginas:
        c.setFont("Helvetica-Bold", 7.80)
        for (x, y), obs in zip(cfg["observaciones"], pedido.observaciones or []):
            c.drawString(x, y, str(obs)[:94])

    c.setFont("Helvetica-Bold", 8.50)
    c.drawString(cfg["fecha_entrega"][0], cfg["fecha_entrega"][1], "FECHA ENTREGA: " + pedido.fecha_entrega)

    c.setFont("Helvetica", 7.80)
    registro = pedido.registro
    if total_paginas > 1:
        registro = f"{registro} P{pagina}/{total_paginas}"
    c.drawString(cfg["registro"][0], cfg["registro"][1], "REGISTRO: " + registro)

    c.save()
    packet.seek(0)
    return packet


def generar_pdf_lote(lote: Lote) -> bytes:
    if not PLANTILLA.exists():
        raise HTTPException(status_code=500, detail=f"No existe plantilla oficial: {PLANTILLA}")

    cfg = cargar_coordenadas()
    writer = PdfWriter()
    max_lineas = int(cfg.get("max_lineas", 28))

    for pedido in lote.pedidos:
        bloques = [pedido.lineas[i:i + max_lineas] for i in range(0, len(pedido.lineas), max_lineas)] or [[]]

        for pagina, bloque in enumerate(bloques, start=1):
            base_pdf = PdfReader(str(PLANTILLA))
            page = base_pdf.pages[0]
            overlay_pdf = PdfReader(crear_overlay(pedido, bloque, pagina, len(bloques), cfg))
            page.merge_page(overlay_pdf.pages[0])
            writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "plantilla": PLANTILLA.exists(),
        "coordenadas": COORDENADAS.exists(),
        "api_key_configurada": bool(API_KEY),
    }


@app.post("/generar-pdf")
def generar_pdf(lote: Lote, x_api_key: Optional[str] = Header(default=None)):
    verificar_clave(x_api_key)

    if not lote.pedidos:
        raise HTTPException(status_code=400, detail="El lote no contiene pedidos.")

    pdf_bytes = generar_pdf_lote(lote)
    filename = lote.nombre_salida or "LOTE_BOLADO_GPT.pdf"
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@app.get("/")
def root():
    return JSONResponse({
        "servicio": "FRUTAS BOLADO API",
        "uso": "POST /generar-pdf",
        "docs": "/docs",
        "health": "/health"
    })
