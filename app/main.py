"""
Fault tolerance implementation for external AI service handling.
"""

import asyncio
import uuid
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from starlette.middleware.base import BaseHTTPMiddleware as BaseMiddleware

from app.database import init_db, get_db, SessionLocal
from app.models import Document, WebhookEvent
from app.circuit_breaker import CircuitBreaker, ServiceUnavailableError
from app.optimistic_lock import update_document_with_lock
from app.webhook_handler import process_webhook_event

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

llm_circuit_breaker = CircuitBreaker(
    max_failures=3,
    reset_after=8,
    service_name="llm-service"
)


@asynccontextmanager
async def lifespan(app: FastAPI):

    init_db()

    logger.info("database initialized")

    yield

    logger.info("application shutdown")


app = FastAPI(
    title="StudySync API",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STUDENT_ID = "BSAI23033"


class StudentIDMiddleware(BaseMiddleware):

    async def dispatch(self, request: Request, call_next):

        response = await call_next(request)

        response.headers["X-Student-ID"] = STUDENT_ID

        return response


app.add_middleware(StudentIDMiddleware)

# document routes


@app.post("/documents/", status_code=201)
def create_document(
    title: str,
    content: str,
    db: SessionLocal = Depends(get_db)
):

    doc = Document(
        id=str(uuid.uuid4()),
        title=title,
        content=content,
        version=1
    )

    db.add(doc)

    db.commit()

    db.refresh(doc)

    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "version": doc.version
    }


@app.get("/documents/{doc_id}")
def get_document(
    doc_id: str,
    db: SessionLocal = Depends(get_db)
):

    doc = db.query(Document).filter(Document.id == doc_id).first()

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="document not found"
        )

    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "version": doc.version
    }


@app.put("/documents/{doc_id}")
def update_document(
    doc_id: str,
    content: str,
    expected_version: int,
    db: SessionLocal = Depends(get_db),
):

    doc = update_document_with_lock(
        db,
        doc_id,
        content,
        expected_version
    )

    return {
        "id": doc.id,
        "content": doc.content,
        "version": doc.version,
        "message": "document updated"
    }


# webhook routes


@app.post("/webhooks/clerk")
async def clerk_webhook(
    request: Request,
    db: SessionLocal = Depends(get_db)
):

    event_key = request.headers.get("svix-id")

    if not event_key:
        event_key = str(uuid.uuid4())

    body = await request.json()

    result = process_webhook_event(
        db,
        event_key,
        body
    )

    return result


@app.get("/webhooks/events")
def list_webhook_events(
    db: SessionLocal = Depends(get_db)
):

    events = db.query(WebhookEvent).all()

    return [
        {
            "id": event.id,
            "type": event.event_type,
            "status": event.status
        }
        for event in events
    ]


# AI routes


async def call_llm_api(
    prompt: str,
    simulate_failure: bool = False
):

    if simulate_failure:

        await asyncio.sleep(0.1)

        raise ConnectionError("simulated AI service failure")

    await asyncio.sleep(0.05)

    return f"generated response for: {prompt}"


@app.post("/ai/summarise")
async def summarise(
    prompt: str,
    simulate_failure: bool = False
):

    fallback_reply = {
        "message": "AI service currently unavailable",
        "status": "degraded",
        "breaker_state": llm_circuit_breaker.state,
    }

    try:

        output = await llm_circuit_breaker.execute(
            call_llm_api,
            prompt,
            simulate_failure=simulate_failure
        )

        return {
            "message": output,
            "status": "success",
            "breaker_state": llm_circuit_breaker.state,
        }

    except ServiceUnavailableError:

        return JSONResponse(
            status_code=503,
            content=fallback_reply
        )

    except Exception as exc:

        logger.error("AI request failed: %s", exc)

        return JSONResponse(
            status_code=503,
            content={
                **fallback_reply,
                "temporary_issue": True
            }
        )


@app.get("/ai/circuit-status")
def circuit_status():

    return {
        "breaker_state": llm_circuit_breaker.state,
        "failed_attempts": llm_circuit_breaker.current_failures,
        "limit_before_open": llm_circuit_breaker.max_failures,
        "service": "llm-service"
    }


@app.get("/health")
def health():

    return {
        "status": "ok",
        "student_id": STUDENT_ID
    }