#!/usr/bin/env python3
"""core/shortlist.py — twoja własna lista: dorzuć narzędzie i wygeneruj Markdown."""

import json
import time
from collections import defaultdict
from pathlib import Path

from core import store

BASE_DIR = Path(__file__).parent.parent


class Shortlist:
    """Lista wybranych narzędzi. Przechowywana w SQLite (przetrwa przebudowę bazy)."""

    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else BASE_DIR / "data"
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = store.connect(self.data_dir)
        return self._conn

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def add(self, tool, note=""):
        """Zapisuje narzędzie (dict z tools_db) i zwraca (status, info)."""
        identity = tool.get("url_norm") or tool.get("url")
        if not identity:
            return "error", "brak URL narzędzia"
        exists = self.conn.execute(
            "SELECT 1 FROM shortlist WHERE url_norm=?", (identity,)
        ).fetchone()
        self.conn.execute(
            "INSERT INTO shortlist (url_norm, added_at, note) VALUES (?,?,?)"
            " ON CONFLICT(url_norm) DO UPDATE SET note=excluded.note",
            (identity, time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), note or ""),
        )
        self.conn.commit()
        if exists:
            return "updated", "zaktualizowano notatkę"
        return "added", "dodano do twojej listy"

    def remove(self, url_norm):
        cursor = self.conn.execute("DELETE FROM shortlist WHERE url_norm=?", (url_norm,))
        self.conn.commit()
        return cursor.rowcount > 0

    def has(self, url_norm):
        return self.conn.execute(
            "SELECT 1 FROM shortlist WHERE url_norm=?", (url_norm,)
        ).fetchone() is not None

    def items(self, include_missing=True):
        """Narzędzia z listy wraz z notatką; te, których już nie ma w bazie, też."""
        rows = self.conn.execute(
            "SELECT url_norm, added_at, note FROM shortlist ORDER BY added_at DESC"
        ).fetchall()
        known = {
            row["url_norm"]: row
            for row in self.conn.execute("SELECT url_norm FROM tools")
        }
        out = []
        for row in rows:
            entry = {
                "url_norm": row["url_norm"],
                "added_at": row["added_at"],
                "note": row["note"] or "",
                "in_db": row["url_norm"] in known,
            }
            if entry["in_db"]:
                full = self.conn.execute(
                    "SELECT * FROM tools WHERE url_norm=?", (row["url_norm"],)
                ).fetchone()
                entry["tool"] = dict(full)
            out.append(entry)
        if not include_missing:
            out = [entry for entry in out if entry["in_db"]]
        return out

    def count(self):
        return self.conn.execute("SELECT COUNT(*) FROM shortlist").fetchone()[0]

    def to_json(self, out_path=None):
        data = []
        for entry in self.items():
            tool = entry.get("tool") or {}
            data.append({
                "name": tool.get("name", entry["url_norm"]),
                "url": tool.get("url", entry["url_norm"]),
                "note": entry["note"],
                "lang": tool.get("lang", ""),
                "platform": tool.get("platform", ""),
                "stars": tool.get("tool_stars", 0),
                "lists": tool.get("lists_count", 0),
                "score": tool.get("score", 0),
                "added_at": entry["added_at"],
                "in_db": entry["in_db"],
            })
        path = Path(out_path) if out_path else None
        text = json.dumps(data, indent=2, ensure_ascii=False)
        if path:
            path.write_text(text, encoding="utf-8")
        return text

    def to_markdown(self, title="Moja lista narzędzi", out_path=None,
                    group_by="lang", include_notes=True):
        """Markdown gotowy do wklejenia we własną awesome list."""
        groups = defaultdict(list)
        for entry in self.items():
            tool = entry.get("tool")
            if not tool:
                continue
            key = self._group_key(tool, group_by)
            groups[key].append((entry, tool))

        lines = [f"# {title}", ""]
        if not groups:
            lines += ["_Pusto — dodaj narzędzia komendą `awesome shortlist add <nazwa>`._", ""]
        for key in sorted(groups, key=lambda k: (k == "Inne", k.lower())):
            lines.append(f"## {key}")
            lines.append("")
            for entry, tool in sorted(
                groups[key],
                key=lambda pair: (-(pair[1].get("tool_stars") or 0), pair[1].get("name") or ""),
            ):
                name = tool.get("name") or entry["url_norm"]
                url = tool.get("url") or entry["url_norm"]
                suffix = ""
                if include_notes and entry["note"]:
                    suffix = f" — {entry['note']}"
                stars = f" ⭐{tool['tool_stars']:,}" if tool.get("tool_stars") else ""
                lists = f" · {tool['lists_count']} list" if tool.get("lists_count", 0) > 1 else ""
                desc = (tool.get("description") or "").strip()
                if len(desc) > 140:
                    desc = desc[:140].rsplit(" ", 1)[0] + "…"
                text = f"- [{name}]({url}){stars}{lists}{suffix}"
                if desc:
                    text += f" — {desc}"
                lines.append(text)
            lines.append("")

        text = "\n".join(lines).rstrip() + "\n"
        if out_path:
            Path(out_path).write_text(text, encoding="utf-8")
        return text

    @staticmethod
    def _group_key(tool, group_by):
        if group_by == "domain":
            return (tool.get("tags") or "?").split(";")[0] or "Inne"
        if group_by == "section":
            return tool.get("section") or "Inne"
        if group_by == "platform":
            return (tool.get("platform") or "?").split(";")[0] or "Inne"
        lang = tool.get("lang") or ""
        return lang if lang and lang != "?" else "Inne"
