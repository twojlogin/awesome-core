#!/usr/bin/env python3
"""core/validator.py — sprawdza czy linki do narzędzi wciąż działają.

Dla GitHuba robi to hurtowo przez GraphQL (40 repozytoriów na zapytanie) —
dlatego walidacja 100k linków to minuty, nie godziny. Poza GitHubem linki
sprawdzane są opcjonalnie, pojedynczym HEAD-em.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import enrich, langmap, store  # noqa: E402


BASE_DIR = Path(__file__).parent.parent


class Validator:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else BASE_DIR / "data"
        self.report_file = self.data_dir / "validation_report.json"
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = store.connect(self.data_dir)
        return self._conn

    def _github_pending(self, limit=None):
        return enrich.missing_repos(self.conn, limit=limit)

    def validate_all(self, limit=None, non_github=False, verbose=True):
        """Uzupełnia brakujące metadane GitHub i (opcjonalnie) sprawdza resztę."""
        started = time.perf_counter()
        found = enrich.enrich(limit=limit, verbose=verbose)
        checked_non_github = 0
        if non_github:
            checked_non_github = self._validate_non_github(limit=limit, verbose=verbose)

        report = self._report(found, checked_non_github, time.perf_counter() - started)
        self.report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    def _validate_non_github(self, limit=None, verbose=True):
        rows = self.conn.execute(
            "SELECT url_norm, url FROM tools WHERE url_norm NOT LIKE 'github.com/%'"
            " AND alive IS NULL ORDER BY score DESC"
        ).fetchall()
        if limit:
            rows = rows[: int(limit)]
        checked = 0
        for row in rows:
            ok, reason = self._check_url(row["url"])
            self.conn.execute(
                "UPDATE tools SET alive=?, alive_reason=? WHERE url_norm=?",
                (1 if ok else 0, reason, row["url_norm"]),
            )
            checked += 1
            if verbose and checked % 100 == 0:
                print(f"  sprawdzono {checked}/{len(rows)}", flush=True)
            time.sleep(0.05)
        self.conn.commit()
        return checked

    @staticmethod
    def _check_url(url):
        host = langmap.host_of(url)
        if not host:
            return False, "bad_url"
        try:
            result = subprocess.run(
                ["curl", "-sS", "-o", "/dev/null", "-L", "--max-time", "15",
                 "-w", "%{http_code}", url],
                capture_output=True, text=True, timeout=20,
            )
        except (OSError, subprocess.SubprocessError):
            return False, "error"
        status = (result.stdout or "").strip()[-3:]
        if status == "200":
            return True, "ok"
        if status in {"301", "302", "307", "308"}:
            return True, "redirect"
        if status == "429":
            return None, "rate_limited"
        return False, f"http_{status}"

    def _report(self, github_found, non_github_checked, seconds):
        row = self.conn.execute(
            "SELECT COUNT(*) total,"
            " SUM(CASE WHEN alive = 1 THEN 1 ELSE 0 END) alive,"
            " SUM(CASE WHEN alive = 0 THEN 1 ELSE 0 END) dead,"
            " SUM(CASE WHEN alive IS NULL THEN 1 ELSE 0 END) unknown"
            " FROM tools"
        ).fetchone()
        return {
            "total": row["total"] or 0,
            "alive": row["alive"] or 0,
            "dead": row["dead"] or 0,
            "unknown": row["unknown"] or 0,
            # Wynik tego przebiegu, nie całej bazy. Wcześniej "results" podawało
            # globalne sumy, więc "Sprawdzono: 3" stało obok "Żywe: 100360" i
            # wyglądało, jakbym sprawdził 100 tysięcy linków.
            "results": {
                "alive": github_found or 0,
                "dead": 0,
                "rate_limited": 0,
                "error": non_github_checked,
            },
            "total_checked": (github_found or 0) + (non_github_checked or 0),
            "github_found": github_found or 0,
            "non_github_checked": non_github_checked or 0,
            "seconds": round(seconds, 1),
        }

    def validate_sample(self, n=100):
        return self.validate_all(limit=int(n))

    def get_stats(self):
        report = self._report(0, 0, 0.0)
        return {
            "total": report["total"],
            "alive": report["alive"],
            "dead": report["dead"],
            "unknown": report["unknown"],
        }

    def get_alive_tools(self, min_stars=0, limit=200):
        return [
            dict(r)
            for r in self.conn.execute(
                "SELECT name, url, lang, source_repo, tool_stars, score FROM tools"
                " WHERE alive = 1 AND COALESCE(tool_stars, source_stars) >= ?"
                " ORDER BY score DESC LIMIT ?",
                (min_stars, limit),
            )
        ]

    def get_dead_tools(self, limit=200):
        return [
            dict(r)
            for r in self.conn.execute(
                "SELECT name, url, source_repo, alive_reason FROM tools"
                " WHERE alive = 0 ORDER BY lists_count DESC LIMIT ?",
                (limit,),
            )
        ]
