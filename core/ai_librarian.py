#!/usr/bin/env python3
"""core/ai_librarian.py - AI Bibliotekarz: pytanie po ludzku -> narzedzia z bazy.

RAG-lite: keyword search wyznacza kandydatow z DB, LLM tylko rankinguje i
tlumaczy. LLM nigdy nie wymysla nazw - wybiera wylacznie z podanych kandydatow.
Degradacja: brak ai_providers -> recommend() rzuca RuntimeError z podpowiedzia.
"""

import json
import re

# Polskie stopwordy - slowa funkcyjne nie niosą sensu wyszukiwania
_STOPWORDS = frozenset("""
a aby ale albo ani az bardzo bez bi bo by byl byla było będą co coś czy czyli
dla do gdy gdyby gdzie go i ich ile im inne iz ja jak jakie jako je jednak jego
jesli jeszcze juz kazda kiedy kilka kto ktora ktore ktory które lat lub ma maja
mam mamy mi mnie moje mozna mu my na nam nas nasz nawet nic nich nie niego no o
od oraz oto owszem pan pana pani po pod ponad przez przy raz razie sa się skad
sobie sobie sposob swoje ta tak taka takie tam te tego tej temu ten teraz tez
to tobie tu tutaj twoje ty tych tylko tym u w we wie wszystko właśnie z za zaś
ze zeby ze mnie chce chce chcialbym potrzebuje potrzeba polecam najlepsze najlepszy
""".split())

MAX_CANDIDATES = 30


def extract_keywords(question: str) -> list:
    """Pytanie naturalnym jezykiem -> lista fraz do wyszukiwania."""
    words = re.findall(r"[a-zA-Z0-9_\-\.]+", question.lower())
    words = [w for w in words if len(w) > 1 and w not in _STOPWORDS]
    # unikalne, zachowujac kolejnosc
    seen = set()
    out = []
    for w in words:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out


def translate_queries(analyze_payload, question: str) -> list:
    """
    Etap 1 RAG: pytanie (np. po polsku) -> 3-6 anglojezycznych fraz
    wyszukiwania (baza narzedzi jest po angielsku).
    Zwraca liste fraz; przy problemach - surowe slowa kluczowe pytania.
    """
    result = analyze_payload(
        f"PYTANIE UZYTKOWNIKA (moze byc po polsku): {question}",
        system="Jestes translatorsem zadan wyszukiwania. Odpowiadasz WYLACZNIE tablica JSON.",
        instructions=(
            "Zamien pytanie na 3-6 KROTKICH anglojezycznych fraz do przeszukania "
            "bazy narzedzi open-source (indeks jest po angielsku).\n"
            'Format - tylko JSON: ["vpn monitor", "subdomain enumeration", ...]\n'
            "Uzywaj terminologii technicznej (np. 'port scanner', 'log analyzer').\n\n"
        ),
        answer_cap=800,
    )
    if result is None:
        return [" ".join(extract_keywords(question))]
    m = re.search(r"\[.*\]", result["analysis"], flags=re.S)
    if not m:
        return [" ".join(extract_keywords(question))]
    try:
        qs = json.loads(m.group(0))
        qs = [str(q) for q in qs if str(q).strip()]
        return qs or [" ".join(extract_keywords(question))]
    except Exception:
        return [" ".join(extract_keywords(question))]


def gather_candidates(tools_db, queries: list) -> list:
    """Zbierz pulę kandydatów: search po kazdej frazie (ToolsDB zwraca narzedzia)."""
    pool = {}
    for q in queries:
        try:
            hits = tools_db.search(q, limit=15)
        except Exception:
            continue
        for tool in hits:
            url = tool.get("url", "")
            if url and url not in pool:
                pool[url] = tool

    # zachowaj kolejnosc trafien (najlepsze frazy pierwsze), obetnij pule
    return list(pool.values())[:MAX_CANDIDATES]


def _candidates_block(candidates: list) -> str:
    lines = []
    for t in candidates:
        stars = t.get("source_stars") or 0
        desc = (t.get("description") or "").replace("\n", " ")[:110]
        lines.append(f"- {t.get('name','?')} [{t.get('section','?')}] "
                     f"({stars}*) {desc}")
    return "\n".join(lines)


def _parse_llm_json(text: str) -> list:
    """Wyciagnij tablice [{name, why}] z odpowiedzi LLM."""
    m = re.search(r"\[.*\]", text, flags=re.S)
    if not m:
        raise ValueError("brak JSON w odpowiedzi")
    items = json.loads(m.group(0))
    if not isinstance(items, list):
        raise ValueError("JSON nie jest tablica")
    return items


def recommend(tools_db, question: str, limit: int = 5) -> dict:
    """
    GLOWNA FUNKCJA: pytanie -> rekomendacje narzedzi.
    Pipeline RAG-lite:
      1) LLM tlumaczy pytanie na ang. frazy wyszukiwania (baza jest po angielsku)
      2) keyword search wyznacza kandydatow z DB
      3) LLM rankinguje i uzasadnia (tylko z kandydatow - zero halucynacji nazw)
    Zwraca {"question", "recommendations", "queries", "provider"}.
    RuntimeError gdy AI niedostepne / brak pokrycia w bazie.
    """
    try:
        from ai_providers.text_analysis import analyze_payload, status as ai_status
    except ImportError:
        raise RuntimeError("pip3 install --user -e ~/<katalog>/projekty")

    queries = translate_queries(analyze_payload, question)
    candidates = gather_candidates(tools_db, queries)
    if not candidates:
        raise RuntimeError("search nie zwrocil kandydatow dla tego pytania")

    result = analyze_payload(
        f"PYTANIE: {question}\n\nKANDYDACI Z BAZY:\n{_candidates_block(candidates)}",
        system=(
            "Jestes bibliotekarzem narzedzi open-source. Rekomendujesz WYLACZNIE "
            "narzedzia z podanej listy kandydatow - nigdy innych. Odpowiadasz "
            "WYLACZNIE tablica JSON."
        ),
        instructions=(
            "Wybierz maksymalnie " + str(limit) + " najlepiej pasujacych narzedzi "
            "do pytania uzytkownika.\n"
            'Format ODPOWIEDZI - tylko JSON:\n'
            '[{"name": "dokladna nazwa z listy", "why": "1 zdanie po polsku"}]\n'
            "Uwaga: pole 'name' MUSI byc skopiowane 1:1 z listy kandydatow.\n\n"
        ),
        answer_cap=2500,
    )
    if result is None:
        st = ai_status()
        raise RuntimeError(st.get("reason", "AI nieosiagalne (klucze/offline)"))

    by_name = {t.get("name", ""): t for t in candidates}
    recs = []
    for item in _parse_llm_json(result["analysis"]):
        tool = by_name.get(str(item.get("name", "")))
        if tool is None:
            continue  # halucynacja LLM - pomijamy
        recs.append({
            "tool": {
                "name": tool.get("name"),
                "url": tool.get("url"),
                "section": tool.get("section"),
                "description": (tool.get("description") or "")[:200],
                "source_stars": tool.get("source_stars") or 0,
            },
            "why": str(item.get("why", "")),
        })
        if len(recs) >= limit:
            break

    if not recs:
        raise RuntimeError("LLM nie wskazal zadnego narzedzia z bazy")

    return {
        "question": question,
        "recommendations": recs,
        "queries_used": queries,
        "candidates_searched": len(candidates),
        "provider": result.get("provider", "?"),
    }
