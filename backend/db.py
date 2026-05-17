"""Firestore database client — singleton with emulator support."""
from __future__ import annotations
import os

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client

from config import settings

_db: Client | None = None


def get_db() -> Client:
    global _db
    if _db is not None:
        return _db

    if settings.firestore_emulator_host:
        os.environ["FIRESTORE_EMULATOR_HOST"] = settings.firestore_emulator_host

    if not firebase_admin._apps:
        if settings.google_application_credentials:
            cred = credentials.Certificate(settings.google_application_credentials)
            firebase_admin.initialize_app(cred, {"projectId": settings.google_cloud_project})
        else:
            # Use Application Default Credentials (Cloud Run / local gcloud auth)
            firebase_admin.initialize_app(options={"projectId": settings.google_cloud_project or "guardian-del-agua"})

    _db = firestore.client()
    return _db
