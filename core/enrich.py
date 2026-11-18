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
            " primaryLanguage { name } url isFork"
            " repositoryTopics(first: 20) { nodes { topic { name } } } }"
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

    Priorytet (domyślnie): najpierw repozytoria najczęściej cytowane na różnych
    listach/wzmiankach — jawnie COALESCE(tools.lists_count, 0) DESC, z fallbackiem
    score DESC, lists_count DESC, tool_stars DESC, url_norm ASC. Dzięki temu
    limitowany enrich (np. 1000) wzbogaca najważniejsze narzędzia.
    """
    known = {
        row["full_name"].lower()
        for row in conn.execute("SELECT full_name FROM tool_repo_meta")
    }
    if priority:
        # kanoniczne źródło liczby unikalnych list/wzmianek w tej bazie: tools.lists_count
        order = (
            "COALESCE(t.lists_count, 0) DESC, "
            "COALESCE(t.score, 0) DESC, "
            "COALESCE(t.lists_count, 0) DESC, "
            "COALESCE(t.tool_stars, 0) DESC, "
            "t.url_norm ASC"
        )
    else:
        order = "t.url_norm ASC"
    out = []
    seen = set()
    try:
        rows = conn.execute(
            "SELECT t.url_norm, COALESCE(t.lists_count,0) AS lc, COALESCE(t.score,0) AS sc"
            " FROM tools t WHERE t.url_norm LIKE 'github.com/%'"
            f" ORDER BY {order}"
        )
    except Exception:
        # odporność na brak kolumn/niestandardowy schemat
        rows = conn.execute(
            "SELECT DISTINCT url_norm FROM tools WHERE url_norm LIKE 'github.com/%'"
            " ORDER BY url_norm"
        )
    for row in rows:
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


def save(conn, records, commit=True):
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
    if commit:
        conn.commit()
    return len(rows)


def enrich(limit=None, verbose=True, batch_size=BATCH_SIZE, pause=PAUSE,
           priority=True):
    """Metadane repozytoriów narzędzi. Wymaga zalogowania do GitHuba.

    Priorytet kolejki (priority=True): najpierw repozytoria najczęściej
    cytowane/występujące na listach (kanonicznie tools.lists_count DESC),
    z fallbackiem score/tool_stars/url_norm — limitowany enrich trafia w
    najważniejsze narzędzia. Zapis w większych transakcjach; Ctrl+C kończy
    bieżącą paczkę, robi bezpieczny commit i zamyka się czysto.
    """
    import shutil
    import signal

    if not shutil.which("gh"):
        if verbose:
            print("Pomijam enrich: pobieranie metadanych wymaga GitHub CLI (gh).")
            print("  Bez tego ranking nadal działa — opiera się na zgodzie kuratorów.")
            print("  Żeby dociągnąć prawdziwe gwiazdki: zainstaluj GitHub CLI, "
                  "potem gh auth login")
        return 0
    if not github_token():
        if verbose:
            print("Pomijam enrich: GitHub wymaga logowania dla GraphQL.")
            print("  Bez tego ranking nadal działa — opiera się na zgodzie kuratorów.")
            print("  Żeby dociągnąć prawdziwe gwiazdki: gh auth login")
        return 0
    token = github_token()
    if not token and verbose:
        print("Uwaga: brak tokena — batch po 1 (wolno). Zaloguj gh CLI albo ustaw GITHUB_TOKEN.")
    conn = store.connect()
    pairs = missing_repos(conn, limit=limit, priority=priority)
    if not pairs:
        print("Wszystkie repozytoria narzędzi mają już metadane.")
        conn.close()
        return 0

    if verbose:
        print(f"[*] Kolejka enrich: priorytet={'mentions/lists_count DESC' if priority else 'alfabetycznie'}")

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

    store.set_meta(conn, "enrich_started_at", time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), commit=False)
    store.set_meta(conn, "enrich_limit", limit or 0, commit=False)
    conn.commit()
    size = batch_size if token else 1
    total = len(pairs)
    done = 0
    found = 0
    dead = 0
    failures = 0
    started = time.perf_counter()
    commit_every_batches = max(1, (500 // max(1, size)))  # ~co 500 repo
    batches_since_commit = 0
    try:
        for i in range(0, total, size):
            if stop_requested["v"]:
                break
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
                if records:
                    found += save(conn, records, commit=False)
                missing_in_batch = {}
                for pair in chunk:
                    key = f"{pair[0]}/{pair[1]}".lower()
                    if key not in records:
                        missing_in_batch[key] = dead_marker(*pair)
                        dead += 1
                if missing_in_batch:
                    save(conn, missing_in_batch, commit=False)
                batches_since_commit += 1
                if batches_since_commit >= commit_every_batches or (i + size) >= total or stop_requested["v"]:
                    conn.commit()
                    batches_since_commit = 0
            except sqlite3.Error as exc:
                try:
                    conn.rollback()
                except Exception:
                    pass
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
            if not stop_requested["v"]:
                time.sleep(pause)
    finally:
        try:
            if batches_since_commit:
                conn.commit()
            store.set_meta(conn, "last_enrich", time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), commit=False)
            store.set_meta(conn, "last_enrich_found", found, commit=False)
            store.set_meta(conn, "last_enrich_dead", dead, commit=False)
            github_left = conn.execute(
                "SELECT COUNT(*) FROM tools WHERE tool_stars = 0 AND url_norm LIKE 'github.com/%'"
            ).fetchone()[0]
            store.set_meta(conn, "github_tools_without_own_meta", github_left, commit=False)
            store.set_meta(conn, "repos_to_fetch", len(missing_repos(conn)), commit=False)
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
    if stop_requested["v"]:
        print(f"Przerwano bezpiecznie. Zapisano metadane dla {found} repozytoriów narzędzi "
              f"({dead} nie istnieje).")
    else:
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
