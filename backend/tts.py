"""Backend text-to-speech integration.

This module keeps OpenAI credentials server-side and degrades explicitly when
TTS is disabled, unconfigured, or unavailable.
"""

from __future__ import annotations

import inspect
import os
from typing import Any


DEFAULT_TTS_MODEL = "tts-1"
DEFAULT_TTS_VOICE = "alloy"


class TTSUnavailableError(RuntimeError):
    """Raised when TTS should fall back without breaking the chat flow."""


def tts_enabled() -> bool:
    return os.getenv("TTS_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


def configured_voice(voice: str | None = None) -> str:
    return voice or os.getenv("TTS_VOICE") or DEFAULT_TTS_VOICE


async def synthesize_speech(text: str, voice: str = DEFAULT_TTS_VOICE) -> bytes:
    """Synthesize plain spoken text to MP3 bytes using OpenAI's speech API."""
    spoken_text = text.strip()
    if not spoken_text:
        raise TTSUnavailableError("No text was provided for speech synthesis.")
    if not tts_enabled():
        raise TTSUnavailableError("Text-to-speech is disabled.")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise TTSUnavailableError("Text-to-speech is unavailable because OPENAI_API_KEY is not configured.")

    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise TTSUnavailableError("Text-to-speech is unavailable because the OpenAI SDK is not installed.") from exc

    try:
        client = AsyncOpenAI(api_key=api_key)
        response = await client.audio.speech.create(
            model=os.getenv("TTS_MODEL", DEFAULT_TTS_MODEL),
            voice=voice,
            input=spoken_text,
            response_format="mp3",
        )
        return await _response_to_bytes(response)
    except TTSUnavailableError:
        raise
    except Exception as exc:  # pragma: no cover - concrete SDK exceptions vary by version
        raise TTSUnavailableError("Text-to-speech generation failed.") from exc


async def _response_to_bytes(response: Any) -> bytes:
    if isinstance(response, bytes):
        return response

    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content

    read = getattr(response, "read", None)
    if callable(read):
        result = read()
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, bytes):
            return result

    raise TTSUnavailableError("Text-to-speech response did not contain audio bytes.")
