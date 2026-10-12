"""Configurazione centrale JARVIS (solo locale, senza fallback cloud)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent

load_dotenv(BACKEND_ROOT / ".env")


def _env(name: str, default: str | None = None) -> str | None:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if raw is None:
        return default
    return float(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on", "si", "sì"}


HOST = _env("JARVIS_HOST", "127.0.0.1") or "127.0.0.1"
PORT = _env_int("JARVIS_PORT", 8000)

OLLAMA_MODEL = _env("OLLAMA_MODEL", "llama3.2:3b") or "llama3.2:3b"
OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL", "http://127.0.0.1:11434") or "http://127.0.0.1:11434"
OLLAMA_NUM_CTX = _env_int("OLLAMA_NUM_CTX", 2048)
OLLAMA_NUM_PREDICT = _env_int("OLLAMA_NUM_PREDICT", 256)
OLLAMA_KEEP_ALIVE = _env("OLLAMA_KEEP_ALIVE", "30m") or "30m"
OLLAMA_TEMPERATURE = _env_float("OLLAMA_TEMPERATURE", 0.4)
OLLAMA_TIMEOUT_S = _env_float("OLLAMA_TIMEOUT_S", 90.0)
OLLAMA_PRELOAD = _env_bool("OLLAMA_PRELOAD", True)

HISTORY_MAX_MESSAGES = _env_int("HISTORY_MAX_MESSAGES", 6)
MEMORY_BUDGET_CHARS = _env_int("MEMORY_BUDGET_CHARS", 1200)
LLM_QUEUE_SIZE = _env_int("LLM_QUEUE_SIZE", 1)

DATA_DIR = Path(_env("JARVIS_DATA_DIR", str(BACKEND_ROOT / "data")) or (BACKEND_ROOT / "data"))
VAULT_DIR = Path(_env("JARVIS_VAULT_DIR", str(BACKEND_ROOT / "vault")) or (BACKEND_ROOT / "vault"))
DB_PATH = Path(_env("JARVIS_DB_PATH", str(DATA_DIR / "jarvis.db")) or (DATA_DIR / "jarvis.db"))
APPS_CONFIG = Path(
    _env("JARVIS_APPS_CONFIG", str(BACKEND_ROOT / "config" / "apps.json"))
    or (BACKEND_ROOT / "config" / "apps.json")
)
ROUTINES_CONFIG = Path(
    _env("JARVIS_ROUTINES_CONFIG", str(BACKEND_ROOT / "config" / "routines.json"))
    or (BACKEND_ROOT / "config" / "routines.json")
)
METRICS_CSV = Path(
    _env("JARVIS_METRICS_CSV", str(DATA_DIR / "metrics.csv")) or (DATA_DIR / "metrics.csv")
)

VOICE_STT_MODEL = _env("VOICE_STT_MODEL", "tiny") or "tiny"
VOICE_STT_ENABLED = _env_bool("VOICE_STT_ENABLED", True)
VOICE_TTS_ENABLED = _env_bool("VOICE_TTS_ENABLED", True)
VOICE_MAX_SECONDS = _env_int("VOICE_MAX_SECONDS", 30)
KEEP_AUDIO = _env_bool("VOICE_KEEP_AUDIO", False)

QUIET_HOURS_START = _env("QUIET_HOURS_START", "22:00") or "22:00"
QUIET_HOURS_END = _env("QUIET_HOURS_END", "07:00") or "07:00"

CORS_ORIGINS = [
    o.strip()
    for o in (_env("JARVIS_CORS_ORIGINS", "http://localhost:4200,http://127.0.0.1:4200") or "").split(",")
    if o.strip()
]

SYSTEM_PROMPT = (
    "Sei JARVIS, assistente personale locale in italiano. "
    "Rispondi in modo breve e concreto. "
    "La memoria a lungo termine è il vault Obsidian (Markdown): "
    "se un fatto non è nel vault, non inventarlo. "
    "Non inventare file o azioni eseguite. "
    "Se non sai qualcosa, dillo. "
    "Non eseguire comandi di sistema: proponi solo azioni strutturate quando richiesto."
)


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Vault Obsidian: raw (catture), wiki (conoscenza), outputs (generati da JARVIS)
    for sub in ("raw", "wiki", "outputs"):
        (VAULT_DIR / sub).mkdir(parents=True, exist_ok=True)
    obsidian = VAULT_DIR / ".obsidian"
    obsidian.mkdir(parents=True, exist_ok=True)
    app_json = obsidian / "app.json"
    if not app_json.exists():
        app_json.write_text(
            json.dumps(
                {
                    "alwaysUpdateLinks": True,
                    "newFileLocation": "folder",
                    "newFileFolderPath": "raw",
                    "attachmentFolderPath": "raw",
                    "showUnsupportedFiles": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    home = VAULT_DIR / "wiki" / "Home.md"
    if not home.exists():
        home.write_text(
            "---\n"
            "title: Home\n"
            "tags: [home, jarvis]\n"
            "---\n\n"
            "# Home\n\n"
            "Vault Obsidian di JARVIS. **Se non è nel vault, non è successo.**\n\n"
            "## Struttura\n\n"
            "- [[raw]] — catture e inbox (`raw/`)\n"
            "- [[wiki]] — conoscenza collegata (`wiki/`)\n"
            "- [[outputs]] — briefing e riepiloghi (`outputs/`)\n"
            "- [[Preferenze]] — preferenze esplicite\n\n"
            "Tutto è Markdown. Apri questa cartella in Obsidian per il grafo.\n",
            encoding="utf-8",
        )
    prefs = VAULT_DIR / "wiki" / "preferences.md"
    legacy_prefs = VAULT_DIR / "preferences.md"
    if not prefs.exists() and legacy_prefs.exists():
        prefs.write_text(legacy_prefs.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            legacy_prefs.unlink()
        except OSError:
            pass
    if not prefs.exists():
        prefs.write_text(
            "---\ntitle: Preferenze\ntags: [preferenze]\n---\n\n# Preferenze\n\n"
            "Salva qui solo preferenze esplicitamente richieste dall'utente.\n",
            encoding="utf-8",
        )
    (BACKEND_ROOT / "config").mkdir(parents=True, exist_ok=True)
    if not APPS_CONFIG.exists():
        example = BACKEND_ROOT / "config" / "apps.example.json"
        if example.exists():
            APPS_CONFIG.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            APPS_CONFIG.write_text(
                json.dumps(
                    {
                        "apps": [
                            {
                                "id": "notepad",
                                "name": "Blocco note",
                                "aliases": ["blocco note", "notepad"],
                                "path": "notepad.exe",
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
    if not ROUTINES_CONFIG.exists():
        example = BACKEND_ROOT / "config" / "routines.example.json"
        if example.exists():
            ROUTINES_CONFIG.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")


def load_json_config(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def public_settings() -> dict[str, Any]:
    return {
        "model": OLLAMA_MODEL,
        "ollama_base_url": OLLAMA_BASE_URL,
        "num_ctx": OLLAMA_NUM_CTX,
        "num_predict": OLLAMA_NUM_PREDICT,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "temperature": OLLAMA_TEMPERATURE,
        "timeout_s": OLLAMA_TIMEOUT_S,
        "history_max_messages": HISTORY_MAX_MESSAGES,
        "memory_budget_chars": MEMORY_BUDGET_CHARS,
        "vault_dir": str(VAULT_DIR),
        "data_dir": str(DATA_DIR),
        "voice_stt_model": VOICE_STT_MODEL,
        "voice_stt_enabled": VOICE_STT_ENABLED,
        "voice_tts_enabled": VOICE_TTS_ENABLED,
        "quiet_hours": {"start": QUIET_HOURS_START, "end": QUIET_HOURS_END},
        "integrations": {
            "email": "non_configurato",
            "notizie": "non_configurato",
            "calendario_esterno": "non_configurato",
            "social": "non_configurato",
        },
    }
