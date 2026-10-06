#!/usr/bin/env python3
"""web/app.py — Awesome Core: Flask UI (CLI / TUI / Web na jednym silniku)."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from flask import (
    Flask, abort, flash, redirect, render_template, request, url_for,
)


BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from core import md, status as status_mod, store  # noqa: E402
from core.ai_librarian import recommend as ai_recommend  # noqa: E402
from core.curator import ToolCurator  # noqa: E402
from core.database import AwesomeDB  # noqa: E402
from core.shortlist import Shortlist  # noqa: E402
from core.tools_db import ToolsDB  # noqa: E402
from core.trust import assess_repo  # noqa: E402

app = Flask(__name__)
app.secret_key = os.environ.get("AWESOME_SECRET_KEY") or os.urandom(32)


README_DIR = BASE_DIR / "offline-db" / "data" / "readmes"


INDEX_FILE = BASE_DIR / "offline-db" / "data" / "index.json"


AI_CACHE_TTL = 300


AI_MIN_INTERVAL = 10

_ai_cache = {}
_ai_last_request = {}
_readme_cache = {}

tools_db = None
repo_db = None
curator = None
shortlist = None


def get_shortlist():
    global shortlist
    if shortlist is None:
        shortlist = Shortlist(BASE_DIR / "data")
    return shortlist


def dbs():
    global tools_db, repo_db, curator
    if tools_db is None:
        tools_db = ToolsDB(BASE_DIR / "data")
    if repo_db is None:
        repo_db = AwesomeDB(BASE_DIR / "data")
    if curator is None:
        curator = ToolCurator(BASE_DIR / "data")
    return tools_db, repo_db, curator


def _int_arg(name, default=0):
    try:
        return int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default


def read_readme(repo_name, use_cache=True):
    _, repo_db, _ = dbs()
    metadata = repo_db.get_repo(repo_name)
    if not metadata:
        return ""
    path = README_DIR / f"{metadata['owner']}__{metadata['name']}.md"
    if not path.exists():
        return ""
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if use_cache and key in _readme_cache:
        return _readme_cache[key]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    _readme_cache[key] = text
    if len(_readme_cache) > 64:
        for stale in list(_readme_cache)[:16]:
            _readme_cache.pop(stale, None)
    return text


def readme_path(repo_name):
    _, repo_db, _ = dbs()
    metadata = repo_db.get_repo(repo_name)
    if not metadata:
        return None
    path = README_DIR / f"{metadata['owner']}__{metadata['name']}.md"
    return path if path.exists() else None


def find_tool(needle):
    """Szuka narzędzia po znormalizowanym URL-u albo po nazwie."""
    tools, _, _ = dbs()
    if not needle:
        return None
    tool = tools.get_tool(needle)
    if tool:
        return tool
    tool = tools.get_tool_by_url(needle)
    if tool:
        return tool
    return tools.tool_by_name(needle)


@app.route("/")
def index():
    tools, repo_db, _ = dbs()
    stats = tools.stats()
    return render_template(
        "index.html",
        stats=stats,
        langs=tools.langs(min_count=20, limit=18),
        platforms=tools.platforms(min_count=20, limit=12),
        domains=tools.domains(min_count=20, limit=12),
        best_lists=tools.best_lists(n=12, min_tools=20),
        top_lists=tools.top_lists(12),
    )


@app.route("/search")
def search():
    tools, _, _ = dbs()
    query = request.args.get("q", "").strip()
    filters = {
        "lang": request.args.get("lang") or None,
        "platform": request.args.get("os") or request.args.get("platform") or None,
        "domain": request.args.get("domain") or None,
        "source": request.args.get("list") or None,
        "min_stars": _int_arg("min_stars", 0),
        "alive_only": request.args.get("alive") == "1",
        "sort": request.args.get("sort", "score"),
    }
    min_consensus = _int_arg("min_consensus", 0)
    results = []
    hints = []
    if query:
        results = tools.search(query, limit=200, **filters)
        if min_consensus:
            results = [t for t in results if t["lists_count"] >= min_consensus]
        tools.disambiguate(results)
        hints = tools.narrowing_hints(query, filters, len(results))
    return render_template(
        "search.html",
        results=results[:100],
        total=len(results),
        query=query,
        filters=filters,
        min_consensus=min_consensus,
        hints=hints,
        langs=tools.langs(min_count=5, limit=40),
        platforms=tools.platforms(min_count=5, limit=30),
        domains=tools.domains(min_count=10, limit=25),
    )


@app.route("/lang/<name>")
def lang_page(name):
    return _facet_page("lang", name)


@app.route("/os/<name>")
def platform_page(name):
    return _facet_page("platform", name)


@app.route("/domain/<name>")
def domain_page(name):
    return _facet_page("domain", name)


def _facet_page(kind, name):
    tools, _, _ = dbs()
    sort = request.args.get("sort", "score")
    min_stars = _int_arg("min_stars", 0)
    limit = min(500, _int_arg("limit", 150))
    if kind == "lang":
        results = tools.by_lang(name, limit=limit, sort=sort, min_stars=min_stars)
        label = f"język: {name}"
    elif kind == "platform":
        results = tools.by_platform(name, limit=limit, sort=sort, min_stars=min_stars)
        label = f"platforma: {name}"
    else:
        results = tools.by_domain(name, limit=limit, sort=sort, min_stars=min_stars)
        label = f"domena: {name}"
    return render_template(
        "facet.html",
        kind=kind, name=name, label=label, results=results, sort=sort,
        min_stars=min_stars, count=len(results),
        langs=tools.langs(min_count=5, limit=40),
        platforms=tools.platforms(min_count=5, limit=30),
        domains=tools.domains(min_count=10, limit=25),
    )


@app.route("/section/<name>")
def section(name):
    tools, _, _ = dbs()
    items = tools.by_section(name, limit=300)
    return render_template("facet.html", kind="section", name=name,
                           label=f"sekcja: {name}", results=items, sort="score",
                           min_stars=0, count=len(items),
                           langs=[], platforms=[], domains=[])


@app.route("/lists")
def lists_page():
    tools, _, _ = dbs()
    return render_template(
        "lists.html",
        best=tools.best_lists(n=120, min_tools=10),
    )


@app.route("/lists/clones")
def clones_page():
    tools, _, _ = dbs()
    threshold = float(request.args.get("overlap", 0.8))
    report = tools.clones_report(min_shared=_int_arg("min_shared", 20) or 20,
                                 threshold=threshold)
    return render_template(
        "clones.html",
        report=report, threshold=threshold,
        forks_known=int(tools.conn.execute(
            "SELECT COUNT(*) FROM repos WHERE is_fork=1 OR parent != ''"
        ).fetchone()[0]),
    )


@app.route("/underrated")
def underrated_page():
    tools, _, _ = dbs()
    lang = request.args.get("lang") or None
    return render_template(
        "facet.html", kind="underrated", name=lang or "wszystkie",
        label="niedoceniane: dobra jakość, mało gwiazdek",
        results=tools.underrated(limit=120, lang=lang), sort="underrated",
        min_stars=0, count=120, langs=tools.langs(min_count=5, limit=40),
        platforms=[], domains=[],
    )


@app.route("/gems")
def gems_page():
    tools, _, _ = dbs()
    lang = request.args.get("lang") or None
    return render_template(
        "facet.html", kind="gem", name=lang or "wszystkie",
        label="ukryte perełki: mało list, ale wysoki score",
        results=tools.gems(limit=120, lang=lang), sort="gem",
        min_stars=0, count=120, langs=tools.langs(min_count=5, limit=40),
        platforms=[], domains=[],
    )


@app.route("/list/<path:repo>")
def awesome_list(repo):
    tools, _, _ = dbs()
    stats = tools.get_list_stats(repo)
    if not stats:
        flash(f"Lista '{repo}' nie ma narzędzi w bazie", "error")
        return redirect(url_for("lists_page"))
    items = tools.by_source_repo(repo, limit=400)
    return render_template(
        "list.html", items=items, title=repo, stats=stats,
        clones=tools.list_clones(repo),
    )


@app.route("/tool/<path:needle>")
def tool_detail(needle):
    tools, _, local_curator = dbs()
    tool = find_tool(needle)
    if not tool:
        abort(404)
    similar = tools.find_similar(tool, limit=5)
    install = local_curator.detect_install_method(tool)
    explain = tools.explain(tool)
    mentions = explain["mentions"]
    excerpt_html = ""
    excerpt_toc = []
    source = tool.get("source_repo")
    if source:
        text = read_readme(source)
        if text:
            section = md.excerpt(text, tool.get("name", ""), max_chars=20000)
            excerpt_html, excerpt_toc = md.render(
                section, base_url=md.raw_github_url(source)
            )
    return render_template(
        "tool.html",
        kept=get_shortlist().has(tool["url_norm"]),
        tool=tool,
        similar=similar,
        install=install,
        explain=explain,
        mentions=mentions,
        excerpt_html=excerpt_html,
        excerpt_toc=md.render_toc(excerpt_toc, limit=12),
    )


@app.route("/repo/<path:name>")
def repo_detail(name):
    tools, repo_db, _ = dbs()
    repo = repo_db.get_repo(name)
    if not repo:
        flash(f"Lista '{name}' nie istnieje w bazie", "error")
        return redirect(url_for("index"))
    text = read_readme(name)
    body, toc = md.render(text, base_url=md.raw_github_url(name))
    path = readme_path(name)
    return render_template(
        "repo.html",
        repo=repo,
        readme_html=body,
        toc=md.render_toc(toc),
        raw_link=f"/readme/{name}",
        has_readme=bool(text),
        readme_size=path.stat().st_size if path else 0,
        trust=assess_repo(repo),
        clones=tools.list_clones(name),
        quality=repo.get("quality", 0),
        tool_count=repo.get("unique_tool_count", 0),
        top_tools=tools.by_source_repo(name, limit=12),
        sections=tools.get_list_stats(name) or {},
    )


@app.route("/readme/<path:name>")
def readme_raw(name):
    """Surowy lokalny README (bez renderu) — do podglądu w <pre>."""
    text = read_readme(name)
    if not text:
        abort(404)
    return render_template("raw.html", name=name, text=text)


@app.route("/shortlist")
def shortlist_page():
    entries = get_shortlist().items()
    if request.args.get("markdown") == "1":
        text = get_shortlist().to_markdown(
            title=_first_arg(request.args, "title", "Moja lista narzędzi")
        )
        return render_template("shortlist.html", entries=entries, markdown=text)
    return render_template(
        "shortlist.html", entries=entries,
        markdown=_first_arg(request.args, "markdown", ""),
    )


def _first_arg(args, name, default=""):
    value = args.get(name)
    return value.strip() if value else default


@app.route("/shortlist/add", methods=["POST"])
def shortlist_add():
    tools, _, _ = dbs()
    needle = request.form.get("tool", "").strip()
    note = request.form.get("note", "").strip()
    tool = tools.get_tool_by_url(needle) or tools.tool_by_name(needle)
    if not tool:
        flash(f"Nie znaleziono narzędzia: {needle}", "error")
        return redirect(url_for("index"))
    _status, message = get_shortlist().add(tool, note)
    flash(f"{message}: {tool['name']}", "success")
    return redirect(request.form.get("back") or f"/tool/{tool['url_norm']}")


@app.route("/shortlist/remove", methods=["POST"])
def shortlist_remove():
    get_shortlist().remove(request.form.get("url_norm", "").strip())
    flash("Usunięto z twojej listy", "success")
    return redirect(url_for("shortlist_page"))


@app.route("/mentions/<path:needle>")
def mentions_page(needle):
    tools, _, _ = dbs()
    tool = find_tool(needle)
    if not tool:
        abort(404)
    return render_template(
        "mentions.html", tool=tool, mentions=tools.mentions(tool["url_norm"])
    )


@app.route("/category/<name>")
def category(name):
    _, repo_db, _ = dbs()
    repos = repo_db.list_category(name)
    if not repos:
        flash(f"Brak tematu '{name}'", "error")
        return redirect(url_for("index"))
    return render_template("list.html", items=repos, title=name, stats=None)


@app.route("/random")
def random_page():
    tools, _, _ = dbs()
    return render_template("facet.html", kind="random", name="losowe",
                           label="losowe narzędzia",
                           results=tools.random(20), sort="score",
                           min_stars=0, count=20, langs=[], platforms=[], domains=[])


@app.route("/stats")
def stats_page():
    tools, repo_db, _ = dbs()
    stats = tools.stats()
    mentions = tools.conn.execute("SELECT COUNT(*) FROM tool_mentions").fetchone()[0]
    repos = tools.conn.execute(
        "SELECT COUNT(*) total, SUM(CASE WHEN stars > 0 THEN 1 ELSE 0 END) with_meta,"
        " SUM(CASE WHEN archived = 1 THEN 1 ELSE 0 END) archived FROM repos"
    ).fetchone()
    consensus = tools.conn.execute(
        "SELECT COUNT(*) FROM tools WHERE lists_count > 1"
    ).fetchone()[0]
    alive = tools.conn.execute(
        "SELECT COUNT(*) FROM tools WHERE alive IS NOT NULL"
    ).fetchone()[0]
    return render_template(
        "stats.html", stats=stats, mentions=mentions, repos=dict(repos),
        consensus=consensus, alive=alive,
        langs=tools.langs(min_count=5, limit=25),
        platforms=tools.platforms(min_count=5, limit=20),
        domains=tools.domains(min_count=10, limit=20),
        best_lists=tools.best_lists(n=10, min_tools=50),
    )


@app.route("/help")
def help_page():
    return render_template("help.html")


@app.route("/installed")
def installed_page():
    _, _, local_curator = dbs()
    return render_template("installed.html", installed=local_curator.list_installed())


@app.route("/tool/action", methods=["POST"])
def tool_action():
    _, _, local_curator = dbs()
    name = request.form.get("tool_name", "").strip()
    action = request.form.get("action", "").strip()
    tools, _, _ = dbs()
    if action not in {"install", "uninstall"}:
        flash("Nieprawidłowa akcja", "error")
        return redirect(url_for("index"))
    result = (
        local_curator.install_tool(name)
        if action == "install"
        else local_curator.uninstall_tool(name)
    )
    if result["status"] in {"installed", "already_installed", "uninstalled"}:
        flash(result.get("message", "Gotowe"), "success")
    else:
        flash(result.get("message", "Operacja nieudana"), "error")
    tool = find_tool(name)
    if tool:
        return redirect(f"/tool/{tool['url_norm']}")
    return redirect(url_for("index"))


@app.route("/add", methods=["GET", "POST"])
def add_repo():
    if request.method == "GET":
        return render_template("add.html")
    url_value = request.args.get("url", "").strip().rstrip("/")
    if not url_value:
        flash("Podaj URL repozytorium", "error")
        return redirect(url_for("add_repo"))
    if "github.com" in url_value:
        parts = url_value.split("github.com/")[-1].strip("/").split("/")
        if len(parts) < 2:
            flash("Nieprawidłowy URL GitHub", "error")
            return redirect(url_for("add_repo"))
        owner, name = parts[0], parts[1]
    else:
        flash("Tylko GitHub jest wspierany", "error")
        return redirect(url_for("add_repo"))

    ok, message = fetch_readme(owner, name)
    if not ok:
        flash(f"Błąd: {message}", "error")
        return redirect(url_for("add_repo"))
    flash(f"Dodano {owner}/{name} ({message}). Przebuduj bazę: python3 extract_tools.py", "success")
    return redirect(url_for("repo_detail", name=f"{owner}/{name}"))


def fetch_readme(owner, name):
    full = f"{owner}/{name}"
    path = README_DIR / f"{owner}__{name}.md"
    if path.exists():
        return True, "Już pobrane"
    path.parent.mkdir(parents=True, exist_ok=True)
    for branch in ("main", "master"):
        result = subprocess.run(
            ["curl", "-f", "-s", "-o", str(path), "-w", "%{http_code}", "-L",
             f"https://raw.githubusercontent.com/{full}/{branch}/README.md"],
            capture_output=True, text=True, timeout=30,
        )
        if result.stdout.strip() == "200":
            return True, "Pobrano"
    if path.exists():
        path.unlink()
    return False, "Nie znaleziono README"


@app.route("/add/topic", methods=["POST"])
def add_topic():
    topic = request.form.get("topic", "").strip()
    if not topic:
        flash("Podaj topic", "error")
        return redirect(url_for("add_repo"))
    return run_step("download", topic)


def run_step(step, topic="awesome-list", limit=20000):
    """Wspólna ścieżka dla /refresh, /rebuild i /add/topic — synchronicznie."""
    if step == "build":
        code, log = run_script([sys.executable, "extract_tools.py"], timeout=1800)
    elif step == "backfill":
        code, log = run_script(
            [sys.executable, "-c",
             "from core import backfill; backfill.clean_index(); backfill.backfill()"],
            timeout=1800,
        )
    elif step == "enrich":
        code, log = run_script(
            [sys.executable, "core/enrich.py", "--limit", str(limit)], timeout=7200
        )
    elif step == "download":
        code, log = run_script(
            ["bash", "download.sh", topic, "100", "1", "20", "--wide"], timeout=7200
        )
    else:
        flash("Nieznany krok", "error")
        return redirect(url_for("refresh_page"))
    global tools_db, repo_db
    tools_db = repo_db = None
    dbs()
    return render_template(
        "refresh.html",
        status=status_mod.collect(BASE_DIR / "data"),
        step=step,
        log="\n".join(log),
        code=code,
        ok=code == 0,
        message="Gotowe." if code == 0 else "Zakończone z błędem — szczegóły poniżej.",
    )


def run_script(args, timeout=None):
    """Odpala składnię i zwraca (kod wyjścia, końcówkę logu)."""
    try:
        result = subprocess.run(
            args, cwd=str(BASE_DIR), capture_output=True, text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, "Przekroczono limit czasu — przerwane."
    log = (result.stdout or "") + (result.stderr or "")
    return result.returncode, log.strip().split("\n")[-60:]


@app.route("/refresh", methods=["GET", "POST"])
def refresh_page():
    """Ręczne odświeżanie: każdy krok jednym kliknięciem, nic nie leci w tle."""
    current = status_mod.collect(BASE_DIR / "data")
    if request.method == "POST":
        step = request.form.get("step", "")
        topic = request.form.get("topic", "awesome-list").strip() or "awesome-list"
        limit = _int_arg("limit", 20000) or 20000
        return run_step(step, topic=topic, limit=limit)
    return render_template("refresh.html", status=current, step=None, log=None, code=None)


@app.route("/rebuild", methods=["POST"])
def rebuild():
    return run_step("build")


@app.route("/api/ai/ask", methods=["GET", "POST"])
def api_ai_ask():
    tools, _, _ = dbs()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        q = str(data.get("q", "")).strip()
    else:
        q = request.args.get("q", "").strip()
    if not q:
        return {"error": "parametr 'q' wymagany"}, 400
    try:
        limit = max(1, min(_int_arg("limit", 5), 10))
    except (TypeError, ValueError):
        limit = 5
    client = request.remote_addr or "local"
    cache_key = (q.lower(), limit)
    now = time.monotonic()
    cached = _ai_cache.get(cache_key)
    if cached and now - cached[0] < AI_CACHE_TTL:
        return cached[1]
    last = _ai_last_request.get(client, 0)
    if now - last < AI_MIN_INTERVAL:
        return {"error": "Za dużo zapytań AI. Spróbuj ponownie za chwilę."}, 429
    _ai_last_request[client] = now
    try:
        result = ai_recommend(tools, q, limit=limit)
        _ai_cache[cache_key] = (now, result)
        return result
    except RuntimeError as exc:
        return {"error": str(exc)}, 503


@app.route("/api/tools")
def api_tools():
    tools, _, _ = dbs()
    query = request.args.get("q", "").strip()
    if not query:
        return {"error": "parametr 'q' wymagany"}, 400
    results = tools.search(
        query, limit=min(50, _int_arg("limit", 20)),
        lang=request.args.get("lang") or None,
        platform=request.args.get("os") or None,
    )
    return {
        "query": query,
        "count": len(results),
        "tools": [
            {
                "name": t["name"], "url": t["url"], "lang": t["lang"],
                "platform": t["platform"], "score": t["score"],
                "lists": t["lists_count"], "stars": t["tool_stars"],
                "source": t["source_repo"],
            }
            for t in results
        ],
    }


def find_free_port(default=5001):
    for candidate in range(default, default + 60):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", candidate)) != 0:
                return candidate
    return default


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else find_free_port()
    if store.db_ready(BASE_DIR / "data"):
        dbs()
        print(f"Awesome Core — http://localhost:{port}")
    else:
        print("Brak bazy. Zbuduj ją ręcznie: ./awesome build  (lub python3 extract_tools.py)")
        print(f"Web UI bez bazy: http://localhost:{port}/refresh")
    app.run(debug=False, port=port)
