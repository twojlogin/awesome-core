"""Local repository watch list with opt-in GitHub refreshes."""

from datetime import datetime, timezone
import json
from pathlib import Path

from .trust import fetch_github_audit


DEFAULT_FILE = Path(__file__).parent.parent / "data" / "watched_repos.json"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _validate_name(name):
    parts = name.split("/", 1)
    if len(parts) != 2 or not all(parts) or any(part in {".", ".."} for part in parts):
        raise ValueError("Repozytorium musi mieć format owner/repo")
    return f"{parts[0]}/{parts[1]}"


class RepoWatcher:
    def __init__(self, path=DEFAULT_FILE):
        self.path = Path(path)
        self.data = self._load()

    def _load(self):
        if not self.path.exists():
            return {}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Nie można odczytać watchera: {exc}") from exc
        if not isinstance(value, dict):
            raise RuntimeError("Plik watchera ma nieprawidłowy format")
        return value

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def add(self, name):
        name = _validate_name(name)
        if name not in self.data:
            self.data[name] = {"repo": name, "added_at": _now(), "snapshot": None}
            self._save()
        return self.data[name]

    def remove(self, name):
        name = _validate_name(name)
        removed = self.data.pop(name, None) is not None
        if removed:
            self._save()
        return removed

    def list(self):
        return [self.data[name] for name in sorted(self.data)]

    def check(self, name, token):
        name = _validate_name(name)
        remote = fetch_github_audit(name, token)
        snapshot = {
            "stars": remote.get("stargazers_count", remote.get("stars", 0)),
            "forks": remote.get("forks_count", remote.get("forks", 0)),
            "pushed_at": remote.get("pushed_at", ""),
            "archived": bool(remote.get("archived", False)),
            "license": (remote.get("license") or {}).get("spdx_id", "")
            if isinstance(remote.get("license"), dict)
            else remote.get("license", ""),
            "checked_at": _now(),
        }
        previous = (self.data.get(name) or {}).get("snapshot")
        changes = {}
        if previous:
            for field, value in snapshot.items():
                if field != "checked_at" and previous.get(field) != value:
                    changes[field] = {"old": previous.get(field), "new": value}
        self.data[name] = {
            **self.data.get(name, {"repo": name, "added_at": _now()}),
            "repo": name,
            "snapshot": snapshot,
        }
        self._save()
        return snapshot, changes
