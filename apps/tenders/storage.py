"""Storage helpers for confidential tender documents.

The ``FileField`` uses the ``tender_documents`` storage alias so the same code
path targets the local filesystem in dev and a private Cloudflare R2 bucket in
production — chosen entirely by settings, never by the model.
"""

from django.core.files.storage import Storage, storages


def tender_document_storage() -> Storage:
    """Callable passed to ``FileField(storage=...)`` — resolved lazily so the
    active ``STORAGES["tender_documents"]`` backend is used, and it deconstructs
    to a stable import path for migrations."""
    return storages["tender_documents"]


def tender_document_upload_to(instance: "object", filename: str) -> str:
    # tenders/{tender.public_id}/{filename}
    return f"tenders/{instance.tender.public_id}/{filename}"
