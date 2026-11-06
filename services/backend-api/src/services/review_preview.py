"""Explicit binding for the isolated, one-community dashboard preview."""
import os
from fastapi import HTTPException


def preview_organization_id() -> int | None:
    if os.getenv("BOOMSAY_REVIEW_PREVIEW", "").lower() != "true":
        return None
    configured = os.getenv("BOOMSAY_PREVIEW_ORGANIZATION_ID", "")
    if not configured.isdecimal() or int(configured) < 1:
        raise HTTPException(503, "Review preview community is not configured")
    return int(configured)


def require_preview_organization(organization_id: int) -> None:
    bound = preview_organization_id()
    if bound is not None and organization_id != bound:
        raise HTTPException(403, "This account does not have access to the preview community")
