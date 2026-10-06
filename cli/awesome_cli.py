#!/usr/bin/env python3
"""
awesome — CLI Awesome Core: lokalne wyszukiwanie i sortowanie awesome list.

PIERWSZE URUCHOMIENIE (zacznij tutaj):
  awesome start                      — robi wszystko za Ciebie i mówi co się dzieje
  awesome search nmap               — szukaj
  awesome web                        — przeglądarka

Codziennie:
  awesome status                    — co jest w bazie i co warto odświeżyć
  awesome refresh                   — pobierz nowe listy i przebuduj bazę (nic nie działa w tle)

Wyszukiwanie:
  awesome search <zapytanie>          — szukaj narzędzi offline
      --limit N                       — liczba wyników (domyślnie 20)
      --lang <język>                  — filtr języka (python, powershell, go…)
      --os <platforma>                — filtr platformy (windows, linux, docker…)
      --domain <domena>               — osint, security, network, devops, ml…
      --list <owner/repo>             — tylko z jednej listy
      --min-stars N                   — minimalne gwiazdki
      --min-consensus N               — minimalna liczba niezależnych list
      --sort score|stars|consensus|underrated|gem|name
      --alive                         — tylko sprawdzone, żywe linki

Listy i fasetki:
  awesome langs | platforms | domains — co jest w bazie
  awesome lists                       — najlepsze listy wg jakości
awesome clones                      — kopie i forki list (wpływ na ranking)
awesome untrusted                   — skan opisów pod kątem prompt injection
awesome mcp                         — serwer MCP (stdio) dla lokalnych agentów
awesome mcp --demo                  — pokaż wymianę JSON-RPC
  awesome list <owner/repo>           — narzędzia z listy
  awesome mentions <url|nazwa>        — w ilu listach jest narzędzie
  awesome why <url|nazwa>             — rozkład rankingu
  awesome underrated [--lang X]        — dobre z małych list
  awesome gems [--lang X]             — ukryte perełki
  awesome repos <zapytanie>           — szukaj list/repozytoriów
  awesome top [n]                     — top list wg gwiazdek

Zarządzanie danymi:
  awesome build                       — przebuduj bazę z README
  awesome enrich [--limit N]          — metadane repozytoriów narzędzi (GitHub)
  awesome backfill [--force]          — metadane brakujących list
  awesome validate [--limit N]        — sprawdź martwe linki
  awesome export json|csv [ścieżka]  — eksport bazy

Twoja własna lista:
  awesome shortlist add nmap --note   — włóż narzędzie
  awesome shortlist                   — co masz na liście
  awesome shortlist emit --out moja.md — Markdown do wklejenia w listę

Inne:
  awesome tui                         — interfejs terminalowy (curses)
  awesome web [port]                  — uruchom Flask
  awesome demo | stats | info | install | uninstall | installed
  awesome create|add|collection|collections | audit | watch | fetch | topic | check
"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.curator import ToolCurator  # noqa: E402
from core.database import AwesomeDB  # noqa: E402
from core.tools_db import ToolsDB  # noqa: E402
from core.trust import assess_repo, audit_repo, github_token  # noqa: E402
from core.watcher import RepoWatcher  # noqa: E402


BASE_DIR = Path(__file__).parent.parent


README_DIR = BASE_DIR / "offline-db" / "data" / "readmes"


INDEX_FILE = BASE_DIR / "offline-db" / "data" / "index.json"


def print_tools(results, limit=20, show_url=True):
    if not results:
        print("Brak wyników.")
        return
    shown_rows = results[:limit]
    for i, tool in enumerate(shown_rows, 1):
        lang = tool.get("lang") or "?"
        lists = tool.get("lists_count", 0)
        stars = tool.get("tool_stars") or tool.get("source_stars") or 0
        badge = f"{tool.get('score', 0):.0f} pkt"
        label = tool.get("display_name") or tool.get("name", "?")
        taken = tool.get("name_taken_by")
        suffix = f"  ← {taken} narzędzia o tej nazwie" if taken else ""
        print(f"  {i:2d}. {label}{suffix}")
        print(
            f"      {lang:<12} list: {lists:<3} gwiazdki: {stars:<7} "
            f"jakość listy: {badge}"
        )
        if tool.get("platform"):
            print(f"      platforma: {tool['platform']}")
        if tool.get("description"):
            print(f"      {tool['description'][:110]}")
        if show_url and tool.get("url"):
            print(f"      {tool['url']}")
    if len(results) > limit:
        print(f"  ... i {len(results) - limit} więcej")


def cmd_langs(db):
    print("\nJęzyki narzędzi (top 30):")
    for lang, count in db.langs(min_count=5, limit=30):
        print(f"  {count:>7}  {lang}")


def cmd_platforms(db):
    print("\nPlatformy:")
    for name, count in db.platforms(min_count=5, limit=30):
        print(f"  {count:>7}  {name}")


def cmd_domains(db):
    print("\nDomeny:")
    for name, count in db.domains(min_count=5, limit=30):
        print(f"  {count:>7}  {name}")


def cmd_lists(db, n=20):
    print(f"\nNajlepsze listy wg jakości ({n}):")
    for row in db.best_lists(n=n, min_tools=10):
        print(
            f"  {row['quality']:.2f}  {row['stars']:>7}★  "
            f"{row['unique_tool_count']:>5} narzędzi  {row['full_name']}"
        )


def cmd_list(db, repo_name):
    stats = db.get_list_stats(repo_name)
    tools = db.by_source_repo(repo_name, limit=200)
    if not tools:
        print(f"\nLista '{repo_name}' nie ma narzędzi w bazie.")
        return
    header = f"\n{repo_name}: {len(tools)} narzędzi"
    if stats:
        header += f" | jakość {stats.get('quality', 0):.2f} | {stats.get('stars', 0)}★"
    print(header)
    print_tools(tools, 40, show_url=False)


def cmd_mentions(db, needle):
    tool = db.get_tool_by_url(needle) or db.tool_by_name(needle)
    if not tool:
        print(f"Nie znaleziono narzędzia: {needle}")
        return
    mentions = db.mentions(tool["url_norm"])
    print(f"\n{tool['name']} — {tool['url']}")
    print(
        f"  {len(mentions)} list, {tool.get('owners_count', 0)} niezależnych autorów, "
        f"score {tool.get('score', 0):.1f}, lang {tool.get('lang') or '?'}"
    )
    for mention in mentions[:40]:
        print(f"  - {mention['source_repo']:<45} {mention['section']}")


def cmd_why(db, needle):
    tool = db.get_tool_by_url(needle) or db.tool_by_name(needle)
    if not tool:
        print(f"Nie znaleziono narzędzia: {needle}")
        return
    detail = db.explain(tool)
    print(f"\n{tool['name']} — score {detail['score']:.1f}")
    print(f"  niedoceniane: {detail['underrated']:.1f}")
    print("  rozkład:")
    for key, value, weight, points in detail["rows"]:
        print(f"    {key:<11} {value:>6.2f} × waga {weight:.2f} = {points:>5.1f} pkt")
    print(f"  listy ({len(detail['mentions'])}):")
    for mention in detail["mentions"][:10]:
        print(f"    - {mention['source_repo']}")


def cmd_underrated(db, limit=20, lang=None, platform=None):
    print("\nNiedoceniane (dobra jakość, mało gwiazdek):")
    print_tools(db.underrated(limit=limit, lang=lang, platform=platform), limit, show_url=False)


def cmd_gems(db, limit=20, lang=None):
    print("\nUkryte perełki:")
    print_tools(db.gems(limit=limit, lang=lang), limit, show_url=False)


def cmd_info(db, repo_db, curator, name):
    tool = db.get_tool_by_url(name) or db.tool_by_name(name)
    if not tool:
        print(f"Nie znaleziono narzędzia: {name}")
        return
    print(f"\n{tool['name']}")
    print(f"  URL: {tool['url']}")
    print(f"  Opis: {tool.get('description') or '-'}")
    print(f"  Język: {tool.get('lang') or '?'}")
    if tool.get("platform"):
        print(f"  Platforma: {tool['platform']}")
    if tool.get("domains"):
        print(f"  Domeny: {tool['tags']}")
    print(f"  Sekcja: {tool.get('section') or 'Other'}")
    if tool.get("subsection"):
        print(f"  Podsekcja: {tool['subsection']}")
    print(f"  Lista: {tool.get('source_repo')} ({tool.get('source_stars', 0)}★)")
    print(f"  Własne gwiazdki: {tool.get('tool_stars', 0)}")
    print(f"  W listach: {tool.get('lists_count', 0)} (autorów: {tool.get('owners_count', 0)})")
    if tool.get("clones_skipped"):
        print(f"  Pominięto kopie list: {tool['clones_skipped']} "
              "(nie liczą się do zgody kuratorów)")
    print(f"  Score: {tool.get('score', 0):.1f} | niedoceniane: {tool.get('underrated', 0):.1f}")
    if tool.get("alive") is True:
        print("  Link: żywy")
    elif tool.get("alive") is False:
        print(f"  Link: martwy ({tool.get('alive_reason')})")
    method = curator.detect_install_method(tool)
    print(f"  Instalacja: {method or 'brak automatycznej metody'}")
    repo = repo_db.get_repo(tool.get("source_repo", ""))
    if repo:
        report = assess_repo(repo)
        print(f"  Sygnały listy: {report['status']}")
        for item in report["attention"]:
            print(f"    ! {item}")
    print("  Przed instalacją przejrzyj repozytorium i jego instrukcję.")


def cmd_demo(repo_db, tools_db):
    print("\n=== Awesome Core — demo offline ===")
    stats = tools_db.stats()
    if not stats["total"]:
        print("Brak lokalnych danych: ./download.sh awesome-list && python3 extract_tools.py")
        return
    print(f"Narzędzia: {stats['total']} | list: {stats['lists']} | języki: {stats['langs']}")
    print("\n1) Szukanie OSINT:")
    print_tools(tools_db.search("osint", limit=3), 3, show_url=False)
    print("\n2) PowerShell pod Windows:")
    print_tools(
        tools_db.search("powershell", limit=3, lang="PowerShell", platform="windows"),
        3, show_url=False,
    )
    print("\n3) Zgodność kuratorów (najwięcej niezależnych list):")
    print_tools(tools_db.top_consensus(limit=3), 3, show_url=False)
    print("\n4) Niedoceniane perełki:")
    print_tools(tools_db.underrated(limit=3), 3, show_url=False)
    print("\nDalej: ./awesome why <nazwa> | ./awesome langs | ./awesome tui")


def cmd_repos(db, query):
    print(f"\nSzukaj list: {query}")
    results = db.search(query, limit=20)
    print(f"Znaleziono: {len(results)}\n")
    for i, (repo, _matches) in enumerate(results, 1):
        print(f"  {i:2d}. {repo['full_name']}  {repo['stars']}★  {repo.get('language') or '?'}")
        if repo.get("description"):
            print(f"      {repo['description'][:90]}")
        print(f"      jakość {repo.get('quality', 0):.2f} | {repo.get('unique_tool_count', 0)} narzędzi")


def cmd_random(db):
    tools = db.random(5)
    print("\nLosowe narzędzia:")
    print_tools(tools, 5)


def cmd_audit(db, name, online=False):
    repo = db.get_repo(name)
    if not repo and not online:
        print(f"Nie znaleziono listy: {name}")
        return
    if online:
        token = github_token()
        if not token:
            print("Brak tokena. Ustaw GITHUB_TOKEN albo zaloguj gh CLI.")
            return
        try:
            report = audit_repo(name, token)
        except (RuntimeError, ValueError) as exc:
            print(f"Audyt online nieudany: {exc}")
            return
    else:
        report = assess_repo(repo)
    print(f"\nOcena sygnałów: {name}")
    print(f"  Status: {report['status']}")
    for item in report["info"]:
        print(f"    - {item}")
    for item in report["attention"]:
        print(f"    ! {item}")
    print("  To są wskazówki, nie ocena złośliwości.")


def cmd_watch(args):
    if not args or (args[0] != "list" and len(args) < 2):
        print("Użycie: awesome watch add|list|check|remove [owner/repo]")
        return
    watcher = RepoWatcher()
    action = args[0]
    name = args[1] if len(args) > 1 else None
    try:
        if action == "add" and name:
            watcher.add(name)
            print(f"Dodano do obserwowanych: {name}")
        elif action == "remove" and name:
            print("Usunięto." if watcher.remove(name) else "Repo nie było obserwowane.")
        elif action == "list":
            for entry in watcher.list() or []:
                snapshot = entry.get("snapshot") or {}
                print(f"{entry['repo']} — {snapshot.get('checked_at', 'jeszcze nie sprawdzano')}")
        elif action == "check" and name:
            token = github_token()
            if not token:
                print("Brak tokena.")
                return
            snapshot, changes = watcher.check(name, token)
            print(f"Sprawdzono {name}: {snapshot['stars']}★, {snapshot['forks']} forków")
            for field, change in changes.items():
                print(f"  {field}: {change['old']} -> {change['new']}")
        else:
            print("Użycie: awesome watch add|list|check|remove [owner/repo]")
    except (RuntimeError, ValueError) as exc:
        print(f"Watcher: {exc}")


def cmd_stats(repo_db, tools_db, curator):
    stats = tools_db.stats()
    repo_stats = {"total": len(repo_db.repos)}
    curator_stats = curator.get_stats()
    print("\nStatystyki:")
    print(f"  Listy: {repo_stats.get('total', 0)}")
    print(f"  Narzędzia: {stats['total']}")
    print(f"  Wzmianki w listach: {tools_db.conn.execute('SELECT COUNT(*) FROM tool_mentions').fetchone()[0]}")
    print(f"  Języki: {stats['langs']} | sekcje: {stats['sections']}")
    print(f"  Z opisem: {stats['with_desc']} ({stats['with_desc'] * 100 // max(1, stats['total'])}%)")
    print(f"  Linki: żywe {stats['alive']} | martwe {stats['dead']} | nie sprawdzone {stats['unchecked']}")
    print(f"  Z metadanymi GitHub (prawdziwe gwiazdki/język): {stats['with_meta']}")
    print(f"  Kolekcje: {curator_stats.get('collections', 0)} | zainstalowane: {curator_stats.get('installed', 0)}")
    print("\n  Top języki:")
    for lang, count in tools_db.langs(min_count=50, limit=8):
        print(f"    {count:>7}  {lang}")
    print("\n  Top platformy:")
    for platform, count in tools_db.platforms(min_count=100, limit=6):
        print(f"    {count:>7}  {platform}")


def cmd_top(repo_db, n=10):
    print(f"\nTop {n} list wg gwiazdek:")
    for i, repo in enumerate(repo_db.top_repos(n, sort_by="stars"), 1):
        print(f"  {i:2d}. {repo['full_name']}  {repo['stars']}★  {repo.get('language') or '?'}")


def cmd_install(curator, tool_name):
    result = curator.install_tool(tool_name)
    if result["status"] == "installed":
        print(f"Zainstalowano: {result['path']}")
    elif result["status"] == "already_installed":
        print(f"Już zainstalowane: {result['path']}")
    else:
        print(f"Błąd: {result.get('message')}")


def cmd_uninstall(curator, tool_name):
    result = curator.uninstall_tool(tool_name)
    if result["status"] == "uninstalled":
        print("Odinstalowano.")
    else:
        print(f"Błąd: {result.get('message')}")


def cmd_installed(curator):
    installed = curator.list_installed()
    if not installed:
        print("\nBrak zainstalowanych narzędzi.")
        return
    print(f"\nZainstalowane ({len(installed)}):")
    for name, info in installed.items():
        print(f"  {name} — {info['method']} — {info['path']}")


def cmd_collections(curator):
    colls = curator.list_collections()
    if not colls:
        print("\nBrak kolekcji.")
        return
    print(f"\nKolekcje ({len(colls)}):")
    for name, info in colls.items():
        print(f"  {name} ({info['tool_count']} narzędzi) — {info['description']}")


def cmd_collection(curator, name):
    tools = curator.get_collection_tools(name)
    if not tools:
        print(f"\nKolekcja '{name}' nie istnieje lub jest pusta.")
        return
    coll = curator.collections.get(name, {})
    print(f"\n{coll.get('description') or name} ({len(tools)}):")
    print_tools(tools, 100, show_url=False)


def cmd_ask(tools_db, question):
    from core.ai_librarian import recommend

    print(f"\nAI Bibliotekarz: {question}")
    try:
        result = recommend(tools_db, question)
    except RuntimeError as exc:
        print(f"AI niedostępne: {exc}")
        return
    for i, rec in enumerate(result["recommendations"], 1):
        print(f"  {i}. {rec['tool']['name']}")
        print(f"     {rec['why']}")
    print(f"[via {result['provider']}]")


def cmd_web(port=None):
    sys.path.insert(0, str(BASE_DIR / "web"))
    from app import app

    if port is None:
        port = _free_port()
    print(f"Uruchamiam Flask na http://localhost:{port}")
    app.run(debug=False, port=port)


def _free_port(default=5001):
    import socket

    for candidate in range(default, default + 50):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", candidate)) != 0:
                return candidate
    return default


def cmd_tui():
    from cli.tui import run_tui

    run_tui()


def cmd_fetch(repo_str):
    from core import store

    if "/" not in repo_str:
        print("Użycie: awesome fetch owner/repo")
        return
    owner, name = repo_str.split("/", 1)
    full = f"{owner}/{name}"
    readme_file = README_DIR / f"{owner}__{name}.md"
    if readme_file.exists():
        print(f"Już pobrane: {full}")
        return
    readme_file.parent.mkdir(parents=True, exist_ok=True)
    for branch in ("main", "master"):
        result = subprocess.run(
            ["curl", "-f", "-s", "-o", str(readme_file), "-w", "%{http_code}", "-L",
             f"https://raw.githubusercontent.com/{full}/{branch}/README.md"],
            capture_output=True, text=True, timeout=30,
        )
        if result.stdout.strip() == "200":
            index = json.loads(INDEX_FILE.read_text(encoding="utf-8")) if INDEX_FILE.exists() else {}
            index[full] = {"owner": owner, "name": name, "readme_downloaded": True}
            INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
            conn = store.connect()
            store.upsert_repo(conn, full, {"readme_downloaded": True})
            store.mark_readme(conn, full, True)
            conn.close()
            print(f"Pobrano: {full} — przebuduj bazę: python3 extract_tools.py")
            return
        if readme_file.exists():
            readme_file.unlink()
    print(f"Błąd: nie znaleziono README dla {full}")


def cmd_topic(topic, sort="stars", wide=True):
    """Pobiera listy. --wide = kilka zapytań (limit GitHuba to 1000 wyników)."""
    args = ["bash", str(BASE_DIR / "download.sh"), topic, "100", "1", "20"]
    if sort:
        args.extend(["--sort", sort])
    if wide:
        args.append("--wide")
    print(f"Pobieram topic: {topic}" + (" (kilka zapytań)" if wide else ""))
    result = subprocess.run(args, cwd=str(BASE_DIR), check=False)
    if result.returncode != 0:
        print(f"Zakończone z kodem {result.returncode} — sprawdź `./awesome status`.")
    print("Gotowe. Następny krok: ./awesome build")


def cmd_build(export=None):
    args = [sys.executable, str(BASE_DIR / "extract_tools.py")]
    if export:
        args.extend(["--export", export])
    return subprocess.run(args, cwd=str(BASE_DIR), check=False).returncode


def _flag_int(args, name, default=None):
    if name not in args:
        return default
    index = args.index(name)
    if index + 1 < len(args):
        try:
            return int(args[index + 1])
        except ValueError:
            return default
    return default


def _flag_value(args, name, stop_at_flags=True):
    """Wartość po --name; przy stop_at_flags kończy na kolejnym --flag."""
    if name not in args:
        return None
    index = args.index(name)
    values = []
    for item in args[index + 1:]:
        if stop_at_flags and item.startswith("--"):
            break
        values.append(item)
    return " ".join(values) or None


def cmd_shortlist(tools_db, args):
    """Twoja własna lista: add / rm / list / emit."""
    from core.shortlist import Shortlist

    shortlist = Shortlist(BASE_DIR / "data")
    action = args[0] if args else "list"
    rest = args[1:]

    if action in {"list", "show", ""}:
        entries = shortlist.items()
        if not entries:
            print("\nTwoja lista jest pusta. Dodaj narzędzie:\n"
                  "  ./awesome shortlist add nmap --note \"do skanowania\"")
            return
        print(f"\nTwoja lista ({len(entries)}):\n")
        for index, entry in enumerate(entries, 1):
            tool = entry.get("tool") or {}
            name = tool.get("name") or entry["url_norm"]
            stars = tool.get("tool_stars") or 0
            lang = tool.get("lang") or "?"
            flag = "" if entry["in_db"] else "  (nie ma już w bazie)"
            note = f"\n      notatka: {entry['note']}" if entry["note"] else ""
            print(f"  {index:2d}. {name}{flag}")
            print(f"      {lang} · ⭐{stars:,} · dodane {entry['added_at'][:10]}{note}")
            print(f"      {tool.get('url') or entry['url_norm']}")

    elif action in {"add", "keep"}:
        if not rest:
            print("Użycie: awesome shortlist add <nazwa|url> [--notatka \"...\"]")
            return
        needle = rest[0]
        note = _flag_value(rest, "--note") or ""
        tool = tools_db.get_tool_by_url(needle) or tools_db.tool_by_name(needle)
        if not tool:
            print(f"Nie znaleziono narzędzia: {needle}")
            print("Podaj nazwę albo URL, np. ./awesome shortlist add nmap")
            return
        status, message = shortlist.add(tool, note)
        print(f"{message}: {tool['name']}")
        if status == "added":
            print(f"  {tool.get('url')}")
            print(f"  lista ma już {shortlist.count()} pozycji — "
                  "`awesome shortlist emit` zrobi z tego Markdown")

    elif action in {"rm", "remove", "del"}:
        if not rest:
            print("Użycie: awesome shortlist rm <nazwa|url>")
            return
        needle = rest[0]
        tool = tools_db.get_tool_by_url(needle) or tools_db.tool_by_name(needle)
        identity = tool["url_norm"] if tool else needle
        if shortlist.remove(identity):
            print(f"Usunięto z twojej listy: {tool['name'] if tool else needle}")
        else:
            print("Nie było tego na liście.")

    elif action in {"emit", "md", "markdown"}:
        title = _flag_value(rest, "--title") or "Moja lista narzędzi"
        out = None
        if "--out" in rest:
            out = rest[rest.index("--out") + 1]
            if out.endswith(".json"):
                text = shortlist.to_json(out)
                print(f"Zapisano JSON: {out}")
                return
        group_by = "lang"
        if "--group" in rest:
            group_by = rest[rest.index("--group") + 1]
        text = shortlist.to_markdown(title=title, out_path=out, group_by=group_by)
        if out:
            print(f"Zapisano Markdown: {out}")
            print("Wklej tę treść do swojej awesome list na GitHubie.")
        else:
            print()
            print(text)

    else:
        print("Użycie: awesome shortlist [list|add|rm|emit] [opcje]")
        print("  --note \"...\"   notatka przy add")
        print("  --out plik.md      zapisz zamiast wypisywać")
        print("  --group lang|platform|domain|section")
        print("  --title \"Moja lista\"")


def cmd_mcp(args):
    """Serwer MCP po stdio — lokalny katalog dla agentów (read-only, offline)."""
    from core import mcp

    return mcp.main(args)


def cmd_clones(tools_db, args):
    """Kopie i forki awesome list — i co z tego wynika dla rankingu."""
    overlap = _flag_value(args, "--min-overlap")
    threshold = float(overlap) if overlap else 0.8
    report = tools_db.clones_report(
        min_shared=_flag_int(args, "--min-shared", 20) or 20,
        threshold=threshold,
    )
    print("\nKopie i forki awesome list\n")
    print(f"  kopie treści (próg {threshold:.0%}): {report['copy_pairs']} par, "
          f"{report['clone_lists']} list")
    if threshold < 0.8:
        print("  (to tylko podgląd — consensus zawsze liczony z progiem 80%)")
    print(f"  forki repozytoriów:                     {report['fork_pairs']} "
          f"({report['fork_lists']} list)")
    if report["lists_without_parent"]:
        print(f"  forki bez wskazanego rodzica:          {report['lists_without_parent']}")

    if report["copies"]:
        print("\nKopie treści:")
        for row in report["copies"][:20]:
            flag = " (ten sam autor)" if row["same_owner"] else ""
            print(f"  {row['shared']:>5} wspólnych ({row['overlap']:.0%})  "
                  f"{row['clone']}  →  {row['canonical']}{flag}")

    if report["forks"]:
        print("\nForki list (rodzic → fork):")
        for row in report["forks"][:25]:
            print(f"  {row['canonical']:<46} → {row['clone']:<44} "
                  f"{row['tools']} narzędzi")

    print("\nCo to zmienia: wzmianki z kopii i forków są w bazie, ale NIE liczą się")
    print("do zgody kuratorów (lists_count) — inaczej trzy kopie udawałyby trzy opinie.")
    print("Sprawdź konkretne narzędzie: ./awesome why <nazwa>")


def cmd_status():
    from core import status as status_mod

    for line in status_mod.render(status_mod.collect(BASE_DIR / "data")):
        print(line)


REQUIRED_TOOLS = [
    ("python3", "Python 3.8+ — sam program"),
    ("gh", "GitHub CLI — pobieranie list (gh auth login)"),
    ("jq", "jq — obróbka JSON z GitHuba"),
    ("curl", "curl — pobieranie plików"),
]


START_STEPS = [
    ("download", "Pobieram awesome listy z GitHuba", "5–15 min (jeśli już masz, szybciej)"),
    ("build", "Buduję bazę z pobranych plików", "ok. 2 min"),
    ("backfill", "Uzupełniam gwiazdki i języki list", "ok. 1 min"),
]


def check_requirements():
    """Zwraca listę problemów (pusta = wszystko OK)."""
    import shutil

    problems = []
    for tool, hint in REQUIRED_TOOLS:
        if not shutil.which(tool):
            problems.append(f"brakuje '{tool}' — {hint}")
    if not shutil.which("python3") or sys.version_info < (3, 8):
        problems.append("za stary Python — potrzebne 3.8 lub nowsze")
    if shutil.which("gh"):
        result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        if result.returncode != 0:
            problems.append("gh nie jest zalogowane — wpisz: gh auth login")
    return problems


def cmd_start(args):
    """Pierwsze uruchomienie: wszystko po kolei, po ludzku."""
    from core import status as status_mod

    print("=" * 66)
    print(" Awesome Core — pierwsze uruchomienie")
    print("=" * 66)

    problems = check_requirements()
    if problems:
        print("\nNie mogę jeszcze zacząć, bo brakuje kilku rzeczy:\n")
        for problem in problems:
            print(f"  ✗ {problem}")
        print("\nNa Linuksie zwykle wystarczy:")
        print("  sudo apt install python3 jq curl    # albo: sudo dnf install python3 jq curl")
        print("  gh auth login                       # logowanie do GitHuba")
        print("\nSprawdź potem: gh --version && jq --version && curl --version")
        return 1

    state = status_mod.collect(BASE_DIR / "data")
    readmes = state.get("readmes", 0) if state.get("ready") else 0
    steps = list(START_STEPS)
    if "--skip-download" in args:
        steps = [step for step in steps if step[0] != "download"]
        print(f"\nPominam pobieranie (masz już {readmes} plików README lokalnie).")

    print("\nPlan (nic nie działa w tle, widzisz postęp na każdym kroku):\n")
    for index, (_key, label, how_long) in enumerate(steps, 1):
        print(f"  {index}. {label}  [{how_long}]")
    print("\nZaczynam.\n")

    for index, (key, label, how_long) in enumerate(steps, 1):
        print("-" * 66)
        print(f"KROK {index}/{len(steps)}: {label}")
        print("-" * 66)
        started = time.perf_counter()
        if key == "download":
            cmd_topic(args[0] if args and not args[0].startswith("-") else "awesome-list",
                      wide="--no-wide" not in args)
        elif key == "build":
            cmd_build()
        elif key == "backfill":
            cmd_backfill()
        print(f"\n[✓] Krok {index} skończony w {time.perf_counter() - started:.0f}s\n")

    print("=" * 66)
    print(" Gotowe. Baza jest zbudowana.")
    print("=" * 66)
    for line in status_mod.render(status_mod.collect(BASE_DIR / "data"))[1:8]:
        print(line)
    print("\nCo teraz? Spróbuj jednego z tych:\n")
    print("  ./awesome search \"port scanner\"")
    print("  ./awesome search osint --os windows --lang PowerShell")
    print("  ./awesome tui                      # terminal, interaktywnie")
    print("  ./awesome web                      # przeglądarka")
    print("\nJeśli chcesz lepsze dane (prawdziwe gwiazdki i języki narzędzi):")
    print("  ./awesome enrich --limit 40000     # ~35 min, potem ./awesome build")
    return 0


def cmd_refresh(args):
    """Jedna komenda zamiast tła: download -> backfill -> enrich -> build."""
    steps = [a for a in args if not a.startswith("-")]
    limit = _flag_int(args, "--enrich-limit", 40000)
    dry_run = "--dry-run" in args
    wanted = set(steps) & {"download", "backfill", "enrich", "build"}
    plan = {}
    for name in ("download", "backfill", "enrich", "build"):
        plan[name] = (name in wanted) or (not wanted and f"--skip-{name}" not in args)
    print("[*] Odświeżanie bazy — wszystko na żądanie, w tle nic nie działa.")
    for name, enabled in plan.items():
        print(f"    {name}: {'tak' if enabled else 'pomijam'}")
    if dry_run:
        print("\n(dry-run: nic nie uruchamiam)")
        return
    want = plan

    if want["download"]:
        topic = steps[0] if steps and not steps[0].isdigit() else "awesome-list"
        print(f"\n=== 1/4 pobieranie list (topic: {topic}) ===")
        cmd_topic(topic)
    if want["backfill"]:
        print("\n=== 2/4 metadane list ===")
        cmd_backfill()
    if want["enrich"]:
        print(f"\n=== 3/4 metadane narzędzi (limit {limit}) ===")
        cmd_enrich(limit)
    if want["build"]:
        print("\n=== 4/4 przebudowa bazy ===")
        cmd_build()
    print()
    cmd_status()


def cmd_enrich(limit=None):
    from core import enrich

    return 0 if enrich.enrich(limit=limit) is not None else 1


def cmd_backfill(limit=None, force=False):
    from core import backfill

    backfill.clean_index()
    backfill.backfill(limit=limit, force=force)


def cmd_validate(limit=None, non_github=False):
    from core.validator import Validator

    report = Validator().validate_all(limit=limit, non_github=non_github)
    print(f"\nSprawdzono w tym przebiegu: {report['total_checked']}")
    print(f"  znalezionych metadanych: {report['github_found']}"
          + (f", sprawdzonych poza GitHubem: {report['non_github_checked']}"
             if non_github else ""))
    print(f"Stan całej bazy ({report['total']:,} narzędzi):")
    print(f"  żywych {report['alive']:,} · martwych {report['dead']:,} · "
          f"jeszcze nie sprawdzonych {report['unknown']:,}")
    print(f"  czas: {report['seconds']}s")


def cmd_untrusted():
    """Skan bazy pod kątem tekstu wyglądającego na instrukcje (prompt injection).

    Opisy w bazie napisali obcy ludzie. Dziś nie ma tam ani jednego
    "ignoruj poprzednie instrukcje", ale warto to sprawdzać samemu, zamiast
    ufać obietnicy. Ten sam filtr siedzi w serwerze MCP.
    """
    from core import store, untrusted

    conn = store.connect(read_only=True)
    tools, hits = untrusted.scan(conn)
    conn.close()
    print(f"\nSkan {tools:,} narzędzi pod kątem prompt injection")
    if not hits:
        print("  Czysto: nic nie wygląda na polecenia dla modelu.")
        return
    print(f"  Podejrzane: {len(hits)} (większość to fałszywe alarmy, np. "
          f'"Home Assistant" trafia w wzorzec "assistant:")')
    for hit in hits[:25]:
        print(f"  - {hit['name'][:38]:38} {hit['field']:11} "
              f"{', '.join(hit['findings'])}")
        print(f"      {hit['url']}")


def cmd_export(fmt, out=None, limit=None):
    from core import store

    conn = store.connect()
    path = Path(out) if out else BASE_DIR / "data" / f"tools.{fmt}"
    if fmt == "csv":
        count = store.export_csv(conn, path, limit)
    else:
        count = store.export_json(conn, path, limit)
    print(f"Zapisano {count} pozycji do {path}")


def cmd_check(curator):
    installed = curator.list_installed()
    if not installed:
        print("Brak zainstalowanych narzędzi.")
        return
    for name, info in installed.items():
        path = Path(info["path"])
        if not path.exists():
            print(f"  {name}: NIE ISTNIEJE")
            continue
        if info["method"] == "git":
            result = subprocess.run(
                ["git", "-C", str(path), "log", "-1", "--format=%h %ai"],
                capture_output=True, text=True,
            )
            print(f"  {name}: {result.stdout.strip() or 'brak commitów'}")
        else:
            print(f"  {name}: {info['method']} (bez weryfikacji)")


def _flag(args, name):
    """Wartość flagi albo None — bez awarii na dziwnym wejściu."""
    if name not in args:
        return None
    index = args.index(name)
    return args[index + 1] if index + 1 < len(args) else None


def _limit_from(args, default=20):
    """--limit N albo pozycyjna liczba. Śmieciowe wejście → default, nie wyjątek.

    Wcześniej "awesome lists --limit 5" kończyło się tracebackiem, a to jest
    dokładnie ten rodzaj błędu, przez który porzuca się narzędzie.
    """
    value = _flag(args, "--limit")
    if value is None:
        positional = [a for a in args if not a.startswith("-")]
        value = positional[0] if positional else None
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        if value is not None:
            print(f"Nie rozumiem '{value}' jako liczby — używam {default}.")
        return default


def parse_search_args(args):
    filters = {"limit": 20, "sort": "score", "min_stars": 0,
               "min_consensus": 0, "lang": None, "platform": None,
               "domain": None, "source": None, "alive_only": False}
    query_parts = []
    i = 0
    valued = {"--limit", "--lang", "--os", "--platform", "--domain", "--list",
              "--min-stars", "--min-consensus", "--sort"}
    while i < len(args):
        arg = args[i]
        if arg == "--alive":
            filters["alive_only"] = True
        elif arg in valued and i + 1 < len(args):
            key, value = arg, args[i + 1]
            if key == "--limit":
                filters["limit"] = max(1, int(value))
            elif key == "--lang":
                filters["lang"] = value
            elif key in {"--os", "--platform"}:
                filters["platform"] = value
            elif key == "--domain":
                filters["domain"] = value
            elif key == "--list":
                filters["source"] = value
            elif key == "--min-stars":
                filters["min_stars"] = int(value)
            elif key == "--min-consensus":
                filters["min_consensus"] = int(value)
            elif key == "--sort":
                filters["sort"] = value
            i += 1
        else:
            query_parts.append(arg)
        i += 1
    return " ".join(query_parts).strip(), filters


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "--help" or cmd == "-h" or cmd == "help":
        print(__doc__)
        return

    def dbs():
        return ToolsDB(), AwesomeDB(), ToolCurator()

    if cmd == "search" and args:
        query, filters = parse_search_args(args)
        if not query:
            print("Użycie: awesome search <zapytanie> [--lang python --os windows]")
            return
        tools_db, _, _ = dbs()
        min_consensus = filters.pop("min_consensus", 0)
        limit = filters.pop("limit")
        if min_consensus:
            results = tools_db.search(query, limit=min(limit * 5, 500), **filters)
            results = [t for t in results if t["lists_count"] >= min_consensus][:limit]
        else:
            results = tools_db.search(query, limit=limit, **filters)
        filters["limit"] = limit
        # Cztery narzędzia o nazwie "Sherlock" to cztery różne projekty —
        # bez właściciela laik widzi same duplikaty.
        tools_db.disambiguate(results)
        print(f"\nSzukaj: {query}")
        shown = {k: v for k, v in filters.items() if v not in (None, 0, False, "")}
        if shown:
            print("Filtry: " + " ".join(f"{k}={v}" for k, v in shown.items()))
        print(f"Znaleziono: {len(results)}\n")
        hints = tools_db.narrowing_hints(query, filters, len(results))
        if hints:
            key, value, count = hints[0]
            print(f"Uwaga: {len(hints)} filtry łączy AND i zostawiły "
                  f"{len(results)} wynik(ów).")
            for k, v, c in hints:
                print(f"    bez {k}={v}  →  {c} wyników")
            print()
        print_tools(results, filters["limit"])
    elif cmd in {"langs", "platforms", "domains"}:
        tools_db, _, _ = dbs()
        {"langs": cmd_langs, "platforms": cmd_platforms, "domains": cmd_domains}[cmd](tools_db)
    elif cmd == "lists":
        tools_db, _, _ = dbs()
        cmd_lists(tools_db, n=_limit_from(args, 20))
    elif cmd == "list" and args:
        tools_db, _, _ = dbs()
        cmd_list(tools_db, args[0])
    elif cmd in {"mentions", "why"} and args:
        tools_db, _, _ = dbs()
        (cmd_mentions if cmd == "mentions" else cmd_why)(tools_db, args[0])
    elif cmd == "underrated":
        tools_db, _, _ = dbs()
        lang = args[args.index("--lang") + 1] if "--lang" in args else None
        platform = args[args.index("--os") + 1] if "--os" in args else None
        limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 20
        cmd_underrated(tools_db, limit=limit, lang=lang, platform=platform)
    elif cmd in {"gems", "hidden_gem", "hidden-gem", "perelki", "perełki"}:
        tools_db, _, _ = dbs()
        cmd_gems(tools_db, limit=_limit_from(args, 20), lang=_flag(args, "--lang"))
    elif cmd in {"consensus", "top", "zgoda"}:
        tools_db, _, _ = dbs()
        print("\nNajwiększa zgoda kuratorów (niezależne listy):")
        print_tools(tools_db.top_consensus(limit=_limit_from(args, 20)),
                    _limit_from(args, 20), show_url=False)
    elif cmd == "info" and args:
        tools_db, repo_db, curator = dbs()
        cmd_info(tools_db, repo_db, curator, args[0])
    elif cmd == "demo":
        tools_db, repo_db, _ = dbs()
        cmd_demo(repo_db, tools_db)
    elif cmd == "repos" and args:
        _, repo_db, _ = dbs()
        cmd_repos(repo_db, " ".join(args))
    elif cmd == "random":
        tools_db, _, _ = dbs()
        cmd_random(tools_db)
    elif cmd == "audit" and args:
        _, repo_db, _ = dbs()
        cmd_audit(repo_db, args[0], online="--online" in args)
    elif cmd == "watch":
        cmd_watch(args)
    elif cmd == "stats":
        tools_db, repo_db, curator = dbs()
        cmd_stats(repo_db, tools_db, curator)
    elif cmd == "top":
        _, repo_db, _ = dbs()
        cmd_top(repo_db, int(args[0]) if args else 10)
    elif cmd == "install" and args:
        _, _, curator = dbs()
        cmd_install(curator, args[0])
    elif cmd == "uninstall" and args:
        _, _, curator = dbs()
        cmd_uninstall(curator, args[0])
    elif cmd == "installed":
        _, _, curator = dbs()
        cmd_installed(curator)
    elif cmd == "collections":
        _, _, curator = dbs()
        cmd_collections(curator)
    elif cmd == "collection" and args:
        _, _, curator = dbs()
        cmd_collection(curator, args[0])
    elif cmd == "create" and len(args) >= 2:
        _, _, curator = dbs()
        curator.create_collection(args[0], " ".join(args[1:]), [])
        print(f"Utworzono kolekcję: {args[0]}")
    elif cmd == "add" and len(args) >= 3:
        _, _, curator = dbs()
        print("Dodano." if curator.add_to_collection(args[0], args[1]) else "Brak kolekcji.")
    elif cmd == "ask" and args:
        tools_db, _, _ = dbs()
        cmd_ask(tools_db, " ".join(args))
    elif cmd in {"start", "start-here", "pierwszy-raz"}:
        sys.exit(cmd_start(args) or 0)
    elif cmd in {"shortlist", "moja-lista"}:
        tools_db, _, _ = dbs()
        cmd_shortlist(tools_db, args)
    elif cmd in {"mcp", "agent"}:
        sys.exit(cmd_mcp(args) or 0)
    elif cmd in {"clones", "kopie"}:
        tools_db, _, _ = dbs()
        cmd_clones(tools_db, args)
    elif cmd in {"status", "stan"}:
        cmd_status()
    elif cmd in {"refresh", "odswiez"}:
        cmd_refresh(args)
    elif cmd in {"build", "rebuild"}:
        sys.exit(cmd_build())
    elif cmd == "enrich":
        cmd_enrich(_flag_int(args, "--limit"))
    elif cmd == "backfill":
        cmd_backfill(_flag_int(args, "--limit"), force="--force" in args)
    elif cmd in {"untrusted", "trust"}:
        cmd_untrusted()
    elif cmd == "validate":
        cmd_validate(
            int(args[args.index("--limit") + 1]) if "--limit" in args else None,
            non_github="--non-github" in args,
        )
    elif cmd == "export" and args:
        # Nie: cmd_export(args[0], args[1] ...) — brało "--out" jako ścieżkę
        # i pisało plik o nazwie "--out" (171 MB) zamiast podanego miejsca.
        fmt = args[0]
        rest = args[1:]
        if rest and rest[0] in {"json", "csv"}:
            fmt, rest = rest[0], rest[1:]
        cmd_export(fmt, out=_flag(rest, "--out"), limit=_limit_from(rest, None))
    elif cmd == "check":
        _, _, curator = dbs()
        cmd_check(curator)
    elif cmd == "tui":
        cmd_tui()
    elif cmd == "web":
        cmd_web(int(args[0]) if args else None)
    elif cmd == "fetch" and args:
        cmd_fetch(args[0])
    elif cmd == "topic" and args:
        cmd_topic(args[0])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
