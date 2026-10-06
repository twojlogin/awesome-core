#!/usr/bin/env python3
"""core/untrusted.py — tekst z obcych awesome list jest DANYMI, nie instrukcjami.

Te opisy napisali ludzie, których nie znamy, w repozytoriach, których nie
weryfikujemy. Dziś w bazie nie ma ani jednego „ignore previous instructions"
(przeskanowałem 186 861 narzędzi), ale to nie gwarancja — jutro ktoś może
wypchnąć taki opis, a opis trafia prosto do kontekstu modelu przez MCP.

Dlatego trzy warstwy, nie jedna:

1. `sanitize()` — przycinamy instrukcje wyglądające na polecenia oraz tagi
   HTML, zanim tekst opuści proces. Zamiast po cichu usuwać treść,
   zostawiamy znacznik, żeby dało się zauważyć.
2. MCP mówi w `instructions`, że opisy to treść trzecia, nie rozkazy.
3. `awesome validate --untrusted` skanuje bazę, gdyby ktoś chciał sprawdzić
   sam, zamiast ufać mi na słowo.

Nic z GitHuba nigdy nie jest wykonywane: parser wyciąga linki regexem,
`awesome install` robi `git clone` (git nie uruchamia kodu zdalnego),
a web escapuje HTML. To właśnie dlatego ta warstwa wystarcza.
"""

import re

_PATTERNS = [
    (r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above|earlier|preceding)\s+"
     r"(instructions?|prompts?|context|messages?)", "ignoruj instrukcje", 0),
    (r"disregard\s+(all\s+)?(the\s+)?(previous|prior|above|earlier)\s+\w+",
     "ignoruj kontekst", 0),
    (r"forget\s+(everything|all)\s+(you|above)", "zapomnij wszystkiego", 0),
    (r"(you\s+must|you\s+should\s+now|always)\s+(immediately\s+)?"
     r"(run|execute|install|clone|download|call|invoke)\b", "nakaz działania", 0),
    (r"^\s*(system|assistant|user)\s*:\s*", "znacznik roli", re.MULTILINE),
    (r"<\s*(script|iframe|object|embed|form)\b", "tag HTML", 0),
    (r"\bon(error|load|click|mouseover)\s*=", "handler HTML", 0),
    # "JavaScript: Build your own 3D renderer" to tytuł kursu, nie atak —
    # schemat URI rozpoznajemy dopiero po tym, co po nim stoi.
    (r"(javascript|vbscript)\s*:\s*(alert|document|window|location|eval|fetch|prompt)",
     "schemat URI", 0),
    (r"data\s*:\s*(text/html|application/|image/svg)", "schemat URI", 0),
    (r"(curl|wget)\s+[^\s|]+\s*\|\s*(sudo\s+)?(ba|z|k)?sh", "pobierz i wykonaj", 0),
    (r"invoke-expression|\biex\s*\(", "PowerShell IEX", 0),
    (r"(rm\s+-rf|mkfs\.|del\s+/[sf]\s)", "kasowanie danych", 0),
]

# IGNORECASE jest tu obowiązkowy, nie ozdoba: opis zaczyna się wielką literą
# ("Ignore all previous instructions") i bez tej flagi przechodził złoty test
# na "ignore" z małej litery, który nijak nie odpowiadał rzeczywistości.
_COMPILED = [
    (re.compile(pattern, flags | re.IGNORECASE), label)
    for pattern, label, flags in _PATTERNS
]

MAX_LEN = 300


def sanitize(text, limit=MAX_LEN):
    """Zwraca (tekst, lista znaczników). Nic nie znika bez śladu.

    `limit=None` oznacza: nie skracaj (używane przy skanowaniu całej bazy).
    """
    if not text:
        return "", []
    clean = " ".join(str(text).split())
    findings = []
    for pattern, label in _COMPILED:
        clean, hits = pattern.subn(f"[odfiltrowano: {label}]", clean)
        if hits:
            findings.append(f"{label} ×{hits}")
    if limit and len(clean) > limit:
        clean = clean[: limit - 1].rsplit(" ", 1)[0] + "…"
    return clean, findings


def scan(conn):
    """Przejrzyj bazę pod kątem tekstu wyglądającego na polecenia.

    Zwraca (liczba_narzedzi, lista_trafień). Fałszywe alarmy się zdarzą —
    „Home Assistant", „JavaScript: ..." czy nazwa narzędzia IEX trafiają
    w wzorce. Dlatego wypisujemy fragment, a nie tylko liczbę.
    """
    hits = []
    tools = conn.execute("SELECT COUNT(*) FROM tools").fetchone()[0]
    for row in conn.execute("SELECT name, description, url_norm FROM tools"):
        for field in ("name", "description"):
            _clean, findings = sanitize(row[field], limit=None)
            if findings:
                hits.append({
                    "url": row["url_norm"],
                    "name": row["name"],
                    "field": field,
                    "findings": findings,
                })
                break
    return tools, hits
