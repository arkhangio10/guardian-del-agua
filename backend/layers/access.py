"""
Layer 6 — ACCESS: registro de solicitudes de acceso al sistema.

Maneja el formulario público de /pricing donde federaciones, periodistas,
abogados e investigadores solicitan tier de acceso. Cada solicitud:
  1. Se guarda en Firestore (colección `access_requests`) con timestamp.
  2. Dispara email al admin (arkhangio@gmail.com) vía Resend para revisión.
  3. Devuelve un `request_id` legible que el solicitante puede citar.

Esto es la primera implementación técnica del flujo FPIC documentado en
INDEPENDENCE_PLEDGE.md §3 — soberanía de datos de federaciones indígenas.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import uuid4

import resend
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from config import settings

router = APIRouter()

ROLE_LABELS = {
    "federacion": "Representante de federación indígena con FPIC firmado",
    "periodista": "Periodista verificado",
    "abogado": "Abogado ambiental",
    "investigador": "Investigador / académico",
}

ADMIN_EMAIL = "arkhangio@gmail.com"


class AccessRequestPayload(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    role_type: Literal["federacion", "periodista", "abogado", "investigador"]
    organizacion: str = Field(min_length=2, max_length=200)
    telefono: str = Field(min_length=6, max_length=30)
    email: EmailStr
    cuenca: str | None = Field(default=None, max_length=80)


def _normalize_phone(raw: str) -> str:
    """Strip non-digit chars, keep leading +."""
    cleaned = re.sub(r"[^\d+]", "", raw or "")
    return cleaned[:30]


@router.post("/request")
async def create_access_request(req: AccessRequestPayload):
    """Crear solicitud de acceso. Escribe a Firestore + envía email al admin."""
    from db import get_db

    db = get_db()
    request_id = f"REQ-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"
    phone = _normalize_phone(req.telefono)

    doc = {
        "request_id": request_id,
        "nombre": req.nombre,
        "role_type": req.role_type,
        "role_label": ROLE_LABELS[req.role_type],
        "organizacion": req.organizacion,
        "telefono": phone,
        "email": req.email,
        "cuenca": req.cuenca or None,
        "created_at": datetime.utcnow().isoformat(),
        "status": "pending_review",
    }

    try:
        db.collection("access_requests").document(request_id).set(doc)
    except Exception as e:
        # If Firestore fails, still try email so the request isn't lost.
        print(f"[WARN] Firestore write failed for {request_id}: {e}")

    email_status = _notify_admin(doc)

    return {
        "request_id": request_id,
        "status": "received",
        "message": "Solicitud recibida. El equipo evaluará tu acceso en 48-72h y responderá al email que registraste.",
        "admin_notified": email_status,
    }


def _notify_admin(doc: dict) -> bool:
    """Best-effort email to the admin. Never raises."""
    if not settings.resend_api_key:
        print("[WARN] RESEND_API_KEY no configurada — email omitido")
        return False
    try:
        resend.api_key = settings.resend_api_key
        from_addr = settings.email_from or "onboarding@resend.dev"
        subject = (
            f"[Guardián del Agua] Nueva solicitud de acceso — "
            f"{doc['nombre']} ({doc['role_label']})"
        )
        html = f"""
        <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #0E5E7F; color: white; padding: 18px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">Nueva solicitud de acceso</h2>
            <p style="margin: 6px 0 0 0; font-size: 13px; opacity: 0.9;">
                ID: <code style="background: rgba(255,255,255,0.15); padding: 2px 6px; border-radius: 3px;">{doc['request_id']}</code>
            </p>
        </div>
        <div style="padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px;">
            <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                <tr><td style="padding: 8px; background: #f5f5f5;"><strong>Nombre</strong></td>
                    <td style="padding: 8px;">{doc['nombre']}</td></tr>
                <tr><td style="padding: 8px;"><strong>Rol</strong></td>
                    <td style="padding: 8px;">{doc['role_label']}</td></tr>
                <tr><td style="padding: 8px; background: #f5f5f5;"><strong>Organización</strong></td>
                    <td style="padding: 8px;">{doc['organizacion']}</td></tr>
                <tr><td style="padding: 8px;"><strong>Teléfono</strong></td>
                    <td style="padding: 8px;">{doc['telefono']}</td></tr>
                <tr><td style="padding: 8px; background: #f5f5f5;"><strong>Email</strong></td>
                    <td style="padding: 8px;"><a href="mailto:{doc['email']}" style="color: #0E5E7F;">{doc['email']}</a></td></tr>
                <tr><td style="padding: 8px;"><strong>Cuenca / Territorio</strong></td>
                    <td style="padding: 8px;">{doc['cuenca'] or '—'}</td></tr>
                <tr><td style="padding: 8px; background: #f5f5f5;"><strong>Recibido</strong></td>
                    <td style="padding: 8px; font-family: monospace; font-size: 12px;">{doc['created_at']}</td></tr>
            </table>
            <div style="background: #fff4e6; border-left: 4px solid #d97706; padding: 12px; margin-top: 18px; font-size: 13px; color: #92400e;">
                <strong>Próximo paso:</strong> Revisar FPIC (si role_type=federacion), validar credenciales,
                y actualizar status en Firestore <code>access_requests/{doc['request_id']}</code>.
            </div>
        </div>
        </body></html>
        """
        result = resend.Emails.send({
            "from": from_addr,
            "to": [ADMIN_EMAIL],
            "subject": subject,
            "html": html,
        })
        print(f"[OK] Admin notified for {doc['request_id']} → resend id={result.get('id')}")
        return True
    except Exception as e:
        print(f"[WARN] Resend email failed for {doc['request_id']}: {e}")
        return False


@router.get("/requests")
async def list_access_requests(limit: int = 50):
    """List pending access requests. Useful for the admin dashboard."""
    from db import get_db
    db = get_db()
    docs = (
        db.collection("access_requests")
        .order_by("created_at", direction="DESCENDING")
        .limit(limit)
        .stream()
    )
    return [d.to_dict() for d in docs]
