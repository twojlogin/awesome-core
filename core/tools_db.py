#!/usr/bin/env python3
"""core/tools_db.py — silnik wyszukiwania i przeglądania narzędzi (SQLite).

Publiczne API jest zgodne ze starszą wersją (te same metody wywoływane przez CLI,
web i AI Bibliotekarza), plus fasetki: język, platforma, domena, consensus.
"""

import re
import sqlite3
import threading
from collections import Counter, defaultdict
from pathlib import Path

from core import aliases, clones, langmap, scoring, store


BASE_DIR = Path(__file__).parent.parent


TOKEN_RE = re.compile(r"[\w.+#-]+", re.UNICODE)


SORTS = {
    "score": "t.score DESC, t.lists_count DESC",
    "stars": "t.tool_stars DESC, t.source_stars DESC, t.score DESC",
    "list-stars": "t.source_stars DESC, t.score DESC",
    "consensus": "t.lists_count DESC, t.score DESC",
    "underrated": "t.underrated DESC, t.score DESC",
    "gem": "t.hidden_gem DESC, t.score DESC",
    "name": "t.name_norm ASC",
    "updated": "t.source_repo ASC, t.name_norm ASC",
}


TOOL_COLUMNS = (
    "id, name, name_norm, url, url_norm, host, description, section, subsection, source_repo,"
    " source_stars, source_language, lang, platform, tags, install_method,"
    " tool_stars, tool_forks, tool_archived, alive, alive_reason, lists_count,"
    " owners_count, clones_skipped, lists_stars, score, underrated, hidden_gem,"
    " first_seen"
)


def owner_of(url_norm):
    """github.com/owner/name → owner; dla innych hostów pierwszy segment."""
    parts = [p for p in str(url_norm or "").split("/") if p]
    if not parts:
        return ""
    host = parts[0].lower()
    if host.endswith("github.com") or host.endswith("gitlab.com"):
        return parts[1] if len(parts) > 2 else ""
    return ""


def row_to_tool(row):
    if row is None:
        return None
    tool = dict(row)
    tool["source_stars"] = int(tool.get("source_stars") or 0)
    tool["tool_stars"] = int(tool.get("tool_stars") or 0)
    tool["lists_count"] = int(tool.get("lists_count") or 0)
    tool["clones_skipped"] = int(tool.get("clones_skipped") or 0)
    tool["owners_count"] = int(tool.get("owners_count") or 0)
    tool["score"] = float(tool.get("score") or 0)
    tool["underrated"] = float(tool.get("underrated") or 0)
    tool["hidden_gem"] = float(tool.get("hidden_gem") or 0)
    if tool.get("alive") is not None:
        tool["alive"] = bool(tool["alive"])
    tool["platforms"] = [p for p in (tool.get("platform") or "").split(";") if p]
    tool["domains"] = [d for d in (tool.get("tags") or "").split(";") if d]
    return tool


class ToolsDB:
    """Czytelny widok na tabelę tools. Nie ładuje niczego do pamięci na starcie."""

    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else BASE_DIR / "data"
        self._local = threading.local()
        self._fts = None
        self._all = None

    @property
    def conn(self):
        """Połączenie per-wątek: Flask obsługuje żądania wieloma wątkami."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            if not store.db_ready(self.data_dir):
                raise RuntimeError(
                    "Brak bazy danych. Zbuduj ją komendą: python3 extract_tools.py"
                )
            conn = store.connect(self.data_dir, read_only=True)
            self._local.conn = conn
        return conn

    @property
    def fts(self):
        """FTS5 bywa wyłączone — wtedy spadamy do LIKE po indeksowanych kolumnach."""
        self.conn
        if self._fts is None:
            self._fts = store.fts_enabled(self.conn)
        return self._fts

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    @property
    def tools(self):
        if self._all is None:
            self._all = [
                row_to_tool(r) for r in self.conn.execute(f"SELECT {TOOL_COLUMNS} FROM tools")
            ]
        return self._all

    def reload(self):
        self._all = None
        self.close()

    def top_consensus(self, limit=20, lang=None, min_stars=0):
        """Narzędzia wskazane przez najwięcej niezależnych list."""
        filters = ["lists_count >= 2"]
        params = []
        if lang:
            filters.append("lang = ?")
            params.append(lang)
        if min_stars:
            filters.append("(COALESCE(tool_stars,0) >= ? OR source_stars >= ?)")
            params.extend([min_stars, min_stars])
        params.append(int(limit))
        return [
            row_to_tool(r)
            for r in self.conn.execute(
                f"SELECT {TOOL_COLUMNS} FROM tools WHERE {' AND '.join(filters)}"
                " ORDER BY lists_count DESC, owners_count DESC, score DESC LIMIT ?",
                params,
            )
        ]

    def count(self):
        return self.conn.execute("SELECT COUNT(*) FROM tools").fetchone()[0]

    def stats(self):
        row = self.conn.execute(
            "SELECT COUNT(*) total, COUNT(DISTINCT source_repo) lists,"
            " COUNT(DISTINCT lang) langs, COUNT(DISTINCT section) sections,"
            " SUM(CASE WHEN description != '' THEN 1 ELSE 0 END) with_desc,"
            " SUM(CASE WHEN alive = 1 THEN 1 ELSE 0 END) alive,"
            " SUM(CASE WHEN alive = 0 THEN 1 ELSE 0 END) dead,"
            " SUM(CASE WHEN alive IS NULL THEN 1 ELSE 0 END) unchecked,"
            " SUM(CASE WHEN tool_stars > 0 THEN 1 ELSE 0 END) with_meta,"
            " SUM(COALESCE(tool_stars, 0)) stars FROM tools"
        ).fetchone()
        return {
            "total": row["total"] or 0,
            "lists": row["lists"] or 0,
            "langs": row["langs"] or 0,
            "sections": row["sections"] or 0,
            "with_desc": row["with_desc"] or 0,
            "alive": row["alive"] or 0,
            "dead": row["dead"] or 0,
            "unchecked": row["unchecked"] or 0,
            "with_meta": row["with_meta"] or 0,
            "stars": row["stars"] or 0,
        }

    def langs(self, min_count=5, limit=60):
        return self._facet("lang", min_count, limit)

    def platforms(self, min_count=5, limit=40):
        rows = self.conn.execute(
            "SELECT platform, COUNT(*) c FROM tools WHERE platform != ''"
            " GROUP BY platform ORDER BY c DESC LIMIT ?",
            (limit * 3,),
        ).fetchall()
        merged = defaultdict(int)
        for row in rows:
            for part in row["platform"].split(";"):
                if part:
                    merged[part] += row["c"]
        out = [(k, v) for k, v in merged.items() if v >= min_count]
        out.sort(key=lambda kv: -kv[1])
        return out[:limit]

    def domains(self, min_count=5, limit=40):
        rows = self.conn.execute(
            "SELECT tags, COUNT(*) c FROM tools WHERE tags != ''"
            " GROUP BY tags ORDER BY c DESC LIMIT ?",
            (limit * 3,),
        ).fetchall()
        merged = defaultdict(int)
        for row in rows:
            for part in row["tags"].split(";"):
                if part:
                    merged[part] += row["c"]
        out = [(k, v) for k, v in merged.items() if v >= min_count]
        out.sort(key=lambda kv: -kv[1])
        return out[:limit]

    def _facet(self, column, min_count, limit):
        return [
            (row[column], row["c"])
            for row in self.conn.execute(
                f"SELECT {column}, COUNT(*) c FROM tools WHERE {column} NOT IN ('', '?')"
                f" GROUP BY {column} HAVING c >= ? ORDER BY c DESC LIMIT ?",
                (min_count, limit),
            )
        ]

    def by_lang(self, lang, limit=50, sort="score", min_stars=0, alive_only=False):
        return self._query(
            "t.lang = ?", [lang], limit=limit, sort=sort,
            min_stars=min_stars, alive_only=alive_only,
        )

    def by_platform(self, platform, limit=50, sort="score", min_stars=0, alive_only=False):
        return self._query(
            "t.platform LIKE ?", [f"%{platform}%"], limit=limit, sort=sort,
            min_stars=min_stars, alive_only=alive_only,
        )

    def by_domain(self, domain, limit=50, sort="score", min_stars=0, alive_only=False):
        return self._query(
            "t.tags LIKE ?", [f"%{domain}%"], limit=limit, sort=sort,
            min_stars=min_stars, alive_only=alive_only,
        )

    def by_section(self, section, limit=300, sort="score"):
        return self._query("t.section = ?", [section], limit=limit, sort=sort)

    def by_source_repo(self, repo_name, limit=500, sort="score"):
        rows = self.conn.execute(
            "SELECT DISTINCT t.* FROM tools t JOIN tool_mentions m ON m.url_norm = t.url_norm"
            " WHERE m.source_repo = ? ORDER BY t.score DESC LIMIT ?",
            (repo_name, limit),
        ).fetchall()
        return [row_to_tool(r) for r in rows]

    def mentions(self, url_norm):
        """Wszystkie listy, w których występuje narzędzie (nic nie ginie)."""
        return [
            dict(r)
            for r in self.conn.execute(
                "SELECT source_repo, name, section, subsection, description"
                " FROM tool_mentions WHERE url_norm = ? ORDER BY source_repo",
                (url_norm,),
            )
        ]

    def disambiguate(self, rows):
        """O znacznie powtarzających się nazwach dorzuc właściciela repo.

        "Sherlock" to w bazie cztery różne narzędzia: OSINT, skrypt do
        privilege escalation w PowerShellu, launcher Wayland i wrapper na
        apify.com. Cztery pozycje o tej samej nazwie wyglądają jak błąd,
        a laik nie ma jak zgadnąć, o które mu chodzi. Właściciel rozróżnia
        je w jednym spojrzeniu: "Sherlock (rasta-mouse)".
        """
        counts = Counter(row.get("name", "") for row in rows)
        # Duplikaty liczę w całej bazie, nie tylko w wynikach: najbardziej
        # myliący jest przypadek jednego wyniku "Sherlock", którego nie ma
        # z czym porównać na ekranie, a w bazie siedzą jeszcze trzy.
        names = sorted({row.get("name", "") for row in rows if row.get("name")})
        if names:
            marks = ",".join("?" * len(names))
            for row in self.conn.execute(
                f"SELECT name FROM tools WHERE name IN ({marks})"
                " GROUP BY name HAVING COUNT(*) > 1", names
            ):
                counts[row["name"]] = max(counts[row["name"]], 2)
        for row in rows:
            name = row.get("name", "")
            row["name_taken_by"] = counts[name] if counts[name] > 1 else 0
            row["display_name"] = name
            if counts[name] > 1:
                owner = owner_of(row.get("url_norm") or row.get("url") or "")
                if owner:
                    row["display_name"] = f"{name} ({owner})"
        return rows

    def narrowing_hints(self, query, filters, got, min_results=3):
        """Który filtr odsiał prawie wszystko? Mierzymy, nie zgadujemy.

        Filtry łączy AND, więc trzy z nich potrafią wyciszyć wszystko do
        jednego przypadkowego trafienia. Zamiast pokazać taki wynik bez
        słowa wyjaśnienia, mówimy który filtr odpuścić i ile wtedy wychodzi.
        """
        drop = {"limit", "sort"}
        active = {
            k: v for k, v in filters.items()
            if k not in drop and v not in (None, 0, False, "")
        }
        if len(active) < 2 or got >= min_results:
            return []
        out = []
        for key in active:
            probe = dict(active)
            probe.pop(key)
            count = len(self.search(query, limit=min_results * 5, **probe))
            out.append((key, active[key], count))
        out.sort(key=lambda row: -row[2])
        return out

    def search(self, query, limit=50, min_stars=0, alive_only=False, lang=None,
               platform=None, domain=None, source=None, sort="score"):
        terms = [t for t in TOKEN_RE.findall(query or "") if len(t) > 1]
        if not terms:
            return []
        expanded = aliases.expand(query)
        filters, params = self._filters(
            min_stars=min_stars, alive_only=alive_only, lang=lang,
            platform=platform, domain=domain, source=source,
        )
        candidates = []
        if self.fts:
            candidates = self._fts_candidates(terms, filters, params, limit * 6, " AND ")
            seen = {t["url_norm"] for t in candidates}
            for batch, size, order in (
                ([e for e in expanded if e not in terms], limit * 6, "t.score DESC"),
                (terms, limit * 8, "t.score DESC"),
            ):
                if not batch:
                    continue
                filler = self._fts_candidates(
                    batch, filters, params, size, " OR ", order=order
                )
                fresh = [t for t in filler if t["url_norm"] not in seen]
                candidates.extend(fresh)
                seen.update(t["url_norm"] for t in fresh)
                if len(candidates) >= limit * 6:
                    break
        if not candidates:
            candidates = self._like_candidates(terms, filters, params, limit * 6)
        if not candidates:
            return []
        ranked = []
        for tool in candidates:
            score = self._relevance(tool, terms, query)
            if expanded:
                name = (tool.get("name") or "").lower()
                exact = any(
                    name in {e.lower(), e.lower().replace("-", ""), e.lower().replace("_", "")}
                    for e in expanded
                )
                if exact:
                    # Alias to podpowiedź, nie twardy dowód: nazwa narzędzia
                    # bywa aliasem zapytania (aliasy "osint" wymieniają
                    # sherlock/maigret/spiderfoot). Bezwarunkowa podłoga 80
                    # działa dobrze, bo "osint" ma faktycznie prowadzić do
                    # Maigret i SpiderFoot. Nie wolno jej jednak zrównować z
                    # dopasowaniem dosłownym: te 4 punkty zostają tylko wtedy,
                    # gdy narzędzie pasuje do zapytania też bez aliasu —
                    # inaczej wąski filtr potrafi wypchnąć na pierwsze miejsce
                    # cokolwiek, co akurat dzieli nazwę z znaną gwiazdą.
                    score = max(score, 80 if score > 0 else 45)
                elif score > 0 and any(e.lower() in name for e in expanded):
                    score += 25
            if score <= 0:
                continue
            quality = min(1.0, tool["score"] / 100.0)
            breadth = min(1.0, tool["lists_count"] / 5.0)
            name = (tool.get("name") or "").lower()
            short_name = 1.0 if 0 < len(name.split()) <= 3 and ":" not in name else 0.0
            project = 1.0 if (tool.get("host") in langmap.GIT_HOSTS
                              or langmap.is_package_host(tool.get("host") or "")
                              or tool.get("install_method")) else 0.0
            ranked.append((
                score * (0.18 + 0.40 * quality + 0.20 * breadth
                         + 0.12 * project + 0.10 * short_name),
                tool,
            ))
        ranked.sort(key=lambda pair: -pair[0])
        return [tool for _, tool in ranked[:limit]]

    def _fts_candidates(self, terms, filters, params, limit, joiner=" AND ", order="rank"):
        match = joiner.join(f'"{t}"*' for t in terms)
        sql = (
            f"SELECT {self._tool_select()} FROM tools_fts f JOIN tools t ON t.id = f.rowid"
            " WHERE tools_fts MATCH ?"
        )
        args = [match]
        sql, args = self._append_filters(sql, args, filters, params)
        sql += f" ORDER BY {order} LIMIT ?"
        args.append(limit)
        try:
            return [row_to_tool(r) for r in self.conn.execute(sql, args)]
        except sqlite3.OperationalError:
            self._fts = False
            return []

    def _like_candidates(self, terms, filters, params, limit):
        where = " OR ".join(
            "(t.name LIKE ? OR t.description LIKE ? OR t.section LIKE ?)" for _ in terms
        )
        args = []
        for term in terms:
            args.extend([f"%{term}%"] * 3)
        sql = f"SELECT {self._tool_select()} FROM tools t WHERE ({where})"
        sql, args = self._append_filters(sql, args, filters, params)
        sql += " ORDER BY t.score DESC LIMIT ?"
        args.append(limit)
        return [row_to_tool(r) for r in self.conn.execute(sql, args)]

    @staticmethod
    def _tool_select():
        return ", ".join(f"t.{c.strip()}" for c in TOOL_COLUMNS.split(","))

    def _filters(self, min_stars=0, alive_only=False, lang=None, platform=None,
                 domain=None, source=None):
        filters = []
        params = []
        if min_stars:
            filters.append("(COALESCE(t.tool_stars, 0) >= ? OR t.source_stars >= ?)")
            params.extend([int(min_stars), int(min_stars)])
        if alive_only:
            filters.append("t.alive = 1")
        if lang:
            filters.append("t.lang = ?")
            params.append(lang)
        if platform:
            filters.append("t.platform LIKE ?")
            params.append(f"%{platform}%")
        if domain:
            filters.append("t.tags LIKE ?")
            params.append(f"%{domain}%")
        if source:
            filters.append("t.source_repo = ?")
            params.append(source)
        return filters, params

    @staticmethod
    def _append_filters(sql, args, filters, params):
        for clause in filters:
            sql += " AND " + clause
        args.extend(params)
        return sql, args

    def _query(self, where, params, limit=50, sort="score", min_stars=0, alive_only=False):
        extra, extra_params = self._filters(min_stars=min_stars, alive_only=alive_only)
        clauses = [where] + extra
        order = SORTS.get(sort, SORTS["score"])
        sql = (
            f"SELECT {self._tool_select()} FROM tools t WHERE " + " AND ".join(clauses)
            + f" ORDER BY {order} LIMIT ?"
        )
        args = list(params) + extra_params + [int(limit)]
        return [row_to_tool(r) for r in self.conn.execute(sql, args)]

    @staticmethod
    def _relevance(tool, terms, query):
        name = (tool.get("name") or "").lower()
        desc = (tool.get("description") or "").lower()
        section = (tool.get("section") or "").lower()
        lang = (tool.get("lang") or "").lower()
        source = (tool.get("source_repo") or "").lower()
        domain = (tool.get("tags") or "").lower()
        platform = (tool.get("platform") or "").lower()
        q = query.lower().strip()
        score = 0.0
        # Długie zdania w „nazwie" to zwykle artykuły i checklisty, nie narzędzia
        name_weight = 1.0 if len(name.split()) <= 4 else 0.35
        if q and q == name:
            score += 120 * name_weight
        elif q and q in name:
            score += 45 * name_weight
        for term in terms:
            low = term.lower()
            if low == name:
                score += (60 if len(name) > 8 else 30) * name_weight
            elif low in name:
                score += 30 * name_weight
            if low in desc:
                score += 12
            if low in section:
                score += 8
            if low == lang:
                score += 20
            if low in domain:
                score += 18
            if low in platform:
                score += 12
            if low in source:
                score += 6
        if tool.get("lists_count", 0) > 1:
            score += 3
        return score

    def get_tool_by_url(self, url):
        from core import langmap

        identity = langmap.url_identity(url) or (url or "").rstrip("/").lower()
        row = self.conn.execute(
            f"SELECT {self._tool_select()} FROM tools t WHERE t.url_norm = ?", (identity,)
        ).fetchone()
        return row_to_tool(row)

    def get_tool(self, url_norm):
        row = self.conn.execute(
            f"SELECT {self._tool_select()} FROM tools t WHERE t.url_norm = ?", (url_norm,)
        ).fetchone()
        return row_to_tool(row)

    def tool_by_name(self, name):
        low = (name or "").strip().lower()
        if not low:
            return None
        row = self.conn.execute(
            f"SELECT {self._tool_select()} FROM tools t WHERE t.name_norm = ?"
            " ORDER BY t.score DESC LIMIT 1",
            (low,),
        ).fetchone()
        if row:
            return row_to_tool(row)
        row = self.conn.execute(
            f"SELECT {self._tool_select()} FROM tools t WHERE t.url_norm LIKE ?"
            " ORDER BY t.score DESC LIMIT 1",
            (f"%/{low}",),
        ).fetchone()
        return row_to_tool(row)

    def find_similar(self, tool, limit=5):
        if not tool:
            return []
        section = tool.get("section") or ""
        lang = tool.get("lang") or ""
        rows = self.conn.execute(
            f"SELECT {self._tool_select()} FROM tools t"
            " WHERE t.url_norm != ? AND (t.section = ? OR t.lang = ?)"
            " ORDER BY t.score DESC LIMIT ?",
            (tool.get("url_norm"), section, lang, max(limit * 4, 20)),
        ).fetchall()
        results = []
        for row in rows:
            candidate = row_to_tool(row)
            if candidate["name_norm"] == tool.get("name_norm"):
                continue
            results.append(candidate)
            if len(results) >= limit:
                break
        return results

    def get_list_stats(self, repo_name):
        repos = [r for r in self.conn.execute(
            "SELECT full_name, stars, quality, unique_tool_count FROM repos"
            " WHERE full_name = ?", (repo_name,)
        )]
        sections = defaultdict(int)
        for row in self.conn.execute(
            "SELECT section, COUNT(*) c FROM tool_mentions WHERE source_repo = ?"
            " GROUP BY section", (repo_name,)
        ):
            sections[row["section"]] = row["c"]
        if not repos and not sections:
            return None
        repo = dict(repos[0]) if repos else {"full_name": repo_name, "stars": 0, "quality": 0}
        repo["count"] = sum(sections.values())
        repo["sections"] = dict(sections)
        return repo

    def random(self, n=10):
        total = self.count()
        if not total:
            return []
        rows = self.conn.execute(
            f"SELECT {self._tool_select()} FROM tools t"
            " ORDER BY RANDOM() LIMIT ?", (max(1, min(int(n), total)),)
        ).fetchall()
        return [row_to_tool(r) for r in rows]

    def top_sections(self, n=20):
        return [
            (row["section"], row["c"])
            for row in self.conn.execute(
                "SELECT section, COUNT(*) c FROM tools WHERE section != ''"
                " GROUP BY section ORDER BY c DESC LIMIT ?", (n,)
            )
        ]

    def top_lists(self, n=20):
        return [
            (row["source_repo"], row["c"])
            for row in self.conn.execute(
                "SELECT source_repo, COUNT(*) c FROM tools WHERE source_repo != ''"
                " GROUP BY source_repo ORDER BY c DESC LIMIT ?", (n,)
            )
        ]

    def best_lists(self, n=20, min_tools=5):
        return [
            dict(r)
            for r in self.conn.execute(
                "SELECT full_name, stars, quality, tool_count, unique_tool_count,"
                " language FROM repos WHERE unique_tool_count >= ?"
                " ORDER BY quality DESC, unique_tool_count DESC LIMIT ?",
                (min_tools, n),
            )
        ]

    def underrated(self, limit=20, lang=None, platform=None):
        filters = ["tool_stars > 0"]
        params = []
        if lang:
            filters.append("lang = ?")
            params.append(lang)
        if platform:
            filters.append("platform LIKE ?")
            params.append(f"%{platform}%")
        where = (" WHERE " + " AND ".join(filters)) if filters else ""
        params.extend([int(limit)])
        return [
            row_to_tool(r)
            for r in self.conn.execute(
                f"SELECT {TOOL_COLUMNS} FROM tools{where} ORDER BY underrated DESC, score DESC LIMIT ?",
                params,
            )
        ]

    def gems(self, limit=20, lang=None):
        """Ukryte perełki: mało list, ale wysoki score (tylko znane narzędzia)."""
        sql = f"SELECT {TOOL_COLUMNS} FROM tools WHERE tool_stars > 0"
        params = []
        if lang:
            sql += " AND lang = ?"
            params.append(lang)
        sql += " ORDER BY hidden_gem DESC, score DESC LIMIT ?"
        params.append(int(limit))
        return [row_to_tool(r) for r in self.conn.execute(sql, params)]

    def clones_report(self, min_shared=20, threshold=0.8):
        return clones.report(self.conn, min_shared=min_shared, threshold=threshold)

    def list_clones(self, full_name):
        """Kopie treści + forki tej listy (do badge'a na stronie listy)."""
        out = []
        for row in self.conn.execute(
            "SELECT canonical, clone, shared, overlap FROM list_similarity"
            " WHERE canonical = ? OR clone = ? ORDER BY shared DESC",
            (full_name, full_name),
        ):
            is_clone = row["clone"] == full_name
            out.append({
                "kind": "kopia",
                "direction": "klon" if is_clone else "kanon",
                "other": row["clone"] if is_clone else row["canonical"],
                "shared": row["shared"],
                "overlap": row["overlap"],
            })
        for row in self.conn.execute(
            "SELECT full_name FROM repos WHERE is_fork = 1 AND parent = ?"
            " ORDER BY unique_tool_count DESC",
            (full_name,),
        ):
            out.append({
                "kind": "fork", "direction": "fork", "other": row["full_name"],
                "shared": 0, "overlap": None,
            })
        parent = self.conn.execute(
            "SELECT parent FROM repos WHERE full_name = ?", (full_name,)
        ).fetchone()
        if parent and parent["parent"]:
            out.append({
                "kind": "fork", "direction": "rodzic", "other": parent["parent"],
                "shared": 0, "overlap": None,
            })
        return out

    def explain(self, tool):
        if not tool:
            return None
        parts = {
            "consensus": min(1.0, tool.get("lists_count", 0) / 6.0),
            "own_stars": scoring.star_factor(tool.get("tool_stars", 0)),
            "list_stars": 0.5 * scoring.star_factor(tool.get("source_stars", 0)),
            "quality": 0.0,
            "desc": 1.0 if tool.get("description") else 0.0,
            "alive": scoring._alive_score(tool.get("alive")),
            "known": 1.0 if tool.get("tool_stars") else 0.0,
        }
        row = self.conn.execute(
            "SELECT quality FROM repos WHERE full_name = ?", (tool.get("source_repo"),)
        ).fetchone()
        if row:
            parts["quality"] = float(row["quality"] or 0.0)
        detail = scoring.explain({"score": tool.get("score", 0),
                                  "underrated": tool.get("underrated", 0), "parts": parts})
        detail["mentions"] = self.mentions(tool.get("url_norm", ""))
        detail["clones_skipped"] = int(tool.get("clones_skipped") or 0)
        return detail

    def set_alive(self, url_norm, alive, reason=""):
        self.conn.execute(
            "UPDATE tools SET alive = ?, alive_reason = ? WHERE url_norm = ?",
            (1 if alive else 0, reason, url_norm),
        )

    def commit(self):
        self.conn.commit()

    def export(self, fmt="json", out=None, limit=None):
        path = Path(out) if out else (BASE_DIR / "data" / f"tools.{fmt}")
        if fmt == "csv":
            return store.export_csv(self.conn, path, limit)
        return store.export_json(self.conn, path, limit)
