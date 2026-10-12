"""Vault Markdown compatibile Obsidian: raw / wiki / outputs.

Mantra: se non è nel vault, non è successo.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import VAULT_DIR, ensure_dirs
from app.db import db, log_action
from app.security import SecurityError, resolve_under, safe_filename

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?(?:#[^\]]+)?\]\]")

# Cartelle Obsidian canoniche
VAULT_FOLDERS = ("raw", "wiki", "outputs")
# Alias legacy → cartella attuale
FOLDER_ALIASES = {
    "inbox": "raw",
    "notes": "wiki",
    "daily": "wiki",
    "projects": "wiki",
}
LEGACY_MIGRATE = {
    "inbox": "raw",
    "notes": "wiki",
    "daily": "wiki",
    "projects": "wiki",
}


def vault_root() -> Path:
    ensure_dirs()
    return VAULT_DIR.resolve()


def normalize_folder(folder: str) -> str:
    key = (folder or "raw").strip().lower().replace("\\", "/").strip("/")
    if "/" in key:
        raise SecurityError(f"Cartella non consentita: {folder}")
    key = FOLDER_ALIASES.get(key, key)
    if key not in VAULT_FOLDERS:
        raise SecurityError(f"Cartella non consentita: {folder} (usa: {', '.join(VAULT_FOLDERS)})")
    return key


def migrate_legacy_layout(root: Path) -> None:
    """Sposta note dalle cartelle pre-Obsidian verso raw/wiki/outputs."""
    for old, new in LEGACY_MIGRATE.items():
        src = root / old
        dst = root / new
        if not src.is_dir():
            continue
        dst.mkdir(parents=True, exist_ok=True)
        for path in src.iterdir():
            if path.name == ".gitkeep":
                continue
            if not path.is_file():
                continue
            target = dst / path.name
            if target.exists():
                stem, suffix = path.stem, path.suffix
                n = 1
                while target.exists():
                    target = dst / f"{stem}-migrated{n}{suffix}"
                    n += 1
            shutil.move(str(path), str(target))
        # rimuovi cartella legacy se vuota (o solo .gitkeep)
        leftovers = [p for p in src.iterdir() if p.name != ".gitkeep"]
        if not leftovers:
            shutil.rmtree(src, ignore_errors=True)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=str(path.parent), suffix=".tmp"
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key] = [p.strip().strip("'\"") for p in inner.split(",") if p.strip()] if inner else []
        else:
            meta[key] = value.strip("'\"")
    body = text[match.end() :]
    return meta, body


def extract_wikilinks(text: str) -> list[str]:
    seen: list[str] = []
    for m in WIKILINK_RE.finditer(text or ""):
        name = m.group(1).strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def build_note(
    title: str,
    body: str,
    *,
    tags: list[str] | None = None,
    folder: str = "raw",
    source: str = "jarvis",
    links: list[str] | None = None,
) -> dict[str, Any]:
    ensure_dirs()
    folder = normalize_folder(folder)
    now = datetime.now().astimezone()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    slug = safe_filename(title)
    rel = Path(folder) / f"{stamp}-{slug}.md"
    path = resolve_under(vault_root(), rel)
    tags = tags or []
    tags_literal = "[" + ", ".join(tags) + "]" if tags else "[]"
    body_text = body.strip()
    if links:
        link_block = "\n".join(f"- [[{name}]]" for name in links if name.strip())
        if link_block:
            body_text = f"{body_text}\n\n## Collegamenti\n\n{link_block}"
    content = (
        f"---\n"
        f"title: {title}\n"
        f"created: {now.isoformat(timespec='seconds')}\n"
        f"updated: {now.isoformat(timespec='seconds')}\n"
        f"tags: {tags_literal}\n"
        f"source: {source}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{body_text}\n"
    )
    atomic_write(path, content)
    index_note(path)
    log_action("note.save", "ok", f"Nota salvata: {title}", str(path))
    return {
        "path": str(path),
        "relative": str(rel).replace("\\", "/"),
        "title": title,
        "tags": tags,
        "folder": folder,
        "links": extract_wikilinks(content),
    }


def index_note(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    title = str(meta.get("title") or path.stem)
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags_s = tags
    else:
        tags_s = ",".join(str(t) for t in tags)
    links = extract_wikilinks(text)
    links_s = ",".join(links)
    with db() as conn:
        # colonne links opzionali: se assenti, solo campi base
        cols = {r[1] for r in conn.execute("PRAGMA table_info(note_index)").fetchall()}
        if "links" in cols:
            conn.execute(
                """
                INSERT INTO note_index(path, title, tags, mtime, body, links)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                  title=excluded.title,
                  tags=excluded.tags,
                  mtime=excluded.mtime,
                  body=excluded.body,
                  links=excluded.links
                """,
                (str(path.resolve()), title, tags_s, path.stat().st_mtime, body, links_s),
            )
        else:
            conn.execute(
                """
                INSERT INTO note_index(path, title, tags, mtime, body)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                  title=excluded.title,
                  tags=excluded.tags,
                  mtime=excluded.mtime,
                  body=excluded.body
                """,
                (str(path.resolve()), title, tags_s, path.stat().st_mtime, body),
            )


def reindex_vault() -> int:
    root = vault_root()
    migrate_legacy_layout(root)
    count = 0
    with db() as conn:
        conn.execute("DELETE FROM note_index")
    for path in root.rglob("*.md"):
        if ".obsidian" in path.parts:
            continue
        try:
            resolve_under(root, path)
            index_note(path)
            count += 1
        except (OSError, SecurityError, UnicodeError):
            continue
    return count


def _note_hit(row: Any) -> dict[str, Any]:
    snippet = (row["body"] or "").strip().replace("\n", " ")
    if len(snippet) > 180:
        snippet = snippet[:177] + "..."
    path = row["path"]
    try:
        rel = str(Path(path).resolve().relative_to(vault_root()))
    except (OSError, ValueError):
        rel = path
    return {
        "path": path,
        "relative": rel.replace("\\", "/"),
        "title": row["title"],
        "tags": [t for t in (row["tags"] or "").split(",") if t],
        "snippet": snippet,
        "mtime": row["mtime"] if "mtime" in row.keys() else None,
    }


def search_notes(
    query: str,
    *,
    tag: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    ensure_dirs()
    reindex_if_stale()
    q = f"%{query.strip().lower()}%"
    sql = """
        SELECT path, title, tags, body, mtime FROM note_index
        WHERE (lower(title) LIKE ? OR lower(body) LIKE ? OR lower(tags) LIKE ?)
    """
    params: list[Any] = [q, q, q]
    if tag:
        sql += " AND lower(tags) LIKE ?"
        params.append(f"%{tag.lower()}%")
    sql += " ORDER BY mtime DESC LIMIT ?"
    params.append(limit)
    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_note_hit(row) for row in rows]


def recent_notes(limit: int = 8) -> list[dict[str, Any]]:
    ensure_dirs()
    reindex_if_stale()
    with db() as conn:
        rows = conn.execute(
            """
            SELECT path, title, tags, body, mtime FROM note_index
            ORDER BY mtime DESC LIMIT ?
            """,
            (max(1, min(limit, 30)),),
        ).fetchall()
    return [_note_hit(row) for row in rows]


def reindex_if_stale() -> None:
    root = vault_root()
    with db() as conn:
        indexed = {
            r["path"]: r["mtime"]
            for r in conn.execute("SELECT path, mtime FROM note_index").fetchall()
        }
    current = {
        str(p.resolve()): p.stat().st_mtime
        for p in root.rglob("*.md")
        if ".obsidian" not in p.parts
    }
    if set(indexed) != set(current) or any(
        abs(indexed.get(p, -1) - m) > 0.001 for p, m in current.items()
    ):
        reindex_vault()


def open_note_path(user_path: str) -> dict[str, Any]:
    path = resolve_under(vault_root(), user_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Nota non trovata: {path}")
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    return {
        "path": str(path),
        "title": meta.get("title") or path.stem,
        "tags": meta.get("tags") or [],
        "body": body,
        "meta": meta,
        "links": extract_wikilinks(text),
    }


def save_preference(key: str, value: str) -> dict[str, Any]:
    prefs = resolve_under(vault_root(), "wiki/preferences.md")
    # preferenze in wiki; migra da root se presente
    legacy = vault_root() / "preferences.md"
    if not prefs.exists() and legacy.exists():
        prefs.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy), str(prefs))
    existing = (
        prefs.read_text(encoding="utf-8")
        if prefs.exists()
        else "---\ntitle: Preferenze\ntags: [preferenze]\n---\n\n# Preferenze\n\n"
    )
    line = f"- **{key.strip()}**: {value.strip()}"
    pattern = re.compile(rf"^- \*\*{re.escape(key.strip())}\*\*:.*$", re.MULTILINE)
    if pattern.search(existing):
        updated = pattern.sub(line, existing)
    else:
        updated = existing.rstrip() + "\n\n" + line + "\n"
    atomic_write(prefs, updated)
    index_note(prefs)
    log_action("preference.save", "ok", f"Preferenza salvata: {key}")
    return {"path": str(prefs), "key": key, "value": value}


def relevant_excerpts(query: str, budget_chars: int) -> list[dict[str, str]]:
    hits = search_notes(query, limit=5)
    excerpts: list[dict[str, str]] = []
    used = 0
    for hit in hits:
        chunk = f"{hit['title']}: {hit['snippet']}"
        if used + len(chunk) > budget_chars:
            break
        excerpts.append({"path": hit["path"], "text": chunk})
        used += len(chunk)
    return excerpts
