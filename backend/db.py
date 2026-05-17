"""Firestore database client — singleton with emulator + production support."""
from __future__ import annotations
import json
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client

from config import settings

_db: Client | None = None


def _load_credentials() -> credentials.Certificate | None:
    """
    Load GCP service account credentials in this priority order:
      1. GOOGLE_APPLICATION_CREDENTIALS_JSON (env var with full JSON content — Railway/Vercel)
      2. GOOGLE_APPLICATION_CREDENTIALS (env var with file path — local dev)
      3. None → use Application Default Credentials (Cloud Run / gcloud auth)
    """
    # Production: full JSON pasted into env var (Railway, Vercel, etc.)
    json_blob = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON") or settings.google_application_credentials_json
    if json_blob:
        try:
            cred_dict = json.loads(json_blob)
            return credentials.Certificate(cred_dict)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"GOOGLE_APPLICATION_CREDENTIALS_JSON is not valid JSON: {e}")

    # Local dev: file path
    if settings.google_application_credentials:
        path = Path(settings.google_application_credentials)
        if path.exists():
            return credentials.Certificate(str(path))

    return None


def get_db() -> Client:
    global _db
    if _db is not None:
        return _db

    if settings.firestore_emulator_host:
        os.environ["FIRESTORE_EMULATOR_HOST"] = settings.firestore_emulator_host

    if not firebase_admin._apps:
        cred = _load_credentials()
        project_id = settings.google_cloud_project or "guardian-del-agua"
        if cred is not None:
            firebase_admin.initialize_app(cred, {"projectId": project_id})
        else:
            # Application Default Credentials (Cloud Run, gcloud auth)
            firebase_admin.initialize_app(options={"projectId": project_id})

    _db = firestore.client()
    return _db
