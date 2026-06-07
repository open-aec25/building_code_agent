"""Tests for backend text-to-speech integration."""

import asyncio
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.main import app
from backend.tts import TTSUnavailableError, synthesize_speech


client = TestClient(app)


def test_synthesize_speech_uses_openai_client_and_returns_mp3_bytes(monkeypatch):
    captured = {}

    class FakeSpeech:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(content=b"fake-mp3")

    class FakeAsyncOpenAI:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.audio = SimpleNamespace(speech=FakeSpeech())

    monkeypatch.setenv("TTS_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))

    audio = asyncio.run(synthesize_speech("Plain spoken response.", voice="nova"))

    assert audio == b"fake-mp3"
    assert captured["api_key"] == "test-openai-key"
    assert captured["model"] == "tts-1"
    assert captured["voice"] == "nova"
    assert captured["input"] == "Plain spoken response."
    assert captured["response_format"] == "mp3"


def test_synthesize_speech_raises_when_tts_disabled(monkeypatch):
    monkeypatch.setenv("TTS_ENABLED", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    with pytest.raises(TTSUnavailableError, match="disabled"):
        asyncio.run(synthesize_speech("Plain spoken response."))


def test_synthesize_speech_wraps_upstream_failure(monkeypatch):
    class FakeSpeech:
        async def create(self, **kwargs):
            raise RuntimeError("upstream unavailable")

    class FakeAsyncOpenAI:
        def __init__(self, api_key):
            self.audio = SimpleNamespace(speech=FakeSpeech())

    monkeypatch.setenv("TTS_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))

    with pytest.raises(TTSUnavailableError, match="generation failed"):
        asyncio.run(synthesize_speech("Plain spoken response."))


def test_tts_route_returns_audio_mpeg_on_success(monkeypatch):
    captured = {}

    async def fake_synthesize(text, voice):
        captured["text"] = text
        captured["voice"] = voice
        return b"route-mp3"

    monkeypatch.setenv("TTS_VOICE", "alloy")
    monkeypatch.setattr(main, "synthesize_speech", fake_synthesize)

    response = client.post(
        "/tts",
        json={"text": "Plain spoken response.", "session_id": "session-1"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"route-mp3"
    assert captured == {"text": "Plain spoken response.", "voice": "alloy"}


def test_tts_route_returns_json_fallback_when_unavailable(monkeypatch):
    async def fake_synthesize(text, voice):
        raise TTSUnavailableError("Text-to-speech is disabled.")

    monkeypatch.setattr(main, "synthesize_speech", fake_synthesize)

    response = client.post("/tts", json={"text": "Plain spoken response."})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "tts_available": False,
        "detail": "Text-to-speech is disabled.",
    }
