#!/usr/bin/env python3
"""core/doctor.py — „coś nie działa" w jednym miejscu, z gotowym wyjściem.

Skargi w stylu „nie wiem czemu nie działa" kosztują więcej niż kod, który
je powoduje. Ten moduł sprawdza środowisko i zwraca listę problemów razem
z konkretną akcją, więc odpowiedź brzmi „wpisz to", a nie „przeszukaj
internet". Każdy punkt ma status: ok / warn / fail.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

OK = "ok"
WARN = "warn"
FAIL = "fail"


def _check(status, name, detail, action=""):
    return {"status": status, "name": name, "detail": detail, "action": action}


def run(base_dir=None, network=True):
    """Zwraca listę punktów. network=False pomija kontakt z siecią (testy)."""
    from core import api

    base = Path(base_dir or BASE_DIR)
    points = []

    version = sys.version_info
    points.append(_check(
        OK if version >= (3, 8) else FAIL,
        f"Python {version.major}.{version.minor}",
        "wymagane 3.8 lub nowsze" if version >= (3, 8) else "za stary",
        "" if version >= (3, 8) else "Zainstaluj Pythona 3.8+ i uruchom ponownie"))

    points.append(_check(
        OK, "Dostęp do GitHuba", api.describe(),
        "" if api.token() else "Działa bez tego, ale wolniej"))

    db_file = base / "data" / "awesome.db"
    if not db_file.exists():
        points.append(_check(FAIL, "Baza", f"nie ma pliku {db_file}",
                             "./awesome start"))
    else:
        try:
            from core import store

            conn = store.connect(base / "data", read_only=True)
            tools = conn.execute("SELECT COUNT(*) FROM tools").fetchone()[0]
            repos = conn.execute("SELECT COUNT(*) FROM repos").fetchone()[0]
            from core.enrich import missing_repos

            todo = len(missing_repos(conn))
            conn.close()
            if tools == 0:
                points.append(_check(FAIL, "Baza", "pusta — 0 narzędzi",
                                     "./awesome build"))
            else:
                points.append(_check(OK, "Baza",
                                     f"{tools:,} narzędzi z {repos} list"))
                points.append(_check(
                    OK if todo == 0 else WARN,
                    "Metadane narzędzi",
                    "wszystkie repozytoria odpytane" if todo == 0
                    else f"{todo} repozytoriów do odpytania",
                    "" if todo == 0 else "./awesome enrich"))
        except Exception as exc:  # baza uszkodzona — nie wywalaj doctora
            points.append(_check(FAIL, "Baza", f"nie da się otworzyć: {exc}",
                                 "mv data/awesome.db data/old.db && ./awesome build"))

    readmes = base / "offline-db" / "data" / "readmes"
    count = len(list(readmes.glob("*.md"))) if readmes.exists() else 0
    points.append(_check(
        OK if count else WARN, "README list",
        f"{count} plików lokalnie" if count else "brak — baza buduje się "
        "tymczasowo bez nich",
        "" if count else "./awesome download"))

    venv = base / "venv"
    try:
        import flask  # noqa: F401

        flask_ok, flask_detail = True, "Flask dostępny"
    except ImportError:
        flask_ok = flask_detail = None
        flask_detail = "Flask nie importuje się"
    if flask_ok is None:
        points.append(_check(
            WARN, "Web UI", flask_detail,
            "./awesome web   # utworzy venv i zainstaluje samo"))

    for name in ("data", "offline-db"):
        path = base / name
        writable = not path.exists() or os.access(path, os.W_OK)
        points.append(_check(
            OK if writable else FAIL, f"Katalog {name}",
            "zapisywalny" if writable else "brak praw zapisu",
            "" if writable else f"sprawdź uprawnienia do {path}"))

    if network:
        reachable = api.get_json("/rate_limit", retries=1) is not None
        points.append(_check(
            OK if reachable else WARN, "Sieć do api.github.com",
            "odpowiada" if reachable else "brak odpowiedzi",
            "" if reachable else
            "Działa offline po pierwszym pobraniu; przy pierwszym starcie "
            "sprawdź sieć albo proxy"))

    return points


def summary(points):
    """Blok do wklejenia w zgłoszeniu błędu — bez sekretów."""
    lines = ["awesome doctor —", f"python: {sys.version.split()[0]}",
             f"platforma: {sys.platform}"]
    lines += [f"  [{p['status']}] {p['name']}: {p['detail']}"
              for p in points]
    return "\n".join(lines)