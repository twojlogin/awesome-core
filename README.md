# 🔥 Awesome Core

**Offline tool manager — 234k+ tools from 2,047 awesome lists. CLI / TUI / Web.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Tools](https://img.shields.io/badge/tools-234k+-brightgreen.svg)]()
[![Repos](https://img.shields.io/badge/repos-2k+-orange.svg)]()

> **Keywords:** `awesome-lists` `tool-manager` `cli` `tui` `web-ui` `offline` `search-engine` `python` `open-source`

---

## What is it?

Awesome Core is a local database of every tool from every awesome list on GitHub. Search 234k tools in <20ms. Install with one command. Build your own collections. All offline after first download.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/technoporada/awesome-core.git
cd awesome-core

# 2. Install
pip install -r requirements.txt

# 3. Download data (first run)
./download.sh awesome-list

# 4. Extract tools
python3 extract_tools.py

# 5. Search!
./awesome search vpn
./awesome search osint
./awesome search docker
```

## Features

| Feature | Description |
|---------|-------------|
| **234,349 tools** | From 2,047 awesome lists on GitHub |
| **2,285 repos** | With stars, forks, languages, categories |
| **<20ms search** | Inverted index, fuzzy matching |
| **Install tools** | `git clone`, `pip install`, `npm install` |
| **Collections** | Build your own curated tool lists |
| **AI Librarian** | Ask in natural language, get tool recommendations |
| **Web UI** | Beautiful Flask dashboard |
| **CLI** | Full terminal interface |
| **TUI** | Curses-based terminal UI |
| **Offline** | Zero API calls after download |

## CLI Reference

```bash
# Tools
awesome search <query>           # search 234k tools
awesome install <tool>           # install (git clone)
awesome uninstall <tool>         # uninstall
awesome installed                # list installed

# Repos
awesome repos <query>            # search repos (2,285)
awesome list <category>          # list by category
awesome top [n]                  # top by stars
awesome random                   # random repo

# Download
awesome fetch owner/repo         # download README
awesome topic <topic>            # download lists by topic
awesome rebuild                  # rebuild search index

# Collections
awesome create <name> <desc>     # create collection
awesome add <collection> <tool>  # add to collection
awesome collections              # list collections
awesome collection <name>        # show collection

# AI
awesome ask <question>           # natural language search

# Web
awesome web [port]               # launch Flask UI
```

## Web UI

```bash
python3 web/app.py              # auto-port
python3 web/app.py 8888         # specific port
```

| Route | Description |
|-------|-------------|
| `/` | Home — 234k tools, top lists |
| `/search?q=vpn` | Search tools |
| `/section/Security` | Tools by section |
| `/list/avelino/awesome-go` | Tools from specific list |
| `/random` | Random 20 tools |
| `/add` | Add repo / topic / rebuild |

## Architecture

```
awesome-core/
├── core/
│   ├── database.py          # AwesomeDB — repo search, categories
│   ├── tools_db.py          # ToolsDB — 234k tools, search index
│   ├── curator.py           # ToolCurator — install, collections
│   ├── ai_librarian.py      # AI recommendations
│   └── validator.py         # Link validation
├── cli/
│   └── awesome_cli.py       # CLI interface
├── web/
│   ├── app.py               # Flask: routes, search, API
│   └── templates/           # Jinja2 templates
├── data/                    # Generated on first run
│   ├── tools.json           # 234,349 tools
│   ├── search_index.json    # Inverted index (236k words)
│   ├── summary_enriched.csv # 2,285 repos with stars
│   └── collections.json     # Your collections
├── offline-db/              # Downloaded readmes
├── awesome                  # Shell wrapper
├── download.sh              # Download lists from GitHub
├── extract_tools.py         # Extract tools from READMEs
└── requirements.txt         # flask>=3.0.0
```

## API (Python)

```python
from core.database import AwesomeDB
from core.tools_db import ToolsDB
from core.curator import ToolCurator

# Search repos
db = AwesomeDB()
results = db.search("osint")

# Search tools
tools = ToolsDB()
results = tools.search("vpn", limit=50)

# Install & collections
curator = ToolCurator()
curator.install_tool("nmap")
curator.create_collection("my-tools", "My tools", ["nmap", "masscan"])
```

## Dependencies

- Python 3.8+
- Flask >= 3.0.0 (web only)
- curl + jq (download only)
- gh CLI (optional, for auth)
- curses (stdlib, TUI only)

## Philosophy

- **Zero hardcoded paths** — `Path(__file__).parent.parent`
- **One engine, three interfaces** — CLI / TUI / Web
- **Auto-port** — no conflicts with other services
- **Local data** — zero API after download
- **GitHub stars** — we know what's popular

## License

MIT — use it, modify it, share it.

## Author

**Arkadiusz Słowik** — [technoporada](https://github.com/technoporada)

```
██╗   ██╗ █████╗ ██████╗  █████╗
██║   ██║██╔══██╗██╔══██╗██╔══██╗
██║   ██║███████║██████╔╝███████║
╚██╗ ██╔╝██╔══██║██╔══██╗██╔══██║
 ╚████╔╝ ██║  ██║██║  ██║██║  ██║
  ╚═══╝  ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
```

---

*Built with passion for open source tools* 🔧
