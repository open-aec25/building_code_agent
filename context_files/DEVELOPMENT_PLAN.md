# ASCE 7-16 Wind Load Calculator - Development Continuation Plan

## Purpose

This document is an agent-ready plan for continuing development of the ASCE 7-16 Wind Load Calculator from the current repository state.

The project goal is to build a conversational web application that collects building inputs, runs deterministic ASCE 7-16 Chapter 27 wind load calculations, and returns a traceable engineering report.

## Current Repository State

The current workspace is earlier-stage than the target architecture described in `context_files/ARCHITECTURE.md`.

### Existing Folders

```text
asce716/
context_files/
json_files/
outputs/
python_files/
```

### Existing Assets

```text
asce716/                         ASCE 7-16 reference PDFs
context_files/ARCHITECTURE.md    Architecture and agent task specification
json_files/*.json                Existing data/config JSON files
python_files/wind_load_engine.py Deterministic wind load calculation engine
python_files/test_wind_load_engine.py
outputs/app_logic_flow.csv       Step-by-step app logic flow
```

### Current Test Status

The calculation engine test suite currently passes when run from `python_files/`:

```powershell
python -m pytest -q
```

Observed result:

```text
52 passed
```

Note: `ARCHITECTURE.md` references 65 passing tests, but the current repository contains 52 passing tests. Treat the repository as source of truth unless the architecture document is updated.

## Missing From Current Repository

The following target files/folders do not exist yet:

```text
backend/
frontend/
minimal_ui/
tests/
data/
requirements.txt
PROJECT_STATE.md
backend/main.py
backend/models.py
backend/session.py
backend/chatbot.py
backend/tts.py
backend/report_formatter.py
data/wind_speed_lookup.json
tests/test_api.py
tests/test_chatbot.py
tests/test_tts.py
```

## Architectural Principles To Preserve

1. The LLM handles conversation, interpretation, and explanation only.
2. The LLM must never perform wind load arithmetic.
3. Python calculation code owns all calculations and ASCE table lookups.
4. JSON files are passive read-only sources of truth.
5. Hardcoded assumptions must be explicitly flagged to the user.
6. Every output value should be traceable to an ASCE 7-16 section, table, figure, or equation.
7. Do not weaken or remove the existing calculation engine tests.

## Important Current Mismatch

The target architecture says ASCE tables/constants live in JSON and are read by the calculation engine.

The current implementation in `python_files/wind_load_engine.py` embeds many constants and tables directly in Python.

For near-term development, do not refactor this immediately. Preserve the current engine behavior first, get the backend working, then plan a later migration from embedded constants/tables to JSON-backed data loading.

## Recommended Development Sequence

---

## Phase 0 - Normalize The Project Structure

### Goal

Bring the repository layout closer to the target architecture without changing calculation behavior.

### Tasks

1. Create the target folders:

```text
backend/
data/
tests/
frontend/
minimal_ui/
```

2. Move or copy current implementation files:

```text
python_files/wind_load_engine.py      -> backend/wind_load_engine.py
python_files/test_wind_load_engine.py -> tests/test_wind_load_engine.py
json_files/*.json                     -> data/*.json
```

3. Add `requirements.txt` with at least:

```text
fastapi
uvicorn
pydantic
pytest
httpx
anthropic
openai
```

4. Add `PROJECT_STATE.md`.

### Acceptance Criteria

- The target folders exist.
- The engine test file runs from the new `tests/` location.
- Existing engine behavior is unchanged.
- `python -m pytest -q` passes.
- `PROJECT_STATE.md` reflects the current completed, pending, and in-progress items.

### Do Not Change

- Do not rewrite the calculation engine.
- Do not alter ASCE formulas or coefficients.
- Do not change expected test values unless there is a documented engineering correction.

---

## Phase 1 - Stabilize The Calculation Core

### Goal

Ensure the deterministic calculation engine remains stable after the repo is normalized.

### Tasks

1. Fix imports after moving files.
2. Confirm tests still pass.
3. Add a lightweight README note documenting how to run the engine tests.
4. Add a follow-up task to eventually load data tables from JSON, but do not perform that migration yet.

### Acceptance Criteria

- Current engine tests pass from the new project layout.
- The public API remains:

```python
from backend.wind_load_engine import BuildingInputs, run_wind_load_calculation
```

- No behavioral changes are introduced.

### Do Not Change

- Do not convert table data to JSON in this phase.
- Do not add LLM logic to the calculation engine.

---

## Phase 2 - Build FastAPI Backend Skeleton

### Goal

Create a working backend API before adding LLM complexity.

### Tasks

1. Create `backend/main.py`.
2. Create `backend/session.py`.
3. Create `backend/models.py`.
4. Implement these routes:

```text
POST /session/new
GET  /session/{session_id}/state
POST /session/{session_id}/message
POST /session/{session_id}/calculate
```

5. Wire `/session/{session_id}/calculate` directly to `run_wind_load_calculation()`.
6. Use an in-memory session store for v1.

### Acceptance Criteria

- `POST /session/new` returns a unique `session_id`.
- `GET /session/{session_id}/state` returns current session state.
- `POST /session/{session_id}/calculate` accepts a complete calculation payload and returns engine results.
- Invalid inputs return appropriate validation errors.
- Backend can be started with:

```powershell
uvicorn backend.main:app --reload
```

### Do Not Change

- Do not add Anthropic or OpenAI calls yet.
- Do not implement production auth yet.
- Do not let API routes perform engineering math directly.

---

## Phase 3 - Add Backend API Tests

### Goal

Protect the backend API before adding chatbot and frontend layers.

### Tasks

1. Create `tests/test_api.py`.
2. Use FastAPI `TestClient` or `httpx`.
3. Test session creation.
4. Test calculation endpoint with known valid inputs.
5. Test invalid input handling.
6. Test session isolation.

### Acceptance Criteria

- API tests pass together with engine tests.
- Test suite can be run with:

```powershell
python -m pytest -q
```

- At least one valid calculation request proves backend-to-engine integration.

### Do Not Change

- Do not mock the calculation engine for the main happy-path integration test.
- Do not require external API keys for tests.

---

## Phase 4 - Build Deterministic Conversation Controller

### Goal

Implement the conversation state machine before adding LLM interpretation.

### Rationale

The backend should own flow control. The LLM can later assist with interpretation and wording, but it should not be the first source of truth for phase transitions, branch logic, or stored engineering inputs.

### Tasks

1. Create initial `backend/chatbot.py`.
2. Load `data/conversation_flow.json`.
3. Track:

```text
session_id
current_phase
current_question_id
collected_inputs
branch_flags
ready_to_calculate
```

4. Ask one question at a time.
5. Store answers in structured session state.
6. Implement branch logic:

```text
Topographic detail questions only if topographic feature is present.
Roof slope and ridge orientation only if roof is not flat.
```

7. Generate Phase 7 confirmation summary.
8. Add basic correction handling.

### Acceptance Criteria

- A user can progress through the 7-phase flow without external LLM calls.
- Session state updates after each answer.
- Branching works for:

```text
No topographic feature -> skip topographic detail questions.
Flat roof -> skip slope and ridge orientation.
Non-flat roof -> collect slope and ridge orientation.
```

- Confirmation summary is generated before calculation.

### Do Not Change

- Do not call Anthropic yet.
- Do not perform wind load calculations in chatbot code.
- Do not store unvalidated free text directly as engineering inputs when a typed value is expected.

---

## Phase 5 - Add Risk Category And Wind Speed Logic

### Goal

Implement deterministic derivations and lookup behavior required by the conversation.

### Tasks

1. Add helper logic for `data/risk_category.json`.
2. Build `data/wind_speed_lookup.json`.
3. Implement location lookup for:

```text
City
City/state
State abbreviation
ZIP or ZIP prefix
```

4. Add fallback behavior when lookup fails.
5. Add tests for risk category and wind speed lookup.

### Acceptance Criteria

- Risk Category can be derived from Phase 1 answers.
- Basic wind speed can be resolved from known locations.
- Failed lookup asks the user for manual wind speed entry.
- Tests cover at least representative normal and failure cases.

### Do Not Change

- Do not let the LLM guess wind speed.
- Do not claim full national wind-speed map coverage unless the data actually supports it.
- Do not hide manual lookup fallback from the user.

---

## Phase 6 - Add LLM Integration Safely

### Goal

Add Anthropic Claude as a controlled assistant layer while preserving deterministic backend ownership of state and calculation.

### Tasks

1. Extend `backend/chatbot.py` to call Anthropic only after deterministic flow works.
2. Use the LLM for:

```text
Natural-language interpretation
Friendly explanations
Clarifying ambiguous input
Generating display_text
Generating spoken_text
```

3. Require structured output from the LLM:

```json
{
  "display_text": "...",
  "spoken_text": "...",
  "field_update": {},
  "needs_clarification": false
}
```

4. Validate LLM responses using Pydantic models before updating session state.
5. Keep backend validation as the final authority.

### Acceptance Criteria

- LLM responses never directly perform arithmetic.
- LLM output is validated before use.
- The app can recover from malformed LLM output.
- Tests mock Anthropic API calls.

### Do Not Change

- Do not store raw LLM output as trusted engineering state.
- Do not let the LLM choose ASCE coefficients or calculate pressures.
- Do not require live Anthropic calls in automated tests.

---

## Phase 7 - Add TTS Backend Module

### Goal

Add optional text-to-speech for assistant responses.

### Tasks

1. Create `backend/tts.py`.
2. Implement:

```python
async def synthesize_speech(text: str, voice: str = "alloy") -> bytes
```

3. Add `POST /tts` route in `backend/main.py`.
4. Use environment variables:

```text
OPENAI_API_KEY
TTS_VOICE
TTS_ENABLED
```

5. Return `audio/mpeg`.
6. Gracefully degrade if TTS fails.
7. Create `tests/test_tts.py` with mocked OpenAI calls.

### Acceptance Criteria

- TTS route returns MP3 bytes when enabled and successful.
- TTS failures do not break chat flow.
- Tests do not require live OpenAI API calls.

### Do Not Change

- Do not put OpenAI API keys in frontend code.
- Do not hardcode secrets.
- Do not send markdown-heavy `display_text` to TTS; use `spoken_text`.

---

## Phase 8 - Build Production Frontend

### Goal

Create a browser UI connected to the FastAPI backend.

### Recommendation

Skip or de-prioritize the direct-browser API-key `minimal_ui` unless a throwaway demo is specifically required. It is useful for speed, but it is not a production-safe architecture.

### Tasks

1. Create:

```text
frontend/index.html
frontend/app.js
frontend/styles.css
```

2. Connect to backend routes.
3. Implement:

```text
Chat history
User input field
Send button
Enter-to-send
Loading state
Phase progress indicator
New session button
Results display
TTS mute/unmute behavior
```

4. Render calculation results as structured tables and summaries, not raw JSON.

### Acceptance Criteria

- User can complete a session through the browser UI.
- User can submit enough information to trigger calculation.
- Results are readable by an engineer or designer.
- TTS is optional and does not block the app.
- UI is usable on desktop and tablet.

### Do Not Change

- Do not expose API keys in frontend code.
- Do not make the frontend perform engineering calculations.
- Do not display raw JSON as the primary result view.

---

## Phase 9 - Build Report Formatter

### Goal

Convert raw calculation output into a defensible engineering report.

### Tasks

1. Create `backend/report_formatter.py`.
2. Implement:

```python
def format_results_for_display(results: dict) -> dict:
    ...

def format_results_as_markdown(results: dict, inputs: BuildingInputs) -> str:
    ...
```

3. Include:

```text
Project summary
User inputs
Hardcoded assumptions/defaults
ASCE references
Intermediate values
Final wall pressures
Final roof pressures
Minimum pressure checks
Warnings or limitations
```

4. Add report formatter tests.

### Acceptance Criteria

- Markdown report is readable and traceable.
- UI display structure is easier to render than raw engine output.
- All assumptions/defaults are visible.
- Tests verify major report sections exist.

### Do Not Change

- Do not hide hardcoded assumptions.
- Do not remove ASCE references from output.
- Do not present the report as stamped or final engineering design.

---

## Phase 10 - Commercial Readiness Hardening

### Goal

Move from MVP toward a credible commercial application.

### Tasks

1. Replace in-memory sessions with Redis or database-backed sessions.
2. Add project persistence.
3. Add user authentication.
4. Add role-based access control if multi-user teams are required.
5. Add calculation history and versioning.
6. Add structured logs.
7. Add request IDs.
8. Add model-call audit trail.
9. Add CI test runner.
10. Add deployment configuration.
11. Add data retention and PII-handling policy.
12. Add ASCE data licensing/provenance review.

### Acceptance Criteria

- App can survive process restarts without losing sessions/projects.
- Calculations can be reproduced later.
- Logs provide enough information to debug failures.
- CI blocks merges on failing tests.
- Secrets are managed server-side only.

---

## Immediate Next Sprint

If only one sprint is assigned next, do this:

1. Normalize repo into `backend/`, `data/`, and `tests/`.
2. Add `requirements.txt`.
3. Add `PROJECT_STATE.md`.
4. Move engine and tests.
5. Confirm current tests still pass.
6. Build FastAPI backend skeleton.
7. Add `/session/{session_id}/calculate` endpoint.
8. Add API tests.

## First MVP Milestone

The first milestone should be:

```text
User submits a complete BuildingInputs payload to FastAPI.
FastAPI calls wind_load_engine.py.
Backend returns structured calculation results.
Tests prove the flow works.
```

This creates a stable application spine. Chatbot logic, frontend UI, TTS, and reporting should build around that spine rather than before it.

## Agent Handoff Template

Use this template when assigning tasks to another agent.

```markdown
## Task

[Task name and phase]

## Goal

[One paragraph describing the intended outcome]

## Files To Read First

- context_files/ARCHITECTURE.md
- context_files/DEVELOPMENT_PLAN.md
- [Any specific implementation files]

## Files To Modify

- [Exact paths]

## Acceptance Criteria

- [Pass/fail condition 1]
- [Pass/fail condition 2]
- [Pass/fail condition 3]

## Do Not Change

- [Protected file or behavior]
- [Protected file or behavior]

## Verification

Run:

```powershell
python -m pytest -q
```

Expected:

```text
All tests pass.
```
```

