#!/usr/bin/env python3
"""core/leaks.py — lokalny skan pod kątem możliwych wycieków sekretów.

Opisy/nazwy w bazie pochodzą z zewnętrznych list i README. Mogą w nich
przypadkowo trafić się klucze API, tokeny albo fragmenty kluczy prywatnych.

To tylko heurystyki (mogą być fałszywe alarmy i mogą czegoś nie wykryć).
Moduł działa lokalnie: wykrywa i raportuje — niczego nie wysyła na zewnątrz.
W raporcie sekret jest maskowany, żeby nie powielać go w logach/terminalu.
"""

import re


# (wzorzec, etykieta)
_PATTERNS = [
    (r"\bghp_[A-Za-z0-9]{36}\b", "GitHub token (classic PAT)"),
    (r"\bgithub_pat_[A-Za-z0-9_]{22,}\b", "GitHub token (fine-grained PAT)"),
    (r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", "AWS Access Key ID"),
    (r"\bAIza[0-9A-Za-z\-_]{35}\b", "Google API key"),
    (r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b", "Slack token"),
    (r"\b(?:sk_live|rk_live)_[0-9A-Za-z]{20,}\b", "Stripe live key"),
    (r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----",
     "Private key block"),
]

_COMPILED = [(re.compile(pattern), label) for pattern, label in _PATTERNS]


def _mask(secret):
    """Maskuje sekret, zostawiając krótki prefiks/sufiks dla identyfikacji."""
    s = str(secret)
    if len(s) <= 12:
        return s[:2] + "…" + s[-2:]
    return s[:6] + "…" + s[-4:]


def scan_text(text):
    """Zwraca listę trafień [(etykieta, zamaskowana_próbka), ...]."""
    if not text:
        return []
    text = str(text)
    hits = []
    seen = set()
    for pattern, label in _COMPILED:
        for match in pattern.finditer(text):
            sample = _mask(match.group(0))
            key = (label, sample)
            if key in seen:
                continue
            seen.add(key)
            hits.append((label, sample))
    return hits


def scan(conn):
    """Przeskanuj bazę pod kątem możliwych wycieków sekretów.

    Zwraca (liczba_przeskanowanych_narzędzi, lista_trafień).
    Każde trafienie: {url, name, field, kind, sample, source}.

    To heurystyki — wyniki wymagają ręcznej weryfikacji. Nic nie jest
    zgłaszane ani wysyłane automatycznie.
    """
    hits = []
    tools = conn.execute("SELECT COUNT(*) FROM tools").fetchone()[0]

    for row in conn.execute(
            "SELECT name, description, url_norm, source_repo FROM tools"):
        for field in ("name", "description"):
            for kind, sample in scan_text(row[field]):
                hits.append({
                    "url": row["url_norm"] or "",
                    "name": row["name"] or "",
                    "field": field,
                    "kind": kind,
                    "sample": sample,
                    "source": row["source_repo"] or "",
                })

    # Opisy we wzmiankach (tekst z list/README) to osobne źródło.
    try:
        for row in conn.execute(
                "SELECT url_norm, name, source_repo, description FROM tool_mentions"):
            for kind, sample in scan_text(row["description"]):
                hits.append({
                    "url": row["url_norm"] or "",
                    "name": row["name"] or "",
                    "field": "mention_description",
                    "kind": kind,
                    "sample": sample,
                    "source": row["source_repo"] or "",
                })
    except Exception:
        # starsze bazy/wywołania bez tabeli — pomijamy
        pass

    return tools, hits
