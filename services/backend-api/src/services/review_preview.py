"""Explicit binding for the isolated, one-community dashboard preview."""
import os
from fastapi import HTTPException


def require_preview_organization(organization_id: int) -> None:
    if os.getenv("BOOMSAY_REVIEW_PREVIEW", "").lower() != "true":
        return
    configured = os.getenv("BOOMSAY_PREVIEW_ORGANIZATION_ID", "")
    if not configured.isdecimal() or int(configured) < 1:
        raise HTTPException(503, "Review preview community is not configured")
    if organization_id != int(configured):
        raise HTTPException(403, "This account does not have access to the preview community")
