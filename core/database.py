#!/usr/bin/env python3
"""core/database.py — AwesomeDB: wyszukiwanie po repozytoriach/listach (SQLite)."""

import math
import random
from collections import defaultdict

from core import store


class AwesomeDB:
    def __init__(self, data_dir=None):
        self.data_dir = data_dir
        self._conn = None
        self._repos = None
        self.categories = defaultdict(list)
        self.stats = {}

    @property
    def conn(self):
        if self._conn is None:
            if not store.db_ready(self.data_dir):
                raise RuntimeError(
                    "Brak bazy danych. Zbuduj ją komendą: python3 extract_tools.py"
                )
            self._conn = store.connect(self.data_dir, read_only=True)
        return self._conn

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def load(self):
        self._repos = None
        self.categories = defaultdict(list)
        try:
            rows = self.conn.execute("SELECT * FROM repos ORDER BY stars DESC").fetchall()
        except Exception:
            rows = []
        self._repos = [_as_repo(dict(r)) for r in rows]
        for repo in self._repos:
            for cat in repo.get("categories", "").split(";"):
                cat = cat.strip()
                if cat:
                    self.categories[cat].append(repo)
        for cat in self.categories:
            self.categories[cat].sort(key=lambda r: r.get("stars", 0), reverse=True)
        self.stats = {
            "total": len(self._repos),
            "categories": {k: len(v) for k, v in self.categories.items()},
        }
        return self._repos

    @property
    def repos(self):
        if self._repos is None:
            self.load()
        return self._repos

    def get_repo(self, name):
        low = (name or "").strip().lower()
        for repo in self.repos:
            if repo["full_name"].lower() == low:
                return repo
        return None

    def search(self, query, limit=100, min_stars=0, alive_only=False):
        q = (query or "").lower().strip()
        if not q:
            return []
        words = q.split()
        results = []
        for repo in self.repos:
            name = repo["full_name"].lower()
            desc = (repo.get("description") or "").lower()
            cats = (repo.get("categories") or "").lower()
            lang = (repo.get("language") or "").lower()
            score = 0
            matched = []
            if q in name:
                score += 500
                matched.append("name")
            for word in words:
                if word in name:
                    score += 200
                    matched.append("name")
                if word in desc:
                    score += 30
                    matched.append("description")
                if word in cats:
                    score += 25
                    matched.append("topics")
                if word in lang:
                    score += 50
                    matched.append("language")
            if repo.get("alive") is False and alive_only:
                continue
            if repo.get("stars", 0) < min_stars:
                continue
            if score > 0:
                score += math.log10(max(repo.get("stars", 0), 1)) * 3
                results.append((repo, score, list(dict.fromkeys(matched))))
        results.sort(key=lambda item: -item[1])
        return [(repo, matches) for repo, _, matches in results[:limit]]

    def list_category(self, cat):
        return self.categories.get((cat or "").strip(), [])

    def random_repo(self):
        if not self.repos:
            return None
        return random.choice(self.repos)

    def top_repos(self, n=10, sort_by="stars"):
        key = "stars" if sort_by == "stars" else "quality"
        return sorted(
            self.repos,
            key=lambda r: (r.get(key, 0) or 0),
            reverse=True,
        )[:n]

    def best_lists(self, n=20, min_tools=5):
        rows = self.conn.execute(
            "SELECT full_name, quality, unique_tool_count FROM repos"
            " WHERE unique_tool_count >= ? ORDER BY quality DESC LIMIT ?",
            (min_tools, n),
        ).fetchall()
        return [dict(r) for r in rows]

    def by_language(self, language, n=50):
        rows = self.conn.execute(
            "SELECT * FROM repos WHERE language = ? ORDER BY stars DESC LIMIT ?",
            (language, n),
        ).fetchall()
        return [_as_repo(dict(r)) for r in rows]

    def languages(self, min_lists=1):
        return [
            (row["language"], row["c"])
            for row in self.conn.execute(
                "SELECT language, COUNT(*) c FROM repos WHERE language != ''"
                " GROUP BY language HAVING c >= ? ORDER BY c DESC",
                (min_lists,),
            )
        ]

    def stats_summary(self):
        cats = {}
        for cat, repos in self.categories.items():
            stars = [r.get("stars", 0) for r in repos]
            cats[cat] = {
                "count": len(repos),
                "max_stars": max(stars) if stars else 0,
                "total_stars": sum(stars),
            }
        return {"total": len(self.repos), "categories": cats}


def _as_repo(row):
    topics = row.get("topics") or ""
    repo = {
        "full_name": row["full_name"],
        "owner": row.get("owner", ""),
        "name": row.get("name", ""),
        "stars": int(row.get("stars") or 0),
        "forks": int(row.get("forks") or 0),
        "language": row.get("language") or "",
        "license": row.get("license") or "",
        "topics": topics,
        "categories": topics,
        "description": row.get("description") or "",
        "html_url": row.get("url") or f"https://github.com/{row['full_name']}",
        "created_at": row.get("created_at") or "",
        "pushed_at": row.get("pushed_at") or "",
        "archived": bool(row.get("archived")),
        "quality": float(row.get("quality") or 0),
        "tool_count": int(row.get("tool_count") or 0),
        "unique_tool_count": int(row.get("unique_tool_count") or 0),
    }
    repo["alive"] = True if repo["unique_tool_count"] else None
    return repo
