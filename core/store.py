#!/usr/bin/env python3
"""core/store.py — warstwa dostępu do SQLite (jedyne źródło prawdy)."""

import csv
import json
import re
import sqlite3
import time
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent


DATA_DIR = BASE_DIR / "data"


DB_FILE = "awesome.db"


SCHEMA_VERSION = 2


SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    full_name           TEXT PRIMARY KEY,
    owner               TEXT NOT NULL DEFAULT '',
    name                TEXT NOT NULL DEFAULT '',
    url                 TEXT NOT NULL DEFAULT '',
    description         TEXT NOT NULL DEFAULT '',
    stars               INTEGER NOT NULL DEFAULT 0,
    forks               INTEGER NOT NULL DEFAULT 0,
    watchers            INTEGER NOT NULL DEFAULT 0,
    language            TEXT NOT NULL DEFAULT '',
    topics              TEXT NOT NULL DEFAULT '',
    license             TEXT NOT NULL DEFAULT '',
    archived            INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT '',
    pushed_at           TEXT NOT NULL DEFAULT '',
    readme_downloaded   INTEGER NOT NULL DEFAULT 0,
    fetched_at          TEXT NOT NULL DEFAULT '',
    meta_fetched_at     TEXT NOT NULL DEFAULT '',
    quality             REAL NOT NULL DEFAULT 0,
    tool_count          INTEGER NOT NULL DEFAULT 0,
    unique_tool_count   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tools (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    name_norm       TEXT NOT NULL,
    url             TEXT NOT NULL,
    url_norm        TEXT NOT NULL,
    host            TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    section         TEXT NOT NULL DEFAULT '',
    subsection      TEXT NOT NULL DEFAULT '',
    source_repo     TEXT NOT NULL DEFAULT '',
    source_stars    INTEGER NOT NULL DEFAULT 0,
    source_language TEXT NOT NULL DEFAULT '',
    lang            TEXT NOT NULL DEFAULT '',
    platform        TEXT NOT NULL DEFAULT '',
    tags            TEXT NOT NULL DEFAULT '',
    install_method  TEXT NOT NULL DEFAULT '',
    tool_stars      INTEGER NOT NULL DEFAULT 0,
    tool_forks      INTEGER NOT NULL DEFAULT 0,
    tool_archived   INTEGER NOT NULL DEFAULT 0,
    alive           INTEGER,
    alive_reason    TEXT NOT NULL DEFAULT '',
    lists_count     INTEGER NOT NULL DEFAULT 0,
    owners_count    INTEGER NOT NULL DEFAULT 0,
    lists_stars     INTEGER NOT NULL DEFAULT 0,
    score           REAL NOT NULL DEFAULT 0,
    underrated      REAL NOT NULL DEFAULT 0,
    first_seen      TEXT NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tools_urlnorm ON tools(url_norm);
CREATE INDEX IF NOT EXISTS idx_tools_lang ON tools(lang, score DESC);
CREATE INDEX IF NOT EXISTS idx_tools_platform ON tools(platform);
CREATE INDEX IF NOT EXISTS idx_tools_section ON tools(section);
CREATE INDEX IF NOT EXISTS idx_tools_source ON tools(source_repo);
CREATE INDEX IF NOT EXISTS idx_tools_score ON tools(score DESC);
CREATE INDEX IF NOT EXISTS idx_tools_stars ON tools(source_stars DESC);
CREATE INDEX IF NOT EXISTS idx_tools_alive ON tools(alive);
CREATE INDEX IF NOT EXISTS idx_tools_lists ON tools(lists_count DESC);
CREATE INDEX IF NOT EXISTS idx_tools_name ON tools(name_norm);

CREATE TABLE IF NOT EXISTS tool_mentions (
    url_norm    TEXT NOT NULL,
    source_repo TEXT NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    section     TEXT NOT NULL DEFAULT '',
    subsection  TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (url_norm, source_repo)
);

CREATE INDEX IF NOT EXISTS idx_mentions_repo ON tool_mentions(source_repo);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tool_repo_meta (
    full_name TEXT PRIMARY KEY,
    url         TEXT NOT NULL DEFAULT '',
    stars       INTEGER NOT NULL DEFAULT 0,
    forks       INTEGER NOT NULL DEFAULT 0,
    language    TEXT NOT NULL DEFAULT '',
    archived    INTEGER NOT NULL DEFAULT 0,
    pushed_at   TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT '',
    topics      TEXT NOT NULL DEFAULT '',
    status      INTEGER NOT NULL DEFAULT 0,
    fetched_at  TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_toolmeta_lang ON tool_repo_meta(language);
"""


FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS tools_fts USING fts5(
    name, description, section, subsection, source_repo,
    content='tools', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
"""


REPO_INT_FIELDS = ("stars", "forks", "watchers")


REPO_TEXT_FIELDS = (
    "owner", "name", "url", "description", "language", "topics",
    "license", "created_at", "pushed_at",
)


REPO_BOOL_FIELDS = ("archived", "readme_downloaded")


def db_path(data_dir=None):
    base = Path(data_dir) if data_dir else DATA_DIR
    return base / DB_FILE


def connect(data_dir=None, timeout=30.0, read_only=False):
    """Otwórz bazę. W trybie read_only nie rusza schematu, więc nie koliduje
    z równoległym `enrich`/`backfill` (a web/CLI tylko czytają)."""
    path = db_path(data_dir)
    if read_only:
        if not path.exists():
            raise RuntimeError(
                "Brak bazy danych. Zbuduj ją komendą: python3 extract_tools.py"
            )
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        return conn
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    migrate(conn)
    return conn


EXTRA_COLUMNS = {
    "tools": {
        "owners_count": "INTEGER NOT NULL DEFAULT 0",
        "underrated": "REAL NOT NULL DEFAULT 0",
        "hidden_gem": "REAL NOT NULL DEFAULT 0",
        "lists_stars": "INTEGER NOT NULL DEFAULT 0",
        "score": "REAL NOT NULL DEFAULT 0",
        "platform": "TEXT NOT NULL DEFAULT ''",
        "tags": "TEXT NOT NULL DEFAULT ''",
        "install_method": "TEXT NOT NULL DEFAULT ''",
        "tool_stars": "INTEGER NOT NULL DEFAULT 0",
        "tool_forks": "INTEGER NOT NULL DEFAULT 0",
        "tool_archived": "INTEGER NOT NULL DEFAULT 0",
        "alive": "INTEGER",
        "alive_reason": "TEXT NOT NULL DEFAULT ''",
        "first_seen": "TEXT NOT NULL DEFAULT ''",
    },
    "repos": {
        "quality": "REAL NOT NULL DEFAULT 0",
        "tool_count": "INTEGER NOT NULL DEFAULT 0",
        "unique_tool_count": "INTEGER NOT NULL DEFAULT 0",
        "meta_fetched_at": "TEXT NOT NULL DEFAULT ''",
        "description": "TEXT NOT NULL DEFAULT ''",
        "topics": "TEXT NOT NULL DEFAULT ''",
        "watchers": "INTEGER NOT NULL DEFAULT 0",
    },
}


def _ensure_columns(conn):
    for table, columns in EXTRA_COLUMNS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if not existing:
            continue
        for column, definition in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def migrate(conn):
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    try:
        conn.executescript(FTS_SCHEMA)
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    except sqlite3.OperationalError:
        conn.rollback()
    conn.commit()
    return conn


def fts_enabled(conn):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tools_fts'"
    ).fetchone()
    return row is not None


def db_ready(data_dir=None):
    path = db_path(data_dir)
    if not path.exists():
        return False
    try:
        conn = sqlite3.connect(str(path))
        row = conn.execute("SELECT 1 FROM sqlite_master WHERE name='tools'").fetchone()
        conn.close()
        return row is not None
    except sqlite3.Error:
        return False


def _clean_meta(full_name, meta):
    """Zamienia metadane z GitHub API na typy SQLite, bez nadpisywania pustymi."""
    meta = dict(meta or {})
    if "/" not in full_name:
        return None
    owner, name = full_name.split("/", 1)
    row = {
        "full_name": full_name,
        "owner": meta.get("owner") or owner,
        "name": meta.get("name") or name,
        "url": meta.get("html_url") or meta.get("url") or f"https://github.com/{full_name}",
    }
    for field in REPO_INT_FIELDS:
        value = meta.get(field)
        if value is None:
            row[field] = 0
            continue
        try:
            row[field] = int(value)
        except (TypeError, ValueError):
            row[field] = 0
    for field in REPO_BOOL_FIELDS:
        row[field] = 1 if meta.get(field) else 0
    license_obj = meta.get("license")
    if isinstance(license_obj, dict):
        spdx = license_obj.get("spdx_id") or ""
        row["license"] = "" if spdx == "NOASSERTION" else spdx
    else:
        row["license"] = license_obj if isinstance(license_obj, str) else ""
    topics = meta.get("topics")
    if isinstance(topics, (list, tuple)):
        row["topics"] = ";".join(str(t) for t in topics)
    elif isinstance(topics, str):
        row["topics"] = topics
    else:
        row["topics"] = ""
    for field in ("description", "language", "created_at", "pushed_at"):
        value = meta.get(field)
        row[field] = "" if value is None else str(value)
    return row


def upsert_repo(conn, full_name, meta=None):
    """Wpisz metadane listy. Puste wartości NIE nadpisują istniejących."""
    row = _clean_meta(full_name, meta)
    if row is None:
        return False
    cur = conn.execute("SELECT * FROM repos WHERE full_name=?", (full_name,))
    existing = cur.fetchone()
    if existing is None:
        row["meta_fetched_at"] = _now()
        conn.execute(
            "INSERT INTO repos (full_name, owner, name, url, description, stars, forks,"
            " watchers, language, topics, license, archived, created_at, pushed_at,"
            " readme_downloaded, meta_fetched_at)"
            " VALUES (:full_name, :owner, :name, :url, :description, :stars, :forks,"
            " :watchers, :language, :topics, :license, :archived, :created_at, :pushed_at,"
            " 1, :meta_fetched_at)",
            row,
        )
        return True

    updates = {}
    for field, value in row.items():
        if field in {"full_name", "meta_fetched_at"}:
            continue
        if value in (0, "", None) and field not in {"forks", "watchers"}:
            continue
        old = existing[field]
        if old in (None, "") or old == 0:
            updates[field] = value
    if meta and (meta.get("stars") or meta.get("language") or meta.get("topics")):
        updates["meta_fetched_at"] = _now()
    if not updates:
        return False
    assignments = ", ".join(f"{k}=:{k}" for k in updates)
    params = dict(updates)
    params["full_name"] = full_name
    conn.execute(f"UPDATE repos SET {assignments} WHERE full_name=:full_name", params)
    return True


def mark_readme(conn, full_name, downloaded=True):
    conn.execute(
        "UPDATE repos SET readme_downloaded=?, fetched_at=? WHERE full_name=?",
        (1 if downloaded else 0, _now(), full_name),
    )


def get_repo(conn, full_name):
    row = conn.execute(
        "SELECT * FROM repos WHERE full_name=?", (full_name,)
    ).fetchone()
    return dict(row) if row else None


def all_repos(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM repos")]


TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}:\d{2})?")


def valid_topics(value):
    """Topiki GitHuba są małe, bez spacji. Po błędzie TSV bywa tam data."""
    if not value:
        return ""
    parts = [p.strip() for p in str(value).split(";")]
    kept = [p for p in parts if p and TOPIC_RE.match(p)]
    return ";".join(kept[:20])


def sanitize_index_entry(entry):
    """Naprawia wpis z index.json po błędzie z przesuniętymi polami TSV."""
    full_name = entry.get("full_name", "")
    if "/" not in full_name:
        return None, {}
    owner, name = full_name.split("/", 1)
    meta = {"readme_downloaded": True}

    for field in ("stars", "forks", "watchers"):
        value = entry.get(field)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value >= 0:
            meta[field] = value
        elif isinstance(value, str) and value.isdigit():
            meta[field] = int(value)

    language = str(entry.get("language") or "").strip()
    if language and ";" not in language and not ISO_RE.match(language):
        meta["language"] = language[:40]

    topics = valid_topics(entry.get("topics"))
    if topics:
        meta["topics"] = topics

    description = str(entry.get("description") or "").strip()
    if description and not ISO_RE.match(description):
        meta["description"] = description[:300]

    for field in ("created_at", "pushed_at"):
        value = str(entry.get(field) or "").strip()
        if ISO_RE.match(value):
            meta[field] = value

    archived = entry.get("archived")
    if isinstance(archived, (bool, int)):
        meta["archived"] = bool(archived)
    elif isinstance(archived, str) and archived.lower() in {"true", "false", "1", "0"}:
        meta["archived"] = archived.lower() in {"true", "1"}

    spdx = entry.get("license") or entry.get("license_id")
    if isinstance(spdx, str) and re.match(r"^[A-Za-z0-9.+-]{1,20}$", spdx) and spdx != "NOASSERTION":
        meta["license"] = {"spdx_id": spdx}

    return full_name, meta


def set_meta(conn, key, value):
    """Zapisuje znacznik (np. kiedy ostatnio przebudowano bazę)."""
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()


def get_meta(conn, key, default=""):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def tool_meta_map(conn, identities=None):
    """full_name (lowercase) -> metadane repozytorium narzędzia."""
    sql = "SELECT * FROM tool_repo_meta"
    params = ()
    out = {}
    for row in conn.execute(sql, params):
        out[row["full_name"].lower()] = dict(row)
    return out


def build_mode(conn):
    """Przyspiesza build: synchroniczne zapisy są tu niepotrzebne."""
    for pragma in ("PRAGMA synchronous=OFF", "PRAGMA temp_store=MEMORY",
                   "PRAGMA cache_size=-200000"):
        try:
            conn.execute(pragma)
        except sqlite3.OperationalError:
            pass
    return conn


def finish_build(conn, vacuum=False):
    try:
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        if vacuum:
            conn.execute("VACUUM")
    except sqlite3.OperationalError:
        pass
    return conn


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def export_json(conn, out_path, limit=None):
    sql = "SELECT * FROM tools"
    params = ()
    if limit:
        sql += " LIMIT ?"
        params = (int(limit),)
    rows = conn.execute(sql + " ORDER BY score DESC", params).fetchall()
    data = [dict(r) for r in rows]
    Path(out_path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return len(data)


def export_csv(conn, out_path, limit=None):
    sql = "SELECT * FROM tools"
    params = ()
    if limit:
        sql += " LIMIT ?"
        params = (int(limit),)
    rows = conn.execute(sql + " ORDER BY score DESC", params).fetchall()
    fields = [d[0] for d in conn.execute("SELECT * FROM tools LIMIT 0").description]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return len(rows)
