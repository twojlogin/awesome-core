#!/usr/bin/env python3
"""core/scoring.py — consensus score, jakość list i ranking narzędzi.

Formuły są w jednym miejscu, żeby dało się je wytłumaczyć (`awesome why`).
"""

import math
import re
from datetime import datetime, timezone


WEIGHTS_TOOL = {
    "consensus": 0.28,
    "own_stars": 0.22,
    "list_stars": 0.06,
    "quality": 0.14,
    "desc": 0.10,
    "alive": 0.14,
    "known": 0.06,
}


WEIGHTS_LIST = {
    "desc": 0.26,
    "alive": 0.18,
    "unique": 0.18,
    "projects": 0.16,
    "fresh": 0.12,
    "size": 0.10,
}


DAY = 86400.0


FRESH_HALFLIFE_DAYS = 540.0


CONSENSUS_PER_LIST = 0.10


CONSENSUS_PER_OWNER = 0.12


def _parse_date(value):
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    match = re.match(r"^(\d{4}-\d{2}-\d{2})([T ](\d{2}:\d{2}:\d{2}))?", text)
    if not match:
        return None
    stamp = match.group(1)
    if match.group(3):
        stamp += "T" + match.group(3)
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def age_days(value, now=None):
    stamp = _parse_date(value)
    if stamp is None:
        return None
    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    return max(0.0, (now - stamp) / DAY)


def freshness(pushed_at, now=None):
    """1.0 dla świeżego repo, ~0.5 po roku, ~0.1 po 4 latach."""
    days = age_days(pushed_at, now)
    if days is None:
        return 0.5
    return round(0.5 ** (days / FRESH_HALFLIFE_DAYS), 4)


def size_factor(count):
    """Nasycenie: małe listy są mniej wiarygodne, duże nie rosną w nieskończoność."""
    if count <= 0:
        return 0.0
    if count < 30:
        return round(0.15 * count / 30, 4)
    return round(min(1.0, math.log10(count) / math.log10(1000)), 4)


def star_factor(stars):
    stars = max(0, int(stars or 0))
    if stars <= 0:
        return 0.0
    return round(min(1.0, math.log10(1 + stars) / 6.0), 4)


def consensus(list_count, owners_count, quality_sum):
    """Zgoda niezależnych kuratorów: 1 lista ≈ 0.10, 3 niezależne ≈ 0.5, 8+ ≈ 1.0.

    owners_count ma większą wagę niż sam licznik list, bo 12 kopii tej samej
    listy (forki/mirrory) to nie jest 12 niezależnych opinii.
    """
    if list_count <= 0:
        return 0.0
    avg_quality = max(0.0, min(1.0, quality_sum / max(1, list_count)))
    raw = (
        CONSENSUS_PER_LIST * list_count
        + CONSENSUS_PER_OWNER * max(0, owners_count - 1)
    )
    return round(min(1.0, raw) * (0.55 + 0.45 * avg_quality), 4)


def repo_quality(stats, now=None):
    """Jakość listy 0..1 z rozbiciem na składowe (do `--explain`)."""
    total = max(0, int(stats.get("total", 0) or 0))
    with_desc = max(0, int(stats.get("with_desc", 0) or 0))
    duplicates = max(0, int(stats.get("duplicates", 0) or 0))
    junk = max(0, int(stats.get("junk", 0) or 0))
    alive_checked = max(0, int(stats.get("alive_checked", 0) or 0))
    alive_ok = max(0, int(stats.get("alive_ok", 0) or 0))
    projects = stats.get("projects")
    projects_ratio = 0.6 if projects is None else max(0.0, min(1.0, float(projects)))

    denom = max(1, total)
    parts = {
        "desc": round(with_desc / denom, 4),
        "unique": round(1.0 - min(1.0, duplicates / denom), 4) if total else 0.0,
        "alive": round(alive_ok / alive_checked, 4) if alive_checked else None,
        "projects": round(projects_ratio, 4) if total else 0.0,
        "fresh": freshness(stats.get("pushed_at"), now),
        "size": size_factor(total),
    }
    quality = 0.0
    weight_sum = 0.0
    for key, weight in WEIGHTS_LIST.items():
        value = parts.get(key)
        if value is None:
            continue
        quality += weight * value
        weight_sum += weight
    parts["junk"] = round(junk / denom, 4)
    parts["quality"] = round(min(1.0, quality / weight_sum), 4) if weight_sum else 0.0
    return parts


def tool_score(ctx):
    """Ranking 0..100 + `underrated` (dobre narzędzia z małych list).

    Priorytet mają gwiazdki samego narzędzia (z GitHub API), a nie gwiazdki
    listy, w której trafiło — inaczej „najlepsze" znaczy tylko „najgłośniejsza lista".
    """
    list_stars = max(0, int(ctx.get("source_stars", 0) or 0))
    own_stars = max(0, int(ctx.get("tool_stars", 0) or 0))
    parts = {
        "consensus": max(0.0, min(1.0, float(ctx.get("consensus", 0.0) or 0.0))),
        "own_stars": star_factor(own_stars),
        "list_stars": 0.5 * star_factor(list_stars),
        "quality": max(0.0, min(1.0, float(ctx.get("list_quality", 0.0) or 0.0))),
        "desc": 1.0 if ctx.get("has_desc") else 0.0,
        "alive": _alive_score(ctx.get("alive")),
        "known": 1.0 if ctx.get("has_own_meta") else 0.0,
    }
    score = sum(WEIGHTS_TOOL[key] * value for key, value in parts.items())
    ctx_out = dict(ctx)
    ctx_out["parts"] = {k: round(v, 4) for k, v in parts.items()}
    ctx_out["score"] = round(100.0 * score, 2)
    reach = parts["own_stars"] if own_stars else parts["list_stars"]
    ctx_out["underrated"] = round(
        100.0 * parts["quality"] * parts["desc"] * parts["consensus"] * (1.0 - reach),
        2,
    )
    ctx_out["hidden_gem"] = round(
        100.0 * parts["quality"] * parts["desc"] * parts["consensus"]
        * (0.15 + 0.85 * (1.0 - reach)) * max(parts["own_stars"], parts["list_stars"]),
        2,
    )
    return ctx_out


def _alive_score(alive):
    if alive is True:
        return 1.0
    if alive is False:
        return 0.0
    return 0.5


def explain(tool):
    """Czytelne rozbicie rankingu dla `awesome why`."""
    parts = tool.get("parts") or {}
    rows = []
    for key, weight in WEIGHTS_TOOL.items():
        value = float(parts.get(key, 0.0))
        rows.append((key, value, weight, round(weight * value * 100, 2)))
    rows.sort(key=lambda r: -r[3])
    return {
        "score": tool.get("score", 0),
        "underrated": tool.get("underrated", 0),
        "rows": rows,
    }
