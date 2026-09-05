#!/usr/bin/env python3
"""web/app.py — Awesome Tools - Flask web interface"""

import sys
import json
import subprocess
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.tools_db import ToolsDB
from core.ai_librarian import recommend as ai_recommend

app = Flask(__name__)
app.secret_key = "awesome-tools"
db = ToolsDB()

BASE_DIR = Path(__file__).parent.parent
README_DIR = BASE_DIR / "offline-db" / "data" / "readmes"
INDEX_FILE = BASE_DIR / "offline-db" / "data" / "index.json"


def load_index():
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return {}


def save_index(idx):
    INDEX_FILE.write_text(json.dumps(idx, indent=2, ensure_ascii=False))


def fetch_readme(owner, name):
    full = f"{owner}/{name}"
    safe_name = f"{owner}__{name}"
    readme_file = README_DIR / f"{safe_name}.md"

    if readme_file.exists():
        return True, "Już pobrane"

    for branch in ["main", "master"]:
        raw = f"https://raw.githubusercontent.com/{full}/{branch}/README.md"
        result = subprocess.run(
            ["curl", "-s", "-o", str(readme_file), "-w", "%{http_code}", "-L", raw],
            capture_output=True, text=True, timeout=30
        )
        if result.stdout.strip() == "200":
            return True, "Pobrano"

    if readme_file.exists():
        readme_file.unlink()
    return False, "Nie znaleziono README"


@app.route("/")
def index():
    return render_template("index.html", stats=db.stats, top_sections=db.top_sections(15), top_lists=db.top_lists(15))


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    min_stars = int(request.args.get("min_stars", 0))
    alive_only = request.args.get("alive", "0") == "1"
    results = db.search(q, limit=100, min_stars=min_stars, alive_only=alive_only) if q else []
    return render_template("search.html", results=results, query=q, min_stars=min_stars, alive_only=alive_only)


@app.route("/section/<name>")
def section(name):
    items = db.by_section(name, limit=300)
    return render_template("list.html", items=items, title=name, subtitle=f"sekcja")


@app.route("/list/<path:repo>")
def awesome_list(repo):
    info = db.get_list_stats(repo)
    items = db.by_source_repo(repo)
    if not items:
        flash(f"Lista '{repo}' nie znaleziona", "error")
        return redirect(url_for("index"))
    return render_template("list.html", items=items, title=repo, subtitle=f"lista ({info['count']} narzędzi)")


@app.route("/tool/<path:url>")
def tool_detail(url):
    tool = db.get_tool_by_url(url)
    if not tool:
        flash("Narzędzie nie znalezione", "error")
        return redirect(url_for("index"))

    similar = db.find_similar(tool, limit=5)
    install_info = db.get_install_info(tool)
    return render_template("tool.html", tool=tool, similar=similar, install=install_info)


@app.route("/random")
def random_page():
    items = db.random(20)
    return render_template("list.html", items=items, title="Losowe", subtitle="")


@app.route("/help")
def help_page():
    return render_template("help.html")


@app.route("/add", methods=["GET", "POST"])
def add_repo():
    if request.method == "GET":
        return render_template("add.html")

    url = request.args.get("url", "").strip()
    if not url:
        flash("Podaj URL repozytorium", "error")
        return redirect(url_for("add_repo"))

    url = url.rstrip("/")
    if "github.com" in url:
        parts = url.split("github.com/")[-1].strip("/").split("/")
        if len(parts) >= 2:
            owner, name = parts[0], parts[1]
        else:
            flash("Nieprawidłowy URL GitHub", "error")
            return redirect(url_for("add_repo"))
    else:
        flash("Tylko GitHub jest wspierany", "error")
        return redirect(url_for("add_repo"))

    ok, msg = fetch_readme(owner, name)
    if not ok:
        flash(f"Błąd: {msg}", "error")
        return redirect(url_for("add_repo"))

    idx = load_index()
    full = f"{owner}/{name}"
    idx[full] = {"owner": owner, "name": name, "readme_downloaded": True}
    save_index(idx)

    flash(f"Dodano: {full} ({msg})", "success")
    return redirect(url_for("awesome_list", repo=full))


@app.route("/add/topic", methods=["POST"])
def add_topic():
    topic = request.args.get("topic", "").strip()
    if not topic:
        flash("Podaj topic", "error")
        return redirect(url_for("add_repo"))

    subprocess.Popen(
        ["bash", str(BASE_DIR / "download.sh"), topic, "100", "1"],
        cwd=str(BASE_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    flash(f"Pobieranie topicu '{topic}' uruchomione w tle", "success")
    return redirect(url_for("add_repo"))


@app.route("/rebuild", methods=["POST"])
def rebuild():
    subprocess.run(
        ["python3", str(BASE_DIR / "extract_tools.py")],
        cwd=str(BASE_DIR),
        capture_output=True
    )

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

    global db
    db = ToolsDB()

    flash("Baza przebudowana!", "success")
    return redirect(url_for("add_repo"))


@app.route("/api/ai/ask", methods=["GET", "POST"])
def api_ai_ask():
    """AI Bibliotekarz: pytanie po ludzku -> rekomendacje narzedzi (JSON)."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        q = str(data.get("q", "")).strip()
    else:
        q = request.args.get("q", "").strip()
    if not q:
        return {"error": "parametr 'q' wymagany"}, 400
    try:
        limit = min(int(request.values.get("limit", 5)), 10)
    except ValueError:
        limit = 5
    try:
        return ai_recommend(db, q, limit=limit)
    except RuntimeError as e:
        return {"error": str(e)}, 503


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    print(f"Awesome Tools — http://localhost:{port}")
    app.run(debug=False, port=port)
