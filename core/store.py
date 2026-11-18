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


SCHEMA_VERSION = 4


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
    unique_tool_count   INTEGER NOT NULL DEFAULT 0,
    clone_of            TEXT NOT NULL DEFAULT '',
    is_fork             INTEGER NOT NULL DEFAULT 0,
    parent              TEXT NOT NULL DEFAULT ''
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
    clones_skipped  INTEGER NOT NULL DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS list_similarity (
    canonical   TEXT NOT NULL,
    clone       TEXT NOT NULL,
    shared      INTEGER NOT NULL DEFAULT 0,
    overlap     REAL NOT NULL DEFAULT 0,
    clone_size  INTEGER NOT NULL DEFAULT 0,
    same_owner  INTEGER NOT NULL DEFAULT 0,
    via_chain   INTEGER NOT NULL DEFAULT 0,
    computed_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (canonical, clone)
);

CREATE INDEX IF NOT EXISTS idx_similarity_clone ON list_similarity(clone);

CREATE TABLE IF NOT EXISTS shortlist (
    url_norm TEXT PRIMARY KEY,
    added_at TEXT NOT NULL DEFAULT '',
    note     TEXT NOT NULL DEFAULT ''
);

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

CREATE TABLE IF NOT EXISTS list_fetch_state (
    full_name      TEXT PRIMARY KEY,
    kind           TEXT NOT NULL DEFAULT 'list',
    status         TEXT NOT NULL DEFAULT '',
    fail_count     INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT NOT NULL DEFAULT '',
    retry_after_at TEXT NOT NULL DEFAULT '',
    reason         TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_fetch_state_retry ON list_fetch_state(retry_after_at);

CREATE TABLE IF NOT EXISTS suspected_farms (
    owner          TEXT PRIMARY KEY,
    first_seen_at  TEXT NOT NULL DEFAULT '',
    last_seen_at   TEXT NOT NULL DEFAULT '',
    repo_count     INTEGER NOT NULL DEFAULT 0,
    median_stars   REAL NOT NULL DEFAULT 0,
    sample_repos   TEXT NOT NULL DEFAULT '',
    status         TEXT NOT NULL DEFAULT 'active',
    vanished_at    TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_suspected_farms_status ON suspected_farms(status);
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


REPO_BOOL_FIELDS = ("archived", "readme_downloaded", "is_fork")


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
        conn = sqlite3.connect(
            f"file:{path}?mode=ro", uri=True, timeout=timeout,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        return conn
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=timeout, check_same_thread=False)
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
        "clones_skipped": "INTEGER NOT NULL DEFAULT 0",
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
        "clone_of": "TEXT NOT NULL DEFAULT ''",
        "is_fork": "INTEGER NOT NULL DEFAULT 0",
        "parent": "TEXT NOT NULL DEFAULT ''",
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
    parent = meta.get("parent") or meta.get("parent_repo")
    if isinstance(parent, dict):
        row["parent"] = (parent.get("full_name") or parent.get("fullName") or "")[:120]
    elif isinstance(parent, str):
        row["parent"] = parent[:120]
    else:
        row["parent"] = ""
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


def set_meta(conn, key, value, commit=True):
    """Zapisuje znacznik (np. kiedy ostatnio przebudowano bazę)."""
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    if commit:
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


def _export_rows(conn, limit=None):
    """LIMIT musi iść po ORDER BY — inaczej SQLite mówi "near ORDER"."""
    sql = "SELECT * FROM tools ORDER BY score DESC"
    if limit:
        sql += " LIMIT ?"
        return conn.execute(sql, (int(limit),)).fetchall()
    return conn.execute(sql).fetchall()


def export_json(conn, out_path, limit=None):
    rows = _export_rows(conn, limit)
    data = [dict(r) for r in rows]
    Path(out_path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return len(data)


def export_csv(conn, out_path, limit=None):
    rows = _export_rows(conn, limit)
    fields = [d[0] for d in conn.execute("SELECT * FROM tools LIMIT 0").description]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return len(rows)



# --- list fetch/backfill state (retry_after) ---

def _parse_ts(value):
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        # allow "YYYY-MM-DD HH:MM:SSZ" style used elsewhere
        if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}Z$", text):
            text = text.replace(" ", "T").replace("Z", "+00:00")
        dt = __import__('datetime').datetime.fromisoformat(text)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=__import__('datetime').timezone.utc)
    return dt.timestamp()


def list_fetch_deferred(conn, full_name, kind='list', now=None):
    row = conn.execute(
        "SELECT retry_after_at, status, reason FROM list_fetch_state WHERE full_name=?",
        (full_name,),
    ).fetchone()
    if not row:
        return False
    now_ts = now if now is not None else time.time()
    retry_ts = _parse_ts(row["retry_after_at"])
    if retry_ts is not None and retry_ts > now_ts:
        return True
    return False


def set_list_fetch_state(conn, full_name, *, kind='list', status='', fail_count=None,
                         retry_after_at='', reason='', commit=True):
    now = _now()
    if fail_count is None:
        row = conn.execute(
            "SELECT fail_count FROM list_fetch_state WHERE full_name=?", (full_name,)
        ).fetchone()
        fail_count = int(row["fail_count"] or 0) if row else 0
    conn.execute(
        "INSERT INTO list_fetch_state (full_name, kind, status, fail_count, last_attempt_at, retry_after_at, reason)"
        " VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(full_name) DO UPDATE SET kind=excluded.kind, status=excluded.status,"
        " fail_count=excluded.fail_count, last_attempt_at=excluded.last_attempt_at,"
        " retry_after_at=excluded.retry_after_at, reason=excluded.reason",
        (full_name, kind, status, int(fail_count), now, retry_after_at or '', reason or ''),
    )
    if commit:
        conn.commit()


def clear_list_fetch_ok(conn, full_name, kind='list', commit=True):
    now = _now()
    conn.execute(
        "INSERT INTO list_fetch_state (full_name, kind, status, fail_count, last_attempt_at, retry_after_at, reason)"
        " VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(full_name) DO UPDATE SET kind=excluded.kind, status='ok', fail_count=0,"
        " last_attempt_at=excluded.last_attempt_at, retry_after_at='', reason=''",
        (full_name, kind, 'ok', 0, now, '', ''),
    )
    if commit:
        conn.commit()


def bump_list_fetch_failure(conn, full_name, *, kind='list', status='error', reason='',
                            retry_days=7, commit=True):
    row = conn.execute(
        "SELECT fail_count FROM list_fetch_state WHERE full_name=?", (full_name,)
    ).fetchone()
    prev = int(row["fail_count"] or 0) if row else 0
    fails = prev + 1
    # backoff: 7d, 30d for repeated permanent-ish failures
    days = retry_days
    if status in ('404', 'missing') and fails >= 2:
        days = max(days, 30)
    retry_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc) + __import__('datetime').timedelta(days=days)
    retry_str = retry_at.strftime('%Y-%m-%dT%H:%M:%SZ')
    set_list_fetch_state(conn, full_name, kind=kind, status=status, fail_count=fails,
                         retry_after_at=retry_str, reason=reason, commit=commit)
    return fails




# --- suspected SEO farms ---

def upsert_suspected_farm(conn, owner, repo_count, median_stars, sample_repos='',
                          status='active', commit=True):
    owner = (owner or '').lower().strip()
    if not owner:
        return
    now = _now()
    vanished_at = now if status == 'vanished' else ''
    conn.execute(
        "INSERT INTO suspected_farms (owner, first_seen_at, last_seen_at, repo_count, median_stars, sample_repos, status, vanished_at)"
        " VALUES (?,?,?,?,?,?,?,?)"
        " ON CONFLICT(owner) DO UPDATE SET "
        " last_seen_at=excluded.last_seen_at,"
        " repo_count=excluded.repo_count,"
        " median_stars=excluded.median_stars,"
        " sample_repos=CASE WHEN excluded.sample_repos!='' THEN excluded.sample_repos ELSE suspected_farms.sample_repos END,"
        " status=excluded.status,"
        " vanished_at=CASE WHEN excluded.status='vanished' THEN excluded.vanished_at ELSE '' END,"
        " first_seen_at=CASE WHEN suspected_farms.first_seen_at='' THEN excluded.first_seen_at ELSE suspected_farms.first_seen_at END",
        (owner, now, now, int(repo_count or 0), float(median_stars or 0),
         sample_repos or '', status or 'active', vanished_at),
    )
    if commit:
        conn.commit()


def suspected_farm_owners(conn, active_only=True):
    try:
        if active_only:
            rows = conn.execute("SELECT owner FROM suspected_farms WHERE status='active'").fetchall()
        else:
            rows = conn.execute("SELECT owner FROM suspected_farms").fetchall()
        return {r['owner'].lower() for r in rows}
    except Exception:
        return set()

