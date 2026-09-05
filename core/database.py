#!/usr/bin/env python3
"""core/database.py - silnik Awesome DB."""

import csv
import json
import math
import random
import re
from pathlib import Path
from collections import defaultdict


class AwesomeDB:
    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"
        self.data_dir = Path(data_dir)
        self.csv_path = self.data_dir / "summary_enriched.csv"
        if not self.csv_path.exists():
            self.csv_path = self.data_dir / "summary.csv"
        self.repos = []
        self.categories = defaultdict(list)
        self.stats = {}
        self.readme_cache = {}
        self.readme_dir = Path(__file__).parent.parent / "offline-db" / "data" / "readmes"
        self.readme_index = {}
        self._load_readmes_index()
        self.load()

    def _load_readmes_index(self):
        if not self.readme_dir.exists():
            return
        index_file = Path(__file__).parent.parent / "offline-db" / "data" / "index.json"
        if index_file.exists():
            with open(index_file) as f:
                self.readme_index = json.load(f)

    def _get_readme(self, repo_name):
        if repo_name in self.readme_cache:
            return self.readme_cache[repo_name]
        if repo_name not in self.readme_index:
            return ""
        meta = self.readme_index[repo_name]
        readme_path = self.readme_dir / f"{meta['owner']}__{meta['name']}.md"
        if not readme_path.exists():
            return ""
        try:
            content = readme_path.read_text(encoding="utf-8", errors="replace")
            self.readme_cache[repo_name] = content
            return content
        except Exception:
            return ""

    def load(self):
        if not self.csv_path.exists():
            return
        with open(self.csv_path, "r", encoding="utf-8") as f:
            self.repos = list(csv.DictReader(f))
        self.categories = defaultdict(list)
        for repo in self.repos:
            cats = repo.get("categories", "")
            for cat in cats.split(";"):
                cat = cat.strip()
                if cat:
                    self.categories[cat].append(repo)
        for cat in self.categories:
            self.categories[cat].sort(
                key=lambda r: int(r.get("stars") or 0), reverse=True
            )
        self.stats = {
            "total": len(self.repos),
            "categories": {k: len(v) for k, v in self.categories.items()},
        }

    def search(self, query):
        q = query.lower().strip()
        if not q:
            return []
        words = q.split()
        results = []
        for repo in self.repos:
            name = repo.get("full_name", "").lower()
            desc = repo.get("description", "").lower()
            cats = repo.get("categories", "").lower()
            lang = repo.get("language", "").lower()
            topics = repo.get("topics", "").lower()
            score = 0
            match_in = set()
            # NAME — highest priority
            if q in name:
                score += 500
                match_in.add("name")
            for w in words:
                if w in name:
                    score += 200
                    match_in.add("name")
            # TOPICS
            if q in topics:
                score += 100
                match_in.add("topics")
            for w in words:
                if w in topics:
                    score += 40
            # DESCRIPTION
            if q in desc:
                score += 80
                match_in.add("description")
            for w in words:
                if w in desc:
                    score += 30
            # CATEGORY
            if q in cats:
                score += 60
                match_in.add("category")
            for w in words:
                if w in cats:
                    score += 25
            # LANGUAGE
            if q in lang:
                score += 50
                match_in.add("language")
            # README — only if name/desc already matched, or exact word match
            readme = self._get_readme(repo.get("full_name", ""))
            if readme and score > 0:
                readme_lower = readme.lower()
                readme_count = readme_lower.count(q)
                if readme_count >= 3:
                    score += 20
                    match_in.add("readme")
            if score > 0:
                stars = int(repo.get("stars") or 0)
                star_boost = math.log10(max(stars, 1)) * 3
                results.append((repo, score + star_boost, list(match_in)))
        results.sort(key=lambda x: x[1], reverse=True)
        return [(r, m) for r, s, m in results]

    def list_category(self, cat):
        return self.categories.get(cat.lower(), [])

    def random_repo(self):
        return random.choice(self.repos) if self.repos else None

    def get_repo(self, name):
        for repo in self.repos:
            if repo.get("full_name", "") == name:
                return repo
        return None

    def top_repos(self, n=10, sort_by="stars"):
        return sorted(
            self.repos,
            key=lambda r: int(r.get("stars") or 0),
            reverse=True,
        )[:n]

    def top_in_category(self, cat, n=10):
        return self.categories.get(cat.lower(), [])[:n]

    def stats_summary(self):
        cats = {}
        for cat, repos in self.categories.items():
            stars = [int(r.get("stars") or 0) for r in repos]
            cats[cat] = {
                "count": len(repos),
                "max_stars": max(stars) if stars else 0,
                "total_stars": sum(stars),
            }
        return {"total": len(self.repos), "categories": cats}
