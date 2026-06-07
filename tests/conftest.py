"""Shared test configuration."""

import pytest


@pytest.fixture(autouse=True)
def disable_optional_external_services(monkeypatch):
    """Keep the default suite deterministic even when local .env enables APIs."""
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("TTS_ENABLED", "false")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
