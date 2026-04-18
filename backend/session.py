"""In-memory session storage for the first backend API skeleton."""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


SessionDict = dict[str, Any]

_sessions: dict[str, SessionDict] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session() -> SessionDict:
    """Create and store a new empty conversation/calculation session."""
    session_id = str(uuid4())
    session = {
        "session_id": session_id,
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "current_phase": 1,
        "collected_inputs": {},
        "messages": [],
        "ready_to_calculate": False,
        "last_calculation": None,
    }
    _sessions[session_id] = session
    return deepcopy(session)


def get_session(session_id: str) -> SessionDict | None:
    """Return a defensive copy of a session, if it exists."""
    session = _sessions.get(session_id)
    if session is None:
        return None
    return deepcopy(session)


def append_message(session_id: str, role: str, content: str) -> SessionDict | None:
    """Append a message to a session and return the updated session."""
    session = _sessions.get(session_id)
    if session is None:
        return None
    session["messages"].append(
        {
            "role": role,
            "content": content,
            "created_at": _utc_now_iso(),
        }
    )
    session["updated_at"] = _utc_now_iso()
    return deepcopy(session)


def update_collected_inputs(session_id: str, inputs: dict[str, Any]) -> SessionDict | None:
    """Merge structured inputs into the session state."""
    session = _sessions.get(session_id)
    if session is None:
        return None
    session["collected_inputs"].update(inputs)
    session["updated_at"] = _utc_now_iso()
    return deepcopy(session)


def store_calculation_result(
    session_id: str,
    inputs: dict[str, Any],
    result: dict[str, Any],
) -> SessionDict | None:
    """Store the latest calculation payload and engine result for a session."""
    session = _sessions.get(session_id)
    if session is None:
        return None
    session["collected_inputs"] = deepcopy(inputs)
    session["last_calculation"] = deepcopy(result)
    session["ready_to_calculate"] = True
    session["updated_at"] = _utc_now_iso()
    return deepcopy(session)

