#!/usr/bin/env python3
"""core/backfill.py — dociąga brakujące metadane awesome list z GitHub API.

Powstało, bo 774 z 950 wpisów w index.json nie miało `stars` ani `language`
(web dodawał same `owner`/`name`), więc 76% narzędzi miało `source_stars = 0`
i sortowanie po gwiazdkach nie miało o czym sortować.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import store  # noqa: E402


BASE_DIR = Path(__file__).parent.parent


BATCH_SIZE = 40


PAUSE = 0.2


QUERY_TMPL = """
query {
%s
}
"""


FIELD_TMPL = (
    '  r%d: repository(owner: "%s", name: "%s")'
    " { nameWithOwner stargazerCount forkCount isArchived pushedAt createdAt"
    " primaryLanguage { name } url description }"
)


def github_token():
    env = os.environ.get("GITHUB_TOKEN")
    if env:
        return env.strip()
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def _gh(args, payload=None):
    try:
        result = subprocess.run(
            args, input=payload, capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 and not result.stdout.strip():
        return None
    return result.stdout or None


def fetch(pairs, token):
    if not pairs:
        return True, {}
    parts = [
        FIELD_TMPL % (i, owner, name)
        for i, (owner, name) in enumerate(pairs)
    ]
    args = [
        "gh", "api", "graphql", "--method", "POST",
        "-H", "Accept: application/vnd.github+json",
    ]
    if token:
        args.extend(["-H", f"Authorization: bearer {token}"])
    args.extend(["--input", "-"])
    raw = _gh(args, json.dumps({"query": QUERY_TMPL % "\n".join(parts)}))
    if raw is None:
        if token:
            return False, {}
        return _fetch_rest(pairs)
    try:
        data = json.loads(raw)
    except ValueError:
        return False, {}
    if data.get("errors") and not data.get("data"):
        return False, {}
    out = {}
    for value in (data.get("data") or {}).values():
        if isinstance(value, dict) and value.get("nameWithOwner"):
            out[value["nameWithOwner"].lower()] = value
    return True, out


def _fetch_rest(pairs):
    out = {}
    for owner, name in pairs:
        raw = _gh(["api", f"repos/{owner}/{name}"])
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        if data.get("full_name"):
            out[data["full_name"].lower()] = data
    return True, out


def _to_meta(data):
    language = ""
    primary = data.get("primaryLanguage") or {}
    if isinstance(primary, dict):
        language = primary.get("name") or ""
    elif isinstance(primary, str):
        language = primary
    license_obj = data.get("license") or {}
    spdx = license_obj.get("spdx_id") if isinstance(license_obj, dict) else ""
    topics = data.get("topics") or []
    return {
        "stars": int(data.get("stargazerCount") or data.get("stargazers_count") or 0),
        "forks": int(data.get("forkCount") or data.get("forks_count") or 0),
        "watchers": int(data.get("watchers_count") or 0),
        "language": language,
        "topics": topics,
        "description": data.get("description") or "",
        "archived": 1 if (data.get("isArchived") or data.get("archived")) else 0,
        "created_at": data.get("createdAt") or data.get("created_at") or "",
        "pushed_at": data.get("pushedAt") or data.get("pushed_at") or "",
        "license": {"spdx_id": spdx} if spdx else {},
        "html_url": data.get("url") or data.get("html_url") or "",
    }


def missing(conn, force=False):
    if force:
        return [
            r["full_name"] for r in conn.execute(
                "SELECT full_name FROM repos ORDER BY full_name"
            )
        ]
    return [
        r["full_name"]
        for r in conn.execute(
            "SELECT full_name FROM repos WHERE stars = 0 AND language = ''"
            " ORDER BY full_name"
        )
    ]


def backfill(limit=None, verbose=True, force=False):
    token = github_token()
    conn = store.connect()
    full_names = missing(conn, force=force)
    if limit:
        full_names = full_names[:limit]
    if not full_names:
        print("Wszystkie listy mają metadane.")
        conn.close()
        return 0

    pairs = []
    for full_name in full_names:
        if "/" not in full_name:
            continue
        owner, name = full_name.split("/", 1)
        pairs.append((owner, name))

    size = BATCH_SIZE if token else 1
    updated = 0
    total = len(pairs)
    started = time.perf_counter()
    for i in range(0, total, size):
        chunk = pairs[i:i + size]
        ok, records = fetch(chunk, token)
        if not ok:
            print("Błąd API/rate limit — zatrzymuję, postęp zapisany.")
            break
        for key, data in records.items():
            full_name = data.get("nameWithOwner") or key
            if store.upsert_repo(conn, full_name, _to_meta(data)):
                updated += 1
        done = min(i + size, total)
        conn.commit()
        if verbose and (done % 200 < size or done == total):
            rate = done / max(0.001, time.perf_counter() - started)
            print(f"  {done}/{total} list, uzupełniono {updated} "
                  f"({rate:.0f}/s, ETA {(total - done) / max(0.001, rate) / 60:.1f} min)",
                  flush=True)
        time.sleep(PAUSE)

    still = len(missing(conn))
    store.set_meta(conn, "last_backfill", time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()))
    store.set_meta(conn, "last_backfill_updated", updated)
    store.set_meta(conn, "lists_without_meta", still)
    print(f"Uzupełniono {updated} list. Bez metadanych zostało: {still}.")
    conn.close()
    return updated


def clean_index(verbose=True):
    """Porządkuje offline-db/data/index.json (naprawia zapis po błędzie TSV)."""
    index_file = BASE_DIR / "offline-db" / "data" / "index.json"
    if not index_file.exists():
        return 0
    data = json.loads(index_file.read_text(encoding="utf-8"))
    fixed = 0
    for full_name, entry in list(data.items()):
        if not isinstance(entry, dict) or "/" not in full_name:
            data.pop(full_name, None)
            fixed += 1
            continue
        owner, name = full_name.split("/", 1)
        _, meta = store.sanitize_index_entry({**entry, "full_name": full_name})
        clean = {
            "owner": owner,
            "name": name,
            "readme_downloaded": bool(entry.get("readme_downloaded", True)),
        }
        for field in ("stars", "forks", "watchers", "language", "topics",
                      "description", "created_at", "pushed_at", "archived"):
            if field in meta:
                clean[field] = meta[field]
        spdx = (meta.get("license") or {}).get("spdx_id")
        if spdx:
            clean["license"] = spdx
        if clean != entry:
            data[full_name] = clean
            fixed += 1
    if fixed:
        index_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    if verbose:
        print(f"index.json: poprawiono {fixed} wpisów.")
    return fixed


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Backfill awesome list metadata")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true", help="odśwież wszystkie listy")
    ap.add_argument("--clean-only", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    clean_index(verbose=not args.quiet)
    if not args.clean_only:
        backfill(limit=args.limit, verbose=not args.quiet, force=args.force)
