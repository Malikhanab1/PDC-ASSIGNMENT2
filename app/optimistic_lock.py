import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Document

logger = logging.getLogger(__name__)


def update_document_with_lock(
    db: Session,
    doc_id: str,
    new_content: str,
    expected_version: int,
) -> Document:

    document = (
        db.query(Document)
        .filter(Document.id == doc_id)
        .first()
    )

    if not document:

        raise HTTPException(
            status_code=404,
            detail="document does not exist"
        )

    current_version = document.version

    if current_version != expected_version:

        logger.warning(
            "version mismatch for %s",
            doc_id
        )

        raise HTTPException(
            status_code=409,
            detail=(
                f"update rejected because document version changed "
                f"(current={current_version}, received={expected_version})"
            )
        )

    document.content = new_content
    document.version += 1

    db.commit()
    db.refresh(document)

    logger.info(
        "document %s updated successfully",
        doc_id
    )

    return document