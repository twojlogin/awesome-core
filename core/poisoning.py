#!/usr/bin/env python3
"""core/poisoning.py — wykrywanie list, które mogą zatruwać katalog.

Problem, który zgłosił właściciel: skoro katalog powstaje z cudzych
repozytoriów, to ktoś może celowo wstawić fałszywą listę, która wywindowa
się wysoko, a narzędzia w niej będą złośliwe albo podszywające się pod
cudze domeny. Stąd pytanie: „nie wypuszczamy oszustwa".

To NIE jest skaner złośliwego oprogramowania i nie obiecujemy, że przepuści
niczego złośliwego. Robimy jedno uczciwie: **liczymy z tego, co mamy
lokalnie, jakie listy wyglądają jak masowe rozrzucanie linków**, i pokazujemy
to człowiekowi przed zaufaniem. Każdy sygnał daje się sprawdzić ręcznie.

Dlaczego to w ogóle działa na dane, które już mamy:
- zero gwiazdek + setki narzędzi = ktoś właśnie zrobił listę, żeby zbierać
  wejścia (stars of a list with no stars = no reputation to lose),
- narzędzia niemal z jednego właściciela = spraying pod jeden projekt,
- duży udział martwych linków = farma linków, nie katalog,
- niedawno utworzone repozytorium + dużo narzędzi = kampania, nie dorobek,
- klon innej listy (mamy to już w clones.py).
"""

import re

# Domena wyglądająca jak domena zaufana, ale nią niebędąca. Sygnał phishingu,
# nie dowód — stąd lista, nie wyrok.
LOOKALIKE_HOSTS = {
    "github.com": ("githvb.com", "github-cm.com", "gitnub.com", "github.co",
                   "github.io", "githubapp.com", "github.com.pl"),
    "raw.githubusercontent.com": ("raw-githubusercontent.com",),
    "gitlab.com": ("gitalb.com", "gitlab.co"),
    "pypi.org": ("pypi.cm", "pypi.org.pl", "pythonpkgs.org"),
    "npmjs.com": ("npmjs.co", "npmmjs.com"),
    "docker.io": ("docker-io.com",),
}

TRUSTED_HOST_SUFFIXES = (
    ".github.com", ".github.io", ".gitlab.com", ".readthedocs.io",
    ".python.org", ".pypi.org", ".npmjs.com", ".crates.io", ".nuget.org",
    ".docker.com", ".r-project.org", ".freebsd.org", ".kernel.org",
)


def _ratio(part, whole):
    return len(part) / len(whole) if whole else 0


def url_risks(url_norm):
    """Sygnały ryzyka dla pojedynczego URL (nie decyzja o bezpieczeństwie)."""
    flags = []
    url = (url_norm or "").lower()
    if not url:
        return ["brak URL"]
    if url.startswith("http://"):
        flags.append("http bez szyfrowania")
    authority = url.split("//", 1)[-1].split("/", 1)[0]
    host = authority.split(":", 1)[0]
    # "@" grozi tylko w części przed domeną (github.com@evil.tld).
    # W ścieżce jest normalny: observablehq.com/@ktoś/coś
    if "@" in authority:
        flags.append("znak @ przed domeną — podszywanie domeny")
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
        flags.append("adres IP zamiast domeny")
    if "xn--" in host:
        flags.append("domena w kodowaniu punycode")
    for real, fakes in LOOKALIKE_HOSTS.items():
        if host in fakes:
            flags.append(f"domena wygląda jak {real}, ale nią jest")
    return flags


def _stars(row):
    try:
        return int(row["stars"] or 0)
    except (TypeError, ValueError, IndexError, KeyError):
        return 0


def assess_list(conn, full_name):
    """Ocenia jedną listę na podstawie tego, co mamy lokalnie.

    Zwraca {"status", "info", "attention", "score"} — score to liczba
    ostrzeżeń, nie ocena jakości listy.
    """
    repo = conn.execute(
        "SELECT * FROM repos WHERE full_name = ?", (full_name,)
    ).fetchone()
    if repo is None:
        return {"status": "brak danych", "info": [], "attention": [], "score": 0}
    repo = dict(repo)

    attention = []
    info = []
    # Wszystko z jednego zapytania: dwa osobne liczniki alive kosztowały
    # 90 ms na listę (indeks na alive prowadził przez 109k żywych wierszy),
    # bo jeden pełny audyt wychodził wtedy 92 s zamiast kilku sekund.
    counts = conn.execute(
        "SELECT COUNT(*) tools, SUM(alive = 0) dead, SUM(alive IS NOT NULL) checked "
        "FROM tools WHERE source_repo = ?", (full_name,)
    ).fetchone()
    tools = counts["tools"] or 0
    dead = counts["dead"] or 0
    checked = counts["checked"] or 0
    unique_tools = repo.get("unique_tool_count") or tools
    stars = _stars(repo)

    if unique_tools >= 20 and stars == 0:
        attention.append(
            f"{unique_tools} narzędzi przy 0 gwiazdek — brak reputacji do stracenia, "
            f"typowy wzorzec rozrzucania linków")
    elif unique_tools >= 60 and stars < 5:
        attention.append(f"{unique_tools} narzędzi przy {stars} gwiazdkach")

    owners = conn.execute(
        "SELECT COUNT(DISTINCT substr(url_norm, 12, instr(substr(url_norm, 12), '/') - 1)) "
        "c FROM tools WHERE source_repo = ? AND url_norm LIKE 'github.com/%'",
        (full_name,),
    ).fetchone()["c"]
    github_tools = conn.execute(
        "SELECT COUNT(*) c FROM tools WHERE source_repo = ? "
        "AND url_norm LIKE 'github.com/%'", (full_name,)
    ).fetchone()["c"]
    if github_tools >= 10 and owners == 1:
        attention.append(
            f"{github_tools} linków do jednego właściciela — linki do jednego projektu, "
            f"nie katalog")
    elif github_tools >= 40 and owners <= max(2, github_tools // 40):
        attention.append(f"tylko {owners} różnych właścicieli dla {github_tools} linków")

    if checked >= 20 and dead / checked > 0.4:
        attention.append(f"{dead} z {checked} sprawdzonych linków nie żyje "
                         f"({dead / checked:.0%})")

    if repo.get("archived") in {True, "true", "1"}:
        info.append("repozytorium zarchiwizowane")
    if repo.get("clone_of"):
        info.append(f"kopia listy {repo['clone_of']}")
    if repo.get("is_fork") in {True, "true", "1"} and repo.get("parent"):
        info.append(f"fork listy {repo['parent']}")
    if not (repo.get("description") or "").strip():
        info.append("brak opisu")
    if unique_tools and conn.execute(
            "SELECT COUNT(DISTINCT source_repo) c FROM tools WHERE url_norm = "
            "(SELECT url_norm FROM tools WHERE source_repo = ? LIMIT 1)",
            (full_name,)).fetchone()["c"] <= 1:
        info.append("jeden z jej linków nie ma żadnego potwierdzenia w innej liście")

    return {
        "status": "warto sprawdzić" if attention else "brak szczególnych sygnałów",
        "info": info,
        "attention": attention,
        "score": len(attention),
        "tools": unique_tools,
        "stars": stars,
    }


def scan_lists(conn, min_tools=20, only_attention=True, limit=None):
    """Przegląda listy i zwraca te z ostrzeżeniami (domyślnie)."""
    rows = conn.execute(
        "SELECT full_name, stars, unique_tool_count FROM repos "
        "WHERE COALESCE(unique_tool_count, tool_count, 0) >= ? "
        "ORDER BY COALESCE(unique_tool_count, tool_count, 0) DESC", (min_tools,)
    ).fetchall()
    flagged = []
    for row in rows:
        verdict = assess_list(conn, row["full_name"])
        if verdict["attention"] or not only_attention:
            verdict["full_name"] = row["full_name"]
            flagged.append(verdict)
    flagged.sort(key=lambda item: -item["score"])
    return flagged[:limit] if limit else flagged


def scan_tools(conn, limit=None):
    """Narzędzia, których URL wygląda podejrzanie (lookalike, http, IP, punycode)."""
    flagged = []
    for row in conn.execute(
            "SELECT name, url_norm, source_repo, lists_count FROM tools "
            "WHERE url_norm IS NOT NULL"):
        flags = url_risks(row["url_norm"])
        if flags:
            flagged.append({"name": row["name"], "url": row["url_norm"],
                            "source_repo": row["source_repo"],
                            "lists_count": row["lists_count"],
                            "flags": flags})
    flagged.sort(key=lambda item: -len(item["flags"]))
    return flagged[:limit] if limit else flagged
