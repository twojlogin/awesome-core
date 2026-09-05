#!/usr/bin/env python3
"""
awesome — CLI do Awesome Tools Manager
Użycie:
  awesome search <query>          — szukaj narzędzi
  awesome repos <kategoria>       — szukaj repo (awesome lists)
  awesome list <kategoria>        — lista z kategorii
  awesome random                  — losowe repo
  awesome stats                   — statystyki
  awesome top [n]                 — top repo wg gwiazdek
  awesome install <tool>          — zainstaluj narzędzie
  awesome uninstall <tool>        — odinstaluj narzędzie
  awesome installed               — lista zainstalowanych
  awesome check                   — sprawdź aktualizacje
  awesome validate [n]            — waliduj linki GitHub (n=limit)
  awesome collection <name>       — pokaż kolekcję
  awesome collections             — lista kolekcji
  awesome create <name> <desc>    — utwórz kolekcję
  awesome add <collection> <tool> — dodaj do kolekcji
  awesome fetch <owner/repo>      — pobierz README z GitHub
  awesome topic <topic>           — pobierz listy z topicem
  awesome rebuild                 — przebuduj indeks
  awesome ask <pytanie>           — AI Bibliotekarz: pytanie po ludzku -> narzędzia
  awesome web [port]              — uruchamia Flask
"""

import sys
import json
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.database import AwesomeDB
from core.tools_db import ToolsDB
from core.curator import ToolCurator

BASE_DIR = Path(__file__).parent.parent
README_DIR = BASE_DIR / "offline-db" / "data" / "readmes"
INDEX_FILE = BASE_DIR / "offline-db" / "data" / "index.json"


def print_repos(results, limit=10):
    if not results:
        print("Brak wyników.")
        return
    for i, repo in enumerate(results[:limit], 1):
        name = repo.get("full_name", "?")
        stars = repo.get("stars", "?")
        lang = repo.get("language", "")
        cats = repo.get("categories", "")
        url = repo.get("html_url", "")
        desc = repo.get("description", "")[:60]
        star_str = f"stars={stars}" if stars else ""
        lang_str = f" | {lang}" if lang else ""
        print(f"  {i:2d}. {name}  {star_str}{lang_str}")
        if desc:
            print(f"      {desc}")
        print(f"      {cats} | {url}")
    if len(results) > limit:
        print(f"  ... i {len(results) - limit} więcej")


def print_tools(results, limit=20):
    if not results:
        print("Brak wyników.")
        return
    for i, tool in enumerate(results[:limit], 1):
        name = tool.get("name", "?")
        url = tool.get("url", "")
        desc = tool.get("description", "")[:60]
        source = tool.get("source_repo", "")
        print(f"  {i:2d}. {name}")
        if desc:
            print(f"      {desc}")
        print(f"      {url}")
        if source:
            print(f"      from: {source}")
    if len(results) > limit:
        print(f"  ... i {len(results) - limit} więcej")


def cmd_search_tools(tools_db, query):
    print(f"\nSzukaj narzędzi: {query}")
    results = tools_db.search(query)
    print(f"Znaleziono: {len(results)}\n")
    print_tools(results)


def cmd_repos(db, query):
    print(f"\nSzukaj repo: {query}")
    results = db.search(query)
    print(f"Znaleziono: {len(results)}\n")
    repos = [r for r, m in results]
    print_repos(repos)


def cmd_list(db, cat):
    print(f"\nKategoria: {cat}")
    results = db.list_category(cat)
    print(f"Repo: {len(results)}\n")
    print_repos(results)


def cmd_random(db):
    repo = db.random_repo()
    if repo:
        print(f"\nLosowe repo:")
        print(f"  Nazwa: {repo.get('full_name', '?')}")
        print(f"  Stars: {repo.get('stars', '?')}")
        print(f"  Language: {repo.get('language', '?')}")
        print(f"  Kategorie: {repo.get('categories', '')}")
        print(f"  URL: {repo.get('html_url', '')}")
    else:
        print("Brak repo w bazie.")


def cmd_stats(db, tools_db, curator):
    s = db.stats
    ts = tools_db.stats
    cs = curator.get_stats()
    print(f"\nStatystyki:")
    print(f"  Repo: {s.get('total', 0)}")
    print(f"  Narzędzia: {ts.get('total', 0)}")
    print(f"  Kategorie repo: {len(s.get('categories', {}))}")
    print(f"  Sekcje narzędzi: {len(ts.get('sections', {}))}")
    print(f"  Kolekcje: {cs.get('collections', 0)}")
    print(f"  Zainstalowane: {cs.get('installed', 0)}")
    print(f"\n  Top kategorie repo:")
    for cat, count in sorted(s.get("categories", {}).items(), key=lambda x: -x[1])[:5]:
        print(f"    {cat}: {count}")
    print(f"\n  Top sekcje narzędzi:")
    for sec, count in sorted(ts.get("sections", {}).items(), key=lambda x: -x[1])[:5]:
        print(f"    {sec}: {count}")


def cmd_top(db, n=10):
    print(f"\nTop {n} repo (wg gwiazdek):")
    results = db.top_repos(n, sort_by="stars")
    print_repos(results, n)


def cmd_install(curator, tool_name):
    print(f"\nInstaluję: {tool_name}")
    result = curator.install_tool(tool_name)
    if result["status"] == "installed":
        print(f"  Zainstalowano: {result['path']}")
    elif result["status"] == "already_installed":
        print(f"  Już zainstalowane: {result['path']}")
    else:
        print(f"  Błąd: {result['message']}")


def cmd_uninstall(curator, tool_name):
    print(f"\nOdinstalowuję: {tool_name}")
    result = curator.uninstall_tool(tool_name)
    if result["status"] == "uninstalled":
        print(f"  Odinstalowano.")
    else:
        print(f"  Błąd: {result['message']}")


def cmd_installed(curator):
    installed = curator.list_installed()
    if not installed:
        print("\nBrak zainstalowanych narzędzi.")
        return
    print(f"\nZainstalowane ({len(installed)}):")
    for name, info in installed.items():
        print(f"  {name}")
        print(f"    {info['path']}")
        print(f"    {info['method']} | {info.get('installed_at', '')}")


def cmd_collection(curator, name):
    tools = curator.get_collection_tools(name)
    if not tools:
        print(f"\nKolekcja '{name}' nie istnieje lub jest pusta.")
        return
    coll = curator.collections.get(name, {})
    print(f"\nKolekcja: {name}")
    print(f"Opis: {coll.get('description', '')}")
    print(f"Narzędzia ({len(tools)}):")
    for i, tool in enumerate(tools, 1):
        print(f"  {i}. {tool.get('name', '?')}")
        print(f"     {tool.get('url', '')}")


def cmd_collections(curator):
    colls = curator.list_collections()
    if not colls:
        print("\nBrak kolekcji.")
        return
    print(f"\nKolekcje ({len(colls)}):")
    for name, info in colls.items():
        print(f"  {name} ({info['tool_count']} narzędzi)")
        print(f"    {info['description']}")


def cmd_create_collection(curator, name, desc):
    curator.create_collection(name, desc, [])
    print(f"\nUtworzono kolekcję: {name}")


def cmd_add_to_collection(curator, collection, tool):
    if curator.add_to_collection(collection, tool):
        print(f"\nDodano {tool} do {collection}")
    else:
        print(f"\nNie znaleziono kolekcji: {collection}")


def cmd_ask(tools_db, question):
    """AI Bibliotekarz: naturalne pytanie -> rekomendacje z bazy."""
    from core.ai_librarian import recommend
    print(f"\n🤖 AI Bibliotekarz: {question}")
    print("Szukam w 234k narzedzi...\n")
    try:
        r = recommend(tools_db, question)
    except RuntimeError as e:
        print(f"AI niedostepne: {e}")
        print("Tip: sprobuj tez 'awesome search <slowo>' (klasyczne szukanie).")
        return
    for i, rec in enumerate(r["recommendations"], 1):
        t = rec["tool"]
        print(f"  {i}. {t['name']} ({t.get('source_stars', 0)}*)")
        print(f"     {rec['why']}")
        if t.get("url"):
            print(f"     {t['url']}")
        print()
    print(f"[via {r['provider']} | frazy: {', '.join(r['queries_used'][:4])}]")


def cmd_web(port=None):
    sys.path.insert(0, str(Path(__file__).parent.parent / "web"))
    from app import app, find_free_port
    if port is None:
        port = find_free_port()
    print(f"Uruchamiam Flask na http://localhost:{port}")
    app.run(debug=True, port=port)


def load_index():
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return {}


def save_index(idx):
    INDEX_FILE.write_text(json.dumps(idx, indent=2, ensure_ascii=False))


def cmd_fetch(repo_str):
    if "/" not in repo_str:
        print("Użycie: awesome fetch owner/repo")
        return

    owner, name = repo_str.split("/", 1)
    full = f"{owner}/{name}"
    safe_name = f"{owner}__{name}"
    readme_file = README_DIR / f"{safe_name}.md"

    if readme_file.exists():
        print(f"Już pobrane: {full}")
        return

    print(f"Pobieram: {full}")
    for branch in ["main", "master"]:
        raw = f"https://raw.githubusercontent.com/{full}/{branch}/README.md"
        result = subprocess.run(
            ["curl", "-s", "-o", str(readme_file), "-w", "%{http_code}", "-L", raw],
            capture_output=True, text=True, timeout=30
        )
        if result.stdout.strip() == "200":
            idx = load_index()
            idx[full] = {"owner": owner, "name": name, "readme_downloaded": True}
            save_index(idx)
            print(f"Pobrano: {full}")
            return

    if readme_file.exists():
        readme_file.unlink()
    print(f"Błąd: Nie znaleziono README dla {full}")


def cmd_topic(topic):
    print(f"Pobieram topic: {topic}")
    subprocess.run(
        ["bash", str(BASE_DIR / "download.sh"), topic, "100", "1"],
        cwd=str(BASE_DIR)
    )


def cmd_rebuild():
    print("Przebudowa tools.json...")
    subprocess.run(
        ["python3", str(BASE_DIR / "extract_tools.py")],
        cwd=str(BASE_DIR),
        capture_output=True
    )

    print("Przebudowa indeksu...")
    subprocess.run(
        ["python3", "-c", """
import json
from collections import defaultdict
tools = json.load(open('data/tools.json'))
index = defaultdict(list)
for i, tool in enumerate(tools):
    name = tool.get('name', '').lower()
    desc = tool.get('description', '').lower()
    text = f'{name} {desc}'
    words = set()
    for w in text.split():
        w = w.strip('.,;:!?()[]{}\"\\' -/')
        if len(w) >= 2:
            words.add(w)
    for w in words:
        index[w].append(i)
with open('data/search_index.json', 'w') as f:
    json.dump(dict(index), f)
"""],
        cwd=str(BASE_DIR),
        capture_output=True
    )

    print("Gotowe!")


def cmd_validate(limit=None):
    from core.validator import Validator
    v = Validator()

    if limit:
        print(f"Waliduję {limit} narzędzi...")
        report = v.validate_all(limit=limit)
    else:
        print("Waliduję wszystkie narzędzia...")
        report = v.validate_all()

    print(f"\nWyniki:")
    print(f"  Sprawdzono: {report['total_checked']}")
    print(f"  Żywe: {report['results']['alive']}")
    print(f"  Martwe: {report['results']['dead']}")
    print(f"  Rate limited: {report['results']['rate_limited']}")
    print(f"  Błędy: {report['results']['error']}")


def cmd_check():
    curator = ToolCurator()
    installed = curator.list_installed()
    if not installed:
        print("Brak zainstalowanych narzędzi.")
        return

    print(f"Sprawdzam {len(installed)} narzędzi...")
    for name, info in installed.items():
        path = Path(info["path"])
        if not path.exists():
            print(f"  {name}: NIE ISTNIEJE")
            continue

        if info["method"] == "git":
            result = subprocess.run(
                ["git", "-C", str(path), "log", "-1", "--format=%H %ai"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(" ", 1)
                commit = parts[0][:8]
                date = parts[1] if len(parts) > 1 else "?"
                print(f"  {name}: {commit} ({date})")
            else:
                print(f"  {name}: błąd")
        else:
            print(f"  {name}: {info['method']} (brak weryfikacji)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    db = AwesomeDB()
    tools_db = ToolsDB()
    curator = ToolCurator()
    cmd = sys.argv[1]

    if cmd == "search" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        cmd_search_tools(tools_db, query)
    elif cmd == "ask" and len(sys.argv) > 2:
        question = " ".join(sys.argv[2:])
        cmd_ask(tools_db, question)
    elif cmd == "repos" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        cmd_repos(db, query)
    elif cmd == "list" and len(sys.argv) > 2:
        cat = sys.argv[2]
        cmd_list(db, cat)
    elif cmd == "random":
        cmd_random(db)
    elif cmd == "stats":
        cmd_stats(db, tools_db, curator)
    elif cmd == "top":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        cmd_top(db, n)
    elif cmd == "install" and len(sys.argv) > 2:
        cmd_install(curator, sys.argv[2])
    elif cmd == "uninstall" and len(sys.argv) > 2:
        cmd_uninstall(curator, sys.argv[2])
    elif cmd == "installed":
        cmd_installed(curator)
    elif cmd == "collection" and len(sys.argv) > 2:
        cmd_collection(curator, sys.argv[2])
    elif cmd == "collections":
        cmd_collections(curator)
    elif cmd == "create" and len(sys.argv) > 3:
        cmd_create_collection(curator, sys.argv[2], " ".join(sys.argv[3:]))
    elif cmd == "add" and len(sys.argv) > 3:
        cmd_add_to_collection(curator, sys.argv[2], sys.argv[3])
    elif cmd == "fetch" and len(sys.argv) > 2:
        cmd_fetch(sys.argv[2])
    elif cmd == "topic" and len(sys.argv) > 2:
        cmd_topic(sys.argv[2])
    elif cmd == "rebuild":
        cmd_rebuild()
    elif cmd == "check":
        cmd_check()
    elif cmd == "validate":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        cmd_validate(limit)
    elif cmd == "web":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else None
        cmd_web(port)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
