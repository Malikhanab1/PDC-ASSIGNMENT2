# Malik Hanab - BSAI23033
**PDC Assignment 2: Resilient Distributed Systems**

---

## 📌 Project Overview
This project is a refactored and hardened version of the StudySync backend. It addresses three critical distributed systems failures identified in the assignment using industry-standard architectural patterns. 

The primary goal of this implementation is to ensure **Fault Tolerance**, **Data Consistency**, and **Availability** even when network or external service failures occur.

---

## 🛠️ Resilience Implementations

| Feature | Problem Solved | Implementation Pattern |
|:--- |:--- |:--- |
| **Document Sync** | Lost Updates (Problem 1) | **Optimistic Locking**: Implemented a version-tracking mechanism in the database to prevent concurrent writes from overwriting each other. |
| **Clerk Integration** | Dropped Webhooks (Problem 2) | **Idempotent Receiver**: Used unique Event IDs (svix-id) as database primary keys to ensure that duplicate or retried webhooks do not cause inconsistent state. |
| **AI Summarization** | LLM Hangs (Problem 3) | **Circuit Breaker**: Implemented a state-machine (Closed, Open, Half-Open) that detects timeouts and provides an immediate fallback response to keep the server responsive. |

**Assignment Requirement Check:** - [x] Custom Header `X-Student-ID: BSAI23033` added to every response.
- [x] Repository named `PDC-Sp24-BSAI23033-Rizwan`.
- [x] All three problems addressed and fixed.

---

## 📁 Project Structure
```text
.
├── app/
│   ├── main.py            # Entry point with Student ID Middleware
│   ├── models.py          # SQLAlchemy models for Docs and Webhooks
│   ├── database.py        # SQLite & Session management
│   ├── optimistic_lock.py # Logic for preventing Lost Updates
│   ├── circuit_breaker.py # Circuit Breaker logic (Problem 3)
│   └── webhook_handler.py # Logic for Idempotency (Problem 2)
├── tests/
│   └── test_all.py        # Automated Pytest suite
├── requirements.txt       # Dependencies (FastAPI, SQLAlchemy, etc.)
└── demo.sh                # Script to demonstrate fixes via Curl

---

## Quick Start

### 1. Install & Run Server

```bash
bash setup.sh
```

This creates a Python virtual environment, installs all dependencies, and starts the server at **http://127.0.0.1:8000**.

Interactive API docs: **http://127.0.0.1:8000/docs**

### 2. Run Tests (in a new terminal)

```bash
bash run_tests.sh
```

Expected output: **10 passed** — covering all three fixes and the middleware header.

### 3. Run Live Demo (server must be running)

```bash
bash demo.sh
```

Shows before/after for all three bugs using `curl`.

---

## Manual Testing

```bash
# Health check (verify X-Student-ID header)
curl -I http://127.0.0.1:8000/health

# Create a document
curl -s -X POST "http://127.0.0.1:8000/documents/?title=Test&content=Hello"

# Simulate concurrent write conflict (replace DOC_ID with actual ID)
curl -s -X PUT "http://127.0.0.1:8000/documents/DOC_ID?content=Alice&expected_version=1"
curl -s -X PUT "http://127.0.0.1:8000/documents/DOC_ID?content=Bob&expected_version=1"
# → Second returns 409 Conflict

# Simulate duplicate webhook
curl -s -X POST http://127.0.0.1:8000/webhooks/clerk \
  -H "Content-Type: application/json" \
  -H "svix-id: evt-unique-001" \
  -d '{"type":"subscription.cancelled","data":{"id":"user_123"}}'
# → Re-send same command → returns {"status":"duplicate"}

# Trigger circuit breaker (3 failures → OPEN)
for i in 1 2 3; do
  curl -s -X POST "http://127.0.0.1:8000/ai/summarise?prompt=x&simulate_failure=true"
done
curl -s -X POST "http://127.0.0.1:8000/ai/summarise?prompt=x"
# → Returns instant fallback from OPEN circuit
```

---

## Dependencies

- Python 3.10+
- fastapi, uvicorn, sqlalchemy (see requirements.txt)
- No external services required — SQLite is used for the DB

---

## Student ID Header

All API responses include:
```
X-Student-ID: 24I-XXXX
```

Configured in `app/main.py` via `StudentIDMiddleware`. **Replace `STUDENT_ID` with your actual ID before submission.**
