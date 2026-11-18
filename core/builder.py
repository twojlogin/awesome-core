#!/usr/bin/env python3
"""core/builder.py — buduje bazę SQLite z pobranych README."""

import json
import os
import sqlite3
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from core import clones as clones_mod, langmap, parser, scoring, store


BASE_DIR = Path(__file__).parent.parent


INDEX_FILE = BASE_DIR / "offline-db" / "data" / "index.json"


README_DIR = BASE_DIR / "offline-db" / "data" / "readmes"


def _log(verbose, message):
    if verbose:
        print(message, flush=True)


def load_index_entries(index_file=None):
    path = Path(index_file) if index_file else INDEX_FILE
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [(k, v) for k, v in data.items() if isinstance(v, dict)]


def sync_repos(conn, verbose=True, index_file=None, readme_dir=None):
    """Synchronizuje offline-db/data/index.json + katalog READMEs z tabelą repos."""
    readme_root = Path(readme_dir) if readme_dir else README_DIR
    entries = dict(load_index_entries(index_file))
    files = {}
    if readme_root.exists():
        for path in readme_root.glob("*.md"):
            files[path.stem] = path

    added = updated = 0
    for full_name, entry in entries.items():
        clean, meta = store.sanitize_index_entry({**entry, "full_name": full_name})
        owner = entry.get("owner") or (full_name.split("/")[0] if "/" in full_name else "")
        name = entry.get("name") or (full_name.split("/")[1] if "/" in full_name else "")
        readme = readme_root / f"{owner}__{name}.md"
        exists = readme.exists()
        before = store.get_repo(conn, full_name)
        changed = store.upsert_repo(conn, full_name, meta)
        if exists:
            store.mark_readme(conn, full_name, True)
        if before is None and changed:
            added += 1
        elif changed:
            updated += 1

    for stem, path in files.items():
        full_name = _full_name_from_file(stem)
        if not full_name or full_name in entries:
            continue
        if store.get_repo(conn, full_name) is None:
            if store.upsert_repo(conn, full_name, {}):
                added += 1
        store.mark_readme(conn, full_name, True)

    conn.commit()
    _log(verbose, f"  repo: {added} nowych, {updated} zaktualizowanych")
    return added + updated


def _full_name_from_file(stem):
    if "__" not in stem:
        return None
    owner, name = stem.split("__", 1)
    return f"{owner}/{name}"


def _carry_over(conn):
    """Zachowuje alive / alive_reason / first_seen z poprzedniego buildu."""
    carried = {}
    try:
        rows = conn.execute(
            "SELECT url_norm, alive, alive_reason, first_seen FROM tools"
        ).fetchall()
    except Exception:
        return carried
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for row in rows:
        carried[row["url_norm"]] = (
            row["alive"],
            row["alive_reason"] or "",
            row["first_seen"] or now,
        )
    return carried


def _best_mention(existing, candidate):
    def key(m):
        return (
            1 if langmap.has_description(m["description"]) else 0,
            min(len(m["description"] or ""), 120),
            m["repo_stars"],
            0 if m["junk"] else 1,
            -len(m["name"] or ""),
        )

    return candidate if key(candidate) > key(existing) else existing


def _drop_bulk_indexes(conn):
    names = [
        "idx_tools_urlnorm", "idx_tools_lang", "idx_tools_platform", "idx_tools_section",
        "idx_tools_source", "idx_tools_score", "idx_tools_stars", "idx_tools_alive",
        "idx_tools_lists", "idx_tools_name", "idx_mentions_repo", "idx_similarity_clone",
    ]
    for name in names:
        try:
            conn.execute(f"DROP INDEX IF EXISTS {name}")
        except Exception:
            pass


def _create_bulk_indexes(conn):
    stmts = [
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_tools_urlnorm ON tools(url_norm)",
        "CREATE INDEX IF NOT EXISTS idx_tools_lang ON tools(lang, score DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tools_platform ON tools(platform)",
        "CREATE INDEX IF NOT EXISTS idx_tools_section ON tools(section)",
        "CREATE INDEX IF NOT EXISTS idx_tools_source ON tools(source_repo)",
        "CREATE INDEX IF NOT EXISTS idx_tools_score ON tools(score DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tools_stars ON tools(source_stars DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tools_alive ON tools(alive)",
        "CREATE INDEX IF NOT EXISTS idx_tools_lists ON tools(lists_count DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tools_name ON tools(name_norm)",
        "CREATE INDEX IF NOT EXISTS idx_mentions_repo ON tool_mentions(source_repo)",
        "CREATE INDEX IF NOT EXISTS idx_similarity_clone ON list_similarity(clone)",
    ]
    for stmt in stmts:
        try:
            conn.execute(stmt)
        except Exception:
            pass


def _open_build_conn(data_dir, tmp_path):
    conn = sqlite3.connect(str(tmp_path), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    store.migrate(conn)
    store.build_mode(conn)
    return conn


def build(data_dir=None, verbose=True, export=None, export_limit=None,
          index_file=None, readme_dir=None, vacuum=False,
          clone_threshold=None, clone_min_shared=None, clone_min_size=None):
    """Buduje bazę atomowo: zapis do *.db.tmp + os.replace po sukcesie."""
    started = time.perf_counter()
    final_path = store.db_path(data_dir)
    tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")
    try:
        if tmp_path.exists():
            tmp_path.unlink()
    except Exception:
        pass

    conn = _open_build_conn(data_dir, tmp_path)
    try:
        carried = _carry_over(conn)
        readme_root = Path(readme_dir) if readme_dir else README_DIR

        _log(verbose, "Synchronizacja list...")
        sync_repos(conn, verbose, index_file=index_file, readme_dir=readme_root)

        phase = time.perf_counter()
        repos = {r["full_name"]: r for r in store.all_repos(conn)}
        with_readme = 0
        raw_mentions = 0
        stats_by_repo = {}
        best = {}
        all_mentions = defaultdict(list)
        junk_count = 0

        for full_name, repo in repos.items():
            readme = readme_root / f"{repo['owner']}__{repo['name']}.md"
            if not readme.exists():
                continue
            try:
                text = readme.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            mentions = parser.parse_readme(text)
            if not mentions:
                stats_by_repo[full_name] = parser.parse_stats([])
                continue
            with_readme += 1
            raw_mentions += len(mentions)
            stats_by_repo[full_name] = parser.parse_stats(mentions)
            repo_stars = int(repo["stars"] or 0)

            for mention in mentions:
                identity = langmap.url_identity(mention["url"])
                junk = langmap.looks_like_junk(
                    mention["name"], mention["url"], mention["description"], identity=identity
                )
                if junk or not identity:
                    junk_count += 1
                    continue
                enriched = dict(mention)
                enriched["url"] = langmap.normalize_url(mention["url"])
                enriched["repo_stars"] = repo_stars
                enriched["repo"] = full_name
                enriched["junk"] = junk
                enriched["repo_language"] = repo["language"] or ""
                enriched["repo_topics"] = repo["topics"] or ""
                all_mentions[identity].append(enriched)
                current = best.get(identity)
                best[identity] = enriched if current is None else _best_mention(current, enriched)

            if verbose and with_readme % 100 == 0 and with_readme:
                _log(verbose, f"  sparsowano {with_readme} list, {raw_mentions} wystąpień")

        _log(
            verbose,
            f"  list z README: {with_readme} | wystąpień: {raw_mentions} | "
            f"odrzuconych śmieci: {junk_count} | unikalnych narzędzi: {len(best)} "
            f"| parsowanie: {time.perf_counter() - phase:.1f}s",
        )

        clone_rows, clone_of = _detect_clones(
            all_mentions, repos, clone_threshold, clone_min_shared, clone_min_size
        )
        if clone_rows:
            summary_clones = clones_mod.summarize(clone_rows)
            _log(
                verbose,
                f"  klony list: {summary_clones['pairs']} par, {summary_clones['clones']} list to kopie "
                f"({summary_clones['same_owner']} w ręku tego samego autora)",
            )

        started_quality = time.perf_counter()
        repo_quality, owner_info = _compute_repo_quality(stats_by_repo, repos, all_mentions, best, carried)
        _log(verbose, f"  jakość list: {time.perf_counter() - started_quality:.1f}s")

        tool_meta = store.tool_meta_map(conn)
        if tool_meta:
            _log(verbose, f"  metadane narzędzi w bazie: {len(tool_meta)} repozytoriów")
        phase = time.perf_counter()
        rows, mention_rows = _build_tool_rows(
            best, all_mentions, repos, repo_quality, carried, tool_meta, clone_of, owner_info, verbose
        )

        _log(verbose, f"  przygotowanie wierszy: {time.perf_counter() - phase:.1f}s")

        # masowy zapis: indeksy po załadowaniu danych
        _drop_bulk_indexes(conn)
        now_t = time.perf_counter()
        _write(conn, rows, mention_rows, repo_quality, clone_rows, verbose)
        _create_bulk_indexes(conn)
        conn.commit()
        _log(verbose, f"  zapis do SQLite: {time.perf_counter() - now_t:.1f}s")

        if store.fts_enabled(conn):
            now_t = time.perf_counter()
            conn.execute("INSERT INTO tools_fts(tools_fts) VALUES('rebuild')")
            conn.commit()
            _log(verbose, f"  indeks FTS5 przebudowany ({time.perf_counter() - now_t:.1f}s)")

        _update_repo_stats(conn)
        conn.commit()

        summary = _summary(conn)
        store.set_meta(conn, "last_build", summary["built_at"], commit=False)
        store.set_meta(conn, "last_build_tools", summary["tools"], commit=False)
        store.set_meta(conn, "last_build_mentions", summary["mentions"], commit=False)
        store.set_meta(conn, "clone_pairs", len(clone_rows), commit=False)
        store.set_meta(conn, "clone_lists", len({row["clone"] for row in clone_rows}), commit=False)
        store.set_meta(conn, "lists_without_meta",
                       conn.execute(
                           "SELECT COUNT(*) FROM repos WHERE stars=0 AND language=''"
                       ).fetchone()[0], commit=False)
        store.set_meta(conn, "github_tools_without_own_meta",
                       conn.execute(
                           "SELECT COUNT(*) FROM tools WHERE tool_stars = 0"
                           " AND url_norm LIKE 'github.com/%'"
                       ).fetchone()[0], commit=False)
        summary["seconds"] = round(time.perf_counter() - started, 1)
        store.set_meta(conn, "last_build_seconds", summary["seconds"], commit=False)
        conn.commit()
        store.finish_build(conn, vacuum=vacuum)
        if export:
            path = Path(export)
            if export.endswith(".csv"):
                count = store.export_csv(conn, path, export_limit)
            else:
                count = store.export_json(conn, path, export_limit)
            _log(verbose, f"  eksport {path} ({count} pozycji)")
        conn.close()
        conn = None
        os.replace(tmp_path, final_path)
        return summary
    except Exception:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        raise
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def _detect_clones(all_mentions, repos, threshold=None, min_shared=None, min_size=None):
    """Kopie list + mapa {klon: kanon} (używana przy liczeniu consensusu)."""
    per_list = defaultdict(set)
    for identity, mentions in all_mentions.items():
        for mention in mentions:
            per_list[mention["repo"]].add(identity)
    meta = {
        name: {"stars": repo.get("stars", 0), "quality": repo.get("quality", 0.0)}
        for name, repo in repos.items()
    }
    options = {}
    if threshold is not None:
        options["threshold"] = threshold
    if min_shared is not None:
        options["min_shared"] = min_shared
    if min_size is not None:
        options["min_size"] = min_size
    rows = clones_mod.detect_clones(per_list, meta, **options)
    return rows, clones_mod.clone_map(rows)


def _owner_farm_info(repos):
    """Wykrywa farmy jednego autora: wielu list od tego samego ownera
    przy niskiej medianie gwiazdek list."""
    by_owner = defaultdict(list)
    for full_name, repo in repos.items():
        owner = (repo.get("owner") or (full_name.split("/")[0] if "/" in full_name else "")).lower()
        if not owner:
            continue
        by_owner[owner].append(max(0, int(repo.get("stars", 0) or 0)))
    info = {}
    for owner, stars_list in by_owner.items():
        count = len(stars_list)
        vals = sorted(stars_list)
        mid = len(vals) // 2
        median = vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0
        is_farm = count >= 8 and median < 150
        info[owner] = {
            "count": count,
            "median_stars": median,
            "farm": is_farm,
            "multiplier": 0.78 if is_farm else 1.0,
        }
    return info


def _compute_repo_quality(stats_by_repo, repos, all_mentions, best, carried):
    project_hits = defaultdict(lambda: [0, 0])
    for identity, mention in best.items():
        host = identity.split("/", 1)[0]
        is_project = host in langmap.GIT_HOSTS or langmap.is_package_host(host)
        repo = mention["repo"]
        project_hits[repo][0] += 1
        if is_project:
            project_hits[repo][1] += 1

    alive_by_repo = defaultdict(lambda: [0, 0])
    for identity, mentions in all_mentions.items():
        alive = carried.get(identity, (None, "", ""))[0]
        if alive is None:
            continue
        for mention in mentions:
            alive_by_repo[mention["repo"]][0] += 1
            if alive:
                alive_by_repo[mention["repo"]][1] += 1

    owner_info = _owner_farm_info(repos)

    quality = {}
    for full_name, repo in repos.items():
        stats = dict(stats_by_repo.get(full_name) or {"total": 0})
        stats["pushed_at"] = repo.get("pushed_at")
        stats["list_stars"] = max(0, int(repo.get("stars", 0) or 0))
        checked, ok = alive_by_repo.get(full_name, [0, 0])
        stats["alive_checked"] = checked
        stats["alive_ok"] = ok
        seen, projects = project_hits.get(full_name, [0, 0])
        stats["projects"] = (projects / seen) if seen else None
        owner = (repo.get("owner") or (full_name.split("/")[0] if "/" in full_name else "")).lower()
        oi = owner_info.get(owner) or {}
        if oi.get("farm"):
            stats["owner_farm"] = True
            stats["owner_farm_multiplier"] = oi.get("multiplier", 0.78)
        quality[full_name] = scoring.repo_quality(stats)["quality"]
    return quality, owner_info


def _tool_meta_for(identity, tool_meta):
    if not identity or not tool_meta:
        return None

    raw = identity.strip()
    parsed = urlsplit(raw if "://" in raw else f"//{raw}")
    host = (parsed.hostname or "").lower()
    if host != "github.com":
        return None

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    return tool_meta.get(f"{parts[0]}/{parts[1]}".lower())


def _build_tool_rows(best, all_mentions, repos, repo_quality, carried, tool_meta,
                     clone_of, owner_info, verbose):
    rows = []
    mention_rows = []
    enriched_count = 0
    owner_info = owner_info or {}
    for identity, primary in best.items():
        meta = _tool_meta_for(identity, tool_meta)
        mentions = all_mentions[identity]
        quality_sum = 0.0
        stars_sum = 0
        seen_repos = set()
        for mention in mentions:
            repo = mention["repo"]
            if repo in seen_repos or repo in clone_of:
                continue
            seen_repos.add(repo)
            q = repo_quality.get(repo, 0.0)
            owner = (repo.split("/")[0] if "/" in repo else "").lower()
            oi = owner_info.get(owner) or {}
            if oi.get("farm"):
                # obniż wagę farm jednego autora także w consensus
                q *= float(oi.get("multiplier", 0.78) or 0.78)
            quality_sum += q
            stars_sum += int(repos.get(repo, {}).get("stars", 0) or 0)
        for mention in mentions:
            seen_repos.add(mention["repo"])

        independent = [repo for repo in seen_repos if repo not in clone_of]
        clones_skipped = len(seen_repos) - len(independent)
        lists_count = len(independent)
        owners_count = len({
            repo.split("/")[0].lower() for repo in independent
        })
        consensus = scoring.consensus(lists_count, owners_count, quality_sum)
        best_quality = max(
            (repo_quality.get(m["repo"], 0.0) for m in mentions), default=0.0
        )

        tool_stars = int(meta.get("stars", 0) or 0) if meta else 0
        tool_forks = int(meta.get("forks", 0) or 0) if meta else 0
        tool_archived = 1 if meta and meta.get("archived") else 0
        if meta:
            enriched_count += 1

        lang = langmap.infer_lang(
            primary["url"],
            primary["name"],
            primary["description"],
            meta.get("language", "") if meta else "",
            primary.get("repo_topics", ""),
            tool_meta=meta,
        )
        platform = langmap.infer_platform(
            primary["url"],
            primary["name"],
            primary["description"],
            primary["section"],
            primary["subsection"],
            primary.get("repo_topics", ""),
        )
        if meta and meta.get("topics"):
            extra = langmap.infer_platform(topics=meta["topics"])
            if extra:
                platform = ";".join(sorted({*platform.split(";"), *extra.split(";")} - {""}))
        domain = langmap.infer_domain(
            primary["section"],
            primary["subsection"],
            meta.get("topics", "") if meta else primary.get("repo_topics", ""),
            primary["description"],
            primary["name"],
        )
        install_method, _ = langmap.install_hint(primary["url"], primary["name"])
        alive = carried.get(identity, (None,))[0]
        alive_reason = carried.get(identity, (None, ""))[1]
        if meta and alive is None:
            alive = 0 if meta.get("status") == 1 else 1
            alive_reason = "not_found" if alive == 0 else "ok"
        first_seen = carried.get(identity, (None, "", ""))[2] or time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )

        ctx = {
            "source_stars": primary["repo_stars"],
            "tool_stars": tool_stars,
            "consensus": consensus,
            "list_quality": best_quality,
            "has_desc": langmap.has_description(primary["description"]),
            "alive": alive,
            "source_language": primary.get("repo_language", ""),
            "has_own_meta": bool(meta),
        }
        scored = scoring.tool_score(ctx)

        rows.append(
            (
                primary["name"],
                (primary["name"] or "").lower(),
                primary["url"],
                identity,
                langmap.host_of(primary["url"]),
                primary["description"],
                primary["section"],
                primary["subsection"],
                primary["repo"],
                primary["repo_stars"],
                primary.get("repo_language", ""),
                lang,
                platform,
                domain,
                install_method,
                tool_stars,
                tool_forks,
                tool_archived,
                alive,
                alive_reason,
                lists_count,
                owners_count,
                clones_skipped,
                stars_sum,
                scored["score"],
                scored["underrated"],
                scored["hidden_gem"],
                first_seen,
            )
        )
        for mention in mentions:
            mention_rows.append(
                (
                    identity,
                    mention["repo"],
                    mention["name"],
                    mention["section"],
                    mention["subsection"],
                    langmap.truncate_words(mention["description"], 300),
                )
            )
    _log(
        verbose,
        f"  przygotowano {len(rows)} narzędzi (z metadanymi GitHub: {enriched_count}) "
        f"i {len(mention_rows)} wystąpień",
    )
    return rows, mention_rows


def _write(conn, rows, mention_rows, repo_quality, clone_rows, verbose):
    # Kolejność ma znaczenie dla przeżywalności: _save_clones kończy się
    # własnym commit() (linia niżej). Gdyby stało po DELETE, przerwany build
    # zostawiałby pustą bazę — kasowanie byłoby zapisane, a wstawianie nie.
    # Stąd: wszystko, co commituje, zanim cokolwiek skasujemy.
    _save_clones(conn, clone_rows)
    conn.execute("DELETE FROM tools")
    conn.execute("DELETE FROM tool_mentions")
    conn.executemany(
        "UPDATE repos SET quality=? WHERE full_name=?",
        [(value, full_name) for full_name, value in repo_quality.items()],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO tool_mentions (url_norm, source_repo, name, section,"
        " subsection, description) VALUES (?,?,?,?,?,?)",
        mention_rows,
    )
    insert_sql = (
        "INSERT INTO tools (name, name_norm, url, url_norm, host, description, section,"
        " subsection, source_repo, source_stars, source_language, lang, platform, tags,"
        " install_method, tool_stars, tool_forks, tool_archived, alive, alive_reason,"
        " lists_count, owners_count, clones_skipped, lists_stars, score, underrated,"
        " hidden_gem, first_seen)"
        " VALUES (" + ",".join(["?"] * 28) + ")"
    )
    for chunk_start in range(0, len(rows), 5000):
        conn.executemany(insert_sql, rows[chunk_start:chunk_start + 5000])
    conn.commit()


def _save_clones(conn, clone_rows):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn.execute("DELETE FROM list_similarity")
    conn.execute("UPDATE repos SET clone_of=''")
    conn.executemany(
        "INSERT OR REPLACE INTO list_similarity (canonical, clone, shared, overlap,"
        " clone_size, same_owner, via_chain, computed_at) VALUES (?,?,?,?,?,?,?,?)",
        [
            (row["canonical"], row["clone"], row["shared"], row["overlap"],
             row["clone_size"], 1 if row["same_owner"] else 0,
             1 if row.get("chain") else 0, now)
            for row in clone_rows
        ],
    )
    conn.executemany(
        "UPDATE repos SET clone_of=? WHERE full_name=?",
        [(row["canonical"], row["clone"]) for row in clone_rows],
    )
    conn.commit()


def _update_repo_stats(conn):
    conn.execute(
        "UPDATE repos SET tool_count = COALESCE(("
        "  SELECT COUNT(*) FROM tool_mentions m WHERE m.source_repo = repos.full_name), 0)"
    )
    conn.execute(
        "UPDATE repos SET unique_tool_count = COALESCE(("
        "  SELECT COUNT(DISTINCT m.url_norm) FROM tool_mentions m"
        "  WHERE m.source_repo = repos.full_name), 0)"
    )
    conn.commit()


def _summary(conn):
    tools = conn.execute("SELECT COUNT(*) FROM tools").fetchone()[0]
    lists = conn.execute("SELECT COUNT(*) FROM repos").fetchone()[0]
    mentions = conn.execute("SELECT COUNT(*) FROM tool_mentions").fetchone()[0]
    langs = conn.execute(
        "SELECT COUNT(DISTINCT CASE WHEN lang != '?' THEN lang END) FROM tools"
    ).fetchone()[0]
    with_meta = conn.execute(
        "SELECT COUNT(*) FROM repos WHERE stars > 0"
    ).fetchone()[0]
    return {
        "tools": tools,
        "lists": lists,
        "lists_with_meta": with_meta,
        "mentions": mentions,
        "langs": langs,
        "built_at": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
    }
