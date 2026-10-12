"""Sintesi vocale locale Windows (System.Speech) con fallback pyttsx3."""

from __future__ import annotations

import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

from app.config import VOICE_TTS_ENABLED

_lock = threading.Lock()
_last_error: str | None = None


def tts_status() -> dict[str, Any]:
    return {
        "enabled": VOICE_TTS_ENABLED,
        "engine": "System.Speech (PowerShell) / pyttsx3",
        "loaded": True,
        "error": _last_error,
        "voices": [],
    }


def _synthesize_system_speech(text: str, path: Path) -> None:
    # Evita injection: testo passato come argomento singolo quotato via base64.
    import base64

    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    out = str(path)
    ps = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$bytes = [Convert]::FromBase64String('{b64}')
$text = [Text.Encoding]::UTF8.GetString($bytes)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{
  $it = $synth.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like 'it*' }} | Select-Object -First 1
  if ($it) {{ $synth.SelectVoice($it.VoiceInfo.Name) }}
  $synth.SetOutputToWaveFile('{out.replace("'", "''")}')
  $synth.Speak($text)
}} finally {{
  $synth.Dispose()
}}
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    if completed.returncode != 0 or not path.exists() or path.stat().st_size < 44:
        err = (completed.stderr or completed.stdout or "System.Speech fallito").strip()
        raise RuntimeError(err[:300])


def _synthesize_pyttsx3(text: str, path: Path) -> None:
    import pyttsx3

    eng = pyttsx3.init()
    try:
        for voice in eng.getProperty("voices"):
            vid = (voice.id or "").lower()
            name = (getattr(voice, "name", "") or "").lower()
            if "italian" in vid or "italian" in name or "italia" in name or "_it_" in vid:
                eng.setProperty("voice", voice.id)
                break
        eng.setProperty("rate", 175)
        eng.save_to_file(text, str(path))
        eng.runAndWait()
    finally:
        try:
            eng.stop()
        except Exception:  # noqa: BLE001
            pass


def synthesize_to_wav(text: str) -> dict[str, Any]:
    global _last_error
    if not VOICE_TTS_ENABLED:
        return {"ok": False, "error": "TTS disabilitato"}
    text = (text or "").strip()[:800]
    if not text:
        return {"ok": False, "error": "Testo vuoto"}

    with _lock:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            path = Path(tmp.name)
        try:
            try:
                _synthesize_system_speech(text, path)
            except Exception:
                _synthesize_pyttsx3(text, path)
            data = path.read_bytes()
            if len(data) < 44:
                _last_error = "Sintesi vuota"
                return {"ok": False, "error": _last_error}
            _last_error = None
            return {"ok": True, "audio": data, "mime": "audio/wav"}
        except Exception as exc:  # noqa: BLE001
            _last_error = str(exc)
            return {"ok": False, "error": f"TTS non disponibile: {exc}"}
        finally:
            path.unlink(missing_ok=True)


def stop_speech() -> None:
    # System.Speech genera file completi: stop lato client sulla riproduzione.
    return
