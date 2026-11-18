#!/usr/bin/env python3
"""core/leaks.py — lokalny skan pod kątem możliwych wycieków sekretów.

Opisy/nazwy w bazie pochodzą z zewnętrznych list i README. Mogą w nich
przypadkowo trafić się klucze API, tokeny albo fragmenty kluczy prywatnych.

To tylko heurystyki (mogą być fałszywe alarmy i mogą czegoś nie wykryć).
Moduł działa lokalnie: wykrywa i raportuje — niczego nie wysyła na zewnątrz.
W raporcie sekret jest maskowany, żeby nie powielać go w logach/terminalu.
"""

import re
import subprocess
from pathlib import Path


# (wzorzec, etykieta) — świadomie tylko formaty o wysokiej pewności,
# żeby ograniczyć fałszywe alarmy. Brak trafień nie gwarantuje braku wycieków.
_PATTERNS = [
    (r"\bghp_[A-Za-z0-9]{36}\b", "GitHub token (classic PAT)"),
    (r"\bgithub_pat_[A-Za-z0-9_]{22,}\b", "GitHub token (fine-grained PAT)"),
    (r"\bglpat-[A-Za-z0-9_-]{20,}\b", "GitLab token (PAT)"),
    (r"\bnpm_[A-Za-z0-9]{36}\b", "npm access token"),
    (r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", "AWS Access Key ID"),
    (r"\bAIza[0-9A-Za-z\-_]{35}\b", "Google API key"),
    (r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b", "Slack token"),
    (r"\b(?:sk_live|rk_live)_[0-9A-Za-z]{20,}\b", "Stripe live key"),
    (r"\bmcp_ASM-[A-Za-z0-9_-]{20,}\b", "MCP access token"),
    (r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----",
     "Private key block"),
]

_COMPILED = [(re.compile(pattern), label) for pattern, label in _PATTERNS]

# Domyślne pomijanie przy skanie plików repo (lokalne dane/środowiska/artefakty).
_REPO_SKIP_PREFIXES = ("data/", "offline-db/", ".venv/", "venv/", ".git/")
_REPO_SKIP_EXACT = {".git"}
_MAX_REPO_FILE_BYTES = 1_000_000


def _mask(secret):
    """Maskuje sekret, zostawiając krótki prefiks/sufiks dla identyfikacji."""
    s = str(secret)
    if len(s) <= 12:
        return s[:2] + "…" + s[-2:]
    return s[:6] + "…" + s[-4:]


def _is_placeholder(secret):
    """Odrzuca oczywiste przykłady/placeholdery z dokumentacji."""
    up = str(secret).upper()
    return "EXAMPLE" in up


def _compile_extra(extra):
    compiled = []
    for item in (extra or []):
        if not item:
            continue
        if isinstance(item, tuple) and len(item) == 2:
            pat, label = item
            if hasattr(pat, "finditer"):
                compiled.append((pat, label))
            else:
                compiled.append((re.compile(str(pat)), label or "Custom pattern"))
        elif isinstance(item, str):
            compiled.append((re.compile(item), "Custom pattern"))
    return compiled


def _iter_patterns(extra=None):
    return list(_COMPILED) + _compile_extra(extra)


def scan_text(text, extra=None):
    """Zwraca listę trafień [(etykieta, zamaskowana_próbka), ...]."""
    if not text:
        return []
    text = str(text)
    hits = []
    seen = set()
    for pattern, label in _iter_patterns(extra):
        try:
            matches = pattern.finditer(text)
        except Exception:
            continue
        for match in matches:
            secret = match.group(0)
            if _is_placeholder(secret):
                continue
            sample = _mask(secret)
            key = (label, sample)
            if key in seen:
                continue
            seen.add(key)
            hits.append((label, sample))
    return hits


def scan(conn, extra=None):
    """Przeskanuj bazę pod kątem możliwych wycieków sekretów.

    Zwraca (liczba_przeskanowanych_narzędzi, lista_trafień).
    Każde trafienie: {url, name, field, kind, sample, source}.

    To heurystyki — wyniki wymagają ręcznej weryfikacji. Nic nie jest
    zgłaszane ani wysyłane automatycznie.
    """
    hits = []
    seen = set()
    tools = conn.execute("SELECT COUNT(*) FROM tools").fetchone()[0]

    def _add(url, name, field, kind, sample, source):
        key = (url or "", field, kind, sample, source or "")
        if key in seen:
            return
        seen.add(key)
        hits.append({
            "url": url or "",
            "name": name or "",
            "field": field,
            "kind": kind,
            "sample": sample,
            "source": source or "",
        })

    for row in conn.execute(
            "SELECT name, description, url_norm, source_repo FROM tools"):
        for field in ("name", "description"):
            for kind, sample in scan_text(row[field], extra=extra):
                _add(row["url_norm"], row["name"], field, kind, sample,
                     row["source_repo"])

    # Opisy we wzmiankach (tekst z list/README) to osobne źródło.
    try:
        for row in conn.execute(
                "SELECT url_norm, name, source_repo, description FROM tool_mentions"):
            for kind, sample in scan_text(row["description"], extra=extra):
                _add(row["url_norm"], row["name"], "mention_description",
                     kind, sample, row["source_repo"])
    except Exception:
        # starsze bazy/wywołania bez tabeli — pomijamy
        pass

    return tools, hits


def scan_readmes(readmes_dir, extra=None):
    """Skanuje surowe pliki README (*.md) w katalogu (lokalnie, offline).

    Zwraca (liczba_plików, lista_trafień). Każde trafienie ma field='readme',
    name wyprowadzone z nazwy pliku, a source ustawione na ścieżkę pliku.
    To heurystyki — wyniki wymagają ręcznej weryfikacji.
    """
    path = Path(readmes_dir)
    if not path.is_dir():
        return 0, []
    hits = []
    seen = set()
    files = 0
    for md_path in sorted(path.glob("*.md")):
        files += 1
        try:
            text = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        name = md_path.stem.replace("__", "/", 1)
        source = str(md_path)
        for kind, sample in scan_text(text, extra=extra):
            key = (name, "readme", kind, sample, source)
            if key in seen:
                continue
            seen.add(key)
            hits.append({
                "url": "",
                "name": name,
                "field": "readme",
                "kind": kind,
                "sample": sample,
                "source": source,
            })
    return files, hits


def _skip_repo_path(relpath):
    p = relpath.replace("\\", "/")
    if p in _REPO_SKIP_EXACT:
        return True
    for prefix in _REPO_SKIP_PREFIXES:
        if p == prefix.rstrip("/") or p.startswith(prefix):
            return True
    return False


def scan_repo(repo_dir, extra=None, max_bytes=_MAX_REPO_FILE_BYTES):
    """Skanuje pliki śledzone przez git w repozytorium (w tym ukryte).

    Zwraca (liczba_przeskanowanych_plików, lista_trafień). Każde trafienie ma
    field='repo_file', name/source ustawione na ścieżkę względem repo.
    Pomija binaria, duże pliki i lokalne katalogi danych/środowisk.
    To heurystyki — wyniki wymagają ręcznej weryfikacji.
    """
    root = Path(repo_dir)
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True, check=False,
        )
    except OSError:
        return 0, []
    if proc.returncode != 0:
        return 0, []

    raw = proc.stdout.decode("utf-8", errors="replace")
    paths = [p for p in raw.split("\0") if p]
    hits = []
    seen = set()
    files = 0
    for rel in paths:
        if _skip_repo_path(rel):
            continue
        file_path = root / rel
        try:
            if file_path.is_symlink():
                continue
            size = file_path.stat().st_size
            if size > max_bytes:
                continue
            with open(file_path, "rb") as f:
                data = f.read(max_bytes + 1)
        except OSError:
            continue
        if b"\0" in data:
            continue
        files += 1
        text = data.decode("utf-8", errors="replace")
        for kind, sample in scan_text(text, extra=extra):
            key = (rel, "repo_file", kind, sample, rel)
            if key in seen:
                continue
            seen.add(key)
            hits.append({
                "url": "",
                "name": rel,
                "field": "repo_file",
                "kind": kind,
                "sample": sample,
                "source": rel,
            })
    return files, hits
