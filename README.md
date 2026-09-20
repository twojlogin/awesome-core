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

# 4. Extract tools and build the local search index
python3 extract_tools.py

# 5. Search!
./awesome search vpn
./awesome search osint
./awesome search docker
```

To see the project without learning the commands first:

```bash
./awesome demo
```

The demo uses only the local dataset and never calls GitHub or an AI provider.

### OSINT / security quick start

Awesome Core is especially useful as a local catalogue for reconnaissance and
security tooling:

```bash
./awesome search osint
./awesome search reconnaissance
./awesome search subdomain
./awesome search port scanner
./awesome collections
```

Review a tool's repository before installing it. Git installation is limited
to repositories hosted on GitHub, GitLab, or Bitbucket.

Offline search accepts the same quality filters as the web interface:

```bash
./awesome search osint --limit 20
./awesome search reconnaissance --min-stars 100
./awesome search subdomain --alive
./awesome audit jivoi/awesome-osint
```

You can also keep a small local watch list. It never polls in the background:
only `watch check` makes one explicit GitHub API request and stores a snapshot
without the token:

```bash
./awesome watch add owner/repo
./awesome watch list
./awesome watch check owner/repo
./awesome watch remove owner/repo
```

For one repository, users with their own GitHub API access can request an
optional online audit. The token is read from `GITHUB_TOKEN` or `gh auth token`
and is never stored:

```bash
GITHUB_TOKEN=... ./awesome audit owner/repo --online
```

Repository metadata can show neutral maintenance information (for example,
that a project is archived or has not changed recently) and separate signals
worth checking manually. An old project may still be a valuable gem; these
signals do not label a project as safe or malicious.

The normal workflow is offline after the initial download:

```text
online:  download.sh -> README files + repository metadata
local:   extract_tools.py -> tools.json + search_index.json
offline: awesome CLI / TUI / Web -> search, read, filter, collect, install
```

In the Web UI, a tool page shows the install command with a copy button and a
controlled local install action. It is not an arbitrary shell terminal: only
the supported Awesome Core install operation can be triggered from the page.
The `/installed` page lists local installations and provides controlled
uninstall actions.
Tool pages can also expand the locally cached README of the awesome-list that
provided the tool, so browsing the catalogue does not require a network call.
The Web UI footer includes a small coffee easter egg; it does not collect
payments or send data anywhere.

## Features

| Feature | Description |
|---------|-------------|
| **234,349 tools** | From 2,047 awesome lists on GitHub |
| **2,285 repos** | With stars, forks, languages, categories |
| **<20ms search** | Inverted index, fuzzy matching |
| **Install tools** | `git clone`, `pip install`, `npm install` |
| **Collections** | Build your own curated tool lists |
| **Data pipeline** | Download, enrich, filter and sort awesome lists locally |
| **Web UI** | Beautiful Flask dashboard |
| **CLI** | Full terminal interface |
| **TUI** | Curses-based terminal UI |
| **Offline** | Zero API calls after download |

## CLI Reference

```bash
# Tools
awesome search <query>           # offline search
awesome search <query> --min-stars 100
awesome search <query> --limit 50
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

# Web
awesome web [port]               # launch Flask UI
```

## Web UI

```bash
python3 web/app.py              # auto-port
python3 web/app.py 8888         # specific port
```

The core workflow does not require an AI provider or API tokens. The optional
AI endpoint is rate-limited and caches identical questions for five minutes.
Set `AWESOME_SECRET_KEY` in the environment when persistent Flask sessions are
needed.

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
