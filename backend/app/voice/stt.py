"""Trascrizione locale con faster-whisper (multilingue, adatta all'italiano)."""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from typing import Any

from app.config import KEEP_AUDIO, VOICE_STT_ENABLED, VOICE_STT_MODEL

_lock = threading.Lock()
_model = None
_model_error: str | None = None


def stt_status() -> dict[str, Any]:
    return {
        "enabled": VOICE_STT_ENABLED,
        "model": VOICE_STT_MODEL,
        "loaded": _model is not None,
        "error": _model_error,
        "engine": "faster-whisper",
    }


def _load_model():
    global _model, _model_error
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        try:
            from faster_whisper import WhisperModel

            # CPU int8: adatto a macchine senza GPU NVIDIA.
            _model = WhisperModel(VOICE_STT_MODEL, device="cpu", compute_type="int8")
            _model_error = None
        except Exception as exc:  # noqa: BLE001
            _model_error = str(exc)
            _model = None
            raise
        return _model


def transcribe_wav_bytes(audio: bytes, filename: str = "audio.wav") -> dict[str, Any]:
    if not VOICE_STT_ENABLED:
        return {"ok": False, "text": "", "error": "STT disabilitato nella configurazione"}
    if not audio or len(audio) < 44:
        return {"ok": False, "text": "", "error": "Registrazione vuota o troppo corta"}

    suffix = Path(filename).suffix or ".wav"
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio)
            tmp_path = Path(tmp.name)
        model = _load_model()
        segments, info = model.transcribe(
            str(tmp_path),
            language="it",
            vad_filter=True,
            beam_size=1,
        )
        parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
        text = " ".join(parts).strip()
        if not text:
            return {"ok": False, "text": "", "error": "Silenzio o parlato non riconosciuto"}
        return {
            "ok": True,
            "text": text,
            "language": getattr(info, "language", "it"),
            "duration": getattr(info, "duration", None),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "text": "", "error": f"Trascrizione non disponibile: {exc}"}
    finally:
        if tmp_path and tmp_path.exists() and not KEEP_AUDIO:
            try:
                tmp_path.unlink()
            except OSError:
                pass
