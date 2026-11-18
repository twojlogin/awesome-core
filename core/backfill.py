#!/usr/bin/env python3
"""core/backfill.py — dociąga brakujące metadane awesome list z GitHub API.

Powstało, bo 774 z 950 wpisów w index.json nie miało `stars` ani `language`
(web dodawał same `owner`/`name`), więc 76% narzędzi miało `source_stars = 0`
i sortowanie po gwiazdkach nie miało o czym sortować.
"""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
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
    " { nameWithOwner stargazerCount forkCount isArchived isFork pushedAt createdAt"
    " primaryLanguage { name } url description parent { nameWithOwner } }"
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
    parent = data.get("parent") or {}
    return {
        "parent": (parent.get("nameWithOwner") or "") if isinstance(parent, dict) else "",
        "stars": int(data.get("stargazerCount") or data.get("stargazers_count") or 0),
        "forks": int(data.get("forkCount") or data.get("forks_count") or 0),
        "watchers": int(data.get("watchers_count") or 0),
        "language": language,
        "topics": topics,
        "description": data.get("description") or "",
        "archived": 1 if (data.get("isArchived") or data.get("archived")) else 0,
        "is_fork": 1 if (data.get("isFork") or data.get("fork")) else 0,
        "created_at": data.get("createdAt") or data.get("created_at") or "",
        "pushed_at": data.get("pushedAt") or data.get("pushed_at") or "",
        "license": {"spdx_id": spdx} if spdx else {},
        "html_url": data.get("url") or data.get("html_url") or "",
    }


def missing(conn, force=False, only_missing=False):
    """Listy do backfill.

    force: wszystkie. Domyślnie: braki metadanych (stars=0 i brak language)
    lub inne niekompletne pola istotne dla quality/trust/freshness.
    only_missing=True: tryb lekki (jak domyślny) — alias dla czytelności
    w quick refresh.
    """
    if force:
        sql = "SELECT full_name FROM repos ORDER BY full_name"
    else:
        # brak podstawowych metadanych potrzebnych do quality/trust/freshness
        sql = (
            "SELECT full_name FROM repos WHERE "
            "(stars = 0 OR language = '' OR language IS NULL OR "
            " pushed_at = '' OR pushed_at IS NULL)"
            " ORDER BY full_name"
        )
    return [r["full_name"] for r in conn.execute(sql)]


def _retry_days_backfill(status, fail_count):
    if status == "error":
        return 1 if fail_count <= 1 else 3
    return 30 if fail_count >= 2 else 7


def backfill(limit=None, verbose=True, force=False, only_missing=False):
    """Uzupełnia metadane list. W trybie lekkim (only_missing/domyślnie)
    bierze tylko braki i respektuje retry_after_at; pełny pod force/limit.
    Zapis w większych transakcjach; Ctrl+C kończy bieżącą paczkę bezpiecznie.
    """
    token = github_token()
    conn = store.connect()
    full_names = missing(conn, force=force, only_missing=only_missing)
    if limit:
        full_names = full_names[:limit]

    # pomiń listy w oknie retry_after (chyba że force)
    deferred = 0
    if not force:
        filtered = []
        for fn in full_names:
            try:
                if store.list_fetch_deferred(conn, fn, kind="backfill"):
                    deferred += 1
                    continue
            except Exception:
                pass
            filtered.append(fn)
        full_names = filtered

    if not full_names:
        msg = "Wszystkie listy mają metadane."
        if deferred:
            msg += f" Odroczonych (retry_after): {deferred}."
        print(msg)
        conn.close()
        return 0

    pairs = []
    for full_name in full_names:
        if "/" not in full_name:
            continue
        owner, name = full_name.split("/", 1)
        pairs.append((owner, name))

    stop_requested = {"v": False}

    def _on_sigint(signum, frame):
        stop_requested["v"] = True
        if verbose:
            print("\n[!] Przerwanie: kończę bieżącą paczkę i zapisuję postęp...", flush=True)

    prev_handler = None
    try:
        prev_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, _on_sigint)
    except Exception:
        prev_handler = None

    size = BATCH_SIZE if token else 1
    updated = 0
    total = len(pairs)
    started = time.perf_counter()
    commit_every_batches = max(1, (400 // max(1, size)))
    batches_since_commit = 0
    try:
        for i in range(0, total, size):
            if stop_requested["v"]:
                break
            chunk = pairs[i:i + size]
            ok, records = fetch(chunk, token)
            if not ok:
                # błąd API/rate limit: nie oznaczaj wszystkich jako martwe, po prostu przerwij
                print("Błąd API/rate limit — zatrzymuję, postęp zapisany.")
                break
            chunk_keys = {f"{o}/{n}".lower() for o, n in chunk}
            found_keys = set()
            for key, data in records.items():
                full_name = data.get("nameWithOwner") or key
                norm = full_name.lower()
                found_keys.add(norm)
                found_keys.add(key.lower())
                if store.upsert_repo(conn, full_name, _to_meta(data)):
                    updated += 1
                try:
                    store.clear_list_fetch_ok(conn, full_name, kind="backfill", commit=False)
                except Exception:
                    pass
            # brak w odpowiedzi API (np. usunięte) — ustaw retry_after, nie próbuj w kółko
            for o, n in chunk:
                fn = f"{o}/{n}"
                if fn.lower() not in found_keys:
                    try:
                        prev = conn.execute(
                            "SELECT fail_count FROM list_fetch_state WHERE full_name=?",
                            (fn,),
                        ).fetchone()
                        prev_fail = int(prev["fail_count"] or 0) if prev else 0
                        store.bump_list_fetch_failure(
                            conn, fn, kind="backfill", status="missing",
                            reason="not_in_api_response",
                            retry_days=_retry_days_backfill("missing", prev_fail + 1),
                            commit=False,
                        )
                    except Exception:
                        pass
            batches_since_commit += 1
            if batches_since_commit >= commit_every_batches or (i + size) >= total or stop_requested["v"]:
                conn.commit()
                batches_since_commit = 0
            done = min(i + size, total)
            if verbose and (done % 200 < size or done == total):
                rate = done / max(0.001, time.perf_counter() - started)
                print(f"  {done}/{total} list, uzupełniono {updated} "
                      f"({rate:.0f}/s, ETA {(total - done) / max(0.001, rate) / 60:.1f} min)",
                      flush=True)
            if not stop_requested["v"]:
                time.sleep(PAUSE)
    finally:
        try:
            if batches_since_commit:
                conn.commit()
            still = len(missing(conn))
            store.set_meta(conn, "last_backfill", time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), commit=False)
            store.set_meta(conn, "last_backfill_updated", updated, commit=False)
            store.set_meta(conn, "lists_without_meta", still, commit=False)
            conn.commit()
        except Exception:
            try:
                conn.commit()
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass
        if prev_handler is not None:
            try:
                signal.signal(signal.SIGINT, prev_handler)
            except Exception:
                pass

    msg = f"Uzupełniono {updated} list. Bez metadanych zostało: {still}."
    if deferred:
        msg += f" Odroczonych (retry_after): {deferred}."
    if stop_requested["v"]:
        msg = "Przerwano bezpiecznie. " + msg
    print(msg)
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
    ap.add_argument("--only-missing", action="store_true",
                    help="tylko listy z brakującymi metadanymi (lekki tryb)")
    ap.add_argument("--clean-only", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    clean_index(verbose=not args.quiet)
    if not args.clean_only:
        backfill(limit=args.limit, verbose=not args.quiet, force=args.force,
                 only_missing=args.only_missing)
