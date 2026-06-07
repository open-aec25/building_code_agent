# ASCE 7-16 Wind Load Calculator — Application Architecture & Agent Task Specification

---

## 1. Project Overview

**Current implementation status (2026-05-18):**
- FastAPI backend, deterministic chatbot flow, Massachusetts wind lookup, optional Anthropic polish, optional OpenAI TTS, report formatter, and vanilla frontend are implemented.
- The default app path works without API keys when `LLM_ENABLED=false` and `TTS_ENABLED=false`.
- Public demo readiness docs and launchers exist: `README.md`, `.env.example`, `CONTRIBUTING.md`, `LICENSE`, `run_demo.ps1`, and `run_demo.bat`.
- `run_demo.ps1` starts backend/frontend, writes logs under `logs/`, chooses open ports when needed, passes the selected backend URL to the frontend via `?apiBase=...`, and falls back to timestamped log files if a previous process has a log locked.
- Calculation benchmark alignment against a TEDDS-style flat-roof ASCE 7-16 MWFRS example is implemented: flat roof Cp selection at `h/L = 0.5`, raw pressure preservation, orthogonal wind direction summaries, roof zone geometry/areas, and overall horizontal minimum force checks.
- Current verification: `python -m pytest -q` passes with 94 tests.

A conversational web application that guides users through a structured question flow to collect building parameters, then executes a full ASCE 7-16 Chapter 27 Directional Procedure wind load calculation and returns a structured engineering report.

**Target Users:** Engineers, architects, and construction professionals performing preliminary wind load calculations.

**Core Design Principles:**
- The deterministic backend owns conversation state, validation, lookups, and calculations
- The optional LLM handles answer interpretation fallback and response polishing only; it never performs arithmetic
- All table lookups and calculations are executed by the Python engine — never the LLM
- All hardcoded assumptions are explicitly flagged to the user
- Every output value is traceable to a specific ASCE 7-16 section or equation

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          FRONTEND                               │
│                  Chat UI (React / HTML)                         │
│         Conversational interface + results display              │
│                                                                 │
│         [🔊 TTS Audio Player — plays assistant responses]       │
└──────────────┬──────────────────────────────┬───────────────────┘
               │ HTTP (REST)                  │ HTTP (REST)
               │ chat messages                │ TTS audio requests
┌──────────────▼──────────────┐  ┌────────────▼───────────────────┐
│        BACKEND API          │  │         TTS MODULE             │
│      FastAPI (Python)       │  │        tts.py                  │
│                             │  │                                │
│  ┌─────────────────┐        │  │  1. Receives spoken_text from  │
│  │  Chatbot Layer  │        │  │     chatbot layer              │
│  │  (LLM via       │◄──────►│  │  2. Calls OpenAI TTS API       │
│  │  Anthropic API) │        │  │  3. Returns audio/mpeg stream  │
│  └────────┬────────┘        │  │     to frontend                │
│           │                 │  │                                │
│  ┌────────▼──────────────┐  │  │  Voice: alloy (default)        │
│  │  Calculation Engine   │  │  │  Model: tts-1                  │
│  │  wind_load_engine.py  │  │  │  Format: mp3                   │
│  └───────────────────────┘  │  └────────────────────────────────┘
│                             │
│  ┌──────────────────────────┴──────────────────────────────┐    │
│  │                    Data Layer (JSON)                     │    │
│  │  risk_category.json       kz_table_26_10_1.json         │    │
│  │  constants_and_defaults.json  cp_coefficients_27_3.json │    │
│  │  kzt_topographic_26_8.json    wind_speed_lookup.json     │    │
│  │  conversation_flow.json                                  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                         │ HTTP
                              ┌──────────▼──────────┐
                              │   OpenAI TTS API    │
                              │  api.openai.com/v1  │
                              │  /audio/speech      │
                              └─────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Technology |
|---|---|---|
| Frontend Chat UI | Render conversation, collect user inputs, display results, play TTS audio | HTML / vanilla JS |
| FastAPI Backend | Route requests, manage session state, orchestrate deterministic chatbot, optional LLM polish, engine, formatter, and TTS | Python / FastAPI |
| Chatbot Layer | Drive deterministic 7-phase flow, parse answers, derive risk category, perform Massachusetts lookup, optionally use Anthropic for interpretation/polish | Python + optional Anthropic Claude API |
| TTS Module | Convert assistant text to audio and stream to frontend | `tts.py` → OpenAI TTS API |
| Calculation Engine | Execute all ASCE 7-16 math — no LLM involvement | `wind_load_engine.py` |
| Data Layer | JSON files encoding all ASCE 7-16 tables, constants, and flow logic | JSON |
| Session Store | Persist collected inputs between conversation turns | Server-side dict or Redis |

---

## 3. Conversation Flow Summary

The chatbot collects inputs across 7 phases. The deterministic controller owns progression and validation. When enabled, the LLM may interpret ambiguous answers or polish `display_text`/`spoken_text`; it never computes.

```
Phase 1 — Building Classification
  Q1: Primary building use (free text → mapped to occupancy type)
  Q2: Occupant load at peak times
  Q3: Essential post-disaster? (Y/N)
  Q4: Hazardous materials? (Y/N)
  → Derive: Risk Category (I / II / III / IV) from risk_category.json

Phase 2 — Site & Wind Speed
  Q5: City/state or zip code
  → Derive: Basic wind speed V (mph) from wind_speed_lookup.json when national lookup is available
  → Massachusetts interim path: lookup city/town in data/ma_780_cmr_table_1604_11.json and select basic_wind_speed_v_mph by derived Risk Category

Phase 3 — Exposure Category
  Q6: Terrain description (guided multiple choice → B / C / D)

Phase 4 — Topographic Feature
  Q7: Topographic feature present? (Y/N)
    → No:  Kzt = 1.0 (skip to Phase 5)
    → Yes: Q7a (feature type), Q7b (H), Q7c (Lh), Q7d (x)
  → Derive: Kzt from kzt_topographic_26_8.json

Phase 5 — Building Geometry
  Q8:  Mean roof height h (ft)
  Q9:  Building length L (ft) — parallel to wind
  Q10: Building width B (ft) — perpendicular to wind
  Q11: Roof type (flat / gable / hip / monoslope)
    → Flat:     skip Q12/Q13
    → Other:    Q12 (slope degrees), Q13 (ridge orientation)

Phase 6 — Design Intent
  Q14: Analysis type (MWFRS / C&C / both)
  Q15: Design standard (LRFD / ASD)

Phase 7 — Confirmation
  → Display full input summary to user
  → User confirms or corrects individual fields
  → On confirm: pass BuildingInputs to wind_load_engine.py
```

### Hardcoded Defaults (Never Asked)

| Parameter | Value | Reference |
|---|---|---|
| G (gust factor) | 0.85 | ASCE 7-16 §26.11.1 — rigid structure assumed |
| Ke (ground elevation) | 1.0 | ASCE 7-16 §26.9 — conservative default |
| Kd (directionality) | 0.85 | ASCE 7-16 Table 26.6-1 |
| GCpi (internal pressure) | ±0.18 | ASCE 7-16 Table 26.13-1 — enclosed building |
| Enclosure classification | Enclosed | Scope constraint — v1 only |

---

## 4. Data Layer Files

All ASCE 7-16 reference data is encoded in JSON. The calculation engine reads these files — the LLM does not.

| File | Contents | Status |
|---|---|---|
| `risk_category.json` | Occupancy-to-Risk-Category mapping, derivation logic | ✅ Complete |
| `constants_and_defaults.json` | Kd, Ke, G, GCpi, velocity pressure equation, minimum loads | ✅ Complete |
| `kz_table_26_10_1.json` | Kz/Kh values for Exposures B/C/D at all tabulated heights | ✅ Complete |
| `cp_coefficients_27_3.json` | Cp for walls (Fig. 27.3-1) and roofs (Fig. 27.3-2) | ✅ Complete |
| `kzt_topographic_26_8.json` | K1/K2/K3 tables and Kzt formula per Fig. 26.8-1 | ✅ Complete |
| `conversation_flow.json` | Full chatbot Q&A flow with branching logic | ✅ Complete |
| `wind_speed_lookup.json` | Basic wind speed V by location (city/state/zip) | ❌ Not built |
| `ma_780_cmr_table_1604_11.json` | Massachusetts 780 CMR Table 1604.11 municipal snow loads, wind speeds, and seismic parameters with metadata and note refs | ✅ Complete for MA |
| `ma_780_cmr_table_1604_11.jsonl` | One JSON record per municipality from Table 1604.11; best for RAG/retrieval indexing | ✅ Complete for MA |
| `ma_780_cmr_table_1604_11.csv` | Flat inspection/import copy of Table 1604.11 | ✅ Complete for MA |
| `raw_780_cmr_chapter_16_cornell.html` | Raw Cornell LII HTML source used to generate the MA Table 1604.11 files | ✅ Preserved source |

### Massachusetts Wind Speed Lookup Dataset

Use `data/ma_780_cmr_table_1604_11.json` as the canonical Massachusetts lookup source until a national `wind_speed_lookup.json` exists. The JSON contains:

- `metadata`: source URL, scrape date, units, table notes, and an LLM usage hint.
- `records`: one object per unique Massachusetts municipality.
- `city_town`: exact municipality name used for lookup.
- `basic_wind_speed_v_mph`: object keyed by `risk_category_i`, `risk_category_ii`, `risk_category_iii`, and `risk_category_iv`.
- `note_refs`: table footnote references. If this contains `2`, warn that the town is in or near a Special Wind Region and local/ASCE/AHJ confirmation may be required. If this contains `3`, ground snow load may require elevation adjustment.

Workflow for Q5 when the project location is in Massachusetts:

1. Resolve the user location to a Massachusetts municipality. For now this can be exact/fuzzy city/town matching; a later enhancement should use MassGIS town boundaries or a geocoder for addresses.
2. Select the wind key using the already-derived Risk Category:
   - Risk Category I -> `basic_wind_speed_v_mph.risk_category_i`
   - Risk Category II -> `basic_wind_speed_v_mph.risk_category_ii`
   - Risk Category III -> `basic_wind_speed_v_mph.risk_category_iii`
   - Risk Category IV -> `basic_wind_speed_v_mph.risk_category_iv`
3. Confirm the value with the user and cite `780 CMR Table 1604.11`.
4. If `note_refs` includes `2`, include a warning that local conditions may require higher speeds than the tabulated value and the AHJ/ASCE hazard data should be checked.

Regenerate the dataset with:

```powershell
python python_files\scrape_780_cmr_table_1604_11.py
```

The scraper expects `data/raw_780_cmr_chapter_16_cornell.html` to exist. It deduplicates exact duplicate municipality rows and fails if duplicates conflict.

---

## 5. Calculation Engine

**File:** `wind_load_engine.py`
**Status:** ✅ Complete in current repo; covered by the project pytest suite.

### Public API

```python
from wind_load_engine import BuildingInputs, run_wind_load_calculation

inputs = BuildingInputs(
    risk_category         = "II",
    basic_wind_speed_V    = 115.0,
    exposure_category     = ExposureCategory.C,
    mean_roof_height_h    = 50.0,
    building_length_L     = 120.0,
    building_width_B      = 60.0,
    roof_type             = RoofType.GABLE,
    roof_slope_deg        = 18.4,
    ridge_orientation     = RidgeOrientation.NORMAL,
    analysis_type         = AnalysisType.MWFRS,
    design_standard       = DesignStandard.LRFD,
)

results = run_wind_load_calculation(inputs)
```

### Output Structure

```
results
├── inputs          — all user-provided values + derived ratios (h/L, L/B)
├── constants       — all hardcoded values with references
├── Kzt             — topographic factor (computed or default 1.0)
├── velocity_pressure
│   ├── Kh          — exposure coefficient at mean roof height
│   └── qh          — velocity pressure at mean roof height (psf)
├── windward_wall_profile   — qz and Kz at each height interval
├── Cp_values
│   ├── walls       — windward, leeward, side wall Cp
│   └── roof        — Cp zones by roof type
├── wall_pressures  — calculated p (psf) per surface, both GCpi cases, raw values preserved
├── roof_pressures  — calculated p (psf) per roof zone, both GCpi cases, with zone geometry where available
├── wind_direction_cases — 0° and 90° MWFRS summaries with direction-specific ratios, roof zones, and overall horizontal force checks
└── summary         — qh, Kzt, Kh, design standard, minimum load references
```

### Calculation Functions

| Function | ASCE 7-16 Reference | Input → Output |
|---|---|---|
| `calc_kz()` | Table 26.10-1 | height, exposure → Kz |
| `calc_kzt()` | Figure 26.8-1 | TopographicInputs, z → Kzt |
| `calc_velocity_pressure()` | Eq. 26.10-1 | Kz, Kzt, V → qz (psf) |
| `get_cp_leeward_wall()` | Figure 27.3-1 | L/B → Cp |
| `get_cp_roof_flat()` | Figure 27.3-2 | h/L → zone list with Cp |
| `get_cp_roof_gable()` | Figure 27.3-2 | slope, h/L, orientation → Cp dict |
| `calc_design_pressure()` | Eq. 27.3-1 | q, Cp, qi, GCpi → p (psf) |
| `apply_minimum_pressure()` | §27.1.5 | p, surface → threshold-adjusted check value, bool; raw pressure outputs remain preserved |
| `run_wind_load_calculation()` | Chapter 27 | BuildingInputs → full results dict |

### Benchmark Alignment Notes

As of 2026-05-18, the engine/reporting path has a TEDDS-style flat-roof benchmark alignment pass:

- For flat roofs with `h/L <= 0.5`, Cp zones are `0 to h = -0.9`, `h to 2h = -0.5`, and `beyond 2h = -0.3`; zero-width zones are suppressed from final pressure rows.
- Surface pressure tables preserve calculated pressures for both `GCpi = +0.18` and `GCpi = -0.18`; the wall/roof minimums are not substituted into individual leeward/side/roof pressure rows.
- Overall horizontal MWFRS checks are reported by consistent `+GCpi` and `-GCpi` load cases, then compared to the §27.1.5 minimum horizontal force.
- Direction summaries check both 0° and 90° wind directions by swapping along-wind and transverse plan dimensions. For square buildings the results are expected to match; for rectangular buildings, `L/B`, `h/L`, roof zones, and forces may differ.

---

## 6. File & Folder Structure

```
wind-load-calculator/
│
├── backend/
│   ├── main.py                     # FastAPI app — routes, session management
│   ├── chatbot.py                  # LLM conversation logic, phase management
│   ├── tts.py                      # TTS module — OpenAI TTS API integration
│   ├── wind_load_engine.py         # ✅ Calculation engine (complete)
│   ├── models.py                   # Pydantic request/response models
│   └── session.py                  # Session state management
│
├── data/
│   ├── risk_category.json          # ✅ Complete
│   ├── constants_and_defaults.json # ✅ Complete
│   ├── kz_table_26_10_1.json       # ✅ Complete
│   ├── cp_coefficients_27_3.json   # ✅ Complete
│   ├── kzt_topographic_26_8.json   # ✅ Complete
│   ├── conversation_flow.json      # ✅ Complete
│   ├── ma_780_cmr_table_1604_11.json   # ✅ MA municipal Table 1604.11 canonical data
│   ├── ma_780_cmr_table_1604_11.jsonl  # ✅ MA Table 1604.11 retrieval/indexing copy
│   ├── ma_780_cmr_table_1604_11.csv    # ✅ MA Table 1604.11 inspection copy
│   ├── raw_780_cmr_chapter_16_cornell.html # ✅ Raw scrape source
│   └── wind_speed_lookup.json      # ❌ National lookup still needs to be built
│
├── minimal_ui/
│   └── index.html                  # ❌ TASK NEW-A — single-file demo UI with TTS
│                                   # Calls Anthropic API directly, no backend needed
│                                   # Stepping stone before full frontend build
│
├── frontend/                       # ✅ Production vanilla UI
│   ├── index.html                  # Chat UI shell
│   ├── app.js                      # Conversation state, API calls, TTS audio player
│   └── styles.css                  # Styling
│
├── tests/
│   ├── test_wind_load_engine.py    # ✅ 65 tests passing
│   ├── test_tts.py                 # ✅ Mocked backend TTS coverage
│   ├── test_report_formatter.py    # ✅ Formatter coverage
│   └── test_api.py                 # ✅ API and conversation coverage
│
├── README.md                       # Open-source demo setup and scope
├── CONTRIBUTING.md                 # Contributor guidance
├── LICENSE                         # MIT license
├── .env.example                    # Runtime configuration template
├── run_demo.ps1                    # Windows PowerShell demo launcher
├── run_demo.bat                    # Batch wrapper for run_demo.ps1
├── PROJECT_STATE.md                # Master agent maintains this
├── ARCHITECTURE.md                 # This file
└── requirements.txt                # Python dependencies
```

---

## 7. Agent Task Breakdown

### Master Agent Responsibilities
- Maintain `PROJECT_STATE.md` after every completed task
- Assign tasks to sub-agents with explicit acceptance criteria
- Review sub-agent output against acceptance criteria before marking complete
- Manage dependencies — do not assign Task N+1 until Task N is accepted
- Escalate blockers (ambiguous requirements, test failures, scope changes)

### QA Agent Responsibilities
- Run test suite after each sub-agent completes a task
- Report pass/fail results and failure details to master agent
- Never modify source code — report only
- Confirm that new code does not break previously passing tests (regression check)

---

### Task List

---

#### TASK NEW-A — Minimal Chat UI with TTS (Demo Stepping Stone)
**Assigned to:** Frontend Sub-Agent
**Depends on:** Nothing
**Status:** ❌ Not started

**Description:**
Build `minimal_ui/index.html` — a single self-contained HTML file that delivers a working, voice-enabled chatbot demo in the browser. This does NOT require the FastAPI backend. It calls the Anthropic API directly from the browser and the OpenAI TTS API for audio. This is the fastest path to a demoable product.

This file is a stepping stone only — it will be superseded by the production frontend in TASK 06. The TTS audio player pattern established here carries forward into the production UI.

**Acceptance Criteria:**
- Single `.html` file — no build step, opens directly in browser
- Chat conversation renders in a scrollable message window (user and assistant bubbles styled differently)
- Calls Anthropic Claude API (`claude-sonnet-4-20250514`) directly via `fetch()` with the conversation system prompt
- System prompt encodes the 7-phase conversation flow from `conversation_flow.json` (inlined as a JS constant)
- After each assistant response, automatically calls OpenAI TTS API and plays audio via HTML `<audio>` element
- TTS toggle button — user can mute/unmute voice without stopping the conversation
- API keys entered via an input field at the top of the page on first load (stored in `sessionStorage` only — never hardcoded)
- Phase progress indicator (e.g. "Phase 2 of 7 — Site & Wind Speed")
- When Phase 7 confirmation is reached, displays a formatted input summary table
- "Start Over" button resets conversation and clears session state
- Works in Chrome and Firefox

**What this file does NOT need:**
- No connection to `wind_load_engine.py` — calculation output is mocked or skipped in this demo
- No FastAPI backend
- No session persistence across page reloads

---

#### TASK NEW-B — TTS Backend Module
**Assigned to:** Backend Sub-Agent
**Depends on:** TASK 02 (FastAPI skeleton)
**Status:** ✅ Completed 2026-04-25

**Description:**
Build `backend/tts.py` — the TTS integration module that the production backend uses to convert chatbot responses to audio. This replaces the direct browser-to-OpenAI call from TASK NEW-A with a proper server-side implementation.

**Acceptance Criteria:**
- `async def synthesize_speech(text: str, voice: str = "alloy") -> bytes` — calls OpenAI TTS API, returns raw mp3 bytes
- Model: `tts-1` (faster, lower latency — appropriate for conversational use)
- Format: `mp3`
- Default voice: `alloy` — configurable via environment variable `TTS_VOICE`
- `POST /tts` API route in `main.py` — accepts `{ "text": "...", "session_id": "..." }`, returns `audio/mpeg` stream
- TTS text is the **spoken summary version** of the assistant response, not the full display text — the chatbot layer must generate two outputs per turn: `display_text` (full markdown) and `spoken_text` (plain prose, no markdown, no bullet points, optimized for listening)
- Spoken text for results summary must be a natural language narrative — NOT a readout of individual numbers. Example: *"Based on your inputs, the governing design pressure on the windward wall is 18 pounds per square foot, with the side walls experiencing 16 pounds per square foot in suction."* NOT *"p GCpi positive equals 18.0 psf, p GCpi negative equals 16.0 psf..."*
- `OPENAI_API_KEY` loaded from environment variable — never hardcoded
- Graceful degradation: if TTS API call fails, log the error and return a `tts_available: false` flag — the conversation continues without audio
- Unit tests in `tests/test_tts.py`: mock the OpenAI API call and verify correct parameters are sent, correct audio format returned, and graceful failure behavior

**TTS Spoken Text Rules (enforce in chatbot layer system prompt):**
```
When generating a response, always produce two versions:
  display_text: full response with markdown formatting for the UI
  spoken_text:  plain prose version optimized for text-to-speech, following these rules:
    - No markdown (no *, **, #, -, bullet points)
    - No raw numbers without units ("18 psf" not "18.0")
    - No variable names or code ("qh" → "velocity pressure at roof height")
    - No table readouts — summarize in narrative form
    - Maximum 3 sentences for question prompts
    - For results: lead with the governing value, then note any surfaces where the minimum load controlled
```

**Environment Variables Required:**
```
OPENAI_API_KEY=sk-...
TTS_VOICE=alloy           # alloy | echo | fable | onyx | nova | shimmer
TTS_ENABLED=true          # set to false to disable TTS entirely
```

---

#### TASK 01 — Wind Speed Lookup JSON
**Assigned to:** Data Sub-Agent
**Depends on:** Nothing
**Status:** 🔄 Partially complete for Massachusetts

**Description:**
Build `data/wind_speed_lookup.json` encoding basic wind speed V (mph) by US location for all three risk category maps (ASCE 7-16 Figures 26.5-1A, 26.5-1B, 26.5-1C).

Massachusetts has an interim authoritative municipal source in `data/ma_780_cmr_table_1604_11.json`, scraped from Cornell LII's 780 CMR Chapter 16 Table 1604.11. This should be used for MA lookup integration before attempting a national ASCE figure digitization.

**Acceptance Criteria:**
- Coverage of all 50 US states at minimum city/county granularity
- Keys include city name, state abbreviation, and zip code prefix where possible
- Three speed values per entry: `V_cat_I`, `V_cat_II`, `V_cat_III_IV`
- Hurricane-prone coastal regions (Gulf Coast, Atlantic Coast, FL, TX coast) have higher resolution entries
- Schema includes a `source_note` field referencing the applicable ASCE 7-16 figure
- A fallback entry exists for locations not found: `"lookup_failed": true` flag with instruction to prompt user for manual entry
- For Massachusetts, either wrap/import `ma_780_cmr_table_1604_11.json` into the lookup service or support it as a separate first-class data source. Do not duplicate values by hand.

**Schema:**
```json
{
  "lookup": {
    "Boston_MA": {
      "state": "MA",
      "zip_prefixes": ["021", "022"],
      "V_cat_I":     105,
      "V_cat_II":    120,
      "V_cat_III_IV": 130,
      "source_note": "ASCE 7-16 Figures 26.5-1A/B/C — interpolated"
    }
  }
}
```

---

#### TASK 02 — FastAPI Backend Skeleton
**Assigned to:** Backend Sub-Agent
**Depends on:** Nothing (can run parallel to TASK 01)
**Status:** ❌ Not started

**Description:**
Build `backend/main.py` with the core API routes and session management. No LLM integration yet — just the routing skeleton and session store.

**Acceptance Criteria:**
- `POST /session/new` — creates a new session, returns `session_id`
- `POST /session/{session_id}/message` — accepts `{ "message": "..." }`, returns `{ "response": "...", "session_state": {...} }`
- `POST /session/{session_id}/calculate` — accepts a complete `BuildingInputs` payload, calls `run_wind_load_calculation()`, returns full results dict
- `GET /session/{session_id}/state` — returns current collected inputs for the session
- Session state persists between calls (in-memory dict acceptable for v1)
- All routes return proper HTTP status codes and error messages
- `requirements.txt` includes `fastapi`, `uvicorn`, `anthropic`, `pydantic`

---

#### TASK 03 — Pydantic Request/Response Models
**Assigned to:** Backend Sub-Agent
**Depends on:** TASK 02
**Status:** ❌ Not started

**Description:**
Build `backend/models.py` defining all Pydantic models for API request/response validation.

**Acceptance Criteria:**
- `ChatRequest` — `session_id: str`, `message: str`
- `ChatResponse` — `response: str`, `phase: int`, `collected_inputs: dict`, `ready_to_calculate: bool`
- `CalculationRequest` — mirrors `BuildingInputs` dataclass from engine, all fields validated
- `CalculationResponse` — wraps full results dict from `run_wind_load_calculation()`
- `SessionState` — tracks current phase, collected fields, flags (topo present, roof type, etc.)
- All models include field descriptions for API documentation
- Validation errors return 422 with clear field-level messages

---

#### TASK 04 — Chatbot Conversation Layer
**Assigned to:** Backend Sub-Agent
**Depends on:** TASK 02, TASK 03
**Status:** ❌ Not started

**Description:**
Build `backend/chatbot.py` — the LLM-powered conversation manager that drives the 7-phase input collection flow.

**Acceptance Criteria:**
- Reads `conversation_flow.json` and `risk_category.json` at startup
- Maintains phase state per session — knows which question is next
- System prompt instructs Claude to: ask one question at a time, explain why each input matters, never compute values, defer all math to the engine
- Every response returns both `display_text` (markdown, for UI) and `spoken_text` (plain prose, for TTS) — see TASK NEW-B for spoken text rules
- Risk Category derivation: LLM maps Q1–Q4 answers against `risk_category.json` logic — never guesses
- Exposure Category: LLM presents guided options from `conversation_flow.json` Q6
- Branch logic: topo sub-questions only triggered if Q7 = Yes; roof slope/orientation only if roof is not flat
- Phase 7 confirmation: LLM formats collected inputs into a clean summary and asks for user confirmation
- On confirmation: assembles `BuildingInputs` object and passes to calculation engine
- LLM never presents a number as a result — it calls the engine and presents engine output
- Handles corrections: user can say "change my roof slope to 25 degrees" and chatbot updates the field and re-confirms
- Spoken results summary must be narrative prose per the TTS spoken text rules in TASK NEW-B

**System Prompt Constraints to Enforce:**
```
- Never perform wind load calculations yourself
- Never guess or approximate ASCE 7-16 table values
- Always call the calculation engine for numeric results
- Ask exactly one question per turn
- Always explain why you are asking each question
- If user input is ambiguous, ask a clarifying follow-up before proceeding
- Always return both display_text and spoken_text fields in your response JSON
```

---

#### TASK 05 — Wind Speed Lookup Integration
**Assigned to:** Backend Sub-Agent
**Depends on:** TASK 01, TASK 04
**Status:** 🔄 Partially unblocked for Massachusetts

**Description:**
Integrate `wind_speed_lookup.json` into the chatbot layer so Q5 (location) triggers an automatic lookup of V rather than requiring manual user entry.

For Massachusetts locations, integrate `data/ma_780_cmr_table_1604_11.json` first. It provides city/town-level values for Risk Categories I-IV from 780 CMR Table 1604.11, which is enough to remove the manual wind-speed prompt for MA municipalities.

**Acceptance Criteria:**
- Fuzzy location matching — "Boston", "Boston MA", "Boston, Massachusetts", and zip "02101" all resolve to the same entry
- On successful lookup: chatbot confirms "Based on your location, V = X mph per ASCE 7-16 Figure 26.5-1_. Does that look right?"
- On failed lookup: chatbot prompts user to manually enter V from the ASCE 7-16 figure, specifying which figure based on risk category
- Lookup uses the correct figure (1A, 1B, or 1C) based on the already-derived Risk Category
- Unit test: at least 20 representative locations resolve correctly including coastal high-wind zones
- Massachusetts-specific tests should cover at least Boston, Cambridge, Worcester, Chatham, Aquinnah (Gay Head), Mount Washington, Adams, and a non-MA/unknown fallback.
- If a Massachusetts record has note ref `2`, chatbot output must warn that the location may be in a Special Wind Region and AHJ/ASCE confirmation may be required.

---

#### TASK 06 — Production Frontend Chat UI
**Assigned to:** Frontend Sub-Agent
**Depends on:** TASK 02, TASK NEW-B (needs TTS route available)
**Status:** ✅ Completed 2026-04-26

**Description:**
Build the production chat UI in `frontend/`. This replaces `minimal_ui/index.html` with a full implementation connected to the FastAPI backend. Carries forward the TTS audio player pattern from TASK NEW-A.

**Acceptance Criteria:**
- Chat window with message history (user and assistant bubbles)
- Input field with send button (Enter key also submits)
- Loading indicator while waiting for API response
- Phase progress indicator showing which of the 7 phases is active
- **TTS audio player:**
  - Automatically fetches and plays audio from `POST /tts` after each assistant response
  - Mute/unmute toggle button persists across turns (stored in `localStorage`)
  - Visual indicator when audio is playing (subtle animation on assistant bubble)
  - If TTS unavailable (`tts_available: false`), mute button is hidden — no error shown to user
- Results display section — renders calculation output in a structured, readable format (not raw JSON)
- Results include: all intermediate values (qh, Kz, Kzt, Cp per surface), final pressures per surface in a table, minimum load check flags highlighted where they governed
- Responsive — usable on desktop and tablet
- New session button to start over
- No authentication required for v1

---

#### TASK 07 — Results Report Formatter
**Assigned to:** Backend Sub-Agent
**Depends on:** TASK 04
**Status:** ✅ Completed 2026-04-26

**Description:**
Build a report formatter that converts the raw `run_wind_load_calculation()` output dict into a structured, human-readable format suitable for both display in the UI and export as a PDF/markdown calculation sheet.

**Acceptance Criteria:**
- `format_results_for_display(results: dict) -> dict` — returns a UI-friendly nested structure
- `format_results_as_markdown(results: dict, inputs: BuildingInputs) -> str` — returns a full calculation sheet in markdown
- Markdown report includes: project summary, all assumptions/defaults with references, step-by-step intermediate values with ASCE 7-16 citations, final pressure table per surface, minimum load check results
- Each value in the report is labeled with its ASCE 7-16 section or equation
- The report is formatted to serve as a defensible calculation document

---

#### TASK 08 — API Integration Tests
**Assigned to:** QA Sub-Agent
**Depends on:** TASK 04, TASK 05
**Status:** ✅ Completed incrementally through Phases 3-9

**Description:**
Build `tests/test_api.py` — end-to-end integration tests that exercise the full API stack.

**Acceptance Criteria:**
- Tests use `httpx` or `pytest` with FastAPI `TestClient`
- Test full conversation flow: simulate a complete Phase 1–7 interaction for at least 3 building scenarios (flat roof office, gable roof warehouse, topographic feature case)
- Verify that calculation endpoint returns correct `qh` for known input combinations (cross-check against `test_wind_load_engine.py` values)
- Test error handling: missing fields, invalid values, unknown location
- Test session isolation: two concurrent sessions do not interfere
- Test correction flow: user changes a field after Phase 7 summary, confirm updated value flows to engine correctly
- All tests pass before TASK 06 (Frontend) is considered complete

---

#### TASK 09 — C&C Module (Components & Cladding)
**Assigned to:** Backend Sub-Agent
**Depends on:** TASK 04 (core MWFRS engine must be stable first)
**Status:** ❌ Not started — v2 scope

**Description:**
Extend `wind_load_engine.py` to support Components & Cladding (C&C) pressure calculations per ASCE 7-16 Chapter 30.

**Acceptance Criteria:**
- Adds `calc_cc_pressures()` function to engine
- Supports enclosed low-rise buildings (Chapter 30 Part 1) and buildings of all heights (Chapter 30 Part 2)
- Accepts tributary area as additional input
- Returns GCp values and net pressures for wall zones (1, 2, 3) and roof zones
- All new functions covered by unit tests
- Does not break existing MWFRS tests (65/65 still passing)

---

#### TASK 10 — Open Source Demo Readiness
**Assigned to:** Codex
**Depends on:** Production frontend and backend demo flow
**Status:** ✅ Completed 2026-04-26

**Implemented:**
- Added `README.md` with setup, architecture, scope, limitations, deterministic-only mode, run commands, tests, and demo scenarios.
- Added `.env.example`, `CONTRIBUTING.md`, and MIT `LICENSE`.
- Added/updated `.gitignore` for local envs, logs, build output, and cache files.
- Added `run_demo.ps1` and `run_demo.bat` for Windows local demo startup.
- `run_demo.ps1` starts backend/frontend, logs stdout/stderr to `logs/`, checks backend `/health`, prints log tails on failure, and supports dynamic frontend/backend ports.

---

## 8. Project State File Expectations

`PROJECT_STATE.md` is the source of truth for completed work, pending work, known limitations, and latest test status. As of 2026-05-18, the current suite is `python -m pytest -q` with 94 passing tests. The legacy example below is retained only as a formatting example; update concrete phase lists from `PROJECT_STATE.md`, not from the historical sample.

The master agent should keep `PROJECT_STATE.md` aligned with the current repository state. A current example:

```markdown
## Completed Tasks
- Phase 0 - Normalize The Project Structure
- Phase 2 - Build FastAPI Backend Skeleton
- Phase 3 - Add Backend API Tests
- Phase 4 - Build Deterministic Conversation Controller
- Phase 5 - Add Risk Category And Wind Speed Logic
- Phase 6 - Add LLM Integration Safely
- Phase 7 - Add TTS Backend Module
- Phase 8 - Build Production Frontend
- Phase 9 - Build Report Formatter
- Phase 10 - Open Source Demo Readiness
- TEDDS-style MWFRS benchmark alignment
- Demo launcher log-lock hardening

## In Progress
- None.

## Pending
- Phase 1 - Stabilize The Calculation Core
- National wind-speed lookup data
- C&C module (v2 scope)
- Future commercial-readiness hardening if the demo becomes a product

## Test Status
- `python -m pytest -q`: 94 passed
```

---

## 9. Agent Handoff Protocol

When the master agent assigns a task to a sub-agent, the handoff must include:

1. **Task ID and description** from this document
2. **Relevant existing files** the sub-agent needs to read before starting
3. **Explicit acceptance criteria** — these are the pass/fail conditions for review
4. **What NOT to change** — list files that are complete and must not be modified
5. **Where to write output** — exact file paths

When a sub-agent returns work:

1. Master agent reads the output files
2. Master agent sends output to QA agent with the acceptance criteria
3. QA agent runs tests and returns pass/fail report
4. Master agent marks task complete or returns to sub-agent with specific failure notes
5. Master agent updates `PROJECT_STATE.md`

---

## 10. Technology Stack

### Local Demo Runtime

Recommended Windows startup:

```powershell
.\run_demo.ps1 -OpenBrowser
```

or:

```bat
run_demo.bat
```

The launcher defaults to deterministic-only behavior unless `.env` enables optional services. It writes:

- `logs/backend.log`
- `logs/backend.err.log`
- `logs/frontend.log`
- `logs/frontend.err.log`

Manual startup remains:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
python -m http.server 5500 --bind 127.0.0.1 --directory frontend
```

If the backend runs on a non-default port, open the frontend with `?apiBase=<encoded backend URL>`.

| Layer | Technology | Rationale |
|---|---|---|
| Backend framework | FastAPI | Fast, async-native, auto-generates OpenAPI docs |
| LLM | Optional Anthropic Claude API (`claude-sonnet-4-20250514`) | Interpretation fallback and response polish only; deterministic mode works without it |
| TTS | Optional OpenAI TTS API (`tts-1`, voice: `alloy`) | Backend-only speech synthesis using `spoken_text`; deterministic mode works without it |
| Calculation engine | Pure Python (stdlib only) | No dependencies, fully testable, deterministic |
| Data encoding | JSON | Human-readable, easily versioned, LLM-readable for reference |
| Session state | In-memory dict (v1) / Redis (v2) | Simple for v1, scalable for v2 |
| Frontend | HTML / vanilla JS (v1) | No build tooling, fast to iterate |
| Testing | pytest | Standard Python test runner |
| Demo launch | `run_demo.ps1` / `run_demo.bat` + uvicorn + Python static server | No frontend build step; easy local demo |

---

## 11. What Is Intentionally Out of Scope (v1)

- Partially enclosed or open buildings (GCpi ≠ ±0.18)
- Flexible structures (Gf calculation — G = 0.85 assumed for all)
- Components & Cladding (C&C) — Chapter 30 (TASK 09, v2)
- Monoslope roof Cp (Fig. 27.3-3) — flagged in output, manual lookup required
- ASCE 7-22 (next version of standard)
- User authentication or saved projects
- Structural load combinations (wind load output only — no dead/live combination)
- Non-US locations
