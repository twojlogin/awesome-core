# Arek — security automation for Linux & Windows

Buduję narzędzia do bezpieczeństwa i automatyzacji: skanery, recon, hardening,
skrypty PowerShell do Windowsa i katalogi narzędzi, które działają **lokalnie
i offline**. Kod w Pythonie, PowerShellu i bashu. Bez usług w chmurze, bez
telemetrycznych zależności, bez licencji za dostęp.

Główne projekty:

| Projekt | Co to robi |
|---|---|
| **[awesome-core](https://github.com/twojlogin/awesome-core)** | Katalog narzędzi z awesome list — **187 666 narzędzi z 829 list**, ranking oparty o zgodę niezależnych kuratorów, nie o gwiazdki list. CLI, TUI, Web, MCP. Czysty stdlib + jedna zależność, 105 testów, offline po pierwszym pobraniu. |
| **[ROZDANIA](https://github.com/twojlogin/ROZDANIA)** | Agregator giveawayów i darmowych pakietów (archive.org, Epic, IndieGala, GamerPower) z **osobnym krokiem weryfikacji**, który otwiera stronę każdej oferty. 624 paczki, 49 potwierdzonych ofert. Zero zależności zewnętrznych. |
| **[matrixhunt-ultimate](https://github.com/twojlogin/matrixhunt-ultimate)** | Lokalna aplikacja webowa: scrapery, dashboard, **proxy stron z sanacją HTML**, 30 tras API, token na zmiany stanu. React w vendoringu, żeby działało offline. |
| **[Case study: audyt pracy AI](https://github.com/twojlogin/awesome-core/blob/main/docs/case-study-audyt-ai.md)** | Co okazało się nieprawdziwe w kodzie i dokumentacji napisanych przez model: 6 kłamstw w dokumentacji, martwa komenda, wyciek ścieżki z katalogu domowego do publicznego repo, ranking mylący się w 2/15 znanych narzędziach — i metoda, która to wykrywa. |

### Security i automatyzacja (repozytoria na [technoporada](https://github.com/technoporada))

Przejrzane: sprawdzone pod kątem wyciekniętych sekretów, uruchomione w
izolowanym środowisku, licencje i opisy po angielsku dodane.

| Projekt | Co to robi | Testy |
|---|---|---|
| **[Email-Security-Manager](https://github.com/technoporada/Email-Security-Manager)** | Analiza zagrożeń w e-mailu, sprawdzanie linków, wykrywanie oszustw telefonicznych, zgłaszanie nadużyć. FastAPI, zero kont, zero kluczy API. | **27** |
| **[unified-chaos-platform](https://github.com/technoporada/unified-chaos-platform)** | Zintegrowana platforma testowania bezpieczeństwa sieci: 10 modułów, dashboard, terminal WebSocket. | **59** |
| **[matrix-command](https://github.com/technoporada/matrix-command)** | Dashboard reconu bezpieczeństwa: backend FastAPI + interfejs webowy, skanowanie sieci i zbieranie danych OSINT. | **22** |
| **[MatrixHunt](https://github.com/technoporada/MatrixHunt)** | Agregator darmowych gier i ofert AI (PyQt6 + playwright + FastAPI) — **archiwum**, zastąpione przez matrixhunt-ultimate. | **13** |
| **[WindowsToolkit-Pro](https://github.com/technoporada/WindowsToolkit-Pro)** | Zestaw skryptów PowerShell do Windowsa: bezpieczeństwo, optymalizacja, konfiguracja środowiska. | brak (sprawdzona składnia skryptów) |



---

## awesome-core — co to dowodzi

**Problem:** GitHub ma tysiące „awesome list", które powielają te same
narzędzia. Sortowanie po gwiazdkach listy premiuje listy z dobrym README, nie
dobre narzędzia.

**Rozwiązanie:** ranking liczony z **zgody niezależnych kuratorów** — ile
różnych autorów list wskazało to samo narzędzia — plus jakość listy i prawdziwe
gwiazdki repozytorium, pobrane z API GitHuba. Wszystko liczone jawnie, każdą
punktację da się rozłożyć (`awesome why nmap`).

**Skala i inżynieria:**

- **187 666 narzędzi** z **829 list** (1 032 pobrane), 216 383 wzmianek, 81 języków
- **SQLite + FTS5** zamiast plików JSON — 234.5 MB danych, milisekundowe
  wyszukiwanie (3–16 ms), indeksy i transakcje, żeby przerwany build nie
  zniszczył bazy
- **Własny parser Markdown** (linki, tabele, badge'e, kod) + filtr śmieci:
  19 300 odrzuconych pozycji (reklamy, artykuły, sklepy, martwe subdomeny)
- **Detekcja kopii list**: trzy listy kopiujące jedną to nie trzy niezależne
  opinie, więc kopie nie liczą się do zgody kuratorów (próg 80% nakładania)
- **Wykrywanie zatrucia katalogu**: 0 gwiazdek przy setkach linków, setki
  linków do jednego właściciela, martwe linki, domeny-podróżki
  (`github.com@evil.tld`, `githvb.com`)
- **Bezpieczeństwo danych z obcych źródeł**: opisy z cudzych repozytoriów
  przechodzą przez filtr prompt-injection, zanim trafią do kontekstu modelu
- **Serwer MCP** (JSON-RPC po stdio) jako źródło narzędzi dla lokalnych agentów —
  jedyne wejście AI, łatwo odłączalne; rdzeń to czysty stdlib
- **Wydajność zmierzona, nie zgadnięta**: build 300 s → 100 s po analizie
  (jeden regex okazał się 11× wolniejszy niż oryginał i został wycofany)
- **105 testów**, CI na Pythonie 3.8–3.12, jedna zależność zewnętrzna (Flask)
- **Zero kroków konfiguracji**: od `git clone` do pierwszego wyniku — jedno
  polecenie; brak Flaska, `jq`, `curl` i GitHub CLI nie blokuje pracy, a
  `./awesome doctor` odpowiada, co dokładnie jest nie tak

```bash
git clone https://github.com/twojlogin/awesome-core.git
cd awesome-core && ./awesome start          # 10–25 min, potem offline
./awesome search "port scanner" --os windows
./awesome why nmap                          # dlaczego to jest wysoko
```

Dokumentacja (PL/EN), w tym **model zagrożeń** i granice tego, czego system nie
wykrywa: [README](https://github.com/twojlogin/awesome-core#readme)

---

## Jak pracuję

- **Najpierw pomiar, potem twierdzenie.** Każdą optymalizację mierzę i podaję
  liczby z obu stron — także wtedy, gdy wynik jest gorszy niż był.
- **Weryfikuję na czystej maszynie, nie na swojej.** Nowy kod sprawdzam w
  świeżym klonie, bez swoich plików i bez logowania.
- **Nie zostawiam pytań zamiast odpowiedzi.** Każdy błąd kończy się komunikatem
  z komendą do wpisania, nie pytaniem „czy ktoś wie, jak to naprawić".
- **Test ma łapać regresję**, nie dokumentować, że coś działa.
- **Nie polecam niczego.** Pokazuję liczby i filtry o jawnych kryteriach;
  decyzja zostaje po stronie użytkownika.

## Kontakt

GitHub: [twojlogin](https://github.com/twojlogin) ·
profil: [twojlogin.github.io](https://twojlogin.github.io/)

<!--
  Kopia profilu GitHub (twojlogin/twojlogin). Aby wrzucić zmiany:
  cp profile/README.md /tmp/profrepo/README.md && cd /tmp/profrepo \
  && git add README.md && git commit -m "profil" && git push
-->
