# PROJECT_STATE.md
Last updated: 2026-04-25 by Codex

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
- Phase 3 - Add Backend API Tests - completed 2026-04-18
  - Added `tests/test_api.py` covering session creation, state lookup, message persistence, valid calculation, validation errors, missing sessions, and session isolation.
- Phase 4 - Build Deterministic Conversation Controller - completed 2026-04-18
  - Added `backend/chatbot.py` with deterministic question flow, typed parsing, branch handling, confirmation summary, simple correction handling, and calculation-on-confirm through the existing engine.
  - Updated `/session/{session_id}/message` to use the deterministic controller instead of the Phase 2 placeholder response.
  - Extended API tests to cover flat roof, gable roof, topographic branch, correction flow, and calculation from confirmation.
- Phase 5 - Add Risk Category And Wind Speed Logic - completed 2026-04-25
  - Tightened deterministic Risk Category derivation from `data/risk_category.json`.
  - Made wind-speed lookup fallback explicit: the controller asks the user for manual ASCE 7-16 wind speed entry because `wind_speed_lookup.json` is not ready.
  - Added tests for manual wind-speed fallback, positive wind-speed validation, and Risk Categories I, III, and IV.
- Massachusetts 780 CMR Table 1604.11 Data Extraction - completed 2026-04-25
  - Scraped Cornell LII 780 CMR Chapter 16 Table 1604.11 from `https://www.law.cornell.edu/regulations/massachusetts/780-CMR-CHAPTER-16`.
  - Added canonical `data/ma_780_cmr_table_1604_11.json` with 351 unique Massachusetts municipality records.
  - Added `data/ma_780_cmr_table_1604_11.jsonl` for retrieval/indexing and `data/ma_780_cmr_table_1604_11.csv` for inspection/import.
  - Preserved source HTML in `data/raw_780_cmr_chapter_16_cornell.html`.
  - Added `python_files/scrape_780_cmr_table_1604_11.py` to regenerate JSON/JSONL/CSV from the saved HTML.
  - QA note: Cornell HTML contained duplicate identical `Dover` and `Dracut` rows; the scraper deduplicates exact matches and fails on conflicting duplicate rows.
- Context Documentation Update for MA Wind Lookup - completed 2026-04-25
  - Updated `context_files/ARCHITECTURE.md` and `context_files/DEVELOPMENT_PLAN.md` so future agents know how to use the MA Table 1604.11 files.
- Massachusetts Table 1604.11 lookup integration - completed 2026-04-25
  - Wired deterministic Phase 2 location handling in `backend/chatbot.py` to resolve supported Massachusetts municipalities from `data/ma_780_cmr_table_1604_11.json`.
  - Selects `basic_wind_speed_v_mph` by the already-derived Risk Category and stores it as `basic_wind_speed_V`.
  - Confirms successful lookups with a `780 CMR Table 1604.11` citation and warns on note ref `2` for Special Wind Region/local-condition review.
  - Preserves manual wind-speed fallback for non-Massachusetts, unresolved Massachusetts, and unsupported lookup inputs.

## In Progress
- None.

## Pending
- Phase 1 - Stabilize The Calculation Core
- Phase 6 - Add LLM Integration Safely
- Phase 7 - Add TTS Backend Module
- Phase 8 - Build Production Frontend
- Phase 9 - Build Report Formatter
- Phase 10 - Commercial Readiness Hardening

## Known Issues / Decisions
- Existing `python_files/` and `json_files/` source directories were left in place for compatibility during normalization.
- The calculation engine still embeds tables/constants in Python; JSON-backed loading remains a later migration.
- `wind_speed_lookup.json` has not been built yet as a national lookup; the chatbot still asks the user to enter the ASCE 7-16 basic wind speed manually for non-Massachusetts or unresolved locations.
- Massachusetts municipal lookup is wired into `backend/chatbot.py` using `data/ma_780_cmr_table_1604_11.json`; bare ZIP-code-only inputs are not supported by this municipal table and fall back to manual entry.
- Architecture notes mention 65 passing tests, but this repository currently contains 52 engine tests.

## Test Status
- `python -m pytest -q`: 75 passed on 2026-04-25.
- Phase 2 API smoke test: session creation, state lookup, message persistence, calculation, and missing-session 404 passed on 2026-04-18.
- Phase 3 API tests: 10 API tests passing on 2026-04-18.
- Phase 4 deterministic conversation tests: flat roof, gable roof, topographic branch, correction flow, and confirmation calculation passing on 2026-04-18.
- Phase 5 risk/manual wind-speed tests: manual fallback, positive wind-speed validation, and Risk Categories I/III/IV passing on 2026-04-25.
- MA Table 1604.11 scraper QA: 351 unique municipality records, 38 records with Special Wind Region note ref `2`, 55 records with elevation adjustment note ref `3`.
