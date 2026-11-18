# 🔥 Awesome Core

[![PyPI](https://img.shields.io/pypi/v/awesome-core?label=PyPI)](https://pypi.org/project/awesome-core/)
[![Python versions](https://img.shields.io/pypi/pyversions/awesome-core)](https://pypi.org/project/awesome-core/)
[![CI](https://github.com/twojlogin/awesome-core/actions/workflows/ci.yml/badge.svg)](https://github.com/twojlogin/awesome-core/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](#license)
[![MCP Registry](https://img.shields.io/badge/MCP%20Registry-io.github.twojlogin%2Fawesome--core-6f42c1)](https://registry.modelcontextprotocol.io/v0/servers?search=awesome-core)

<!-- mcp-name: io.github.twojlogin/awesome-core -->

**English** · [Polski](README_pl.md)

## What this is (in one sentence)

**It downloads GitHub "awesome" lists into one local catalog on your disk and lets you quickly find tools — by name, language, OS, or topic — completely offline.**

For example, if you want "something for OSINT that runs on Windows", you can type:

```bash
./awesome search osint --os windows
```

You get tools from multiple awesome lists at once, ranked so that items surfaced by **independent curators across multiple lists** tend to appear higher (rather than only items from one popular list).

> **Filters combine with AND, so they can narrow results quickly.** `--os windows --lang PowerShell` may leave very few results for "osint" — and sometimes not the tool you expected. The program warns when filters are too narrow and suggests which one to relax.
>
> Rule of thumb: add a filter only when you have more results than you need.

---

## If you have no time — three commands

```bash
./awesome start      # 1. does the setup/build for you (download, build, ready)
./awesome search nmap
./awesome web        # opens the web UI
```

`./awesome start` explains each step and how long it may take. Nothing runs silently in the background — progress is visible.

---

## What you need before starting

**One thing: Python 3.8 or newer.**

| Requirement | Purpose | Check |
|---|---|---|
| **Python 3.8+** | runtime — the only hard dependency | `python3 --version` |

**You do not need** jq, curl, GitHub CLI, or to create a venv manually:

- fetching lists works over plain HTTPS (`core/api.py`) — without `gh` it is slower due to GitHub unauthenticated search limits, but it works;
- Flask for the web UI is installed automatically on first `./awesome web`;
- the tool reports missing pieces (`./awesome doctor`).

If you have `gh` and log in (`gh auth login`), downloads can be much faster and `enrich` becomes available. That is an optimization, not a requirement.

Linux example:

```bash
sudo apt install python3               # or: sudo dnf install python3
```

Optional (faster downloads and tool metadata):

```bash
gh auth login                          # GitHub CLI, one-time
```

**Windows works without bash.** Use `awesome.cmd` in PowerShell or by double-clicking:

```powershell
awesome.cmd start
awesome.cmd web
```

`download.sh` remains as a wrapper that calls Python — it no longer depends on jq/curl/shell loops.

Flask for the web UI is installed **automatically** on first `./awesome web`. If it fails (e.g. no network/proxy), the program prints manual instructions.

**You do not need** to know SQL, program, configure internals, or enable automatic updates. If something is wrong, `./awesome status` tells you what to run.

---

## First run, step by step

### `./awesome start`

The program checks prerequisites, then:

| Step | What it does | Typical time |
|---|---|---|
| 1 | downloads awesome list READMEs from GitHub (skips what you already have) | 10–25 min |
| 2 | extracts tools into the database | ~2 min |
| 3 | fetches list stars/languages metadata | ~1 min |
| 4 | **starts Web UI** and waits | — |

**If the database is already built, `start` does not re-download everything.** It reports tool count and starts the UI. Rebuild requires an explicit choice:

```bash
./awesome start --rebuild    # deletes DB and rebuilds from scratch (~2 min)
./awesome refresh            # quick refresh (download + light backfill of missing + rebuild)
./awesome refresh --full     # full refresh (includes enrich with limit)
```

This prevents an accidental `./awesome start` from discarding work.

**Honest note:** `start` does not query GitHub for each individual tool repository. Ranking works immediately (based on curator consensus), but tool star counts may initially be estimates from list context, not verified repo stars. To improve that:

```bash
./awesome enrich      # 30–60 min, queries many repositories
./awesome build       # ~2 min, to incorporate data into ranking
```

Or in one go from scratch:

```bash
./awesome start --full   # download → build → backfill → enrich → build
```

You usually do this once. You can interrupt (Ctrl+C) — progress is saved and reruns continue. Without GitHub auth, `enrich` refuses with an explanation instead of pretending to work.

Quick path if you're short on time:

```bash
./awesome start --skip-download     # build from what you already have
```

### Daily use

```bash
./awesome search "port scanner"                    # natural search
./awesome search osint --lang Python               # filter: Python
./awesome search "active directory" --os windows   # filter: Windows
./awesome langs                                    # languages in catalog
./awesome platforms                                # platforms: Windows, Linux, Docker...
./awesome domains                                  # topics: osint, security, network...
./awesome why nmap                                 # explain ranking/score
./awesome mentions nmap                            # in how many lists it appears
./awesome audit                                    # check for suspicious/poisoned lists
./awesome audit sindresorhus/awesome               # audit a single repository
./awesome leaks                                    # scan for possible leaked secrets (local)
./awesome leaks --readmes                          # also scan raw README files (offline)
./awesome lists                                    # top lists
./awesome info nmap                                # details + install hint
./awesome install nmap                             # install (git clone)
```

### Your own shortlist

When you find something useful, save it and export Markdown later:

```bash
./awesome shortlist add nmap --note "network scanning"
./awesome shortlist
./awesome shortlist emit --title "My OSINT list" --group domain
./awesome shortlist emit --out my-list.md
```

The web UI offers the same: **☆ Add to shortlist** on tool pages, shortlist view and Markdown export. In TUI press `k`.

`watch` is separate — it tracks **repositories of lists** you want to follow (new tools in a favorite list), not tools:

```bash
./awesome watch add sindresorhus/awesome
./awesome watch check          # what changed since last check
```

Both lists are local; nothing polls in the background.

### TUI — keys

```text
/  search              l  next language      o  next platform
d  next domain          s  change sort        a  clear filters
g  hidden gems          u  underrated         Enter  details
k  add to shortlist     i  install            ?  help
q  quit
```

### Four interfaces, one catalog

```bash
./awesome            # terminal — fastest for quick search
./awesome tui        # interactive terminal UI
./awesome web        # browser UI (port printed on start)
./awesome help       # all commands
```

---

## Maintenance (nothing runs by itself)

```bash
./awesome status     # what is in DB, when refreshed, what is missing
./awesome refresh    # quick refresh: download + light backfill of missing metadata + rebuild
./awesome refresh --full  # full refresh: + backfill + enrich (limited) + rebuild
```

- `--enrich-limit N` controls enrich size in full mode (default 1000).
- `./awesome status` suggests the exact next command (e.g. `./awesome enrich`). The web UI provides a `/refresh` page with actions. No cron jobs, daemons, or background processes.

**Numbers note:** status reports how many **repositories remain to query**, not "tools without stars". Multiple tools may point to the same repo, and non-GitHub links (articles, videos, docs) **do not and cannot have GitHub stars**.

---

## What is inside

<!-- STAN: these numbers depend on downloaded lists — no hardcoded values.
     Check current: ./awesome status -->
| | |
|---|---|
| tools in database | depends on downloaded lists |
| sources (repositories) | depends on downloaded lists |

Always check current numbers with: `./awesome status`.

**Honest note:** there is no AI here. No language models select, rate, or rank tools. It is plain Python parsing README files from GitHub lists and computing metrics. If numbers in docs differ from your DB, run `./awesome status`.

## Connect an AI agent (MCP) — local, no API keys

You can expose the catalog to a local MCP-capable agent (Claude, Cursor, etc.) as a tool source. The agent receives ranking based on independent curator consensus, not on what is most repeated in a single README.

```bash
./awesome mcp --demo    # preview: see JSON-RPC exchange without an agent
./awesome mcp           # server listens on stdin (normal usage)
```

The server provides 5 tools: `search_tools`, `find_undiscovered_tools`, `explain_tool`, `lists_with_tool`, and `catalog_facets`.

Example `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "awesome-core": {
      "command": "/full/path/to/awesome-core/awesome",
      "args": ["mcp"]
    }
  }
}
```

Or from PyPI without cloning (package `awesome-core`, also in MCP Registry as `io.github.twojlogin/awesome-core`):

```json
{
  "mcpServers": {
    "awesome-core": {
      "command": "uvx",
      "args": ["awesome-core"],
      "env": { "AWESOME_DATA_DIR": "/full/path/to/awesome-core/data" }
    }
  }
}
```

`AWESOME_DATA_DIR` must point to a directory containing a database built by `./awesome start` — the package does not ship data.

Notes:
- **No network access from the server.** No API keys, no accounts, read-only local SQLite access. No side-effect tools.
- **Instant startup** — the server reads an already-built DB.
- Results are plain text with numbers (stars, independent list count, score) so agents can cite/compare.
- Protocol: JSON-RPC 2.0 over stdin/stdout; logs go to stderr.

---

## Where data comes from — and safety

**Sources:** lists are discovered via public GitHub API topics like `topic:awesome-list` (and related topics in wider modes), sorted by popularity signals — no "recommended" random sources.

**Nothing from external repos is executed:**
- READMEs are **data**. The parser extracts links with regex; content is never passed to `eval/exec/shell`.
- `awesome install` performs `git clone --depth 1` (no remote hook execution by this tool).
- Web output and Markdown rendering escape HTML.

**Main risk vector: untrusted descriptions in model context.** MCP returns text written by unknown authors. Therefore:
- descriptions pass through `core/untrusted.py` (filters instruction-like patterns, role markers, HTML tags, dangerous command snippets, etc., leaving `[filtered: ...]` markers);
- MCP `initialize` tells the agent this is third-party content, not instructions;
- you can inspect with:

```bash
./awesome untrusted
```

This is pattern-based filtering, not a guarantee. Treat descriptions as data.

You can also scan locally for possible leaked secrets/tokens in descriptions and README files:

```bash
./awesome leaks
./awesome leaks --readmes   # also scan raw README files (offline)
```

This is heuristic (masked results, no external reporting) — useful for awareness, not a security guarantee.

---

## Principle: no AI in the core

| Layer | AI? | Network? |
|---|---|---|
| parser, DB, ranking, clones, shortlist, TUI, web | **no** | **no** — reads local `data/awesome.db` |
| `core/mcp.py` (agent adapter) | outside process | no — JSON-RPC over stdio |
| `download`, `enrich`, `backfill`, `validate`, `install` | no | yes, only on explicit command |

- Core dependency is stdlib; Flask is for web UI.
- No models/embeddings/neural nets/LLMs in ranking. Scoring is explicit arithmetic (`core/scoring.py`).
- MCP is an edge adapter; removing it should not break core functionality.
- Tests enforce this boundary (including AI-library import checks and MCP isolation).

---

## Can the catalog be poisoned?

The catalog is built from **third-party repositories**, so malicious or low-quality lists/links are possible.

```bash
./awesome audit
```

Signals include (heuristic, for manual review): many tools with zero stars, low-diversity or single-owner external GitHub link sets, self-promotion of **other repositories** by the same owner (links inside the audited list's own repo are treated separately as internal/monorepo structure), many dead links, clones of other lists, and suspicious links/domains (typosquatting-like, IPs, punycode, etc.). Audit may also add context labels such as auto-generated star dumps or same-owner multi-list low-reputation farms.

Important caveats:
- **Not malware scanning of target repos.** It flags suspicious signals, not proof of malice.
- **Signals are for manual review**, not automatic verdicts.
- Ranking/build also reduce single-source influence: tools benefit from agreement across independent lists, clone detection reduces duplicate influence, and suspected SEO farms/mass aggregators are tracked to limit their impact on consensus/quality.
- **`awesome install` is only `git clone`.** It does not execute remote code, but you decide what to do with cloned code afterward.

Rule of thumb: a tool from one new/unknown list is a reason to inspect, not blindly install.

---

## Glossary

| Term | Meaning |
|---|---|
| **awesome list** | a curated list of links/tools maintained on GitHub |
| **database (SQLite)** | local file `data/awesome.db`; generated, can be rebuilt |
| **FTS5** | SQLite full-text search index used for fast search |
| **list metadata** | stars/language/description of a list repo |
| **tool metadata** | stars/language/liveness of a tool repo |
| **consensus** | how many independent list authors point to a tool |
| **list quality** | 0–1 score (descriptions, uniqueness, live links, freshness, size, etc.) |
| **score** | tool score (0–100) from multiple signals |
| **backfill** | fetch missing list metadata |
| **enrich** | fetch tool repository metadata |
| **build** | rebuild DB from local READMEs |
| **facet** | clickable filter (e.g. language/platform/domain) |

**The program does not recommend tools.** It shows metrics and evidence (consensus, stars, list quality, sources) and leaves decisions to you.

---

## License

MIT — see `LICENSE`. Code is licensed under MIT, but names/links/short descriptions of tools come from third-party awesome lists and belong to their authors. The database stores references/facts; third-party READMEs are downloaded locally by the user.

## Known limitations (honest)

- **Ranking reads metadata/text, not repository code.** Names, descriptions, stars, topics and READMEs can be misleading; the tool does not inspect source code of target repos.
- `./awesome selfcheck` (15 known tools) is a useful sanity check but not perfect (e.g. similarly named/fan repos can outrank originals).
- Many entries appear in only one list (consensus = 0 for long tail).
- Many entries are non-GitHub links (articles/videos/docs) and cannot have GitHub stars.
- GitHub search has API/result limits; downloads use multiple queries/strategies.
- True tool language is known only for repos enriched via API; others may be inferred (`?` where unknown).
- Non-GitHub links are validated only on demand (`./awesome validate --non-github --limit 500`).
- This is not a security guarantee for installing/running third-party tools. Review code/releases before installing anything.

---

## For deeper details

See Polish `README.md` for the full, original long-form documentation (project structure, scoring details, and extended notes).

## Project links

- Repository: https://github.com/twojlogin/awesome-core
- Issues: https://github.com/twojlogin/awesome-core/issues
- MCP Registry: `io.github.twojlogin/awesome-core`
