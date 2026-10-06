# 🔥 Awesome Core

## Czym to jest, w jednym zdaniu

**Ściąga wszystkie awesome listy z GitHuba do jednego katalogu na Twoim dysku
i pozwala szybko znaleźć narzędzie — po nazwie, języku, systemie albo temacie —
całkowicie bez internetu.**

Na przykład chcesz „coś do OSINT na Windowsa w PowerShellu". Wpisujesz:

```bash
./awesome search osint --os windows --lang PowerShell
```

i dostajesz listę narzędzi z kilku różnych awesome list naraz, posortowaną tak,
że na górze są te, które **niezależni kuratorzy wskazali w wielu listach**
(a nie tylko te z jednej głośnej listy).

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
`./awesome enrich --limit 20000`. To samo w przeglądarce: strona `/refresh`
z czterema przyciskami. Żadnych cronów, daemonów ani procesów w tle.

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
