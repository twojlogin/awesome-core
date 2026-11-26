#!/usr/bin/env python3
"""core/status.py — stan danych i plan odświeżenia (bez automatyki w tle)."""

import calendar
import json
import time
from pathlib import Path

from core import store
from core.enrich import missing_repos


BASE_DIR = Path(__file__).parent.parent


def collect(data_dir=None):
    """Zwraca stan bazy + co warto odświeżyć. Nic nie uruchamia."""
    path = store.db_path(data_dir)
    if not store.db_ready(data_dir):
        return {
            "ready": False,
            "db": str(path),
            "steps": [
                {"id": "download", "label": "Pobierz listy", "command": "./awesome download"},
                {"id": "build", "label": "Zbuduj bazę", "command": "./awesome build"},
            ],
        }

    conn = store.connect(data_dir, read_only=True)
    row = conn.execute(
        "SELECT COUNT(*) tools, COUNT(DISTINCT source_repo) lists, "
        "COALESCE(SUM(tool_stars=0), 0) tools_no_meta, "
        "COALESCE(SUM(tool_stars=0 AND url_norm LIKE 'github.com/%'), 0) "
        "github_no_meta, COALESCE(SUM(alive=1), 0) alive, "
        "COALESCE(SUM(alive=0), 0) dead FROM tools"
    ).fetchone()
    mentions = conn.execute("SELECT COUNT(*) FROM tool_mentions").fetchone()[0]
    repo_stats = conn.execute(
        "SELECT COUNT(*) lists_total, "
        "COALESCE(SUM(stars=0 AND language=''), 0) lists_no_meta FROM repos"
    ).fetchone()
    lists_total = repo_stats["lists_total"]
    lists_no_meta = repo_stats["lists_no_meta"]
    tools_no_meta = row["tools_no_meta"]
    github_no_meta = row["github_no_meta"]
    nongithub_links = tools_no_meta - github_no_meta
    # Ile faktycznie jest do zrobienia — nie "narzędzi", tylko repozytoriów:
    # kilka narzędzi często wskazuje na to samo repo, a 404 już odpytaliśmy.
    repos_to_fetch = len(missing_repos(conn, priority=False))
    repo_meta = conn.execute("SELECT COUNT(*) FROM tool_repo_meta").fetchone()[0]
    alive = row["alive"]
    dead = row["dead"]
    readmes = 0
    readme_dir = BASE_DIR / "offline-db" / "data" / "readmes"
    if readme_dir.exists():
        readmes = sum(1 for _ in readme_dir.glob("*.md"))

    meta = {row["key"]: row["value"] for row in conn.execute("SELECT * FROM meta")}
    conn.close()

    def age(timestamp):
        """Znacznik jest w UTC, więc timegm — mktime interpretowałoby go lokalnie."""
        if not timestamp:
            return None
        try:
            stamp = calendar.timegm(time.strptime(timestamp, "%Y-%m-%d %H:%M:%SZ"))
        except ValueError:
            return None
        delta = max(0.0, time.time() - stamp)
        if delta < 90:
            return "przed chwilą"
        if delta < 3600:
            return f"{delta / 60:.0f} min temu"
        if delta < 86400:
            return f"{delta / 3600:.1f} h temu"
        return f"{delta / 86400:.1f} dni temu"

    started = meta.get("enrich_started_at", "")
    running = bool(started) and started > meta.get("last_enrich", "")

    steps = []
    if running:
        steps.append({
            "id": "enrich",
            "label": "Trwa pobieranie metadanych narzędzi",
            "why": f"start {started} ({age(started)}), cel "
                   f"{meta.get('enrich_limit', '?')} repozytoriów",
            "command": "poczekaj albo przerwij (Ctrl+C) — postęp jest zapisywany",
        })
    if readmes < lists_total:
        steps.append({
            "id": "download",
            "label": "Pobrać brakujące README",
            "why": f"{lists_total - readmes} list bez lokalnej kopii README",
            "command": "./awesome download",
        })
    if lists_no_meta:
        steps.append({
            "id": "backfill",
            "label": "Uzupełnić metadane list",
            "why": f"{lists_no_meta} list bez gwiazdek/języka",
            "command": "./awesome backfill",
        })
    if repos_to_fetch:
        steps.append({
            "id": "enrich",
            "label": "Pobrać metadane narzędzi",
            "why": f"{repos_to_fetch} repozytoriów GitHub do odpytania "
                   f"({github_no_meta} narzędzi bez własnych gwiazdek)",
            "command": "./awesome enrich",
        })
    last_build = meta.get("last_build", "")
    last_backfill = meta.get("last_backfill", "")
    last_enrich = meta.get("last_enrich", "")
    needs_build = (not last_build) or (
        bool(last_backfill) and last_backfill > last_build
    ) or (bool(last_enrich) and last_enrich > last_build)
    if needs_build:
        steps.append({
            "id": "build",
            "label": "Przebudować bazę",
            "why": "po backfill/enrichu albo po nowym buildzie",
            "command": "./awesome build",
        })

    return {
        "ready": True,
        "tools": row["tools"],
        "lists": row["lists"],
        "lists_total": lists_total,
        "mentions": mentions,
        "readmes": readmes,
        "lists_without_meta": lists_no_meta,
        "tools_without_own_meta": tools_no_meta,
        "github_without_own_meta": github_no_meta,
        "nongithub_links": nongithub_links,
        "repos_to_fetch": repos_to_fetch,
        "repo_meta": repo_meta,
        "alive": alive,
        "dead": dead,
        "last_build": meta.get("last_build", ""),
        "last_build_age": age(meta.get("last_build")),
        "last_build_seconds": meta.get("last_build_seconds", ""),
        "last_backfill": meta.get("last_backfill", ""),
        "last_backfill_age": age(meta.get("last_backfill")),
        "last_enrich": meta.get("last_enrich", ""),
        "last_enrich_age": age(meta.get("last_enrich")),
        "enrich_running": running,
        "enrich_started": started,
        "enrich_limit": meta.get("enrich_limit", ""),
        "db_size_mb": round(path.stat().st_size / 1048576, 1) if path.exists() else 0,
        "steps": steps,
    }


def render(status):
    """Czytelny raport tekstowy (dla CLI)."""
    if not status.get("ready"):
        return [
            "Baza nie istnieje.",
            f"  DB: {status['db']}",
            "Kolejność:",
            *[f"  {s['command']}" for s in status["steps"]],
        ]
    lines = [
        "Stan danych",
        f"  narzędzia:        {status['tools']:,} (unikalne URL)",
        f"  wzmianki:         {status['mentions']:,}",
        f"  listy:            {status['lists']} z {status['lists_total']} "
        f"(README lokalnie: {status['readmes']})",
        f"  linki:            żywe {status['alive']:,} / martwe {status['dead']:,}",
        f"  poza GitHubem:    {status['nongithub_links']:,} "
        "(dokumentacja/artykuły — bez gwiazdek z definicji)",
        f"  baza:             {status['db_size_mb']} MB",
        f"  ostatni build:    {status['last_build'] or '—'}"
        + (f" ({status['last_build_age']})" if status["last_build_age"] else ""),
        f"  ostatni backfill: {status['last_backfill'] or '—'}"
        + (f" ({status['last_backfill_age']})" if status["last_backfill_age"] else ""),
        f"  ostatni enrich:   {status['last_enrich'] or '—'}"
        + (f" ({status['last_enrich_age']})" if status["last_enrich_age"] else "")
        + ("  ← W TRAKCIE" if status.get("enrich_running") else ""),
    ]
    steps = status.get("steps") or []
    if steps:
        lines.append("")
        lines.append("Do odświeżenia (nic nie działa samo):")
        for step in steps:
            lines.append(f"  - {step['label']}: {step['command']}")
            if step.get("why"):
                lines.append(f"      {step['why']}")
        lines.append("")
        has_enrich = any(s.get("id") == "enrich" for s in steps)
        if has_enrich:
            lines.append("Szybko: ./awesome refresh  |  Pełne (z enrich): ./awesome refresh --full")
        else:
            lines.append("Wszystko naraz: ./awesome refresh")
    else:
        lines.append("")
        lines.append("Wszystko aktualne. Nic nie trzeba odświeżać.")
    return lines


SNAPSHOT_KEYS = [
    "tools", "mentions", "lists", "lists_total", "readmes",
    "alive", "dead", "nongithub_links", "db_size_mb",
    "repos_to_fetch", "github_without_own_meta", "lists_without_meta",
]


def snapshot_path(data_dir=None):
    return store.db_path(data_dir).parent / "status_snapshot.json"


def history_path(data_dir=None):
    return store.db_path(data_dir).parent / "status_history.jsonl"


def save_snapshot(status, data_dir=None):
    """Zapisz bieżący snapshot (ostatni + historia JSONL)."""
    if not status.get("ready"):
        return None
    snap = {k: status.get(k) for k in SNAPSHOT_KEYS}
    snap["saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    snap["last_build"] = status.get("last_build", "")
    snap["last_backfill"] = status.get("last_backfill", "")
    snap["last_enrich"] = status.get("last_enrich", "")
    path = snapshot_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        with history_path(data_dir).open("a", encoding="utf-8") as f:
            f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return path


def load_snapshot(data_dir=None):
    path = snapshot_path(data_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def diff_snapshot(current, previous):
    """Porównaj dwa snapshoty. Zwraca listę zmian tekstowych."""
    if not current.get("ready") or not previous:
        return []
    lines = []
    prev_at = previous.get("saved_at", "?")
    lines.append(f"Porównanie z poprzednim snapshotem: {prev_at}")
    labels = {
        "tools": "narzędzia",
        "mentions": "wzmianki",
        "lists": "listy w bazie",
        "lists_total": "listy razem",
        "readmes": "README lokalnie",
        "alive": "linki żywe",
        "dead": "linki martwe",
        "nongithub_links": "poza GitHubem",
        "db_size_mb": "baza MB",
        "repos_to_fetch": "repo do enrich",
        "github_without_own_meta": "narzędzia GH bez meta",
        "lists_without_meta": "listy bez meta",
    }
    for key in SNAPSHOT_KEYS:
        old = previous.get(key)
        new = current.get(key)
        if old is None or new is None:
            continue
        if old == new:
            continue
        delta = new - old
        if isinstance(delta, float):
            lines.append(f"  {labels.get(key, key)}: {old:.1f} -> {new:.1f} ({delta:+.1f})")
        else:
            sign = "+" if delta > 0 else ""
            lines.append(f"  {labels.get(key, key)}: {old:,} -> {new:,} ({sign}{delta:,})")
    if len(lines) == 1:
        lines.append("  (brak zmian w kluczowych liczbach)")
    return lines
