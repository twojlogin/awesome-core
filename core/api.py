#!/usr/bin/env python3
"""core/api.py — jedno miejsce, w którym program rozmawia z GitHubem.

Dotąd pobieranie wymagało zainstalowanego `gh` i zalogowania. To była
ostatnia ściana wymagająca ręcznej pracy: ktoś klonuje repo i musi wiedzieć,
że ma zainstalować GitHub CLI, a potem wpisać `gh auth login`.

Teraz `gh` jest opcjonalne:
  1. gh + token  → pełne limity (5000/h, 30 zapytań search na minutę)
  2. sam token z GITHUB_TOKEN → to samo przez HTTPS
  3. bez niczego  → działa, tylko wolniej (search 10/min), więc wolniej
Wybór jest automatyczny i wypisywany przy pierwszym uruchomieniu, żeby
nikt nie zgadywał, dlaczego pobieranie się wlecza.
"""

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

API_ROOT = "https://api.github.com"
USER_AGENT = "awesome-core"
# search bez logowania: 10 zapytań na minutę. Trzymajmy się z zapasem.
ANON_SEARCH_PAUSE = 6.5
AUTH_SEARCH_PAUSE = 0.0


def gh_path():
    return shutil.which("gh")


def token():
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env and env.strip():
        return env.strip()
    if gh_path():
        try:
            done = subprocess.run([gh_path(), "auth", "token"],
                                  capture_output=True, text=True, timeout=5)
            if done.returncode == 0 and done.stdout.strip():
                return done.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return ""


def mode():
    """'gh+token' | 'token' | 'gh' | 'anonymous' — dla uczciwych komunikatów."""
    has_gh = bool(gh_path())
    has_token = bool(token())
    if has_gh and has_token:
        return "gh+token"
    if has_token:
        return "token"
    if has_gh:
        return "gh"
    return "anonymous"


def describe():
    """Co program powie człowiekowi na starcie."""
    how = {
        "gh+token": "GitHub CLI + token (pełne limity)",
        "token": "token z GITHUB_TOKEN (pełne limity)",
        "gh": "GitHub CLI, ale bez logowania (wolniej, search 10/min)",
        "anonymous": "bez logowania (najwolniej, search 10/min, rdzeń działa)",
    }[mode()]
    if mode() in {"gh", "anonymous"}:
        how += " — opcjonalnie: gh auth login albo GITHUB_TOKEN=... (przyspiesza)"
    return how


def search_pause():
    return AUTH_SEARCH_PAUSE if token() else ANON_SEARCH_PAUSE


def _request(url, headers, timeout=60, retries=3):
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                remaining = exc.headers.get("X-RateLimit-Remaining")
                reset = exc.headers.get("X-RateLimit-Reset")
                wait = 60
                if remaining == "0" and reset and reset.isdigit():
                    wait = max(10, min(900, int(reset) - int(time.time()) + 5))
                print(f"    Limit GitHuba — czekam {wait}s "
                      f"(próba {attempt}/{retries})", flush=True)
                time.sleep(wait)
                continue
            if exc.code == 422 and attempt >= retries:
                return None
            if attempt == retries:
                return None
            time.sleep(2 * attempt)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            if attempt == retries:
                print("    Nie udało się połączyć z api.github.com", flush=True)
                return None
            time.sleep(2 * attempt)
    return None


def get_json(path, params=None, retries=3):
    """GET do REST GitHuba. gh jeśli jest, inaczej HTTPS."""
    query = ("?" + urllib.parse.urlencode(params)) if params else ""
    if gh_path():
        args = [gh_path(), "api", path + query, "-H",
                "Accept: application/vnd.github+json"]
        secret = token()
        if secret:
            args += ["-H", f"Authorization: bearer {secret}"]
        for attempt in range(1, retries + 1):
            try:
                done = subprocess.run(args, capture_output=True, text=True,
                                      timeout=90)
            except (OSError, subprocess.SubprocessError):
                return None
            if done.returncode == 0 and done.stdout.strip():
                try:
                    return json.loads(done.stdout)
                except ValueError:
                    return None
            err = done.stderr.replace("\n", " ")
            if "rate limit" in err.lower():
                wait = 120
                print(f"    Limit GitHuba — czekam {wait}s "
                      f"(próba {attempt}/{retries})", flush=True)
                time.sleep(wait)
                continue
            print(f"    Nieudana próba {attempt}/{retries}: {err[:90]}", flush=True)
            time.sleep(3 * attempt)
        return None

    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    secret = token()
    if secret:
        headers["Authorization"] = f"bearer {secret}"
    return _request(f"{API_ROOT}{path}{query}", headers, retries=retries)


def search_repositories(query, page=1, per_page=100, sort="stars", retries=3):
    params = {"q": query, "per_page": per_page, "page": page}
    if sort:
        params["sort"] = sort
        params["order"] = "desc"
    return get_json("/search/repositories", params=params, retries=retries)