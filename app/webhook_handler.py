import json
import logging

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import WebhookEvent

logger = logging.getLogger(__name__)


def process_webhook_event(
    db: Session,
    idempotency_key: str,
    payload: dict
):

    existing_event = (
        db.query(WebhookEvent)
        .filter(WebhookEvent.id == idempotency_key)
        .first()
    )

    if existing_event:

        logger.info(
            "duplicate webhook ignored: %s",
            idempotency_key
        )

        return {
            "status": "duplicate",
            "event_id": idempotency_key
        }

    event_type = payload.get("type", "unknown")

    logger.info(
        "processing event %s",
        event_type
    )

    try:

        stored_event = WebhookEvent(
            id=idempotency_key,
            event_type=event_type,
            payload=json.dumps(payload),
            status="processed",
            processed_at=datetime.utcnow()
        )

        db.add(stored_event)

        db.commit()

    except IntegrityError:

        db.rollback()

        logger.warning(
            "duplicate insert blocked"
        )

        return {
            "status": "duplicate",
            "event_id": idempotency_key
        }

    return {
        "status": "processed",
        "event_id": idempotency_key,
        "type": event_type
    }