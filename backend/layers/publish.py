"""
Layer 5 — PUBLISH: Zavu SMS/WhatsApp, Resend email, dashboard update.

AUDIT DE ANONIMIZACIÓN (revisado pre-demo hack@latam 2026):
- No exponemos nombres de monitores ambientales individuales (federación → solo cuando
  el destinatario es de esa federación).
- No exponemos coordenadas exactas en SMS/WhatsApp/email; usamos el bbox redondeado o
  el nombre de la cuenca/lote a través de la atribución pública (operator_name + concession_id,
  ambos datos de registro OSINERGMIN público).
- No exponemos identidad de denunciantes individuales; las plantillas hablan en términos
  de "presunto responsable" y "verificación in situ".
- Las URLs en los mensajes apuntan al dashboard público, no a vistas con datos personales.
- Cualquier publicación de evidencia que afecte a una federación requiere FPIC previo
  (ver INDEPENDENCE_PLEDGE.md §3 — soberanía de datos indígena).
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings

router = APIRouter()

DEMO_RECIPIENTS = [
    "+51961530528",
]
JOURNALIST_EMAILS = [
    "arkhangio@gmail.com",
]


async def send_sms_alert(phone: str, alert_data: dict) -> dict:
    """Send SMS via Zavu API."""
    attribution = alert_data.get("attribution", {})
    predictions = alert_data.get("predictions", {})

    # Note: Peruvian carriers block SMS containing full URLs (anti-phishing filter).
    # Use a short alert reference instead and direct people to the dashboard.
    # Uses "Presunto resp." (presunto responsable) — admisibilidad procesal.
    alert_ref = (alert_data.get("alert_id", "") or "")[:8]
    text = (
        f"ALERTA GUARDIAN DEL AGUA\n"
        f"Tipo: {alert_data.get('contamination_type', 'hidrocarburos').upper()}\n"
        f"Presunto resp.: {attribution.get('operator_name', 'sujeto a verificacion')}\n"
        f"Afectados 30d (proyeccion): {predictions.get('people_affected_30d', 0):,}\n"
        f"Ref evidencia: {alert_ref}"
    )

    headers = {"Authorization": f"Bearer {settings.zavu_api_key}"}
    if settings.zavu_sender:
        headers["Zavu-Sender"] = settings.zavu_sender

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{settings.zavu_base_url}/messages",
            headers=headers,
            json={"to": phone, "text": text},
        )
        return {
            "phone": phone,
            "status": resp.status_code,
            "sent": resp.is_success,
            "response": resp.text[:200] if not resp.is_success else None,
        }


async def send_whatsapp_alert(phone: str, alert_data: dict) -> dict:
    """Send WhatsApp message via Zavu API."""
    attribution = alert_data.get("attribution", {})
    predictions = alert_data.get("predictions", {})

    body = (
        f"*ALERTA AMBIENTAL — Guardián del Agua*\n\n"
        f"*Tipo de contaminación detectada:* {alert_data.get('contamination_type', 'hidrocarburos').upper()}\n"
        f"*Presunto responsable* (sujeto a verificación in situ):\n"
        f"  {attribution.get('operator_name', 'operador denunciado')}\n"
        f"  Concesión: {attribution.get('concession_id', '')}\n"
        f"  Sanciones previas registradas: {attribution.get('prior_sanctions', 0)}\n\n"
        f"*Proyección de impacto (30 días, modelo XGBoost):*\n"
        f"• {predictions.get('people_affected_30d', 0):,} personas potencialmente afectadas\n"
        f"• {predictions.get('fish_dieoff_30d_pct', 0):.0f}% mortandad piscícola proyectada\n"
        f"• {predictions.get('drinking_water_sources_at_risk', 0)} fuentes de agua en riesgo\n\n"
        f"_Indicios técnicos preliminares. Requiere verificación humana y firma legal antes de presentación a OEFA._\n\n"
        f"Dossier completo: guardiandelagua.la/alerts/{alert_data.get('alert_id', '')}"
    )

    headers = {"Authorization": f"Bearer {settings.zavu_api_key}"}
    if settings.zavu_sender:
        headers["Zavu-Sender"] = settings.zavu_sender

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{settings.zavu_base_url}/messages",
            headers=headers,
            json={"to": phone, "text": body, "channel": "whatsapp"},
        )
        return {
            "phone": phone,
            "status": resp.status_code,
            "sent": resp.is_success,
            "response": resp.text[:200] if not resp.is_success else None,
        }


async def send_email_alert(to_emails: list[str], alert_data: dict) -> dict:
    """Send email via Resend API."""
    import resend
    resend.api_key = settings.resend_api_key

    attribution = alert_data.get("attribution", {})
    predictions = alert_data.get("predictions", {})
    alert_id = alert_data.get("alert_id", "")

    subject = (
        f"Dossier preliminar: presunto responsable {attribution.get('operator_name', 'operador denunciado')} — "
        f"{alert_data.get('contamination_type', 'contaminación').upper()}"
    )

    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: #0E5E7F; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0;">Guardián del Agua — Dossier probatorio preliminar</h1>
        <p style="margin: 6px 0 0 0; font-size: 13px; opacity: 0.9;">
            Evidencia técnica con cadena de custodia. Sujeta a verificación in situ.
        </p>
    </div>
    <div style="padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px;">
        <div style="background: #fff4e6; border: 1px solid #d97706; padding: 10px 12px; border-radius: 4px; margin-bottom: 16px; font-size: 12px; color: #92400e;">
            <strong>DOCUMENTO PRELIMINAR.</strong> Requiere verificación humana y firma de
            representante legal autorizado antes de presentación formal ante OEFA.
        </div>
        <h2 style="color: #0E5E7F;">Indicios técnicos: {alert_data.get("contamination_type", "").upper()}</h2>
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 8px; background: #f5f5f5;"><strong>Presunto responsable</strong></td>
                <td style="padding: 8px;">{attribution.get("operator_name", "")} <em style="font-size:11px;color:#666;">(sujeto a verificación in situ)</em></td></tr>
            <tr><td style="padding: 8px;"><strong>Concesión / activo</strong></td>
                <td style="padding: 8px;">{attribution.get("concession_id", "")}</td></tr>
            <tr><td style="padding: 8px; background: #f5f5f5;"><strong>Sanciones previas registradas (OEFA)</strong></td>
                <td style="padding: 8px;">{attribution.get("prior_sanctions", 0)}</td></tr>
            <tr><td style="padding: 8px;"><strong>Personas potencialmente afectadas (30d)</strong></td>
                <td style="padding: 8px; color: #c0392b;">{predictions.get("people_affected_30d", 0):,} <em style="font-size:11px;color:#666;">(proyección XGBoost)</em></td></tr>
            <tr><td style="padding: 8px; background: #f5f5f5;"><strong>Mortandad piscícola proyectada</strong></td>
                <td style="padding: 8px; color: #c0392b;">{predictions.get("fish_dieoff_30d_pct", 0):.0f}%</td></tr>
            <tr><td style="padding: 8px;"><strong>Daño económico estimado</strong></td>
                <td style="padding: 8px;">S/ {predictions.get("economic_damage_usd", 0):,}</td></tr>
        </table>
        <p style="margin-top: 20px;">
            <a href="https://guardiandelagua.la/alerts/{alert_id}"
               style="background: #0E5E7F; color: white; padding: 12px 24px;
                      border-radius: 4px; text-decoration: none; font-weight: bold;">
                Ver alerta completa y generar denuncia →
            </a>
        </p>
        <p style="color: #666; font-size: 11px; margin-top: 20px; border-top: 1px solid #eee; padding-top: 12px;">
            <strong>Disclaimer metodológico.</strong> Documento generado mediante análisis
            automatizado de imágenes Sentinel-2 y modelado predictivo. La responsabilidad
            atribuida es <em>presunta, sujeta a verificación in situ</em> por la autoridad
            fiscalizadora competente. Las proyecciones de impacto son estimaciones
            modelísticas, no mediciones de campo.
        </p>
        <p style="color: #666; font-size: 12px; margin-top: 12px;">
            Guardián del Agua — Plataforma de evidencia probatoria grado-litigación.<br>
            guardiandelagua.la · open source MIT ·
            <a href="https://guardiandelagua.la/independence" style="color: #0E5E7F;">Compromiso de Independencia</a>
        </p>
    </div>
    </body></html>
    """

    # Use Resend sandbox domain until guardiandelagua.la is verified at resend.com/domains
    from_addr = settings.email_from or "onboarding@resend.dev"
    result = resend.Emails.send({
        "from": from_addr,
        "to": to_emails,
        "subject": subject,
        "html": html,
    })
    return {"email_id": result.get("id"), "sent_to": to_emails, "from": from_addr}


class PublishRequest(BaseModel):
    sms_recipients: list[str] = []
    whatsapp_recipients: list[str] = []
    email_recipients: list[str] = []


@router.post("/{alert_id}")
async def publish_alert(
    alert_id: str,
    req: PublishRequest | None = None,
    channels: str | None = None,
):
    """
    Send SMS, WhatsApp, and email notifications for a fully attributed alert.

    Query param `channels` (comma-separated, optional) restricts which transports
    fire: e.g. `?channels=sms,whatsapp` (federation flow) or `?channels=email`
    (press flow). If omitted, all three transports run — preserves the original
    /pipeline/run + dossier behavior.
    """
    from db import get_db
    db = get_db()

    doc = db.collection("alerts").document(alert_id).get()
    if not doc.exists:
        raise HTTPException(404, f"Alert {alert_id} not found")

    data = doc.to_dict()
    if not data.get("attribution"):
        raise HTTPException(400, "Alert must be attributed before publishing")

    enabled = (
        {c.strip().lower() for c in channels.split(",") if c.strip()}
        if channels
        else {"sms", "whatsapp", "email"}
    )

    sms_phones = (req.sms_recipients if req else []) or DEMO_RECIPIENTS
    whatsapp_phones = (req.whatsapp_recipients if req else []) or DEMO_RECIPIENTS
    emails = (req.email_recipients if req else []) or JOURNALIST_EMAILS

    results: dict = {"sms": [], "whatsapp": [], "email": None, "channels_used": sorted(enabled)}

    if "sms" in enabled and settings.zavu_api_key:
        for phone in sms_phones:
            results["sms"].append(await send_sms_alert(phone, data))
    if "whatsapp" in enabled and settings.zavu_api_key:
        for phone in whatsapp_phones:
            results["whatsapp"].append(await send_whatsapp_alert(phone, data))
    if "email" in enabled and settings.resend_api_key and emails:
        results["email"] = await send_email_alert(emails, data)

    db.collection("alerts").document(alert_id).update({"status": "published"})

    return {"alert_id": alert_id, "published": True, "notifications": results}
