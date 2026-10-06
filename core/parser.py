#!/usr/bin/env python3
"""core/parser.py — wyciąganie narzędzi z README awesome list (listy + tabele)."""

import re

from core import langmap


FENCE_RE = re.compile(r"^\s*(```+|~~~+)")


BULLET_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")


TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")


LINK_RE = re.compile(r"\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")


BARE_LINK_RE = re.compile(r"(?<![\(\[<])(https?://[^\s<>\)\]|\"']+)")


IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


IMAGE_LINK_RE = re.compile(r"\[!\[[^\]]*\](?:\[[^\]]*\])?\]\([^)]*\)")


REF_IMAGE_RE = re.compile(r"!\[[^\]]*\]\[[^\]]*\]")


ANCHOR_REF_RE = re.compile(r"^\s*\[[^\]]+\]:")
_MD_LINK_INLINE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_ESCAPED_CHAR = re.compile(r"\\([|*_{}\[\]()#+\-.!])")


SKIP_SECTIONS = {
    "table of contents", "contents", "toc", "index", "license", "licence",
    "contributing", "contribute", "changelog", "credits", "acknowledgments",
    "acknowledgements", "authors", "maintainers", "sponsors", "support",
    "related awesome lists", "awesome lists", "more awesome lists",
    "further reading", "references", "bibliography", "books", "papers",
    "articles", "podcasts", "newsletters", "twitter", "twitter follow",
    "star history", "contributors", "footer", "disclaimer",
}


MAX_SECTION_DEPTH = 80


def _strip_markdown(text):
    out = text or ""
    if "![" in out:
        out = IMAGE_LINK_RE.sub("", out)
        out = IMAGE_RE.sub("", out)
        out = REF_IMAGE_RE.sub("", out)
    if "](" in out:
        out = _MD_LINK_INLINE.sub(lambda m: m.group(1), out)
    out = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", lambda m: m.group(1), out)
    out = out.replace("**", "").replace("__", "").replace("*", "")
    out = out.replace("`", "").replace("~~", "")
    out = HTML_TAG_RE.sub("", out)
    out = out.replace("&nbsp;", " ").replace("&amp;", "&")
    if "\\" in out:
        out = _ESCAPED_CHAR.sub(r"\1", out)
    out = re.sub(r"\s{2,}", " ", out).strip(" \t-–—:|.,;")
    return out.strip()


def _first_link(text):
    """Zwraca (nazwa, url) pierwszego linku w tekście + opis reszty."""
    match = IMAGE_RE.search(text)
    prefix = ""
    if match and match.start() == 0:
        prefix = text[: match.end()]
    link = LINK_RE.search(text[match.end():] if prefix else text)
    if not link:
        return None
    name = _strip_markdown(link.group(1))
    url = link.group(2).strip()
    rest = text[link.end():]
    if prefix:
        rest = text[: link.end()] + rest
    desc = _strip_markdown(rest)
    if not name and prefix:
        return None
    return name, url, desc


def _clean_description(text):
    desc = _strip_markdown(text)
    desc = re.sub(r"^[-–—:•*]+\s*", "", desc)
    desc = re.sub(r"^[\[(][^\])]*[\])]\s*", "", desc)
    return langmap.truncate_words(desc)


def _is_toc_heading(title):
    low = re.sub(r"[^a-z ]+", " ", title.lower()).strip()
    low = re.sub(r"\s{2,}", " ", low)
    if not low:
        return True
    if low in SKIP_SECTIONS:
        return True
    if low.startswith("table of content") or low.startswith("index of"):
        return True
    if re.match(r"^(contents|content|index|toc|license|contributing)$", low):
        return True
    return False


def parse_readme(text):
    """Zwraca listę wystąpień narzędzi: dict(name, url, description, section, subsection)."""
    mentions = []
    section = ""
    subsection = ""
    in_comment = False
    in_code = False
    fence = ""

    for line in (text or "").splitlines():
        stripped = line.strip()

        if in_code:
            if FENCE_RE.match(line) and line.strip().startswith(fence):
                in_code = False
            continue

        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue

        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_comment = True
            continue

        fence_match = FENCE_RE.match(line)
        if fence_match:
            in_code = True
            fence = fence_match.group(1)
            continue

        heading = HEADING_RE.match(stripped)
        if heading:
            level = len(heading.group(1))
            title = _strip_markdown(heading.group(2))
            if level <= 1:
                continue
            if _is_toc_heading(title):
                section = ""
                subsection = ""
                continue
            if level == 2:
                section = langmap.normalize_section(title)[:MAX_SECTION_DEPTH]
                subsection = ""
            else:
                parent = langmap.normalize_section(title)[:MAX_SECTION_DEPTH]
                if not section:
                    section = parent
                    subsection = ""
                elif parent != section:
                    subsection = parent
                else:
                    subsection = ""
            continue

        if TABLE_ROW_RE.match(line) or not stripped:
            if TABLE_SEP_RE.match(line):
                continue
            if TABLE_ROW_RE.match(line):
                tool = _parse_table_row(line, section, subsection)
                if tool:
                    mentions.append(tool)
            continue

        if stripped.startswith("|") or stripped.startswith(">"):
            continue

        bullet = BULLET_RE.match(line)
        if not bullet:
            continue
        body = bullet.group(2)
        if ANCHOR_REF_RE.match(body):
            continue
        if body.startswith("!["):
            continue
        found = _first_link(body)
        if not found:
            bare = BARE_LINK_RE.search(body)
            if bare and not IMAGE_RE.search(body):
                name = _strip_markdown(body[: bare.start()]) or body
                tool = _make(name, bare.group(0), body[bare.end():], section, subsection)
                if tool:
                    mentions.append(tool)
            continue
        name, url, desc = found
        tool = _make(name, url, desc, section, subsection)
        if tool:
            mentions.append(tool)

    return mentions


def _parse_table_row(line, section, subsection):
    cells = [c for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
    name = ""
    url = ""
    desc_parts = []
    for cell in cells:
        cell = cell.strip()
        if not cell or TABLE_SEP_RE.match(cell):
            continue
        if IMAGE_RE.search(cell) and not LINK_RE.search(cell):
            continue
        found = _first_link(cell)
        if found and not url:
            name, url, desc_parts = found[0], found[1], [found[2]]
            continue
        if found:
            desc_parts.append(_strip_markdown(cell))
            continue
        text = _strip_markdown(cell)
        if text and text not in {"⭐", "🔰"}:
            desc_parts.append(text)
    if not url:
        return None
    desc = _clean_description(" ".join(p for p in desc_parts if p))
    return _make(name, url, desc, section, subsection, raw_desc=desc)


def _make(name, url, desc, section, subsection, raw_desc=None):
    url = (url or "").strip().strip("<>")
    name = langmap.clean_name(name)
    description = langmap.truncate_words(raw_desc if raw_desc else desc)
    if not url.lower().startswith(("http://", "https://")):
        return None
    if not langmap.valid_url(url):
        return None
    if not name:
        name = url.rstrip("/").rsplit("/", 1)[-1][:60]
    return {
        "name": name,
        "url": url,
        "description": description,
        "section": section or "Other",
        "subsection": subsection or "",
    }


def parse_stats(mentions):
    """Statystyki listy potrzebne do jakości (core/scoring.repo_quality)."""
    total = len(mentions)
    with_desc = sum(1 for m in mentions if langmap.has_description(m["description"]))
    junk = sum(
        1
        for m in mentions
        if langmap.looks_like_junk(m["name"], m["url"], m["description"])
    )
    seen = set()
    duplicates = 0
    for m in mentions:
        key = langmap.url_identity(m["url"])
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)
    return {
        "total": total,
        "with_desc": with_desc,
        "junk": junk,
        "duplicates": duplicates,
        "unique": len(seen),
    }
