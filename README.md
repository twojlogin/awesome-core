# Awesome Core

Lokalna baza danych awesome list z GitHuba. Trzy interfejsy (CLI/TUI/Web), jeden silnik.

## Co umiemy

- **234,349 narzędzi** z 2,047 awesome list
- **2,285 repo** z GitHuba (gwiazdki, forks, języki)
- **Szukanie** narzędzi i repo (< 20ms)
- **Instalacja** narzędzi (git, pip, npm)
- **Kolekcje** — twoje własne listy narzędzi
- **Web UI** — przeszukiwanie, dodawanie, gwiazdki
- **CLI** — pełna obsługa z terminala

## Struktura

```
awesome-core/
├── core/
│   ├── database.py          # AwesomeDB — repo, search, kategorie
│   ├── tools_db.py          # ToolsDB — 234k narzędzi, search index
│   └── curator.py           # ToolCurator — install, collections
├── cli/
│   └── awesome_cli.py       # CLI: search/fetch/topic/install/collections
├── tui/
│   └── awesome_tui.py       # TUI (curses)
├── web/
│   ├── app.py               # Flask: /, /search, /list, /add, /random
│   └── templates/           # Jinja2
├── offline-db/
│   └── data/
│       ├── readmes/         # 2,047 pobranych README
│       └── index.json       # Indeks readme
├── data/
│   ├── tools.json           # 234,349 narzędzi
│   ├── search_index.json    # Indeks odwrócony (236k słów)
│   ├── summary_enriched.csv # 2,285 repo z gwiazdkami
│   └── collections.json     # Twoje kolekcje
├── awesome                  # Wrapper: ./awesome search vpn
├── download.sh              # Pobieranie list z GitHub
├── extract_tools.py         # Wyciąganie narzędzi z README
└── requirements.txt         # flask>=3.0.0
```

## Szybki start

```bash
# Szukaj narzędzi
./awesome search vpn
./awesome search osint
./awesome search docker

# Szukaj repo
./awesome repos osint

# Stats
./awesome stats

# Web UI
./awesome web              # http://localhost:5000
```

## CLI

```bash
# Narzędzia
awesome search <query>           # szukaj narzędzi (234k)
awesome install <tool>           # zainstaluj (git clone)
awesome uninstall <tool>         # odinstaluj
awesome installed                # lista zainstalowanych

# Repo
awesome repos <query>            # szukaj repo (2,285)
awesome list <kategoria>         # lista z kategorii
awesome top [n]                  # top wg gwiazdek
awesome random                   # losowe repo

# Pobieranie
awesome fetch owner/repo         # pobierz README
awesome topic <topic>            # pobierz listy z topicem
awesome rebuild                  # przebuduj indeks

# Kolekcje
awesome create <name> <desc>     # utwórz kolekcję
awesome add <collection> <tool>  # dodaj do kolekcji
awesome collections              # lista kolekcji
awesome collection <name>        # pokaż kolekcję

# Web
awesome web [port]               # uruchamia Flask
```

## Web UI

```bash
python3 web/app.py              # auto-port
python3 web/app.py 8888         # konkretny port
```

Trasy:
| Route | Opis |
|---|---|
| `/` | Strona główna — 234k narzędzi, top listy |
| `/search?q=vpn` | Szukanie narzędzi |
| `/section/Security` | Narzędzia z sekcji |
| `/list/avelino/awesome-go` | Narzędzia z konkretnej listy |
| `/random` | Losowe 20 narzędzi |
| `/add` | Dodaj repo / topic / przebuduj |

## Pobieranie danych

```bash
# Pobierz awesome listy po topic
./download.sh awesome-list          # 11k+ list
./download.sh awesome-osint         # OSINT
./download.sh awesome-security      # Bezpieczeństwo
./download.sh awesome-list 100 12   # od strony 12

# Wyciągnij narzędzia
python3 extract_tools.py

# Przebuduj indeks
./awesome rebuild
```

## Silnik

### AwesomeDB (repo)
```python
from core.database import AwesomeDB
db = AwesomeDB()
results = db.search("osint")       # [(repo, score), ...]
repos = db.list_category("privacy")
repo = db.random_repo()
```

### ToolsDB (narzędzia)
```python
from core.tools_db import ToolsDB
db = ToolsDB()
results = db.search("vpn", limit=50)  # [tool, ...]
```

### ToolCurator (install/collections)
```python
from core.curator import ToolCurator
c = ToolCurator()
c.install_tool("tool-name")
c.create_collection("my-tools", "Moje narzędzia", ["tool1", "tool2"])
```

## Zależności

- Python 3.8+
- Flask >= 3.0.0 (tylko dla web)
- curl + jq (tylko dla download.sh)
- gh CLI (opcjonalnie, dla auth)
- curses (stdlib, tylko dla TUI)

## Filozofia

- Zero hardcoded ścieżek — `Path(__file__).parent.parent`
- Jeden silnik, trzy interfejsy
- Auto-port — nie konfliktuj z innymi serwisami
- Dane lokalne — zero API po pobraniu
- Gwiazdki z GitHuba — wiemy co jest popularne
