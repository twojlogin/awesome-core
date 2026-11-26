#!/usr/bin/env python3
"""core/fetcher.py — pobieranie awesome list. Czysty Python, bez shella.

Powstał, bo `download.sh` wymagał basha + jq + curl. Na Windowsie (PowerShell)
to ślepa uliczka: skrypt się nie uruchamia, a użytkownik nie wie dlaczego.
Teraz ten sam proces działa wszędzie, gdzie działa Python, a `download.sh`
został cienką nakładką wywołującą ten plik — jedna implementacja, dwa wejścia.

Korzysta z `gh` (GitHub CLI) jako klienta API, bo uwierzytelnianie jest już
gotowe po `gh auth login` i nie trzeba wymyślać własnego zarządzania tokenem.
Limity są takie same, jakich pilnuje GitHub: 1000 wyników na zapytanie
stąd `--wide` łączy kilka zapytań (union).
"""

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core import api, store
DATA_DIR = BASE_DIR / "offline-db" / "data"
README_DIR = DATA_DIR / "readmes"
INDEX_FILE = DATA_DIR / "index.json"

QUERIES_WIDE = [
    "topic:awesome-list",
    "topic:awesome-list stars:>=200",
    "topic:awesome",
    "topic:curated-list",
    "topic:awesome-resources",
    "awesome in:name topic:list",
    "awesome in:name stars:>=500",
]

PER_PAGE = 100
MAX_PAGES = 10          # GitHub Search oddaje maks. 1000 wyników na zapytanie
PAUSE = 0.3             # uprzejmość dla raw.githubusercontent


def fetch_readme_status(full_name, token):
    """Jak fetch_readme, ale zwraca (content, status)."""
    saw_404 = False
    for branch in ("main", "master"):
        url = f"https://raw.githubusercontent.com/{full_name}/{branch}/README.md"
        request = urllib.request.Request(url, headers={"User-Agent": "awesome-core"})
        if token:
            request.add_header("Authorization", f"bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
            if data.strip():
                return data.decode("utf-8", "replace"), "ok"
            saw_404 = True
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                saw_404 = True
                continue
            return None, "error"
        except (urllib.error.URLError, TimeoutError, OSError):
            return None, "error"
    return None, "missing" if saw_404 else "error"


def fetch_readme(full_name, token):
    """README z gałęzi main, a jak nie ma to master. Zwraca treść albo None.

    Kompatybilne z testami/patchowaniem (można podmienić tę funkcję).
    """
    content, _status = fetch_readme_status(full_name, token)
    return content


_DEFAULT_FETCH_README = fetch_readme


def merge_index(items, downloaded, token):
    """Metadane tylko dla repo, których README naprawdę mamy lokalnie.

    Bez tegowarzyszącego warunku index.json rósłby o wpisy dla list, których
    nie ma na dysku, a build zacząłby liczyć narzędzia z próżni.
    """
    index = {}
    if INDEX_FILE.exists():
        try:
            index = json.loads(INDEX_FILE.read_text(encoding="utf-8")) or {}
        except ValueError:
            index = {}
    known = {entry["html_url"] for entry in index.values() if entry.get("html_url")}

    for item in items:
        full = item.get("full_name")
        if not full or (full not in downloaded and item.get("html_url") not in known):
            continue
        entry = index.get(full) or {}
        topics = item.get("topics")
        entry.update({
            "owner": full.split("/")[0],
            "name": full.split("/")[1],
            "html_url": item.get("html_url", ""),
            "stars": item.get("stargazers_count", entry.get("stars", 0)) or 0,
            "forks": item.get("forks_count", entry.get("forks", 0)) or 0,
            "language": item.get("language") or entry.get("language", ""),
            "topics": (";".join(topics) if isinstance(topics, list)
                       else (topics or entry.get("topics", ""))),
            "created_at": item.get("created_at") or entry.get("created_at", ""),
            "pushed_at": item.get("pushed_at") or entry.get("pushed_at", ""),
            "archived": bool(item.get("archived", entry.get("archived", False))),
            "readme_downloaded": True,
        })
        lic = item.get("license")
        spdx = lic.get("spdx_id") if isinstance(lic, dict) else ""
        if spdx and spdx != "NOASSERTION":
            entry["license"] = spdx
        index[full] = entry
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False),
                          encoding="utf-8")


def _retry_days(status, fail_count):
    if status == "error":
        return 1 if fail_count <= 1 else 3
    # missing/404: 7 dni, potem 30 dni dla trwałych braków
    return 30 if fail_count >= 2 else 7


def download(topic="awesome-list", wide=True, refresh=False, sort="stars",
             start_page=1, verbose=True, limit=None, data_dir=None, return_deferred=False):
    """Główna pętla. Zwraca (status, nowe, pominięte, bez_readme) dla kompatybilności,
    a z return_deferred=True: (status, nowe, pominięte, bez_readme, odroczone)."""
    token = api.token()
    if verbose:
        print(f"[*] GitHub: {api.describe()}")
        if api.search_pause():
            print("[*] Bez logowania czekam między stronami, bo GitHub "
                  "dopuszcza 10 zapytań na minutę. Przyspieszysz: "
                  f"{api.speedup_hint()}")
    README_DIR.mkdir(parents=True, exist_ok=True)
    conn = None
    try:
        if data_dir is not None:
            conn = store.connect(data_dir)
        elif store.db_ready(store.DATA_DIR):
            conn = store.connect(store.DATA_DIR)
    except Exception:
        conn = None

    queries = [f"topic:{topic}"] + (QUERIES_WIDE[1:] if wide else [])
    new = skipped = missing = deferred = 0
    downloaded = set()
    stop = False
    # wykrywanie farm SEO w trakcie jednego przebiegu search
    owner_seen = {}
    owner_farm = set()

    try:
        for query in queries:
            seen_first = None
            for page in range(start_page, MAX_PAGES + 1):
                if verbose:
                    print(f"\n[*] {query} — strona {page}", flush=True)
                payload = api.search_repositories(query, page=page, per_page=PER_PAGE,
                                                  sort=sort)
                if payload is None:
                    return 1, new, skipped, missing, deferred
                items = payload.get("items") or []
                if not items:
                    break
                first = items[0].get("full_name")
                if first == seen_first:
                    if verbose:
                        print(f"[*] Paginacja zapętliła się na {first} "
                              f"(limit 1000). Kończę to zapytanie.")
                    break
                seen_first = first
                for item in items:
                    if limit and (new + skipped + deferred) >= limit:
                        stop = True
                        break
                    full = item.get("full_name")
                    if not full or "/" not in full:
                        continue
                    owner, name = full.split("/", 1)
                    owner_l = owner.lower()
                    stars_item = int(item.get("stargazers_count") or 0)
                    info = owner_seen.setdefault(owner_l, {"total": 0, "low": 0, "samples": []})
                    info["total"] += 1
                    if stars_item < 30:
                        info["low"] += 1
                    if len(info["samples"]) < 5:
                        info["samples"].append(full)
                    if owner_l not in owner_farm and info["low"] >= 10 and info["total"] >= 10:
                        owner_farm.add(owner_l)
                        if conn is not None:
                            try:
                                store.upsert_suspected_farm(
                                    conn, owner_l,
                                    repo_count=info["total"],
                                    median_stars=stars_item,
                                    sample_repos=";".join(info["samples"]),
                                    status="active",
                                    commit=False,
                                )
                                conn.commit()
                            except Exception:
                                pass
                        if verbose:
                            print(f"  [!] wykryto farmę SEO ownera {owner_l} (>=10 repo <30★) — pomijam dalsze", flush=True)
                    if owner_l in owner_farm:
                        deferred += 1
                        continue
                    target = README_DIR / f"{owner}__{name}.md"
                    if target.exists() and not refresh:
                        skipped += 1
                        downloaded.add(full)
                        if conn is not None:
                            try:
                                store.clear_list_fetch_ok(conn, full, kind="list", commit=False)
                            except Exception:
                                pass
                        continue
                    if conn is not None:
                        try:
                            if store.list_fetch_deferred(conn, full, kind="list"):
                                deferred += 1
                                continue
                        except Exception:
                            pass
                    if fetch_readme is _DEFAULT_FETCH_README:
                        content, status_kind = fetch_readme_status(full, token)
                    else:
                        # compat: podmieniona funkcja (testy) zwraca tylko content
                        content = fetch_readme(full, token)
                        status_kind = "ok" if content else "missing"
                    if not content:
                        missing += 1
                        if conn is not None:
                            try:
                                prev = conn.execute(
                                    "SELECT fail_count FROM list_fetch_state WHERE full_name=?",
                                    (full,),
                                ).fetchone()
                                prev_fail = int(prev["fail_count"] or 0) if prev else 0
                                store.bump_list_fetch_failure(
                                    conn, full, kind="list", status=status_kind,
                                    reason=status_kind, retry_days=_retry_days(status_kind, prev_fail + 1),
                                    commit=False,
                                )
                            except Exception:
                                pass
                        continue
                    target.write_text(content, encoding="utf-8")
                    downloaded.add(full)
                    new += 1
                    if conn is not None:
                        try:
                            store.clear_list_fetch_ok(conn, full, kind="list", commit=False)
                        except Exception:
                            pass
                    if verbose:
                        print(f"  + {full}", flush=True)
                    time.sleep(PAUSE)
                if conn is not None:
                    try:
                        conn.commit()
                    except Exception:
                        pass
                if len(items) < PER_PAGE or stop:
                    break
            merge_index(items, downloaded, token)
            if stop:
                break
    finally:
        if conn is not None:
            try:
                conn.commit()
                conn.close()
            except Exception:
                pass
    if return_deferred:
        return 0, new, skipped, missing, deferred
    return 0, new, skipped, missing


def main(argv=None):
    args = list(argv if argv is not None else sys.argv[1:])
    topic = os.environ.get("AWESOME_TOPIC", "awesome-list")
    wide = "--wide" in args or not args
    refresh = "--refresh" in args
    verbose = "--quiet" not in args
    limit = None
    if "--limit" in args and args.index("--limit") + 1 < len(args):
        try:
            limit = max(1, int(args[args.index("--limit") + 1]))
        except ValueError:
            limit = None
    if args and not args[0].startswith("-"):
        topic = args[0]
    result = download(
        topic=topic, wide=wide, refresh=refresh, verbose=verbose, limit=limit,
        return_deferred=True)
    status, new, skipped, missing, deferred = result
    if verbose:
        print(f"\n[*] Nowych/pobranych: {new}")
        print(f"[*] Pominiętych (już było): {skipped}")
        print(f"[*] Bez README: {missing}")
        if deferred:
            print(f"[*] Odroczonych (retry_after): {deferred}")
        print(f"[*] Pliki w: {README_DIR}")
        print("[*] Następne: ./awesome build   (a potem ./awesome backfill)")
    return status


if __name__ == "__main__":
    sys.exit(main())