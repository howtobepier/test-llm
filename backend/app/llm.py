"""Client Ollama locale ottimizzato: coda, timeout, streaming, niente fallback cloud."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Iterator
from typing import Any

from app.config import (
    HISTORY_MAX_MESSAGES,
    LLM_QUEUE_SIZE,
    MEMORY_BUDGET_CHARS,
    OLLAMA_BASE_URL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
    OLLAMA_PRELOAD,
    OLLAMA_TEMPERATURE,
    OLLAMA_TIMEOUT_S,
    SYSTEM_PROMPT,
)

_llm_semaphore = threading.Semaphore(max(1, LLM_QUEUE_SIZE))
_status_lock = threading.Lock()
_status: dict[str, Any] = {
    "available": False,
    "model": OLLAMA_MODEL,
    "detail": "non verificato",
    "last_check": None,
    "busy": False,
}


def get_llm_status() -> dict[str, Any]:
    with _status_lock:
        return dict(_status)


def _set_status(**kwargs: Any) -> None:
    with _status_lock:
        _status.update(kwargs)
        _status["last_check"] = time.time()


def check_ollama() -> dict[str, Any]:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        names = {m.get("name") for m in payload.get("models", [])}
        ok = OLLAMA_MODEL in names or any(
            (n or "").startswith(OLLAMA_MODEL.split(":")[0]) for n in names
        )
        _set_status(
            available=ok,
            detail="ok" if ok else f"modello {OLLAMA_MODEL} non trovato in Ollama",
            models=sorted(names),
        )
    except Exception as exc:  # noqa: BLE001
        _set_status(available=False, detail=f"Ollama non raggiungibile: {exc}", models=[])
    return get_llm_status()


def preload_model() -> None:
    if not OLLAMA_PRELOAD:
        return
    status = check_ollama()
    if not status.get("available"):
        return
    try:
        _generate("ok", num_predict=1, stream=False)
        _set_status(available=True, detail="modello in memoria")
    except Exception as exc:  # noqa: BLE001
        _set_status(available=False, detail=f"preload fallito: {exc}")


def _messages_payload(
    message: str,
    history: list[dict[str, str]] | None = None,
    memory_excerpts: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if memory_excerpts:
        mem = "\n".join(f"- ({e['path']}) {e['text']}" for e in memory_excerpts)
        messages.append(
            {
                "role": "system",
                "content": (
                    "Estratti memoria (usa solo se pertinenti; cita i file):\n"
                    f"{mem[:MEMORY_BUDGET_CHARS]}"
                ),
            }
        )
    if history:
        for item in history[-HISTORY_MAX_MESSAGES:]:
            role = item.get("role")
            content = (item.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content[:2000]})
    messages.append({"role": "user", "content": message.strip()[:4000]})
    return messages


def _generate(
    message: str,
    *,
    history: list[dict[str, str]] | None = None,
    memory_excerpts: list[dict[str, str]] | None = None,
    num_predict: int | None = None,
    stream: bool = False,
):
    body = {
        "model": OLLAMA_MODEL,
        "messages": _messages_payload(message, history, memory_excerpts),
        "stream": stream,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": num_predict if num_predict is not None else OLLAMA_NUM_PREDICT,
            "temperature": OLLAMA_TEMPERATURE,
        },
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_S)


def generate_reply(
    message: str,
    history: list[dict[str, str]] | None = None,
    memory_excerpts: list[dict[str, str]] | None = None,
) -> str:
    if not _llm_semaphore.acquire(timeout=OLLAMA_TIMEOUT_S):
        raise TimeoutError("Coda modello satura: riprova tra poco")
    _set_status(busy=True)
    try:
        with _generate(message, history=history, memory_excerpts=memory_excerpts, stream=False) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        _set_status(available=True, detail="ok")
        return str((payload.get("message") or {}).get("content") or "").strip()
    except Exception:
        _set_status(available=False, detail="errore generazione")
        raise
    finally:
        _set_status(busy=False)
        _llm_semaphore.release()


def stream_reply(
    message: str,
    history: list[dict[str, str]] | None = None,
    memory_excerpts: list[dict[str, str]] | None = None,
    cancel_event: threading.Event | None = None,
) -> Iterator[str]:
    if not _llm_semaphore.acquire(timeout=OLLAMA_TIMEOUT_S):
        raise TimeoutError("Coda modello satura: riprova tra poco")
    _set_status(busy=True)
    try:
        resp = _generate(message, history=history, memory_excerpts=memory_excerpts, stream=True)
        try:
            for raw in resp:
                if cancel_event is not None and cancel_event.is_set():
                    break
                if not raw.strip():
                    continue
                obj = json.loads(raw.decode("utf-8"))
                token = str((obj.get("message") or {}).get("content") or "")
                if token:
                    yield token
                if obj.get("done"):
                    break
            _set_status(available=True, detail="ok")
        finally:
            resp.close()
    except urllib.error.URLError as exc:
        _set_status(available=False, detail=str(exc))
        raise
    finally:
        _set_status(busy=False)
        _llm_semaphore.release()


async def astream_reply(
    message: str,
    history: list[dict[str, str]] | None = None,
    memory_excerpts: list[dict[str, str]] | None = None,
    cancel_event: threading.Event | None = None,
) -> AsyncIterator[str]:
    # Streaming reale via generatore sync in thread-friendly chunks.
    for token in stream_reply(message, history, memory_excerpts, cancel_event):
        yield token


# Compatibilità con eventuale codice legacy
def generate_reply_legacy(message: str) -> str:
    return generate_reply(message)
