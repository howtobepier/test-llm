"""Protezioni di percorso e validazione argomenti."""

from __future__ import annotations

from pathlib import Path


class SecurityError(ValueError):
    """Violazione di un confine di sicurezza."""


def resolve_under(base: Path, user_path: str | Path) -> Path:
    """Risolve un percorso e verifica che resti sotto base (anche con junction/symlink)."""
    base_resolved = base.resolve()
    candidate = Path(user_path)
    if not candidate.is_absolute():
        candidate = base_resolved / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise SecurityError(f"Percorso fuori dalle directory consentite: {resolved}") from exc
    return resolved


def safe_filename(name: str, max_len: int = 80) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", " "} else "-" for ch in name.strip())
    cleaned = "-".join(cleaned.split())
    if not cleaned:
        cleaned = "nota"
    return cleaned[:max_len].strip("-") or "nota"
