"""Pages package initialization."""

from . import (
    dashboard,
    upload_receipts,
    receipt_management,
    analytics,
    export_reports,
    settings
)

__all__ = [
    "dashboard",
    "upload_receipts",
    "receipt_management",
    "analytics",
    "export_reports",
    "settings"
]