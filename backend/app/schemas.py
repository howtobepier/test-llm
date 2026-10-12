from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000, description="Messaggio dell'utente")
    history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    mode: str = "llm"
    used_model: bool = True
    tool: str | None = None
    tool_ok: bool | None = None
    sources: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    folder: str = "raw"
    tags: list[str] = Field(default_factory=list)


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    priority: int = Field(default=2, ge=1, le=3)
    due_at: str | None = None


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    when: str = Field(min_length=1, max_length=100)


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    when: str = Field(min_length=1, max_length=100)
    notes: str | None = None


class PreferenceSave(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=500)


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=800)
