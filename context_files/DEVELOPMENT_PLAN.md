# ASCE 7-16 Wind Load Calculator - Development Continuation Plan

## Purpose

This document is an agent-ready plan for continuing development of the ASCE 7-16 Wind Load Calculator from the current repository state.

The project goal is to build a conversational web application that collects building inputs, runs deterministic ASCE 7-16 Chapter 27 wind load calculations, and returns a traceable engineering report.

## Current Repository State

As of 2026-05-18, the repository has reached open-source demo readiness and has completed a TEDDS-style benchmark alignment pass for a flat-roof ASCE 7-16 Chapter 27 MWFRS example. The backend, deterministic conversation controller, optional LLM polish, Massachusetts wind lookup, backend TTS route, report formatter, production vanilla frontend, public docs, and Windows demo launchers are implemented.

### Existing Folders

```text
asce716/
backend/
context_files/
data/
frontend/
json_files/
logs/                         generated locally by run_demo.ps1; ignored
minimal_ui/
outputs/
python_files/
tests/
```

### Existing Assets

```text
asce716/                         ASCE 7-16 reference PDFs
context_files/ARCHITECTURE.md    Architecture and agent task specification
backend/main.py                  FastAPI app with session, chat, calculate, and TTS routes
backend/chatbot.py               Deterministic 7-phase conversation controller with optional LLM polish
backend/report_formatter.py      UI-friendly and markdown calculation formatting
backend/tts.py                   Optional backend-only OpenAI TTS integration
frontend/index.html              Production demo UI shell
frontend/app.js                  Session, chat, formatted results, TTS, and dynamic apiBase handling
frontend/styles.css              Responsive frontend styling
README.md                        Public setup, scope, limitations, and demo scenarios
CONTRIBUTING.md                  Contributor guidance and calculation-change guardrails
.env.example                     Runtime configuration template without secrets
run_demo.ps1                     Windows PowerShell launcher with logs, dynamic ports, and timestamped fallback logs if previous processes lock log files
run_demo.bat                     Batch wrapper for the PowerShell launcher
json_files/*.json                Existing data/config JSON files
data/ma_780_cmr_table_1604_11.*  Massachusetts 780 CMR Table 1604.11 lookup data
data/raw_780_cmr_chapter_16_cornell.html  Raw Cornell LII source for MA Table 1604.11
python_files/scrape_780_cmr_table_1604_11.py  Regenerates MA Table 1604.11 JSON/JSONL/CSV
outputs/app_logic_flow.csv       Step-by-step app logic flow
tests/*.py                       Pytest suite for engine, API, TTS, and formatter behavior
```

### Current Test Status

The current project test suite passes from the repository root:

```powershell
python -m pytest -q
```

Observed result:

```text
94 passed
```

The test suite includes engine coverage, API/conversation flows, Massachusetts lookup behavior, mocked LLM fallback/polish behavior, mocked TTS behavior, report formatter checks, and benchmark-oriented checks for flat-roof Cp selection, raw pressure preservation, orthogonal wind direction summaries, and overall horizontal force checks.

## Remaining Known Gaps

- `data/wind_speed_lookup.json` is still missing as a national lookup.
- Massachusetts city/town lookup is integrated through `data/ma_780_cmr_table_1604_11.json`; ZIP-only lookup is not supported by the current municipal-table path.
- The calculation engine still embeds many constants/tables in Python; JSON-backed migration remains a future task.
- Sloped-roof direction-specific roof zone geometry/force expansion is still limited compared with the flat-roof benchmark path.
- In-memory sessions are acceptable for the demo but reset when the backend process restarts.
- C&C, ASCE 7-22, non-US locations, partially enclosed/open buildings, flexible structures, and commercial persistence/auth are out of scope for the current demo.

## Architectural Principles To Preserve

1. The deterministic backend owns conversation progression, validation, lookups, and calculation handoff.
2. The optional LLM handles interpretation fallback and response polish only.
3. The LLM must never perform wind load arithmetic.
4. Python calculation code owns all calculations and ASCE table lookups.
5. JSON files are passive read-only sources of truth.
6. Hardcoded assumptions must be explicitly flagged to the user.
7. Every output value should be traceable to an ASCE 7-16 section, table, figure, or equation.
8. Do not weaken or remove the existing calculation engine tests.

## Important Current Mismatch

The target architecture says ASCE tables/constants live in JSON and are read by the calculation engine.

The current implementation in `python_files/wind_load_engine.py` embeds many constants and tables directly in Python.

For near-term development, do not refactor this immediately. Preserve the current engine behavior first, get the backend working, then plan a later migration from embedded constants/tables to JSON-backed data loading.

## Recommended Development Sequence

---

## Completed 2026-05-18 - TEDDS-Style MWFRS Benchmark Alignment

### Goal

Improve trust in the deterministic calculation engine by aligning a simple flat-roof ASCE 7-16 Chapter 27 MWFRS benchmark with a commercial TEDDS-style reference calculation.

### Implemented

1. Corrected flat-roof Cp selection at the important `h/L = 0.5` boundary:

```text
h/L <= 0.5:
0 to h     Cp = -0.9
h to 2h    Cp = -0.5
beyond 2h  Cp = -0.3
```

2. Preserved raw calculated surface pressures instead of substituting ASCE minimum pressures into individual leeward, side-wall, or roof pressure rows.
3. Added roof zone geometry and area output for flat-roof zones, suppressing zero-width zones from pressure rows.
4. Added 0° and 90° wind direction case summaries by swapping along-wind/transverse dimensions.
5. Reworked overall horizontal force checks to use consistent `+GCpi` and `-GCpi` load cases before comparing to the §27.1.5 minimum horizontal force.
6. Updated the report formatter to show calculated pressures and wind-direction horizontal force checks.
7. Updated `run_demo.ps1` so locked log files from previous background processes do not abort startup; it now falls back to timestamped log files.
8. Added/updated tests for the TEDDS-style flat-roof benchmark, wind direction dimension swapping, raw pressure preservation, and formatted output.

### Verification

```powershell
python -m pytest -q
```

Observed:

```text
94 passed
```

### Remaining Notes

- The flat-roof benchmark path is now much closer to the commercial reference. For the 30 ft x 30 ft, h = 15 ft, Exposure C, V = 120 mph case, `qh = 26.634 psf`, roof Cp values are `-0.9` and `-0.5`, and the overall horizontal force check reports approximately `13.244 kips` versus a `7.2 kips` minimum.
- Sloped roof direction-specific zone geometry and commercial-style force tables remain future improvements.

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

Current status: Risk category logic, manual wind-speed fallback, and Massachusetts city/town wind-speed lookup are implemented in `backend/chatbot.py`. The national `data/wind_speed_lookup.json` remains pending.

### Tasks

1. Add helper logic for `data/risk_category.json`.
2. Build or integrate wind-speed lookup data.
   - National lookup is still pending as `data/wind_speed_lookup.json`.
   - Massachusetts lookup should use `data/ma_780_cmr_table_1604_11.json` first; do not hand-copy its values.
3. Implement location lookup for:

```text
City
City/state
State abbreviation
ZIP or ZIP prefix
```

4. Add fallback behavior when lookup fails.
5. Add tests for risk category and wind speed lookup.

### Massachusetts Lookup Workflow

Use this workflow before a national lookup exists:

1. Detect Massachusetts locations from user text such as `Boston`, `Boston MA`, `Boston, Massachusetts`, or a future geocoder result.
2. Resolve the input to a `city_town` in `data/ma_780_cmr_table_1604_11.json`.
3. Select the basic wind speed by derived Risk Category:

```text
Risk Category I   -> basic_wind_speed_v_mph.risk_category_i
Risk Category II  -> basic_wind_speed_v_mph.risk_category_ii
Risk Category III -> basic_wind_speed_v_mph.risk_category_iii
Risk Category IV  -> basic_wind_speed_v_mph.risk_category_iv
```

4. Store the selected speed as the engine input `basic_wind_speed_V`.
5. Cite `780 CMR Table 1604.11` in the confirmation message.
6. If `note_refs` contains `2`, tell the user that the municipality is flagged for Special Wind Region/local-condition review and that the AHJ or ASCE hazard data may govern a higher value.
7. If MA lookup fails, fall back to the existing manual wind-speed prompt.

The JSONL file, `data/ma_780_cmr_table_1604_11.jsonl`, is optimized for RAG/indexing. Runtime code should prefer the canonical JSON file.

To regenerate the MA dataset from the saved Cornell HTML:

```powershell
python python_files\scrape_780_cmr_table_1604_11.py
```

### Acceptance Criteria

- Risk Category can be derived from Phase 1 answers.
- Basic wind speed can be resolved from known locations.
- Massachusetts municipalities can resolve from `data/ma_780_cmr_table_1604_11.json`.
- Failed lookup asks the user for manual wind speed entry.
- Tests cover at least representative normal and failure cases.
- Tests cover Massachusetts examples including Boston, Cambridge, Worcester, Chatham, Aquinnah (Gay Head), Mount Washington, and an unknown municipality fallback.

### Do Not Change

- Do not let the LLM guess wind speed.
- Do not claim full national wind-speed map coverage unless the data actually supports it.
- Do not present the MA municipal dataset as a full ASCE 7-16 national lookup.
- Do not ignore note ref `2` on Massachusetts records; it is a Special Wind Region/local-conditions warning.
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

### Current Status

Completed 2026-04-26. `frontend/index.html`, `frontend/app.js`, and `frontend/styles.css` implement the production demo UI. The UI creates/restores sessions, renders backend `display_text`, tracks conversation phase, posts user messages, requests backend `/tts` with `spoken_text`, hides voice controls when TTS is unavailable, and renders backend `formatted_display`/`formatted_markdown` after completion. `frontend/app.js` also accepts `?apiBase=...` so `run_demo.ps1` can use dynamic backend ports safely.

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

### Current Status

Completed 2026-04-26. `backend/report_formatter.py` returns both `formatted_display` for the frontend and `formatted_markdown` for a readable calculation report. `/session/{session_id}/calculate` returns raw `results`, `formatted_display`, and `formatted_markdown`.

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

## Phase 10 - Open Source Demo Readiness

### Goal

Prepare the project for public open-source demo sharing without turning it into commercial-production infrastructure.

### Current Status

Completed 2026-04-26.

Implemented:

- `README.md` with project purpose, scope, local setup, deterministic-only mode, backend/frontend run instructions, tests, demo flows, and engineering disclaimer.
- `.env.example` documenting `LLM_ENABLED`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `TTS_ENABLED`, `OPENAI_API_KEY`, `TTS_VOICE`, and `TTS_MODEL`.
- `CONTRIBUTING.md` with project map, safe contribution guidance, and calculation-change guardrails.
- MIT `LICENSE`.
- `.gitignore` additions for env files, virtual environments, logs, build output, and caches.
- `run_demo.ps1` and `run_demo.bat` for Windows-friendly startup.
- `run_demo.ps1` now falls back to timestamped log files when previous background processes keep standard log files locked.

Launcher behavior:

- Starts FastAPI and the static frontend.
- Defaults to no `--reload`; use `.\run_demo.ps1 -Reload` for development reload behavior.
- Writes backend/frontend stdout/stderr to `logs/`.
- Uses alternate timestamped log files instead of failing if a log file is locked by an earlier process.
- Checks backend `/health` and frontend HTTP availability.
- Prints recent log lines if startup fails.
- Chooses available ports and passes the selected backend URL to the frontend with `?apiBase=...`.

Verification:

```powershell
python -m pytest -q
```

Observed result:

```text
94 passed
```

---

## Future Phase - Commercial Readiness Hardening

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

## Recommended Next Sprint

The open-source demo is runnable. Good next work should improve trust, reproducibility, and contributor experience without changing engineering outputs casually.

Recommended options:

1. Add screenshots or a short demo GIF referenced from `README.md`.
2. Add a short `docs/ma-wind-lookup.md` explaining the 780 CMR data provenance and ZIP-code limitation.
3. Add browser smoke testing for `frontend/` against the local backend.
4. Improve frontend accessibility and visible error messages.
5. Add a stop script for demo processes or a `-StopExisting` launcher option.
6. Expand sloped-roof direction-specific roof zone geometry and force summaries.
7. Begin a scoped design note for migrating embedded engine constants/tables to JSON without changing outputs.

## Current MVP Milestone

The current MVP spine is complete:

```text
User completes the chat flow in frontend/.
FastAPI stores session state and deterministic collected inputs.
The chatbot confirms inputs and hands calculation payloads to wind_load_engine.py.
The backend returns raw results, formatted_display, and formatted_markdown.
The frontend renders formatted results and optionally requests backend TTS.
Tests prove the core flow works.
```

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
