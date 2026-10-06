#!/usr/bin/env python3
"""core/enrich.py — dociąga metadane repozytoriów *narzędzi* z GitHub API.

To jest źródło prawdziwego języka, gwiazdek i informacji o martwych linkach
dla narzędzi wskazujących na GitHub. Wynik trafia do tabeli `tool_repo_meta`,
więc build bazy działa nawet bez internetu — po prostu nie ma wtedy enrichment.
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import store  # noqa: E402


BASE_DIR = Path(__file__).parent.parent


GRAPHQL_URL = "https://api.github.com/graphql"


BATCH_SIZE = 50


REST_FALLBACK_BATCH = 1


PAUSE = 0.12


QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    nameWithOwner stargazerCount forkCount isArchived pushedAt createdAt
    primaryLanguage { name }
    url
  }
}
"""


BATCHED_QUERY = """
query {
%s
}
"""


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


def _run_gh(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=45)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def fetch_batch(pairs, token):
    """Jedno zapytanie GraphQL na wiele repozytoriów (aliasy).

    Zwraca (ok, records). ok=False oznacza błąd transportu/rate limit —
    wtedy nie wolno oznaczać repozytoriów jako martwe.
    """
    if not pairs:
        return True, {}
    if len(pairs) == 1 and not token:
        return True, _fetch_rest(pairs[0])
    parts = []
    for i, (owner, name) in enumerate(pairs):
        parts.append(
            f"  r{i}: repository(owner: \"{owner}\", name: \"{name}\") "
            "{ nameWithOwner stargazerCount forkCount isArchived pushedAt createdAt"
            " primaryLanguage { name } url repositoryTopics(first: 20)"
            " { nodes { topic { name } } } }"
        )
    payload = {"query": BATCHED_QUERY % "\n".join(parts)}
    args = [
        "gh", "api", "graphql", "--method", "POST",
        "-H", "Accept: application/vnd.github+json",
    ]
    if token:
        args.extend(["-H", f"Authorization: bearer {token}"])
    args.extend(["--input", "-"])
    raw = _run_gh_with_input(args, json.dumps(payload))
    if raw is None or not raw.strip():
        return False, {}
    try:
        data = json.loads(raw)
    except ValueError:
        return False, {}
    if data.get("errors") and not data.get("data"):
        return False, {}
    out = {}
    for value in (data.get("data") or {}).values():
        if isinstance(value, dict) and value.get("nameWithOwner"):
            out[value["nameWithOwner"].lower()] = _pack(value)
    return True, out


def dead_marker(owner, name):
    return {
        f"{owner}/{name}".lower(): {
            "full_name": f"{owner}/{name}",
            "url": "",
            "stars": 0,
            "forks": 0,
            "language": "",
            "archived": 0,
            "pushed_at": "",
            "created_at": "",
            "topics": "",
            "status": 1,
        }
    }


def _run_gh_with_input(args, payload):
    """Zwraca stdout nawet przy NOT_FOUND (gh ma wtedy rc=1, ale JSON jest poprawny)."""
    try:
        result = subprocess.run(
            args, input=payload, capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 and not result.stdout.strip():
        return None
    return result.stdout


def _fetch_rest(pair):
    owner, name = pair
    raw = _run_gh(["api", f"repos/{owner}/{name}"])
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if data.get("message"):
        return {}
    return {f"{owner}/{name}".lower(): _pack(data)}


def _pack(data):
    language = ""
    primary = data.get("primaryLanguage") or {}
    if isinstance(primary, dict):
        language = primary.get("name") or ""
    elif isinstance(primary, str):
        language = primary
    topics = data.get("topics")
    if isinstance(topics, list):
        topics = ";".join(topics)
    return {
        "full_name": data.get("nameWithOwner") or data.get("full_name") or "",
        "url": data.get("url") or data.get("html_url") or "",
        "stars": int(data.get("stargazerCount") or data.get("stargazers_count") or 0),
        "forks": int(data.get("forkCount") or data.get("forks_count") or 0),
        "language": language or "",
        "archived": 1 if data.get("isArchived", data.get("archived")) else 0,
        "pushed_at": data.get("pushedAt") or data.get("pushed_at") or "",
        "created_at": data.get("createdAt") or data.get("created_at") or "",
        "topics": topics or "",
        "status": 0,
    }


GH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def valid_pair(owner, name):
    return bool(
        owner
        and name
        and GH_SEGMENT_RE.match(owner)
        and GH_SEGMENT_RE.match(name)
        and not owner.startswith((".", "-"))
        and not name.startswith((".", "-"))
        and len(owner) <= 100
        and len(name) <= 120
    )


def missing_repos(conn, limit=None, priority=True):
    """(owner, name) dla repozytoriów z tools, których nie ma w tool_repo_meta.

    Domyślnie kolejność według score — najpierw metadane narzędzi, które
    naprawdę coś znaczą (najczęściej cytowane, najwyżej ocenione).
    """
    known = {
        row["full_name"].lower()
        for row in conn.execute("SELECT full_name FROM tool_repo_meta")
    }
    order = "t.score DESC, t.lists_count DESC" if priority else "t.url_norm"
    out = []
    seen = set()
    for row in conn.execute(
        "SELECT DISTINCT url_norm FROM tools t WHERE t.url_norm LIKE 'github.com/%'"
        f" ORDER BY {order}"
    ):
        identity = row["url_norm"]
        parts = [p for p in identity[len("github.com/"):].split("/") if p]
        if len(parts) < 2:
            continue
        key = f"{parts[0]}/{parts[1]}".lower()
        if key in known or key in seen:
            continue
        if not valid_pair(parts[0], parts[1]):
            continue
        seen.add(key)
        out.append((parts[0], parts[1]))
        if limit and len(out) >= limit:
            break
    return out


def save(conn, records):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows = []
    for full_name, meta in records.items():
        rows.append(
            (
                meta.get("full_name") or full_name,
                meta.get("url", ""),
                meta.get("stars", 0),
                meta.get("forks", 0),
                meta.get("language", ""),
                meta.get("archived", 0),
                meta.get("pushed_at", ""),
                meta.get("created_at", ""),
                meta.get("topics", ""),
                meta.get("status", 0),
                now,
            )
        )
    conn.executemany(
        "INSERT OR REPLACE INTO tool_repo_meta (full_name, url, stars, forks, language,"
        " archived, pushed_at, created_at, topics, status, fetched_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)


def enrich(limit=None, verbose=True, batch_size=BATCH_SIZE, pause=PAUSE,
           priority=True):
    token = github_token()
    if not token and verbose:
        print("Uwaga: brak tokena — batch po 1 (wolno). Zaloguj gh CLI albo ustaw GITHUB_TOKEN.")
    conn = store.connect()
    pairs = missing_repos(conn, limit=limit, priority=priority)
    if not pairs:
        print("Wszystkie repozytoria narzędzi mają już metadane.")
        conn.close()
        return 0

    size = batch_size if token else 1
    total = len(pairs)
    done = 0
    found = 0
    dead = 0
    failures = 0
    started = time.perf_counter()
    for i in range(0, total, size):
        chunk = pairs[i:i + size]
        ok, records = fetch_batch(chunk, token)
        if not ok:
            failures += 1
            if failures <= 3:
                print(f"  Błąd API (próba {failures}/3) — pauza 20s i próbuję dalej.")
                time.sleep(20)
                continue
            print("Błąd API 3× z rzędu — zatrzymuję (postęp zapisany).")
            break
        failures = 0
        try:
            found += save(conn, records)
            for pair in chunk:
                if f"{pair[0]}/{pair[1]}".lower() not in records:
                    save(conn, dead_marker(*pair))
                    dead += 1
        except sqlite3.Error as exc:
            print(f"Baza zablokowana ({exc.__class__.__name__}) — ponawiam za 10s.")
            time.sleep(10)
            try:
                conn.close()
            except sqlite3.Error:
                pass
            conn = store.connect()
            continue
        done += len(chunk)
        if verbose and (done % 500 < size or done == total):
            rate = done / max(0.001, time.perf_counter() - started)
            eta = (total - done) / max(0.001, rate)
            print(f"  {done}/{total} repo (żywych {found}, martwych {dead}) "
                  f"{rate:.0f}/s, ETA {eta / 60:.1f} min", flush=True)
        time.sleep(pause)

    store.set_meta(conn, "last_enrich", time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()))
    store.set_meta(conn, "last_enrich_found", found)
    store.set_meta(conn, "last_enrich_dead", dead)
    store.set_meta(conn, "tools_without_own_meta",
                   conn.execute("SELECT COUNT(*) FROM tools WHERE tool_stars = 0").fetchone()[0])
    conn.close()
    print(f"Zapisano metadane dla {found} repozytoriów narzędzi "
          f"({dead} nie istnieje).")
    return found


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Enrich tool repos from GitHub")
    ap.add_argument("--limit", type=int, help="ile repozytoriów (domyślnie wszystkie brakujące)")
    ap.add_argument("--alphabetical", action="store_true", help="pomijaj kolejność score")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    enrich(limit=args.limit, verbose=not args.quiet,
           priority=not args.alphabetical)
