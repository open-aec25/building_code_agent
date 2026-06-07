# Contributing

Thanks for taking a look at the ASCE 7-16 Wind Load Demo. The safest way to contribute is to keep deterministic engineering behavior separate from conversation polish, UI rendering, and documentation.

## Project Map

- `backend/wind_load_engine.py` contains deterministic calculation logic. Treat this as the highest-risk area.
- `backend/chatbot.py` owns the conversation flow, input parsing, validation, Massachusetts lookup behavior, and optional LLM response polishing.
- `backend/report_formatter.py` converts raw engine output into display and markdown report structures.
- `backend/tts.py` contains optional backend-only OpenAI text-to-speech.
- `backend/main.py` exposes the FastAPI routes.
- `frontend/` contains the vanilla browser UI.
- `data/` contains JSON/CSV reference data. `data/ma_780_cmr_table_1604_11.json` is the canonical Massachusetts lookup file.
- `tests/` contains the regression suite.
- `context_files/` contains project planning and architecture notes for future agents and contributors.

## Local Development

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the backend:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Run the frontend:

```powershell
python -m http.server 5500 --bind 127.0.0.1 --directory frontend
```

Run tests before opening a pull request:

```powershell
python -m pytest -q
```

## Safe Contribution Guidelines

- Do not change formulas, coefficients, pressure signs, or expected values casually.
- If you touch `backend/wind_load_engine.py`, add or update focused tests that explain the engineering correction.
- Keep LLM behavior optional and non-authoritative. The deterministic backend must remain the final source of truth for phase progression, validation, lookups, and calculations.
- Do not put API keys or secrets in frontend code, test fixtures, screenshots, or docs.
- Do not claim broader geographic wind-speed coverage than the data provides.
- Keep generated/provenance data changes reproducible. The Massachusetts dataset can be regenerated with `python_files/scrape_780_cmr_table_1604_11.py`.
- Prefer small, reviewable changes over broad refactors.
- Preserve raw backend outputs and existing tests unless there is a documented compatibility reason to change them.

## Good First Contributions

- Improve documentation clarity.
- Add frontend accessibility refinements.
- Add tests around existing behavior.
- Improve demo reliability without changing engineering outputs.
- Add clearer warnings or UI explanations for unsupported cases.

## Engineering Changes

For calculation changes, include:

- The ASCE/code reference or data source used.
- The before/after behavior.
- Why the current behavior is wrong or incomplete.
- Tests that fail before the change and pass after it.

This project is a preliminary demo. Contributions should make it easier to understand, verify, and safely extend.
