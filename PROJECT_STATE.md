# PROJECT_STATE.md
Last updated: 2026-04-18 by Codex

## Completed Tasks
- Phase 0 - Normalize The Project Structure - completed 2026-04-18
  - Created `backend/`, `data/`, `tests/`, `frontend/`, and `minimal_ui/`.
  - Copied the deterministic wind load engine to `backend/wind_load_engine.py`.
  - Copied the engine tests to `tests/test_wind_load_engine.py` and updated imports to `backend.wind_load_engine`.
  - Copied existing JSON data/config files to `data/`.
  - Added `requirements.txt`.
  - Added `pytest.ini` so project-root pytest runs collect the normalized `tests/` directory only.
- Phase 2 - Build FastAPI Backend Skeleton - completed 2026-04-18
  - Added `backend/main.py` with `/health`, `/session/new`, `/session/{session_id}/state`, `/session/{session_id}/message`, and `/session/{session_id}/calculate`.
  - Added `backend/session.py` with an in-memory session store.
  - Added lightweight Phase 2 request/response models in `backend/models.py`.
  - Wired `/session/{session_id}/calculate` to `run_wind_load_calculation()`.

## In Progress
- None.

## Pending
- Phase 1 - Stabilize The Calculation Core
- Phase 3 - Add Backend API Tests
- Phase 4 - Build Deterministic Conversation Controller
- Phase 5 - Add Risk Category And Wind Speed Logic
- Phase 6 - Add LLM Integration Safely
- Phase 7 - Add TTS Backend Module
- Phase 8 - Build Production Frontend
- Phase 9 - Build Report Formatter
- Phase 10 - Commercial Readiness Hardening

## Known Issues / Decisions
- Existing `python_files/` and `json_files/` source directories were left in place for compatibility during normalization.
- The calculation engine still embeds tables/constants in Python; JSON-backed loading remains a later migration.
- `wind_speed_lookup.json` has not been built yet.
- Architecture notes mention 65 passing tests, but this repository currently contains 52 engine tests.

## Test Status
- `python -m pytest -q`: 52 passed on 2026-04-18.
- Phase 2 API smoke test: session creation, state lookup, message persistence, calculation, and missing-session 404 passed on 2026-04-18.
