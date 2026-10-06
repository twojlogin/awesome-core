#!/usr/bin/env python3
"""core/md.py — własny renderer Markdown → HTML, bez zewnętrznych zależności.

Powód: kiedyś web używał marked.min.js z CDN + fetch z raw.githubusercontent,
więc bez internetu README wyglądał jak surowy tekst. Teraz renderujemy
lokalny plik README przez ten moduł.
"""

import html
import re
from urllib.parse import urljoin, urlparse


MAX_INPUT = 400_000


SAFE_SCHEMES = {"http", "https", "mailto", "ftp", "irc", "gopher"}


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")


FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*([A-Za-z0-9+#.-]*)\s*$")


HR_RE = re.compile(r"^\s{0,3}([-*_])\s*(\1\s*){2,}$")


UL_RE = re.compile(r"^(\s*)([-*+])\s+(.*)$")


OL_RE = re.compile(r"^(\s*)(\d{1,9})[.)]\s+(.*)$")


BLOCKQUOTE_RE = re.compile(r"^\s{0,3}>\s?(.*)$")


TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")


HTML_BLOCK_RE = re.compile(r"^\s*<(\/?)([a-zA-Z][a-zA-Z0-9-]*)")


_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


LINK_RE = re.compile(
    r"\[([^\]]*)\]\(\s*<?([^\s<>]*(?:\([^)]*\)[^\s<>]*)*)>?"
    r"(?:\s+[\"'][^\"']*[\"'])?\s*\)"
)


REF_LINK_RE = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")


IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(\s*<?([^\s<>)]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")


AUTOLINK_RE = re.compile(r"<((?:https?|ftp|mailto):[^>\s]+)>")


BARE_URL_RE = re.compile(r"(?<![\"'(\w])(https?://[^\s<>\)\]\"']+)")


CODE_SPAN_RE = re.compile(r"(`+)(.+?)\1", re.S)


STRONG_RE = re.compile(r"(\*\*|__)(?=\S)(.+?[*_]*)(?<=\S)\1", re.S)


EM_RE = re.compile(r"(\*|_)(?=\S)(.+?)(?<=\S)\1", re.S)


STRIKE_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.S)


EMOJI_SHORTCODE_RE = re.compile(r":([a-z0-9_+-]{2,40}):", re.I)


HEADING_LABELS = {
    1: "h1", 2: "h2", 3: "h3", 4: "h4", 5: "h5", 6: "h6",
}


def slugify(text):
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text or "")
    text = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    return re.sub(r"[\s_]+", "-", text).strip("-")[:80] or "sec"


def is_safe_url(url):
    raw = (url or "").strip()
    if not raw or "[" in raw or "{" in raw or "|" in raw:
        return False
    if raw.startswith(("#", "/", "./", "../")):
        return True
    try:
        scheme = urlparse(raw).scheme.lower()
    except ValueError:
        return False
    return scheme in SAFE_SCHEMES


def absolutize(url, base_url):
    raw = (url or "").strip()
    if not raw or not base_url:
        return raw
    if raw.startswith(("http://", "https://", "mailto:", "#")):
        return raw
    try:
        return urljoin(base_url, raw)
    except ValueError:
        return raw


def _safe_link(href, text, base_url):
    if not is_safe_url(href):
        return html.escape(text)
    target = absolutize(href, base_url)
    escaped = html.escape(target, quote=True)
    external = target.startswith(("http://", "https://"))
    attrs = f' href="{escaped}"'
    if external:
        attrs += ' target="_blank" rel="noopener noreferrer"'
    return f"<a{attrs}>{text}</a>"


class Renderer:
    def __init__(self, base_url="", allow_html=False, heading_offset=1):
        self.base_url = base_url
        self.allow_html = allow_html
        self.heading_offset = heading_offset
        self.toc = []
        self._used_slugs = set()

    def render(self, text):
        lines = self._prepare(text)
        html_out, index = self._blocks(lines, 0)
        while index < len(lines):
            block, index = self._blocks(lines, index)
            html_out.append(block)
        return "\n".join(part for part in html_out if part)

    def _prepare(self, text):
        source = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        if len(source) > MAX_INPUT:
            source = source[:MAX_INPUT]
        source = source.replace(" ", " ")
        lines = []
        in_code = False
        fence = ""
        for line in source.split("\n"):
            fence_match = FENCE_RE.match(line)
            if fence_match:
                token = fence_match.group(1)
                if not in_code:
                    in_code = True
                    fence = token[0] * 3
                    lines.append(f"```code:{fence_match.group(2)}")
                    continue
                if line.strip().startswith(fence):
                    in_code = False
                    lines.append("```")
                    continue
            lines.append(line)
        if in_code:
            lines.append("```")
        return lines

    def _blocks(self, lines, index):
        out = []
        while index < len(lines):
            line = lines[index]
            stripped = line.strip()

            if not stripped:
                index += 1
                continue

            if stripped.startswith("```"):
                language = stripped[3:].replace("code:", "", 1).strip()
                index += 1
                code_lines = []
                while index < len(lines) and not lines[index].strip().startswith("```"):
                    code_lines.append(lines[index])
                    index += 1
                index += 1
                attr = f' class="language-{html.escape(language)}"' if language else ""
                body = html.escape("\n".join(code_lines))
                out.append(f"<pre><code{attr}>{body}</code></pre>")
                continue

            if HR_RE.match(line):
                out.append("<hr>")
                index += 1
                continue

            heading = HEADING_RE.match(stripped)
            if heading:
                level = min(6, len(heading.group(1)) + self.heading_offset - 1)
                text = self.inline(heading.group(2))
                slug = self._unique_slug(heading.group(2))
                self.toc.append((min(6, len(heading.group(1))), text, slug))
                out.append(
                    f'<h{level} id="{slug}">{text}'
                    f'<a class="anchor" href="#{slug}">#</a></h{level}>'
                )
                index += 1
                continue

            if BLOCKQUOTE_RE.match(line):
                quote_lines = []
                while index < len(lines) and (
                    BLOCKQUOTE_RE.match(lines[index]) or lines[index].strip()
                ):
                    match = BLOCKQUOTE_RE.match(lines[index])
                    quote_lines.append(match.group(1) if match else lines[index].strip())
                    index += 1
                inner = Renderer(self.base_url, self.allow_html, self.heading_offset)
                inner.toc = self.toc
                out.append(f"<blockquote>{inner.render(chr(10).join(quote_lines))}</blockquote>")
                continue

            if "|" in line and TABLE_SEP_RE.match(lines[index + 1] if index + 1 < len(lines) else ""):
                block, index = self._table(lines, index)
                out.append(block)
                continue

            list_match = UL_RE.match(line) or OL_RE.match(line)
            if list_match:
                block, index = self._list(lines, index)
                out.append(block)
                continue

            if not self.allow_html and HTML_BLOCK_RE.match(line):
                if not _TAG_RE.sub("", line).strip():
                    index += 1
                    continue

            paragraph = []
            while index < len(lines) and lines[index].strip():
                candidate = lines[index]
                next_line = lines[index + 1] if index + 1 < len(lines) else ""
                if (
                    HEADING_RE.match(candidate.strip())
                    or FENCE_RE.match(candidate)
                    or UL_RE.match(candidate)
                    or OL_RE.match(candidate)
                    or HR_RE.match(candidate)
                    or BLOCKQUOTE_RE.match(candidate)
                    or candidate.strip().startswith("```")
                    or ("|" in candidate and TABLE_SEP_RE.match(next_line))
                ):
                    break
                paragraph.append(candidate.strip())
                index += 1
            if paragraph:
                text = self.inline(" ".join(paragraph))
                out.append(f"<p>{text}</p>")
            else:
                index += 1
        return out, index

    def _unique_slug(self, text):
        base = slugify(re.sub(r"[*`_\[\]]", "", text))
        slug = base
        counter = 2
        while slug in self._used_slugs:
            slug = f"{base}-{counter}"
            counter += 1
        self._used_slugs.add(slug)
        return slug

    def _list(self, lines, index):
        first = UL_RE.match(lines[index]) or OL_RE.match(lines[index])
        ordered = bool(OL_RE.match(lines[index]))
        base_indent = len(first.group(1))
        items = []
        current = None
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                if index + 1 < len(lines) and (UL_RE.match(lines[index + 1])
                                               or OL_RE.match(lines[index + 1])):
                    index += 1
                    continue
                break
            match_ul = UL_RE.match(line)
            match_ol = OL_RE.match(line)
            match = match_ul or match_ol
            if match and len(match.group(1)) <= base_indent + 1:
                current = [self.inline(match.group(3))]
                items.append(current)
                index += 1
                continue
            if match and current is not None:
                current.append(f'<p class="md-cont">- {self.inline(match.group(3))}</p>')
                index += 1
                continue
            if current is not None and line.startswith(" " * (base_indent + 2)):
                current[-1] = current[-1] + " " + self.inline(line.strip())
                index += 1
                continue
            if current is None:
                break
            index += 1
        tag = "ol" if ordered else "ul"
        body = "".join(
            f"<li>{''.join(chunk for chunk in item if not chunk.startswith('<p class=\"md-cont\"'))}"
            f"{''.join(chunk for chunk in item if chunk.startswith('<p class=\"md-cont\"'))}</li>"
            for item in items
        )
        return f"<{tag}>{body}</{tag}>", index

    def _table(self, lines, index):
        header = self._row_cells(lines[index])
        index += 1
        index += 1
        rows = []
        while index < len(lines) and "|" in lines[index] and lines[index].strip():
            rows.append(self._row_cells(lines[index]))
            index += 1
        head = "".join(f"<th>{cell}</th>" for cell in header)
        body = "".join(
            "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>", index

    def _row_cells(self, line):
        raw = line.strip()
        if raw.startswith("|"):
            raw = raw[1:]
        if raw.endswith("|"):
            raw = raw[:-1]
        cells = re.split(r"(?<!\\)\|", raw)
        cleaned = []
        for cell in cells:
            value = cell.strip().replace("\\|", "|")
            if not value:
                continue
            if self.allow_html or not IMAGE_RE.search(value):
                cleaned.append(self.inline(value))
            elif LINK_RE.search(value):
                cleaned.append(self.inline(value))
        return cleaned

    def inline(self, text):
        if not text:
            return ""
        placeholders = []

        def stash(value):
            placeholders.append(value)
            return f"\x00{len(placeholders) - 1}\x00"

        def code_span(match):
            return stash(f"<code>{html.escape(match.group(2).strip())}</code>")

        text = CODE_SPAN_RE.sub(code_span, text)

        def image(match):
            alt, src = match.group(1), match.group(2)
            target = absolutize(src, self.base_url)
            if not is_safe_url(target):
                return stash(html.escape(alt))
            return stash(
                f'<img src="{html.escape(target, quote=True)}"'
                f' alt="{html.escape(alt)}" loading="lazy">'
            )

        text = IMAGE_RE.sub(image, text)

        def link(match):
            label, href = match.group(1), match.group(2)
            return stash(_safe_link(href, self.inline_label(label), self.base_url))

        text = LINK_RE.sub(link, text)
        text = REF_LINK_RE.sub(lambda m: m.group(1), text)
        text = AUTOLINK_RE.sub(
            lambda m: stash(_safe_link(m.group(1), html.escape(m.group(1)), self.base_url)),
            text,
        )
        text = BARE_URL_RE.sub(
            lambda m: stash(
                _safe_link(m.group(1).rstrip(".,);"), html.escape(m.group(1).rstrip(".,);")),
                           self.base_url)
            ),
            text,
        )

        text = html.escape(text)
        text = STRONG_RE.sub(r"<strong>\2</strong>", text)
        text = STRIKE_RE.sub(r"<del>\1</del>", text)
        text = EM_RE.sub(r"<em>\2</em>", text)
        text = EMOJI_SHORTCODE_RE.sub(lambda m: m.group(0), text)

        for index, value in enumerate(placeholders):
            text = text.replace(f"\x00{index}\x00", value)
        return text

    def inline_label(self, label):
        label = CODE_SPAN_RE.sub(lambda m: html.escape(m.group(2).strip()), label)
        label = IMAGE_RE.sub(lambda m: html.escape(m.group(1)), label)
        return html.escape(label)


def render(text, base_url="", allow_html=False):
    renderer = Renderer(base_url=base_url, allow_html=allow_html)
    body = renderer.render(text)
    return body, renderer.toc


def render_toc(toc, limit=40):
    if not toc:
        return ""
    items = []
    for level, label, slug in toc[:limit]:
        items.append(
            f'<li class="md-toc md-toc-{level}">{label}'
            f'<a href="#{slug}">↗</a></li>'
        )
    return f'<ul class="md-toc-list">{"".join(items)}</ul>'


def excerpt(text, needle, max_chars=6000):
    """Wycina sekcję z README, w której pojawia się nazwa narzędzia."""
    if not text:
        return ""
    if not needle:
        return text[:max_chars]
    lines = text.split("\n")
    target = needle.lower().strip()
    hit = None
    for index, line in enumerate(lines):
        if target and target in line.lower():
            hit = index
            break
    if hit is None:
        return text[:max_chars]
    start = hit
    base_level = None
    for index in range(hit, -1, -1):
        heading = HEADING_RE.match(lines[index].strip())
        if heading:
            base_level = len(heading.group(1))
            start = index
            break
    end = len(lines)
    for index in range(hit + 1, len(lines)):
        match = HEADING_RE.match(lines[index].strip())
        if match and len(match.group(1)) <= (base_level or 6):
            end = index
            break
    section = "\n".join(lines[start:end])
    if len(section) > max_chars:
        section = section[:max_chars].rsplit("\n", 1)[0] + "\n…"
    return section


def raw_github_url(full_name, branch="main"):
    owner, _, name = (full_name or "").partition("/")
    if not owner or not name:
        return ""
    return f"https://github.com/{owner}/{name}"
