from __future__ import annotations

from app.memory import vault
from app.tools.registry import ToolResult, register


@register("save_preference")
def save_preference(key: str, value: str) -> ToolResult:
    if not key.strip() or not value.strip():
        return ToolResult(ok=False, summary="Chiave e valore obbligatori", error="args")
    data = vault.save_preference(key.strip(), value.strip())
    return ToolResult(ok=True, summary=f"Preferenza salvata: {key}", data=data)
