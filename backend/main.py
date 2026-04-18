"""FastAPI backend skeleton for the ASCE 7-16 wind load calculator."""

from fastapi import FastAPI, HTTPException

from backend.chatbot import process_user_message
from backend.models import (
    CalculationRequest,
    CalculationResponse,
    ChatRequest,
    ChatResponse,
    SessionResponse,
)
from backend.session import (
    append_message,
    create_session,
    get_session,
    store_calculation_result,
)
from backend.wind_load_engine import run_wind_load_calculation


app = FastAPI(
    title="ASCE 7-16 Wind Load Calculator API",
    version="0.2.0",
    description="Phase 2 backend skeleton with in-memory sessions and engine-backed calculation.",
)


def _require_session(session_id: str) -> dict:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")
    return session


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/session/new", response_model=SessionResponse)
def new_session() -> SessionResponse:
    session = create_session()
    return SessionResponse(session_id=session["session_id"], session_state=session)


@app.get("/session/{session_id}/state")
def session_state(session_id: str) -> dict:
    return _require_session(session_id)


@app.post("/session/{session_id}/message", response_model=ChatResponse)
def session_message(session_id: str, request: ChatRequest) -> ChatResponse:
    _require_session(session_id)
    updated_session = append_message(session_id, "user", request.message)
    if updated_session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")

    try:
        response, updated_session = process_user_message(session_id, request.message)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    updated_session = append_message(session_id, "assistant", response)
    if updated_session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")

    return ChatResponse(response=response, session_state=updated_session)


@app.post("/session/{session_id}/calculate", response_model=CalculationResponse)
def calculate(session_id: str, request: CalculationRequest) -> CalculationResponse:
    _require_session(session_id)

    try:
        engine_inputs = request.to_engine_input()
        results = run_wind_load_calculation(engine_inputs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    updated_session = store_calculation_result(
        session_id=session_id,
        inputs=request.model_dump(mode="json"),
        result=results,
    )
    if updated_session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")

    return CalculationResponse(
        session_id=session_id,
        results=results,
        session_state=updated_session,
    )
