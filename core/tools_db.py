#!/usr/bin/env python3
"""core/tools_db.py - instant search engine for awesome tools."""

import json
import math
import random
from pathlib import Path
from collections import defaultdict


class ToolsDB:
    def __init__(self):
        base = Path(__file__).parent.parent / "data"
        self.tools = json.loads((base / "tools.json").read_text())
        self.index = json.loads((base / "search_index.json").read_text())

        # Build URL lookup
        self.by_url = {}
        for t in self.tools:
            url = t.get("url", "").rstrip("/").lower()
            if url:
                self.by_url[url] = t

        # Build sections and source indexes
        self.sections = defaultdict(list)
        self.by_source = defaultdict(list)
        for i, t in enumerate(self.tools):
            s = t.get("section") or "Other"
            self.sections[s].append(t)
            src = t.get("source_repo", "")
            if src:
                self.by_source[src].append(t)

        self.stats = {
            "total": len(self.tools),
            "sections": {k: len(v) for k, v in self.sections.items()},
            "lists": len(self.by_source),
        }

    def search(self, query, limit=50, min_stars=0, alive_only=False):
        q = query.lower().strip()
        if not q:
            return []

        words = q.split()

        # Index lookup
        candidates = None
        for w in words:
            w_clean = w.strip('.,;:!?()[]{}"\'-/')
            if w_clean in self.index:
                if candidates is None:
                    candidates = set(self.index[w_clean])
                else:
                    candidates &= set(self.index[w_clean])

        # Fallback: union
        if not candidates:
            candidates = set()
            for w in words:
                w_clean = w.strip('.,;:!?()[]{}"\'-/')
                if w_clean in self.index:
                    candidates |= set(self.index[w_clean])

        # Score
        results = []
        for idx in candidates:
            tool = self.tools[idx]
            name = tool.get("name", "").lower()
            desc = tool.get("description", "").lower()
            src = tool.get("source_repo", "").lower()
            source_stars = tool.get("source_stars", 0)
            alive = tool.get("alive")

            if source_stars < min_stars:
                continue

            if alive_only and alive is False:
                continue

            score = 0
            if q == name:
                score += 1000
            elif q in name:
                score += 200
            for w in words:
                if w in name:
                    score += 80
            if q in desc:
                score += 50
            for w in words:
                if w in desc:
                    score += 20
            if q in src:
                score += 30
            for w in words:
                if w in src:
                    score += 15

            if source_stars > 0:
                star_boost = math.log10(max(source_stars, 1)) * 5
                score += star_boost

            # Boost alive tools
            if alive is True:
                score += 10

            if score > 0:
                results.append((tool, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return [t for t, _ in results[:limit]]

    def get_tool_by_url(self, url):
        url_clean = url.rstrip("/").lower()
        return self.by_url.get(url_clean)

    def find_similar(self, tool, limit=5):
        name = tool.get("name", "").lower()
        desc = tool.get("description", "").lower()
        section = tool.get("section", "")
        source_stars = tool.get("source_stars", 0)

        candidates = []
        seen = set()

        # Search by name words
        for word in name.split():
            if len(word) < 3:
                continue
            results = self.search(word, limit=20)
            for r in results:
                url = r.get("url", "")
                if url in seen or url == tool.get("url", ""):
                    continue
                seen.add(url)

                r_stars = r.get("source_stars", 0)
                same_section = 1 if r.get("section") == section else 0
                score = same_section * 10 + math.log10(max(r_stars, 1))
                candidates.append((score, r))

        candidates.sort(key=lambda x: -x[0])
        return [t for _, t in candidates[:limit]]

    def get_install_info(self, tool):
        url = tool.get("url", "").lower()
        if "github.com" in url or "gitlab.com" in url:
            return {"method": "git", "cmd": f"git clone {tool.get('url', '')}"}
        elif "pypi.org" in url or url.endswith(".py"):
            name = url.rstrip("/").split("/")[-1]
            return {"method": "pip", "cmd": f"pip install {name}"}
        elif "npmjs.com" in url:
            name = url.rstrip("/").split("/")[-1]
            return {"method": "npm", "cmd": f"npm install {name}"}
        elif "crates.io" in url:
            name = url.rstrip("/").split("/")[-1]
            return {"method": "cargo", "cmd": f"cargo install {name}"}
        return None

    def by_section(self, section, limit=300):
        return self.sections.get(section, [])[:limit]

    def by_source_repo(self, repo_name, limit=500):
        if repo_name in self.by_source:
            return self.by_source[repo_name][:limit]
        repo_lower = repo_name.lower()
        for src, tools_list in self.by_source.items():
            if repo_lower in src.lower():
                return tools_list[:limit]
        return []

    def get_list_stats(self, repo_name):
        tools = self.by_source_repo(repo_name)
        if not tools:
            return None
        sections = defaultdict(int)
        for t in tools:
            sections[t.get("section") or "Other"] += 1
        return {
            "name": repo_name,
            "count": len(tools),
            "sections": dict(sections),
        }

    def random(self, n=10):
        return random.sample(self.tools, min(n, len(self.tools)))

    def top_sections(self, n=20):
        return sorted(self.stats["sections"].items(), key=lambda x: -x[1])[:n]

    def top_lists(self, n=20):
        tops = sorted(self.by_source.items(), key=lambda x: -len(x[1]))[:n]
        return [(name, len(tools)) for name, tools in tops]
