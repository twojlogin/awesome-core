#!/usr/bin/env python3
"""core/validator.py - Waliduje linki w tools.json przeciwko GitHub API."""

import json
import subprocess
import time
from pathlib import Path
from collections import defaultdict


class Validator:
    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"
        self.data_dir = Path(data_dir)
        self.tools_file = self.data_dir / "tools.json"
        self.report_file = self.data_dir / "validation_report.json"
        self.tools = []
        self._load()

    def _load(self):
        if self.tools_file.exists():
            self.tools = json.loads(self.tools_file.read_text())

    def _save(self):
        self.tools_file.write_text(json.dumps(self.tools, indent=2, ensure_ascii=False))

    def _get_token(self):
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _check_github(self, url, token=None):
        """Check if a GitHub repo exists and get basic info."""
        url = url.rstrip("/")

        # Extract owner/repo from URL
        if "github.com/" not in url:
            return {"alive": False, "reason": "not_github"}

        parts = url.split("github.com/")[-1].strip("/").split("/")
        if len(parts) < 2:
            return {"alive": False, "reason": "invalid_url"}

        owner, name = parts[0], parts[1]

        # Try GitHub API
        api_url = f"https://api.github.com/repos/{owner}/{name}"
        headers = ["-H", "Accept: application/vnd.github+json"]
        if token:
            headers.extend(["-H", f"Authorization: token {token}"])

        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}"] + headers + [api_url],
                capture_output=True, text=True, timeout=10
            )
            status = result.stdout.strip()

            if status == "200":
                return {"alive": True, "reason": "ok"}
            elif status == "404":
                return {"alive": False, "reason": "not_found"}
            elif status == "403":
                return {"alive": False, "reason": "rate_limited"}
            else:
                return {"alive": False, "reason": f"http_{status}"}

        except subprocess.TimeoutExpired:
            return {"alive": False, "reason": "timeout"}
        except Exception as e:
            return {"alive": False, "reason": str(e)}

    def validate_all(self, limit=None):
        """Validate all tools and update status."""
        token = self._get_token()
        print(f"Token: {'TAK' if token else 'NIE'}")

        # Get unique GitHub URLs
        github_urls = {}
        for tool in self.tools:
            url = tool.get("url", "").rstrip("/").lower()
            if "github.com/" in url and url not in github_urls:
                github_urls[url] = tool

        print(f"Unikalne URL-e GitHub: {len(github_urls)}")

        if limit:
            github_urls = dict(list(github_urls.items())[:limit])

        results = {"alive": 0, "dead": 0, "rate_limited": 0, "error": 0}
        checked = 0

        for url, tool in github_urls.items():
            info = self._check_github(url, token)

            # Update tool
            tool["alive"] = info["alive"]
            tool["alive_reason"] = info["reason"]

            if info["alive"]:
                results["alive"] += 1
            elif info["reason"] == "rate_limited":
                results["rate_limited"] += 1
                print(f"  Rate limit! Czekam 60s...")
                time.sleep(60)
            elif info["reason"] in ["not_found", "not_github", "invalid_url"]:
                results["dead"] += 1
            else:
                results["error"] += 1

            checked += 1
            if checked % 50 == 0:
                print(f"  Sprawdzono: {checked}/{len(github_urls)} (alive={results['alive']}, dead={results['dead']})")
                self._save()  # Save progress

            time.sleep(0.1)  # Rate limit protection

        self._save()

        # Save report
        report = {
            "total_checked": checked,
            "github_urls": len(github_urls),
            "results": results,
        }
        self.report_file.write_text(json.dumps(report, indent=2))

        return report

    def validate_sample(self, n=100):
        """Validate a random sample of tools."""
        import random
        sample = random.sample(self.tools, min(n, len(self.tools)))

        token = self._get_token()
        results = {"alive": 0, "dead": 0, "error": 0}

        for tool in sample:
            url = tool.get("url", "").rstrip("/")
            if "github.com/" not in url:
                continue

            info = self._check_github(url, token)
            tool["alive"] = info["alive"]
            tool["alive_reason"] = info["reason"]

            if info["alive"]:
                results["alive"] += 1
            else:
                results["dead"] += 1

            time.sleep(0.1)

        self._save()
        return results

    def get_stats(self):
        """Get validation stats."""
        alive = sum(1 for t in self.tools if t.get("alive") is True)
        dead = sum(1 for t in self.tools if t.get("alive") is False)
        unknown = sum(1 for t in self.tools if t.get("alive") is None)

        return {
            "total": len(self.tools),
            "alive": alive,
            "dead": dead,
            "unknown": unknown,
        }

    def get_alive_tools(self, min_stars=0):
        """Get only alive tools."""
        return [
            t for t in self.tools
            if t.get("alive") is True
            and t.get("source_stars", 0) >= min_stars
        ]

    def get_dead_tools(self):
        """Get dead tools."""
        return [t for t in self.tools if t.get("alive") is False]
