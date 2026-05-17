"""Layer 4 — ACT: Context7 RAG + Claude Haiku denuncia generation + PDF rendering."""
from __future__ import annotations
import base64
import hashlib
import io
import json
import time
from datetime import datetime
from pathlib import Path

import anthropic
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from jinja2 import Environment, FileSystemLoader

from config import settings

router = APIRouter()

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Versiones referenciadas en la cadena de custodia técnica del PDF.
# Cambiar cuando se actualice el modelo de visión o el dataset de concesiones.
MODEL_VERSION = "claude-sonnet-4-5"
DATA_VERSION = "norperuana-2024"


def compute_evidence_hash(alert_data: dict) -> str:
    """
    SHA-256 reproducible del paquete de evidencia. Permite verificar que el documento
    no ha sido alterado post-generación (admisibilidad procesal).
    """
    canonical = {
        "alert_id": alert_data.get("alert_id"),
        "sentinel_image_id": alert_data.get("sentinel_image_id"),
        "sentinel_bbox": alert_data.get("sentinel_bbox"),
        "detected_at": str(alert_data.get("detected_at", "")),
        "contamination_type": alert_data.get("contamination_type"),
        "confidence": alert_data.get("confidence"),
        "attribution": alert_data.get("attribution"),
        "predictions": alert_data.get("predictions"),
        "model_version": MODEL_VERSION,
        "data_version": DATA_VERSION,
    }
    payload = json.dumps(canonical, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def query_legal_context(contamination_type: str, operator_name: str) -> str:
    """Query Context7 for relevant Peruvian environmental law articles."""
    if not settings.context7_api_key:
        return _fallback_legal_context(contamination_type)

    query = (
        f"OEFA denuncia administrativa contaminación {contamination_type} "
        f"operador autorizado Ley 28611 artículos 145 149 responsabilidad ambiental"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.context7.com/v1/query",
                headers={"Authorization": f"Bearer {settings.context7_api_key}"},
                json={"query": query, "corpus": "peru-environmental-law", "top_k": 5},
            )
            resp.raise_for_status()
            return resp.json().get("context", _fallback_legal_context(contamination_type))
    except Exception:
        return _fallback_legal_context(contamination_type)


def _fallback_legal_context(contamination_type: str) -> str:
    return """
Ley N° 28611 — Ley General del Ambiente (Perú):
- Artículo 145: El causante de la degradación del ambiente y de sus componentes, sea una persona
  natural o jurídica, pública o privada, está obligado a adoptar inexcusablemente las medidas
  para su restauración, rehabilitación o reparación según corresponda o, cuando lo anterior no
  fuera posible, a compensar en términos ambientales los daños generados.
- Artículo 149: El Estado Peruano y las personas naturales y jurídicas tienen el deber de
  conservar el ambiente y sus componentes. El incumplimiento de este deber genera responsabilidad
  ambiental por los daños causados.

Reglamento de la Ley OEFA (D.S. 013-2013-PCM):
- Artículo 20: La denuncia puede ser presentada por cualquier persona natural o jurídica ante la
  Oficina de Atención al Ciudadano de OEFA o mediante el sistema virtual SINADA.
- Requiere: identificación del denunciante, descripción de los hechos, datos del presunto infractor,
  evidencias disponibles.

Ley N° 26821 — Ley Orgánica para el Aprovechamiento Sostenible de los Recursos Naturales:
- Artículo 28: Los concesionarios están obligados a realizar sus actividades de aprovechamiento
  cumpliendo las condiciones establecidas en la legislación ambiental.
"""


async def generate_denuncia_text(alert_data: dict, legal_context: str) -> str:
    """Use Claude Haiku to draft a formal OEFA denuncia in Spanish."""
    attribution = alert_data.get("attribution", {})
    predictions = alert_data.get("predictions", {})

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": f"""Redacta una denuncia administrativa formal ante el OEFA (Organismo de Evaluación
y Fiscalización Ambiental) en español jurídico peruano.

CRITERIO LINGÜÍSTICO OBLIGATORIO — admisibilidad procesal:
- Nunca afirmes responsabilidad de manera concluyente. Usa siempre la fórmula
  "presunto responsable, sujeto a verificación in situ" o equivalentes
  ("presuntamente responsable", "el operador denunciado, cuya responsabilidad
  está sujeta a verificación in situ por la autoridad competente").
- Identifica la evidencia como "indicios técnicos" o "elementos probatorios
  preliminares", no como "prueba concluyente".
- Las predicciones de impacto son "proyecciones modelísticas sujetas a
  validación en campo", no hechos consumados.
- El documento es una "solicitud de inicio de procedimiento sancionador",
  no una sentencia.
- Mantén el lenguaje formal y técnico propio del derecho administrativo peruano.

DATOS DEL EVENTO:
- Tipo de contaminación detectada: {alert_data.get("contamination_type", "hidrocarburos")}
- Fecha de detección satelital: {alert_data.get("detected_at", datetime.utcnow().isoformat())}
- Confianza del análisis automatizado: {alert_data.get("confidence", 0.87):.0%}
- ID imagen satelital (Sentinel-2 L2A): {alert_data.get("sentinel_image_id", "S2_2024-03-15")}
- Coordenadas (bbox WGS84): {alert_data.get("sentinel_bbox", [])}

PRESUNTO RESPONSABLE (sujeto a verificación in situ):
- Razón social: {attribution.get("operator_name", "Operador concesionario")}
- Concesión / lote: {attribution.get("concession_id", "")}
- Registro OSINERGMIN: {attribution.get("osinergmin_id", "")}
- Sanciones previas registradas en OEFA: {attribution.get("prior_sanctions", 0)}
- Estado de la concesión: {attribution.get("legal_status", "activa")}

PROYECCIÓN DE IMPACTO (modelado XGBoost, sujeto a validación en campo):
- Personas potencialmente afectadas (30 días): {predictions.get("people_affected_30d", 1200)}
- Mortandad piscícola proyectada: {predictions.get("fish_dieoff_30d_pct", 80)}%
- Fuentes de agua potencialmente en riesgo: {predictions.get("drinking_water_sources_at_risk", 3)}
- Daño económico estimado: S/ {predictions.get("economic_damage_usd", 2400000):,}

BASE LEGAL APLICABLE:
{legal_context}

Estructura la denuncia con estas secciones (en este orden exacto):
1. ENCABEZADO (OEFA, expediente preliminar, fecha de presentación)
2. DATOS DEL DENUNCIANTE (representante legal de federación indígena u organización de base)
3. IDENTIFICACIÓN DEL PRESUNTO RESPONSABLE (datos del operador concesionario, sin atribuir
   responsabilidad de forma concluyente)
4. DESCRIPCIÓN DE LOS INDICIOS TÉCNICOS (qué muestra la imagen satelital, análisis espectral,
   intersección con polígono de concesión registrado en OSINERGMIN)
5. FUNDAMENTOS DE DERECHO (artículos específicos de Ley 28611, Ley 26821, normativa OEFA)
6. MEDIDAS CAUTELARES SOLICITADAS (inspección in situ urgente, suspensión preventiva si procede)
7. PRETENSIONES (apertura de procedimiento sancionador; NO afirmes pena anticipada)
8. MEDIOS PROBATORIOS OFRECIDOS (audit trail satelital con cadena de custodia técnica adjunta)
9. CIERRE Y SOLICITUD DE VERIFICACIÓN IN SITU

CIERRE OBLIGATORIO al final del documento:
"La presente denuncia se sustenta en indicios técnicos preliminares obtenidos por análisis
automatizado de imágenes satelitales. La responsabilidad del operador denunciado queda
sujeta a verificación in situ por la autoridad fiscalizadora competente, conforme al debido
proceso administrativo."
""",
            }
        ],
    )
    return response.content[0].text


def render_pdf(denuncia_text: str, alert_data: dict) -> bytes:
    """
    Render denuncia to PDF. Uses WeasyPrint (HTML→PDF, high-fidelity) on Linux/Docker,
    falls back to reportlab (pure Python) on Windows where GTK3 libs aren't installed.
    """
    evidence_hash = compute_evidence_hash(alert_data)
    try:
        from weasyprint import HTML
        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
        template = env.get_template("denuncia.html")
        html_content = template.render(
            denuncia_text=denuncia_text,
            alert=alert_data,
            attribution=alert_data.get("attribution", {}),
            predictions=alert_data.get("predictions", {}),
            generated_at=datetime.now().strftime("%d de %B de %Y"),
            model_version=MODEL_VERSION,
            data_version=DATA_VERSION,
            evidence_hash=evidence_hash,
        )
        return HTML(string=html_content).write_pdf()
    except Exception:
        # Fallback: pure-Python PDF with reportlab (covers Windows + WeasyPrint runtime errors)
        return _render_pdf_reportlab(denuncia_text, alert_data, evidence_hash)


def _render_pdf_reportlab(denuncia_text: str, alert_data: dict, evidence_hash: str = "") -> bytes:
    """Fallback PDF renderer using reportlab — pure Python, works on Windows without GTK."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_JUSTIFY

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14,
                          alignment=TA_JUSTIFY, spaceAfter=6)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=14, spaceAfter=10)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, spaceAfter=6)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, leading=11,
                           textColor=HexColor("#7f1d1d"))
    stamp = ParagraphStyle("stamp", parent=styles["Normal"], fontSize=9, leading=12,
                           textColor=HexColor("#b45309"), backColor=HexColor("#fff4e6"))

    story = []
    attribution = alert_data.get("attribution", {})

    # Header
    story.append(Paragraph("DENUNCIA ADMINISTRATIVA — DOCUMENTO PRELIMINAR", h1))
    story.append(Paragraph(
        "Organismo de Evaluación y Fiscalización Ambiental — OEFA",
        ParagraphStyle("sub", parent=styles["Normal"], fontSize=10, textColor=HexColor("#0E5E7F"))
    ))
    story.append(Spacer(1, 0.4*cm))

    # Sello de documento preliminar
    story.append(Paragraph(
        "<b>DOCUMENTO PRELIMINAR.</b> Este documento constituye un borrador técnico generado "
        "automáticamente. Requiere <b>verificación humana y firma de representante legal "
        "autorizado</b> antes de presentación formal ante OEFA o cualquier autoridad.",
        stamp
    ))
    story.append(Spacer(1, 0.4*cm))

    # Bloque de cadena de custodia técnica
    story.append(Paragraph("<b>CADENA DE CUSTODIA TÉCNICA</b>", h2))
    bbox = alert_data.get("sentinel_bbox", [])
    bbox_str = ", ".join(f"{v:.4f}" for v in bbox) if bbox else "—"
    chain_rows = [
        ["Campo", "Valor"],
        ["ID de evidencia", str(alert_data.get("alert_id", "—"))],
        ["Imagen satelital", f"Sentinel-2 L2A — {alert_data.get('sentinel_image_id', '—')}"],
        ["Fecha de captura", str(alert_data.get("detected_at", "—"))[:19]],
        ["Bounding box (WGS84)", bbox_str],
        ["Resolución espacial", "10 metros / pixel"],
        ["Bandas analizadas", "B02, B03, B04, B08"],
        ["Modelo de análisis", f"{MODEL_VERSION} (Anthropic)"],
        ["Confianza del análisis", f"{(alert_data.get('confidence', 0) * 100):.1f}%"],
        ["Polígonos concesión", f"OSINERGMIN/OEFA — {DATA_VERSION}"],
        ["Hash SHA-256", evidence_hash[:32] + "…" if len(evidence_hash) > 32 else evidence_hash],
        ["Sistema generador", "Guardián del Agua v1.0 (MIT)"],
    ]
    t = Table(chain_rows, colWidths=[5*cm, 11*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0E5E7F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#f0f9ff")),
        ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*cm))

    # Identificación del presunto responsable (lenguaje no concluyente)
    story.append(Paragraph(
        f"<b>Presunto responsable (sujeto a verificación in situ):</b> "
        f"{attribution.get('operator_name','—')} | "
        f"<b>Concesión:</b> {attribution.get('concession_id','—')} | "
        f"<b>Sanciones previas registradas:</b> {attribution.get('prior_sanctions',0)}",
        body
    ))
    story.append(Spacer(1, 0.4*cm))

    # Convert markdown-style denuncia text to paragraphs
    for line in denuncia_text.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 0.2*cm))
        elif line.startswith("# "):
            story.append(Paragraph(line[2:], h1))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], h2))
        elif line.startswith("**") and line.endswith("**"):
            story.append(Paragraph(f"<b>{line[2:-2]}</b>", body))
        else:
            # Escape HTML chars and convert **bold**
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            import re
            safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
            story.append(Paragraph(safe, body))

    # Disclaimer metodológico (cierre)
    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph(
        "<b>Disclaimer metodológico.</b> Este documento fue generado mediante sistema "
        "automatizado de análisis satelital y modelado predictivo. Los indicios técnicos "
        "aquí descritos son <i>preliminares</i> y la responsabilidad atribuida al operador "
        "denunciado es <b>presunta, sujeta a verificación in situ</b> por la autoridad "
        "fiscalizadora competente. Las proyecciones de impacto son estimaciones modelísticas, "
        "no mediciones de campo. Este documento constituye solicitud de inicio de procedimiento "
        "sancionador, no afirmación de responsabilidad ni sentencia anticipada.",
        small
    ))

    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(
        f"<i>Generado: {datetime.now().strftime('%d/%m/%Y')} · "
        f"Guardián del Agua — Evidencia probatoria grado-litigación · MIT</i>",
        body
    ))

    doc.build(story)
    return buf.getvalue()


@router.post("/denuncia/{alert_id}")
async def generate_denuncia(alert_id: str):
    """Generate a legal denuncia PDF for an attributed alert."""
    from db import get_db
    db = get_db()

    doc = db.collection("alerts").document(alert_id).get()
    if not doc.exists:
        raise HTTPException(404, f"Alert {alert_id} not found")

    data = doc.to_dict()
    if not data.get("attribution"):
        raise HTTPException(400, "Alert must be attributed before generating denuncia")

    start = time.time()
    legal_context = await query_legal_context(
        data.get("contamination_type", "hydrocarbon"),
        data.get("attribution", {}).get("operator_name", ""),
    )
    try:
        denuncia_text = await generate_denuncia_text(data, legal_context)
    except Exception as e:
        raise HTTPException(500, f"Claude API error ({type(e).__name__}): {e}")
    try:
        pdf_bytes = render_pdf(denuncia_text, data)
    except Exception as e:
        raise HTTPException(500, f"PDF render error ({type(e).__name__}): {e}")
    elapsed_ms = int((time.time() - start) * 1000)

    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    db.collection("alerts").document(alert_id).update({
        "denuncia_text": denuncia_text,
        "denuncia_pdf_b64": pdf_b64,
        "status": "act_generated",
    })

    return {
        "alert_id": alert_id,
        "generated_in_ms": elapsed_ms,
        "pdf_size_bytes": len(pdf_bytes),
        "denuncia_preview": denuncia_text[:500] + "...",
    }


@router.get("/denuncia/{alert_id}/download")
async def download_denuncia(alert_id: str):
    """Download the generated PDF denuncia."""
    from db import get_db
    db = get_db()

    doc = db.collection("alerts").document(alert_id).get()
    if not doc.exists:
        raise HTTPException(404, f"Alert {alert_id} not found")

    data = doc.to_dict()
    pdf_b64 = data.get("denuncia_pdf_b64")
    if not pdf_b64:
        raise HTTPException(404, "No PDF generated yet. Call POST /act/denuncia/{alert_id} first.")

    pdf_bytes = base64.b64decode(pdf_b64)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=denuncia_{alert_id}.pdf"},
    )
