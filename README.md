# ASCE 7-16 Wind Load Demo

A local-first open-source demo application for collecting building wind-load inputs through a chat UI, running deterministic ASCE 7-16 Chapter 27 MWFRS calculations, and displaying a formatted preliminary calculation summary.

This project is intended for learning, experimentation, and community contribution. It is not stamped engineering output and is not a substitute for review by a licensed professional engineer.

## What It Does

- Guides a user through a 7-phase wind-load input conversation.
- Derives ASCE Risk Category from deterministic rules.
- Looks up Massachusetts municipality wind speeds from 780 CMR Table 1604.11 when possible.
- Falls back to manual ASCE 7-16 basic wind speed entry for unsupported locations.
- Runs calculations through the Python engine in `backend/wind_load_engine.py`.
- Returns raw engine output, UI-friendly `formatted_display`, and a markdown report.
- Provides optional Anthropic-assisted wording while preserving deterministic backend control.
- Provides optional backend-only OpenAI text-to-speech.
- Runs in deterministic-only mode with no API keys.

## Architecture

```text
frontend/        Vanilla HTML/CSS/JS chat UI and formatted results panel
backend/main.py  FastAPI routes for sessions, chat, calculation, and TTS
backend/chatbot.py
                 Deterministic conversation state machine plus optional LLM polish
backend/wind_load_engine.py
                 Deterministic ASCE 7-16 calculation logic
backend/report_formatter.py
                 Display and markdown formatting for calculation output
backend/tts.py   Optional server-side OpenAI text-to-speech
data/            JSON/CSV reference data, including Massachusetts 780 CMR lookup
tests/           Pytest coverage for API, chatbot, TTS, formatter, and engine behavior
```

The frontend does not perform wind-load calculations. It consumes backend `display_text`, `spoken_text`, `formatted_display`, and `formatted_markdown`.

## Current Supported Scope

- ASCE 7-16 Chapter 27 MWFRS-style wind pressure workflow.
- Enclosed, rigid buildings using the current engine assumptions.
- Flat and gable roof flows covered by tests; hip and monoslope support depends on the existing engine behavior and limitations.
- Exposure categories B, C, and D.
- Topographic factor flow for supported topographic feature inputs.
- Massachusetts city/town wind-speed lookup from 780 CMR Table 1604.11.
- Non-Massachusetts or unresolved locations require manual basic wind speed input.

## Known Limitations

- This is a preliminary demo, not a sealed or code-approved design deliverable.
- National wind-speed lookup is not implemented. Only the Massachusetts municipal table is currently integrated.
- ZIP-code-only Massachusetts lookup is not supported by the current municipal table path.
- Special Wind Region/local-condition flags from 780 CMR are warnings, not final engineering decisions.
- Components and cladding are not a completed v1 scope.
- Partially enclosed/open buildings, flexible structures, ASCE 7-22, non-US locations, load combinations, and commercial project persistence are out of scope.
- The calculation engine still embeds many constants/tables in Python; JSON-backed migration is a future task.
- In-memory sessions are lost when the backend process restarts.
- Optional LLM and TTS integrations require user-provided API keys and are disabled by default.

Always verify inputs, code edition, site wind speed, exposure, topographic applicability, and final loads against the governing code, AHJ requirements, and licensed engineering judgment.

## Local Setup

Prerequisites:

- Python 3.11 or newer
- PowerShell, terminal, or equivalent shell

Create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Copy the environment template if you want optional LLM or TTS features:

```powershell
Copy-Item .env.example .env
```

This repo does not require `.env` loading for deterministic-only mode. For optional integrations, set environment variables in your shell or through your process manager before starting the backend.

## Environment Variables

Deterministic-only demo mode:

```powershell
$env:LLM_ENABLED = "false"
$env:TTS_ENABLED = "false"
```

Optional LLM response polishing:

```powershell
$env:LLM_ENABLED = "true"
$env:ANTHROPIC_API_KEY = "your-anthropic-key"
```

Optional backend text-to-speech:

```powershell
$env:TTS_ENABLED = "true"
$env:OPENAI_API_KEY = "your-openai-key"
$env:TTS_VOICE = "alloy"
$env:TTS_MODEL = "tts-1"
```

Do not put real API keys in frontend files or commit them to git.

## Run The Backend

The easiest demo path is the bundled PowerShell script:

```powershell
.\run_demo.ps1
```

Or run the Windows batch wrapper:

```bat
run_demo.bat
```

These launchers start FastAPI and the static frontend, then print the frontend URL. If the preferred ports are occupied, the PowerShell launcher chooses available ports and passes the selected backend URL to the frontend. Startup output is written to `logs/backend.log`, `logs/backend.err.log`, `logs/frontend.log`, and `logs/frontend.err.log`.

Manual backend startup:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Run The Frontend

In a second terminal:

```powershell
python -m http.server 5500 --bind 127.0.0.1 --directory frontend
```

Open:

```text
http://127.0.0.1:5500/index.html
```

The frontend expects the backend at `http://127.0.0.1:8000`.

If you run the backend on another port, pass it in the page URL:

```text
http://127.0.0.1:5500/index.html?apiBase=http%3A%2F%2F127.0.0.1%3A8001
```

## Deterministic-Only Mode

The app works without Anthropic or OpenAI keys:

- `LLM_ENABLED=false` keeps all chat wording deterministic.
- `TTS_ENABLED=false` makes `/tts` return `{ "tts_available": false }`.
- The frontend hides voice controls when TTS is unavailable.
- Calculations and formatted results still work.

This is the recommended mode for first-time local setup and automated testing.

## Run Tests

```powershell
python -m pytest -q
```

The test suite uses mocks for optional external API behavior and should not require live API keys.

## Demo Scenarios

Use these as manual smoke-test flows in the chat UI.

### Massachusetts Office, Flat Roof

```text
office
45
no
no
Boston, MA
C
no
40
100
50
flat
MWFRS
LRFD
yes
```

Expected behavior: Boston resolves through 780 CMR Table 1604.11, the manual wind-speed prompt is skipped, and formatted wall/roof pressure results appear after confirmation.

### Non-Massachusetts Flat Roof With Manual Wind Speed

```text
office
45
no
no
Chicago, IL
115
C
no
40
100
50
flat
MWFRS
LRFD
yes
```

Expected behavior: the app asks for manual basic wind speed because national lookup is not implemented.

### Gable Roof

```text
warehouse
20
no
no
Chicago, IL
115
B
no
30
120
60
gable
18.4
normal
MWFRS
ASD
yes
```

Expected behavior: the flow collects roof slope and ridge orientation before confirmation.

### Topographic Feature

```text
office
20
no
no
Denver, CO
115
C
yes
3D hill
100
200
50
40
100
50
flat
MWFRS
LRFD
yes
```

Expected behavior: the flow collects topographic feature details and lets the engine compute the topographic factor.

## Safety Disclaimer

This software is provided as an open-source demonstration and preliminary engineering aid. It may contain bugs, incomplete assumptions, unsupported cases, or interpretations that do not match a specific jurisdiction or project condition. Users are responsible for independently verifying all inputs, assumptions, code references, wind-speed data, pressure results, and applicability before using any output. Do not use this project as the sole basis for construction documents, permit submissions, or final structural design.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
