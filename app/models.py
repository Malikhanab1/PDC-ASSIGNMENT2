from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

from app.database import Base


class Document(Base):

    __tablename__ = "documents"

    id = Column(
        String,
        primary_key=True,
        index=True
    )

    title = Column(
        String,
        nullable=False
    )

    content = Column(
        Text,
        nullable=False
    )

    version = Column(
        Integer,
        default=1,
        nullable=False
    )


class WebhookEvent(Base):

    __tablename__ = "webhook_events"

    id = Column(
        String,
        primary_key=True,
        index=True
    )

    event_type = Column(
        String,
        nullable=False
    )

    payload = Column(
        Text,
        nullable=False
    )

    status = Column(
        String,
        default="processed",
        nullable=False
    )

    processed_at = Column(
        DateTime,
        default=datetime.utcnow
    )