#!/usr/bin/env python3
"""core/selfcheck.py — czy katalog potrafi znaleźć znane narzędzie.

Nie jest to test jednostkowy i nie powinien być. Test napisany przez tego
samego, kto napisał kod, potwierdza tylko założenia autora — a tu chodzi
o coś, czego autor nie kontroluje: czy wpisując nazwę narzędzia, dostanę
to narzędzie.

„Prawda" pochodzi ze świata zewnętrznego: narzędzie → repozytorium, które
naprawdę należy do niego. To wiedza o świecie, nie moja hipoteza, więc
wynik tego testu jest zewnętrzny dla kodu, który ocenia.

Znane ograniczenie (mierzone, nie zgadywane): ranking czyta to, co autor
napisał — nazwę, opis, gwiazdki, tematy. Kodu nie czyta. Repozytorium
fanowskie, które powtarza nazwę narzędzia w opisie pięć razy, potrafi
wyprzedzić oryginał. Liczba poniżej mierzy dokładnie to ryzyko.
"""

# (zapytanie, właściciel repozytorium którego szukamy)
KNOWN_TOOLS = [
    ("nmap", "nmap/nmap"),
    ("masscan", "robertdavidgraham/masscan"),
    ("impacket", "fortra/impacket"),
    ("metasploit", "rapid7/metasploit-framework"),
    ("sqlmap", "sqlmapproject/sqlmap"),
    ("wireshark", "wireshark/wireshark"),
    ("hashcat", "hashcat/hashcat"),
    ("ghidra", "NationalSecurityAgency/ghidra"),
    ("radare2", "radareorg/radare2"),
    ("burpsuite", "portswigger"),
    ("nikto", "sullo/nikto"),
    ("gobuster", "OJ/gobuster"),
    ("ffuf", "ffuf/ffuf"),
    ("responder", "lgandx/Responder"),
    ("mimikatz", "gentilkiwi/mimikatz"),
]


def run(tools_db, limit=3):
    """Zwraca (trafienia_na_1, trafienia_w_top, lista_nietrafień)."""
    first = in_top = 0
    misses = []
    for query, expected in KNOWN_TOOLS:
        owner = expected.split("/")[0].lower()
        urls = [t["url_norm"] for t in tools_db.search(query, limit=limit)]
        hit_first = bool(urls) and owner in urls[0]
        hit_top = any(owner in url for url in urls)
        first += hit_first
        in_top += hit_top
        if not hit_first:
            misses.append({
                "query": query,
                "expected": expected,
                "got": urls[0] if urls else "",
                "in_top": hit_top,
            })
    return first, in_top, misses
