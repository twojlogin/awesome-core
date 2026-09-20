"""Local trust signals for repositories and extracted tools.

These are review hints, not a malware scanner or a safety guarantee.
"""

from datetime import datetime, timezone
import json
import os
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def assess_repo(repo):
    """Return neutral maintenance and review signals for a repository."""
    info = []
    attention = []
    created = _date(repo.get("created_at"))
    pushed = _date(repo.get("pushed_at"))
    now = datetime.now(timezone.utc)

    if repo.get("archived") in {True, "true", "1"}:
        info.append("repozytorium zarchiwizowane")
    if pushed and (now - pushed).days > 730:
        info.append("brak zmian od ponad 2 lat")
    if created and (now - created).days < 30:
        attention.append("bardzo nowe repozytorium")

    try:
        stars = int(repo.get("stars", 0) or 0)
        forks = int(repo.get("forks", 0) or 0)
        if stars >= 1000 and forks == 0:
            attention.append("dużo gwiazdek i brak forków — warto sprawdzić ręcznie")
        elif stars >= 100 and forks and stars / forks > 100:
            attention.append("nietypowa proporcja gwiazdek do forków")
    except (TypeError, ValueError):
        pass

    if not repo.get("license"):
        info.append("brak informacji o licencji")

    return {
        "status": "warto sprawdzić" if attention else "brak szczególnych sygnałów",
        "info": info,
        "attention": attention,
        "manual_review_required": bool(attention),
    }


def github_token():
    """Get an explicitly configured token without printing or persisting it."""
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def fetch_github_audit(repo_name, token):
    """Fetch repository and owner metadata for one explicitly requested audit."""
    parts = repo_name.split("/", 1)
    if len(parts) != 2 or not all(parts):
        raise ValueError("Repozytorium musi mieć format owner/repo")

    headers = {"Accept": "application/vnd.github+json", "User-Agent": "awesome-core"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def fetch(path):
        request = Request(f"https://api.github.com/{path}", headers=headers)
        try:
            with urlopen(request, timeout=15) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code in {401, 403, 404}:
                raise RuntimeError(f"GitHub API HTTP {exc.code}") from exc
            raise RuntimeError("GitHub API request failed") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError("Nie można połączyć się z GitHub API") from exc

    repo = fetch(f"repos/{parts[0]}/{parts[1]}")
    owner = fetch(f"users/{parts[0]}")
    repo["owner_created_at"] = owner.get("created_at", "")
    repo["owner_updated_at"] = owner.get("updated_at", "")
    repo["owner_public_repos"] = owner.get("public_repos", 0)
    repo["owner_followers"] = owner.get("followers", 0)
    return repo


def audit_repo(repo_name, token=None):
    """Audit local metadata, optionally enriched with GitHub API data."""
    repo = fetch_github_audit(repo_name, token) if token is not None else {
        "full_name": repo_name
    }
    report = assess_repo(repo)
    owner_created = _date(repo.get("owner_created_at"))
    if owner_created and (datetime.now(timezone.utc) - owner_created).days < 30:
        report["attention"].append("bardzo nowe konto właściciela")
    if repo.get("owner_public_repos") == 0:
        report["info"].append("właściciel nie ma innych publicznych repozytoriów")
    report["manual_review_required"] = bool(report["attention"])
    report["status"] = "warto sprawdzić" if report["attention"] else "brak szczególnych sygnałów"
    return report
