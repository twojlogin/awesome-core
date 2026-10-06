#!/usr/bin/env python3
"""core/clones.py — wykrywanie kopii awesome list.

Trzy listy, które kopiują jedną, to nie trzy niezależne opinie. Bez tego
nasz consensus zawyża zgodę kuratorów. Wykrywamy twarde kopie
(≥80% narzędzi wspólnych z większą listą) i przy liczeniu consensusu
pomijaamy wzmianki z list oznaczonych jako klony.

Kopii nie usuwamy — zostaje w tool_mentions, żeby dało się zobaczyć,
kto co powielał.
"""

from collections import defaultdict

MAX_LISTS_PER_TOOL = 60
MIN_SHARED = 20
MIN_LIST_SIZE = 30
OVERLAP_THRESHOLD = 0.8


def detect_clones(
    list_tools,
    list_meta=None,
    threshold=OVERLAP_THRESHOLD,
    min_shared=MIN_SHARED,
    min_size=MIN_LIST_SIZE,
    max_lists_per_tool=MAX_LISTS_PER_TOOL,
):
    """Zwraca listę par: kanon, klon, wspólne, nakładanie, ten sam właściciel.

    list_tools: {full_name: set(url_norm)}
    list_meta:  {full_name: {"stars": int, "quality": float}} (opcjonalne)
    """
    meta = list_meta or {}
    sets = {name: tools for name, tools in list_tools.items() if len(tools) >= min_size}
    if not sets:
        return []

    inverted = defaultdict(list)
    for name, tools in sets.items():
        for identity in tools:
            inverted[identity].append(name)

    pairs = defaultdict(int)
    for lists in inverted.values():
        if len(lists) < 2 or len(lists) > max_lists_per_tool:
            continue
        ordered = sorted(lists)
        for index, left in enumerate(ordered):
            for right in ordered[index + 1:]:
                pairs[(left, right)] += 1

    found = []
    for (left, right), shared in pairs.items():
        if shared < min_shared:
            continue
        bigger = max(len(sets[left]), len(sets[right]))
        overlap = shared / bigger if bigger else 0.0
        if overlap < threshold:
            continue
        canonical, clone = _canonical(left, right, sets, meta)
        found.append({
            "canonical": canonical,
            "clone": clone,
            "shared": shared,
            "overlap": round(overlap, 4),
            "canonical_size": len(sets[canonical]),
            "clone_size": len(sets[clone]),
            "same_owner": _owner(canonical) == _owner(clone),
        })

    found.sort(key=lambda row: (-row["shared"], row["clone"]))
    return _resolve_chains(found)


def _owner(full_name):
    return (full_name or "").split("/", 1)[0].lower()


def _canonical(left, right, sets, meta):
    """Kanonem jest większa lista; przy remisie jakość, potem gwiazdki."""
    def key(name):
        return (
            len(sets[name]),
            round(float(meta.get(name, {}).get("quality", 0) or 0), 3),
            int(meta.get(name, {}).get("stars", 0) or 0),
            name,
        )

    return (left, right) if key(left) > key(right) else (right, left)


def _resolve_chains(rows):
    """A→B i B→C sprowadza do jednej ścieżki: B i C wskazują na A."""
    parent = {}
    for row in rows:
        parent.setdefault(row["clone"], row["canonical"])

    def root(name):
        seen = set()
        while name in parent and name not in seen:
            seen.add(name)
            name = parent[name]
        return name

    out = []
    seen_pairs = set()
    for row in rows:
        canonical = root(row["canonical"])
        if canonical == row["clone"]:
            continue
        pair = (canonical, row["clone"])
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        resolved = dict(row)
        resolved["canonical"] = canonical
        resolved["chain"] = row["canonical"] != canonical
        out.append(resolved)
    return out


def fork_pairs(repo_rows):
    """Forki z metadanych GitHuba: (fork, parent) dla list, które są forkiem.

    Silniejszy sygnał niż podobieństwo treści — GitHub zna genealogię.
    """
    known = {row["full_name"]: row for row in repo_rows}
    out = []
    for row in repo_rows:
        parent = (row.get("parent") or "").strip()
        if not parent or not row.get("is_fork"):
            continue
        parent_row = known.get(parent)
        out.append({
            "canonical": parent,
            "clone": row["full_name"],
            "shared": int(row.get("unique_tool_count") or 0),
            "overlap": None,
            "fork": True,
            "same_owner": _owner(parent) == _owner(row["full_name"]),
            "stars": int(row.get("stars") or 0),
            "parent_stars": int(parent_row.get("stars") or 0) if parent_row else 0,
            "tools": int(row.get("unique_tool_count") or 0),
        })
    out.sort(key=lambda row: (-row["shared"], row["clone"]))
    return out


def report(conn, min_shared=MIN_SHARED, threshold=OVERLAP_THRESHOLD):
    """Łączy oba sygnały: kopie treści + forki. Wymaga połączenia do tools."""
    list_tools = defaultdict(set)
    for row in conn.execute(
        "SELECT source_repo, url_norm FROM tool_mentions WHERE source_repo != ''"
    ):
        list_tools[row["source_repo"]].add(row["url_norm"])
    repo_rows = [dict(r) for r in conn.execute(
        "SELECT full_name, stars, quality, is_fork, parent, unique_tool_count"
        " FROM repos"
    )]
    meta = {r["full_name"]: r for r in repo_rows}
    copies = detect_clones(list_tools, meta, min_shared=min_shared, threshold=threshold)
    forks = fork_pairs(repo_rows)
    return {
        "copies": copies,
        "forks": forks,
        "copy_pairs": len(copies),
        "fork_pairs": len(forks),
        "clone_lists": len({r["clone"] for r in copies}),
        "fork_lists": len({r["clone"] for r in forks}),
        "lists_without_parent": sum(
            1 for r in repo_rows if r.get("is_fork") and not (r.get("parent") or "")
        ),
    }


def clone_map(rows):
    """{klon: kanon} dla list oznaczonych jako kopie."""
    return {row["clone"]: row["canonical"] for row in rows}


def summarize(rows):
    clones = {row["clone"] for row in rows}
    canon = {row["canonical"] for row in rows}
    same_owner = sum(1 for row in rows if row["same_owner"])
    return {
        "pairs": len(rows),
        "clones": len(clones),
        "canonicals": len(canon),
        "same_owner": same_owner,
        "shared_total": sum(row["shared"] for row in rows),
    }
