"""FastAPI backend skeleton for the ASCE 7-16 wind load calculator."""

from backend.config import load_dotenv_if_present

load_dotenv_if_present()

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.chatbot import llm_status, process_user_message
from backend.models import (
    CalculationRequest,
    CalculationResponse,
    ChatRequest,
    ChatResponse,
    SessionResponse,
    TTSRequest,
)
from backend.session import (
    append_message,
    create_session,
    get_session,
    store_calculation_result,
)
from backend.wind_load_engine import run_wind_load_calculation
from backend.tts import TTSUnavailableError, configured_voice, synthesize_speech
from backend.report_formatter import format_results_as_markdown, format_results_for_display


app = FastAPI(
    title="ASCE 7-16 Wind Load Calculator API",
    version="0.2.0",
    description="Phase 2 backend skeleton with in-memory sessions and engine-backed calculation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _require_session(session_id: str) -> dict:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")
    return session


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "llm": llm_status()}


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
        reply, updated_session = process_user_message(
            session_id,
            request.message,
            llm_enabled=request.llm_enabled,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    updated_session = append_message(session_id, "assistant", reply["display_text"])
    if updated_session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")

    return ChatResponse(
        response=reply["display_text"],
        display_text=reply["display_text"],
        spoken_text=reply["spoken_text"],
        llm_used=reply["llm_used"],
        llm_fallback_reason=reply["llm_fallback_reason"],
        session_state=updated_session,
    )


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
        formatted_display=format_results_for_display(results),
        formatted_markdown=format_results_as_markdown(results, request.model_dump(mode="json")),
        session_state=updated_session,
    )


@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    try:
        audio = await synthesize_speech(request.text, configured_voice(request.voice))
    except TTSUnavailableError as exc:
        return JSONResponse(
            status_code=200,
            content={"tts_available": False, "detail": str(exc)},
        )

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"X-TTS-Available": "true"},
    )
