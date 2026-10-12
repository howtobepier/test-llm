"""JARVIS — API locale FastAPI."""

from __future__ import annotations

import json
import platform
import shutil
import threading
from contextlib import asynccontextmanager
from typing import Any

import psutil
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from app.config import (
    CORS_ORIGINS,
    HOST,
    OLLAMA_MODEL,
    VOICE_MAX_SECONDS,
    ensure_dirs,
    public_settings,
)
from app.db import init_db, log_action, recent_actions
from app.llm import check_ollama, get_llm_status, preload_model
from app.memory import vault
from app.pipeline import handle_message, stream_message
from app.scheduler.engine import get_scheduler, load_routines, next_routines
from app.schemas import (
    ChatRequest,
    ChatResponse,
    EventCreate,
    NoteCreate,
    PreferenceSave,
    ReminderCreate,
    SpeakRequest,
    TodoCreate,
)
from app.tools import reminders as reminders_tool
from app.tools.registry import execute, import_all, list_tools
from app.voice import stt as stt_mod
from app.voice import tts as tts_mod

# richieste cancellabili
_cancel_flags: dict[str, threading.Event] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    init_db()
    import_all()
    vault.reindex_vault()
    check_ollama()
    try:
        preload_model()
    except Exception as exc:  # noqa: BLE001
        log_action("startup", "failed", "Preload modello", str(exc))
    sched = get_scheduler()
    sched.start()
    log_action("startup", "ok", "JARVIS avviato")
    yield
    sched.stop()
    log_action("shutdown", "ok", "JARVIS arrestato")


app = FastAPI(title="JARVIS", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _origin_ok(origin: str | None) -> bool:
    if origin is None:
        return True
    return origin in CORS_ORIGINS


@app.get("/statu-model-server")
def health():
    return {"status": "ok", "service": "jarvis"}


@app.get("/api/status")
def api_status():
    model = check_ollama()
    return {
        "status": "ok",
        "model": model,
        "settings": public_settings(),
        "voice": {"stt": stt_mod.stt_status(), "tts": tts_mod.tts_status()},
        "tools": list_tools(),
        "upcoming_routines": next_routines(),
        "notifications": get_scheduler().last_notifications[-10:],
        "recent_actions": recent_actions(15),
        "host_hint": HOST,
    }


@app.get("/api/system")
def api_system():
    vm = psutil.virtual_memory()
    disk = shutil.disk_usage(".")
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_cores": psutil.cpu_count(logical=True) or 0,
        "ram_percent": vm.percent,
        "ram_total_gb": round(vm.total / (1024**3), 1),
        "disk_percent": round(100 * disk.used / disk.total, 1) if disk.total else 0.0,
        "disk_free_gb": round(disk.free / (1024**3), 1),
        "host": platform.node(),
        "os": platform.system() + " " + platform.release(),
    }


@app.get("/api/dashboard")
def dashboard():
    todos = execute("list_todos")
    agenda = execute("list_agenda")
    rems = execute("list_reminders")
    priorities = execute("daily_priorities")
    recent = execute("list_recent_notes", limit=8)
    settings = public_settings()
    return {
        "backend": {"ok": True, "host": HOST},
        "model": get_llm_status(),
        "voice": {"stt": stt_mod.stt_status(), "tts": tts_mod.tts_status()},
        "todos": (todos.data or {}).get("todos", []),
        "priorities": (priorities.data or {}).get("priorities", []),
        "agenda": (agenda.data or {}).get("events", []),
        "reminders": (rems.data or {}).get("reminders", []),
        "routines": load_routines(),
        "upcoming_routines": next_routines(),
        "recent_notes": (recent.data or {}).get("results", []),
        "notifications": get_scheduler().last_notifications[-10:],
        "recent_actions": recent_actions(20),
        "integrations": settings["integrations"],
        "settings": {
            "model": OLLAMA_MODEL,
            "vault": settings["vault_dir"],
            "quiet_hours": settings["quiet_hours"],
            "voice_stt_enabled": settings["voice_stt_enabled"],
            "voice_tts_enabled": settings["voice_tts_enabled"],
            "voice_stt_model": settings["voice_stt_model"],
        },
    }


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    try:
        result = handle_message(body.message.strip(), history=body.history)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ChatResponse(
        reply=result.reply,
        mode=result.mode,
        used_model=result.used_model,
        tool=result.tool,
        tool_ok=result.tool_ok,
        sources=result.sources,
        data=result.data,
    )


@app.post("/chat/stream")
async def chat_stream(body: ChatRequest):
    cancel = threading.Event()
    req_id = str(id(cancel))
    _cancel_flags[req_id] = cancel

    def event_gen():
        try:
            yield f"data: {json.dumps({'request_id': req_id}, ensure_ascii=False)}\n\n"
            for event in stream_message(body.message.strip(), history=body.history, cancel_event=cancel):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            _cancel_flags.pop(req_id, None)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/chat/cancel")
def chat_cancel(payload: dict[str, Any]):
    req_id = str(payload.get("request_id") or "")
    flag = _cancel_flags.get(req_id)
    if not flag:
        return {"ok": False, "detail": "richiesta non trovata"}
    flag.set()
    return {"ok": True}


@app.post("/api/notes")
def api_save_note(body: NoteCreate):
    result = execute(
        "save_note",
        title=body.title,
        body=body.body,
        folder=body.folder,
        tags=body.tags,
    )
    if not result.ok:
        raise HTTPException(400, result.error or result.summary)
    return result.data


@app.get("/api/notes/search")
def api_search_notes(q: str, tag: str | None = None):
    result = execute("search_notes", query=q, tag=tag)
    return result.data or {"results": []}


@app.get("/api/notes/recent")
def api_recent_notes(limit: int = 8):
    result = execute("list_recent_notes", limit=limit)
    return result.data or {"results": []}


@app.get("/api/notes/open")
def api_open_note(path: str):
    result = execute("open_note", path=path)
    if not result.ok:
        raise HTTPException(400, result.error or result.summary)
    return result.data


@app.post("/api/briefing")
def api_briefing():
    result = execute("briefing")
    if not result.ok:
        raise HTTPException(400, result.error or result.summary)
    return {"ok": True, "summary": result.summary, "data": result.data}


@app.post("/api/evening-summary")
def api_evening_summary():
    result = execute("evening_summary")
    if not result.ok:
        raise HTTPException(400, result.error or result.summary)
    return {"ok": True, "summary": result.summary, "data": result.data}


@app.post("/api/priorities")
def api_priorities():
    result = execute("daily_priorities")
    if not result.ok:
        raise HTTPException(400, result.error or result.summary)
    return {"ok": True, "summary": result.summary, "data": result.data}


@app.post("/api/todos")
def api_add_todo(body: TodoCreate):
    result = execute("add_todo", title=body.title, priority=body.priority, due_at=body.due_at)
    if not result.ok:
        raise HTTPException(400, result.error or result.summary)
    return result.data


@app.post("/api/todos/complete")
def api_complete_todo(payload: dict[str, str]):
    result = execute("complete_todo", title_or_id=payload.get("title_or_id", ""))
    if not result.ok:
        raise HTTPException(400, result.error or result.summary)
    return result.data


@app.get("/api/todos")
def api_list_todos():
    return execute("list_todos").data


@app.post("/api/reminders")
def api_add_reminder(body: ReminderCreate):
    result = execute("add_reminder", title=body.title, when=body.when)
    if not result.ok:
        raise HTTPException(400, result.error or result.summary)
    return result.data


@app.get("/api/reminders")
def api_list_reminders():
    return execute("list_reminders").data


@app.post("/api/events")
def api_add_event(body: EventCreate):
    result = execute("add_event", title=body.title, when=body.when, notes=body.notes)
    if not result.ok:
        raise HTTPException(400, result.error or result.summary)
    return result.data


@app.get("/api/agenda")
def api_agenda(day: str | None = None):
    return execute("list_agenda", day=day).data


@app.post("/api/preferences")
def api_pref(body: PreferenceSave):
    result = execute("save_preference", key=body.key, value=body.value)
    if not result.ok:
        raise HTTPException(400, result.error or result.summary)
    return result.data


@app.get("/api/routines")
def api_routines():
    return {"routines": load_routines(), "upcoming": next_routines()}


@app.post("/api/routines/{routine_id}/run")
def api_run_routine(routine_id: str):
    result = execute("run_routine", routine_id=routine_id)
    return {"ok": result.ok, "summary": result.summary, "data": result.data, "error": result.error}


@app.get("/api/apps")
def api_apps():
    return execute("list_apps").data


@app.post("/api/apps/open")
def api_open_app(payload: dict[str, str]):
    result = execute("open_app", name=payload.get("name", ""))
    if not result.ok:
        raise HTTPException(400, result.error or result.summary)
    return result.data


@app.post("/api/voice/transcribe")
async def api_transcribe(file: UploadFile = File(...)):
    audio = await file.read()
    # Limite grezzo ~ voice max seconds * 192kbps
    max_bytes = max(VOICE_MAX_SECONDS, 5) * 48000
    if len(audio) > max_bytes:
        raise HTTPException(400, "Registrazione troppo lunga")
    result = stt_mod.transcribe_wav_bytes(audio, filename=file.filename or "audio.webm")
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "Trascrizione fallita")
    return result


@app.post("/api/voice/speak")
def api_speak(body: SpeakRequest):
    result = tts_mod.synthesize_to_wav(body.text)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "TTS fallito")
    return Response(content=result["audio"], media_type="audio/wav")


@app.post("/api/voice/stop")
def api_voice_stop():
    tts_mod.stop_speech()
    return {"ok": True}


@app.get("/api/diagnostics")
def diagnostics():
    return {
        "model": check_ollama(),
        "settings": public_settings(),
        "voice": {"stt": stt_mod.stt_status(), "tts": tts_mod.tts_status()},
        "reminders_due": reminders_tool.due_reminders(),
        "actions": recent_actions(30),
    }
