# 🔥 Awesome Core

## Czym to jest, w jednym zdaniu

**Ściąga wszystkie awesome listy z GitHuba do jednego katalogu na Twoim dysku
i pozwala szybko znaleźć narzędzie — po nazwie, języku, systemie albo temacie —
całkowicie bez internetu.**

Na przykład chcesz „coś do OSINT-a działające pod Windows". Wpisujesz:

```bash
./awesome search osint --os windows
```

i dostajesz narzędzia z kilku różnych awesome list naraz, posortowane tak, że
na górze są te, które **niezależni kuratorzy wskazali w wielu listach**
(a nie tylko te z jednej głośnej listy).

> **Filtry łączy AND, więc kumulują się szybko.** `--os windows --lang PowerShell`
> zostawia z „osint" **jedno** narzędzie — i to nie to, czego szukałeś, tylko
> skrypt PowerShell, który akurat też nazywa się „Sherlock". Program wie, że
> filtr jest za wąski, i mówi wprost, który odpuścić:
>
> ```
> Uwaga: 2 filtry łączy AND i zostawiły 1 wynik(ów).
>     bez lang=PowerShell  →  8 wyników
> ```
>
> Zasada: dodawaj filtr tylko wtedy, gdy wyników jest więcej niż kilka.

---

## Jeśli nie masz czasu — trzy komendy

```bash
./awesome start      # 1. wszystko robi za Ciebie (pobiera, buduje, gotowe)
./awesome search nmap
./awesome web        # i otwiera przeglądarkę
```

`./awesome start` mówi w każdym kroku, co robi i ile to potrwa. Nic działa się
samo w tle — zawsze widzisz postęp.

---

## Co musisz mieć zanim zaczniesz

Trzy rzeczy, wszystkie darmowe:

| Potrzebujesz | Po co | Sprawdzenie |
|---|---|---|
| **Python 3.8+** | program | `python3 --version` |
| **gh** (GitHub CLI) | pobieranie list i metadanych (logujesz się raz) | `gh --version` |
| **jq** i **curl** | pomocnicze narzędzia do pobierania | `jq --version && curl --version` |

Instalacja na Linuksie:

```bash
sudo apt install python3 jq curl        # albo: sudo dnf install python3 jq curl
gh auth login                          # zaloguj się do GitHuba (jednorazowo)
```

Reszta (Flask do web UI) instaluje się sama:

```bash
python3 -m venv venv && source venv/bin/activate
pip install flask
```

**Nie musisz** znać SQL, programować, nic konfigurować w środku i **nie musisz**
nic aktualizować automatycznie. Jak coś nie działa — `./awesome status` powie
Ci, co dokładnie odpalić.

---

## Pierwsze uruchomienie, krok po kroku

### `./awesome start`

Program sprawdza, czy masz wszystko, potem:

| Krok | Co robi | Ile trwa |
|---|---|---|
| 1 | pobiera README awesome list z GitHuba (pomija to, co już masz) | 5–15 min |
| 2 | wyciąga z nich narzędzia do bazy | ~2 min |
| 3 | dociąga gwiazdki i języki list | ~1 min |
| 4 | gotowe | — |

Jeśli masz mało czasu, krok 1 możesz pominąć i nadrobić później:

```bash
./awesome start --skip-download     # szybka ścieżka: buduje z tego, co już jest
```

### Codzienne użycie

```bash
./awesome search "port scanner"                    # szukaj po ludzku
./awesome search osint --lang Python              # ...tylko Python
./awesome search "active directory" --os windows  # ...tylko pod Windowsa
./awesome langs                                    # co jest w bazie (języki)
./awesome platforms                                # systemy: Windows, Linux, Docker...
./awesome domains                                  # tematy: osint, security, network...
./awesome why nmap                                 # skąd ten wynik — punkt po punkcie
./awesome mentions nmap                            # w ilu listach jest to narzędzie
./awesome lists                                    # najlepsze listy
./awesome info nmap                                # dane + komenda instalacji
./awesome install nmap                             # zainstaluj (git clone)
```

### Twoja własna lista

Jak coś znajdziesz i działa — włóż to od razu na swoją listę, a na końcu
wklej gotowy Markdown:

```bash
./awesome shortlist add nmap --note "do skanowania sieci"
./awesome shortlist                            # co jest na liście
./awesome shortlist emit --title "Moja lista OSINT" --group domain
./awesome shortlist emit --out moja-lista.md  # zapisz do pliku
```

W web UI jest to samo: przycisk **☆ Do mojej listy** na stronie narzędzia,
lista i Markdown pod linkiem *Moja lista* w menu. W TUI klawisz `k`.

Osobno istnieje `watch` — lista **repozytoriów list**, które chcesz śledzić
(nowe narzędzia w ulubionej liście), a nie lista narzędzi:

```bash
./awesome watch add sindresorhus/awesome
./awesome watch check          # co doszło od ostatniego sprawdzenia
```

Obie listy są lokalne i żadna nie odpytuje się sama w tle.

### Trzy interfejsy, ten sam katalog

```bash
./awesome            # terminal — najszybszy do szybkiego szukania
./awesome tui        # terminal, ale interaktywnie (strzałki, filtry)
./awesome web        # przeglądarka (http://localhost:5001)
./awesome help       # wszystkie komendy
```

---

## Codzienna pielęgnacja (nic nie leci samo)

```bash
./awesome status     # co jest w bazie, kiedy ostatnio odświeżone, czego brakuje
./awesome refresh    # pobierz nowe listy → metadane → przebuduj bazę
```

`./awesome status` po odświeżeniu podpowiada dokładną komendę, np.
`./awesome enrich`. To samo w przeglądarce: strona `/refresh`
z czterema przyciskami. Żadnych cronów, daemonów ani procesów w tle.

**Ważne przy liczbach:** status nie mówi „X narzędzi bez gwiazdek", tylko ile
**repozytoriów zostało do odpytania**. Różnica jest ogromna, bo kilka narzędzi
często wskazuje na to samo repo, a linki poza GitHubem (artykuły, filmy,
dokumentacja) **nie mają i nigdy nie będą miały gwiazdek** — nie licz ich
jako brakującej pracy.

---

## Podłącz agenta AI (MCP) — lokalnie, bez kluczy API

Katalog można dać do dyspozycji lokalnemu agentowi (Claude, Cursor, cokolwiek
mówi „Model Context Protocol”) jako źródło narzędzi. Agent dostaje ranking
oparty o zgodę niezależnych kuratorów, a nie o to, co jest najczęściej
wypisane w jednym README.

```bash
./awesome mcp --demo    # podgląd: zobaczysz całą wymianę JSON-RPC bez agenta
./awesome mcp           # serwer czeka na stdin (tak to działa w praktyce)
```

Serwer daje 5 narzędzi: `search_tools` (szukanie z filtrami),
`find_undiscovered_tools` (niedoceniane i ukryte perełki), `explain_tool`
(uzasadnienie rankingu: z jakich list, ile punktów, co ważyło),
`lists_with_tool` (wszystkie listy + oznaczone kopie) i `catalog_facets`
(co jest w bazie: języki, platformy, domeny).

Wpisz to do konfiguracji klienta, np. `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "awesome-core": {
      "command": "/pełna/ścieżka/do/awesome-core2/awesome",
      "args": ["mcp"]
    }
  }
}
```

Co warto wiedzieć:

- **Nic nie wychodzi do sieci.** Zero kluczy API, zero kont, tylko odczyt
  lokalnej bazy SQLite. Serwer nie ma narzędzi z efektem ubocznym.
- **Start jest natychmiastowy** — baza jest już zbudowana, serwer tylko czyta.
- Wyniki to zwykły tekst z liczbami (gwiazdki, liczba niezależnych list, score),
  więc agent może je cytować i porównywać.
- Protokół jest czystym JSON-RPC 2.0 po stdin/stdout; logi idą na stderr,
  żeby nie psuły kanału.

---

## Skąd to wszystko pochodzi — i czy mi szkodzi

Pytanie, które powinien zadać każdy: *co jeśli ktoś wrzuci złośliwą listę?*

**Skąd listy:** `download.sh` pyta publiczne API GitHuba o repozytoria
oznaczone `topic:awesome-list` (plus `topic:awesome` i `topic:curated-list`
w trybie `--wide`), posortowane po gwiazdkach. Nic więcej — żadnych
„polecanych" repozytoriów, żadnych losowych adresów.

**Nic z obcego repozytorium nigdy nie jest wykonywane:**

- README jest **danymi**. Parser wyciąga z niego linki regexem i tyle.
  Nie ma miejsca, w którym treść README trafiłaby do `eval`, `exec`,
  `shell=True` czy któregokolwiek wywołania systemowego.
- `awesome install` robi dokładnie `git clone --depth 1`. Git nie uruchamia
  kodu z zdalnego repozytorium (żadnych hooków).
- Przeglądarka escapuje HTML, a renderer Markdown w `core/md.py` też —
  `<script>` w opisie wychodzi jako tekst, nie jako tag.

**Jedyny realny wektor: opisy trafiające do kontekstu modelu.** Serwer MCP
zamienia opisy narzędzi w tekst, który czyta agent. Opis napisał ktoś
nieznany, w repozytorium niesprawdzonym. Dlatego:

- Opisy przechodzą przez `core/untrusted.py`, które wycina instrukcje
  wyglądające na polecenia, znaczniki ról (`system:`, `assistant:`), tagi
  HTML, `curl … | sh` i `rm -rf` — zostawiając przy tym znacznik
  `[odfiltrowano: …]`, żeby dało się zauważyć.
- `initialize` w MCP mówi agentowi wprost: to treść trzecia, nie rozkazy.
- Sprawdź sam, kiedy chcesz:

```bash
./awesome untrusted
```

Stan na dziś: **0 wykrytych ataków** w 186 861 narzędziach (3 trafienia to
fałszywe alarmy — `rimraf` ma w opisie „like rm -rf", a `safety-net` to
narzędzie, które `rm -rf` blokuje). Ciekawa ironia: katalog zawiera trzy
narzędzia do obrony przed dokładnie tym problemem (`nvidia/skillspector`,
`vaporif/parry-guard`, `safety-net`).

Czego **nie** obiecuję: skaner łapie znane wzorce, nie jest dowodem
niezawodności. Dlatego traktuj opisy jako dane, a nie polecenia.

---

## Zasada: rdzeń bez AI

Właściciel projektu dopuścił MCP, ale nie chce sztucznej inteligencji
wszędzie — szczególnie nie w narzędziu, które miało być lokalne. Zapisuję to,
bo obietnica bez pilotausu wyparuje się przy pierwszym refaktorze:

| Warstwa | AI? | Sieć? |
|---|---|---|
| parser, baza, ranking, kopie, shortlist, TUI, web | **nie** | **nie** — czyste odczyty z `data/awesome.db` |
| `core/mcp.py` (adapter dla agentów) | tak, poza procesem | nie — JSON-RPC po stdio |
| `download`, `enrich`, `backfill`, `validate`, `install` | nie | tak, tylko na wyraźne polecenie |

Z tego wynika reszta decyzji:

- **Cała zależność zewnętrzna to `flask`** (web UI). Rdzeń to czysty stdlib.
- **Zero modeli, embeddingów, sieci neuronowych czy LLM w rankingu.** Sortowanie
  to jawna arytmetyka (`core/scoring.py`), którą da się wypisać i podważyć.
- **Ranking nie zależy od usługi firmy trzeciej.** Nikt nie może Ci podsunąć
  wyników ani zobaczyć, czego szukałeś.
- **MCP jest adapterem na brzegu**, nie logiki w środku. Możesz go wywalić
  i nic nie przestanie działać.
- Test `test_no_ai_in_core` pilnuje tego mechanicznie: rdzeń nie zaimportuje
  biblioteki AI ani sieciowej modułu bez zgody, a jedynym plikiem znającym
  protokół MCP jest `core/mcp.py`.

---

## Czego nie wiem — słowniczek

| Słowo | Co to znaczy |
|---|---|
| **awesome list** | lista linków do narzędzi prowadzona na GitHubie (np. `sindresorhus/awesome`) |
| **baza (SQLite)** | jeden plik `data/awesome.db` z całym katalogiem; zwykły plik, możesz go skasować i przebudować |
| **FTS5** | wbudowany w SQLite szybki indeks tekstowy — dzięki niemu szukanie trwa milisekundy |
| **metadane listy** | gwiazdki, język, opis listy z GitHuba |
| **metadane narzędzia** | gwiazdki, język i czy żyje repozytorium **samego narzędzia** |
| **consensus (zgoda)** | narzędzie wskazane przez ilu **różnych** autorów list — nasz główny ranking |
| **jakość listy** | 0–1: czy lista ma opisy, czy duplikaty, czy jej linki żyją, czy jest aktualna |
| **score** | punkty narzędzia (0–100) z tych wszystkich sygnałów |
| **backfill** | dociąganie brakujących metadanych list |
| **enrich** | sprawdzanie repozytoriów narzędzi (batch po 50 na zapytanie do API) |
| **build** | przebudowa bazy z lokalnych plików README (~2 min) |
| **fasetka** | klikalny filtr boczny, np. „język: Python” |

---

## Licencja

MIT — `LICENSE` w katalogu. Kod jest mój, ale **nazwy, linki i krótkie opisy
narzędzi pochodzą z cudzych awesome list** i należą do ich autorów. W bazie
są tylko adresy i nazwy repozytoriów (fakty, nie czyjeś treści), a same
README nie są dołączane do repo — pobierasz je na swój dysk przez
`./download.sh`.

## Znane ograniczenia (uczciwie)

* **Wyszukiwarka GitHuba oddaje maks. 1000 wyników na jedno zapytanie.**
  Dlatego pobieranie używa kilku zapytań naraz (`--wide`) i skaluje wyniki.
* **Prawdziwy język narzędzia** znamy tylko dla repozytoriów sprawdzonych przez
  `./awesome enrich`. Reszta zgadywana jest z adresu i opisu — stąd `?` tam,
  gdzie nie wiadomo. Ranking celowo nie ufa temu zgadywaniu.
* **Linki poza GitHubem** sprawdzamy tylko na żądanie:
  `./awesome validate --non-github --limit 500`.
* **Nie sprawdzamy, czy narzędzie jest bezpieczne.** Sygnały przy repozytoriach
  (archiwalne, dawno nieaktualizowane) to wskazówki do sprawdzenia, nie etykieta.
  Przeczytaj kod i release'y, zanim cokolwiek zainstalujesz.

---

## Dla tych, którzy chcą wejść głębiej

<details>
<summary>Struktura projektu</summary>

```
awesome              # wygodny wrapper: ./awesome <komenda>
download.sh          # pobieranie README list z GitHuba (bash + gh + jq)
extract_tools.py     # budowa bazy z lokalnych README
data/awesome.db      # baza SQLite (generowana, w .gitignore)
offline-db/          # pobrane README list (generowane, w .gitignore)

core/store.py        # schemat bazy, migracje, zapis metadanych
core/parser.py       # wyciąganie narzędzi z markdown (listy i tabele)
core/langmap.py      # język / platforma / domena / czyszczenie URL-i
core/scoring.py      # consensus, jakość listy, ranking
core/aliases.py      # synonimy („port scanner” → nmap, masscan…)
core/md.py           # własny renderer Markdown → HTML (bez CDN)
core/builder.py      # orkiestracja builda
core/backfill.py     # metadane list
core/enrich.py       # metadane repozytoriów narzędzi
core/status.py       # stan danych i plan odświeżenia
core/tools_db.py     # zapytania (search, fasetki, ranking)
core/database.py     # zapytania po listach/repozytoriach
core/curator.py      # kolekcje + instalacja
core/validator.py    # weryfikacja linków
core/trust.py        # sygnały ryzyka przy repozytoriach
cli/awesome_cli.py   # CLI
cli/tui.py           # TUI (curses)
web/app.py           # Flask UI
web/templates/       # szablony Jinja2
tests/smoke_test.py  # 32 testy (CI)
```

</details>

<details>
<summary>Jak liczymy ranking</summary>

`score` (0–100) to świadoma korekta nad „sortuj po gwiazdkach listy”:

| Składowa | Waga | Znaczenie |
|---|---|---|
| `consensus` | 0.28 | w ilu **niezależnych** listach jest narzędzie × jakość tych list |
| `own_stars` | 0.22 | gwiazdki **samego narzędzia** (z API), nie listy |
| `quality` | 0.14 | jakość listy: opisy, unikalność, żywe linki, świeżość, rozmiar |
| `alive` | 0.14 | link sprawdzony i żywy |
| `desc` | 0.10 | ma sensowny opis |
| `list_stars` | 0.06 | gwiazdki listy (słaby sygnał) |
| `known` | 0.06 | mamy metadane narzędzia z API |

Dodatkowo `underrated` (dobra jakość, mało gwiazdek) i `hidden_gem` (mało list,
wysoki score). `./awesome why <nazwa>` pokazuje rozkład punktów.

</details>

<details>
<summary>Wymagania i licencja</summary>

* Python 3.8+ (SQLite z FTS5; bez FTS5 działa fallback na LIKE)
* Flask ≥ 3.0 — tylko dla web UI
* `gh`, `jq`, `curl` — tylko do pobierania i enrichmentu
* `curses` z biblioteki standardowej — tylko dla TUI

MIT — używaj, zmieniaj, dziel się.
Autor: [Arkadiusz Słowik](https://github.com/technoporada)

</details>
