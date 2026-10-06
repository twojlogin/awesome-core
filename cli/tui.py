#!/usr/bin/env python3
"""cli/tui.py — Awesome Core w terminalu (curses, tylko biblioteka standardowa)."""

import curses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import store  # noqa: E402
from core.tools_db import ToolsDB  # noqa: E402


SORTS = [
    ("score", "score"),
    ("consensus", "zgoda kuratorów"),
    ("stars", "gwiazdki"),
    ("gem", "ukryte perełki"),
    ("underrated", "niedoceniane"),
    ("name", "alfabetycznie"),
]


HELP = [
    ("/", "szukaj"),
    ("l", "następny język"),
    ("o", "następna platforma"),
    ("d", "następna domena"),
    ("s", "zmień sortowanie"),
    ("a", "wyczyść filtry"),
    ("g", "tylko ukryte perełki"),
    ("u", "tylko niedoceniane"),
    ("Enter", "szczegóły"),
    ("i", "instaluj"),
    ("?", "pomoc"),
    ("q", "wyjście"),
]


class TuiState:
    def __init__(self, db):
        self.db = db
        self.query = ""
        self.langs = [name for name, _count in db.langs(min_count=3, limit=40)]
        self.platforms = [name for name, _count in db.platforms(min_count=3, limit=25)]
        self.domains = [name for name, _count in db.domains(min_count=5, limit=20)
                        if name != "?"]
        self.lang_index = -1
        self.platform_index = -1
        self.domain_index = -1
        self.sort_index = 0
        self.only_gems = False
        self.only_underrated = False
        self.results = []
        self.cursor = 0
        self.offset = 0
        self.status = ""
        self.running = True
        self.mode = "list"

    @property
    def lang(self):
        if 0 <= self.lang_index < len(self.langs):
            return self.langs[self.lang_index]
        return None

    @property
    def platform(self):
        if 0 <= self.platform_index < len(self.platforms):
            return self.platforms[self.platform_index]
        return None

    @property
    def domain(self):
        if 0 <= self.domain_index < len(self.domains):
            return self.domains[self.domain_index]
        return None

    @property
    def sort(self):
        return SORTS[self.sort_index][0]

    def filters_active(self):
        return bool(self.lang or self.platform or self.domain)

    def refresh(self):
        query = self.query.strip()
        if self.only_gems:
            self.results = self.db.gems(limit=200, lang=self.lang)
        elif self.only_underrated:
            self.results = self.db.underrated(limit=200, lang=self.lang)
        elif query:
            self.results = self.db.search(
                query, limit=200, lang=self.lang, platform=self.platform,
                domain=self.domain, sort=self.sort,
            )
        else:
            self.results = self.db._query(
                "1=1", [], limit=200, sort=self.sort,
            )
        self.cursor = min(self.cursor, max(0, len(self.results) - 1))

    def current(self):
        if 0 <= self.cursor < len(self.results):
            return self.results[self.cursor]
        return None


def _safe(text, width):
    text = str(text or "").replace("\n", " ").replace("\t", " ")
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 1] + "…"


def _header(stdscr, state, rows):
    lang = state.lang or "dowolny"
    platform = state.platform or "dowolna"
    domain = state.domain or "dowolna"
    extra = []
    if state.only_gems:
        extra.append("TRYB: perełki")
    if state.only_underrated:
        extra.append("TRYB: niedoceniane")
    title = f" Awesome Core — {len(state.results)} wyników | sort: {SORTS[state.sort_index][1]} "
    sub = f" lang: {lang} | os: {platform} | domena: {domain} | {state.sort} "
    if extra:
        sub += " | " + " ".join(extra)
    try:
        stdscr.addnstr(0, 0, title.ljust(rows), rows, curses.A_BOLD | curses.A_REVERSE)
        stdscr.addnstr(1, 0, _safe(sub, rows), rows, curses.A_DIM)
        if state.query:
            stdscr.addnstr(2, 0, _safe(f"szukaj: {state.query}", rows), rows,
                           curses.A_UNDERLINE)
    except curses.error:
        pass
    return 4 if state.query else 3


def _footer(stdscr, state, rows, height):
    keys = "  ".join(f"{key}={label}" for key, label in HELP)
    try:
        stdscr.addnstr(height - 2, 0, _safe(keys, rows), rows, curses.A_DIM)
        stdscr.addnstr(height - 1, 0, _safe(state.status, rows), rows, curses.A_BOLD)
    except curses.error:
        pass


def _draw_list(stdscr, state, rows, height):
    top = _header(stdscr, state, rows)
    bottom = height - 2
    visible = max(1, bottom - top)
    if state.cursor < state.offset:
        state.offset = state.cursor
    if state.cursor >= state.offset + visible:
        state.offset = state.cursor - visible + 1
    state.offset = max(0, min(state.offset, max(0, len(state.results) - visible)))

    name_w = max(18, rows // 3)
    lang_w = 12
    for index in range(visible):
        pos = state.offset + index
        if pos >= len(state.results):
            break
        tool = state.results[pos]
        stars = tool.get("tool_stars") or tool.get("source_stars") or 0
        line = (
            _safe(tool.get("name", "?"), name_w).ljust(name_w)
            + _safe(tool.get("lang") or "?", lang_w).ljust(lang_w)
            + f"{tool.get('lists_count', 0):>3} list "
            + f"{stars:>7}★ "
            + f"{tool.get('score', 0):>5.1f} "
            + _safe(tool.get("section") or "", max(8, rows - name_w - lang_w - 26))
        )
        attr = curses.A_REVERSE if pos == state.cursor else curses.A_NORMAL
        if tool.get("alive") is False:
            attr |= curses.A_DIM
        try:
            stdscr.addnstr(top + index, 0, _safe(line, rows), rows, attr)
        except curses.error:
            pass


def _draw_detail(stdscr, state, rows, height):
    tool = state.current()
    if not tool:
        return
    lines = [
        ("", tool.get("name", "?"), curses.A_BOLD),
        ("URL", tool.get("url", ""), curses.A_NORMAL),
        ("Opis", tool.get("description") or "-", curses.A_NORMAL),
        ("Język", tool.get("lang") or "?", curses.A_NORMAL),
        ("Platforma", tool.get("platform") or "-", curses.A_NORMAL),
        ("Domena", tool.get("tags") or "-", curses.A_NORMAL),
        ("Sekcja", f"{tool.get('section') or '-'} / {tool.get('subsection') or '-'}", curses.A_NORMAL),
        ("Lista", f"{tool.get('source_repo')} ({tool.get('source_stars', 0)}★)", curses.A_NORMAL),
        ("Gwiazdki", tool.get("tool_stars", 0), curses.A_NORMAL),
        ("Zgoda", f"{tool.get('lists_count', 0)} list / {tool.get('owners_count', 0)} autorów",
         curses.A_NORMAL),
        ("Score", f"{tool.get('score', 0):.1f} (niedoceniane {tool.get('underrated', 0):.1f})",
         curses.A_NORMAL),
        ("Link", "żywy" if tool.get("alive") else ("martwy" if tool.get("alive") is False else "nie sprawdzony"),
         curses.A_NORMAL),
        ("Instalacja", tool.get("install_method") or "brak", curses.A_NORMAL),
        ("", "W listach:", curses.A_BOLD),
    ]
    for mention in state.db.mentions(tool.get("url_norm", ""))[:12]:
        lines.append(("  ·", f"{mention['source_repo']} — {mention['section']}", curses.A_NORMAL))
    try:
        for index, (label, value, attr) in enumerate(lines[: height - 3]):
            text = f"{label:<11} {value}" if label else f" {value}"
            stdscr.addnstr(index, 0, _safe(text, rows), rows, attr)
        stdscr.addnstr(height - 2, 0, _safe("Enter/wstecz = powrót", rows), rows, curses.A_DIM)
    except curses.error:
        pass


def _read_query(stdscr, state, rows, height):
    curses.curs_set(1)
    buffer = ""
    prompt = "szukaj: "
    while True:
        try:
            stdscr.erase()
            stdscr.addnstr(0, 0, _safe(prompt + buffer + "_", rows), rows, curses.A_BOLD)
            stdscr.refresh()
            key = stdscr.get_wch()
        except curses.error:
            return state.query
        if key in ("\n", "\r", curses.KEY_ENTER):
            curses.curs_set(0)
            return buffer.strip()
        if key == "\x1b":
            curses.curs_set(0)
            return state.query
        if isinstance(key, str) and key in ("\b", "\x7f"):
            buffer = buffer[:-1]
            continue
        if isinstance(key, str) and key.isprintable():
            buffer += key


def _run(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    try:
        data_dir = Path(__file__).parent.parent / "data"
    except NameError:
        data_dir = None
    try:
        db = ToolsDB(data_dir)
        db.stats()
    except RuntimeError as exc:
        stdscr.addnstr(0, 0, str(exc)[:100], 100, curses.A_BOLD)
        stdscr.addnstr(1, 0, "Naciśnij dowolny klawisz, aby wyjść", 100)
        stdscr.refresh()
        stdscr.getch()
        return
    state = TuiState(db)
    state.refresh()

    while state.running:
        height, width = stdscr.getmaxyx()
        rows = max(20, width - 1)
        stdscr.erase()
        if state.mode == "detail":
            _draw_detail(stdscr, state, rows, height)
        else:
            _draw_list(stdscr, state, rows, height)
            _footer(stdscr, state, rows, height)
        stdscr.refresh()

        try:
            key = stdscr.get_wch()
        except (curses.error, KeyboardInterrupt):
            break

        if state.mode == "detail":
            if key in ("\n", "\r", curses.KEY_ENTER, "q", "\x1b"):
                state.mode = "list"
            continue

        if isinstance(key, str) and key == "/":
            state.query = _read_query(stdscr, state, rows, height)
            state.cursor = 0
            state.refresh()
        elif key in (curses.KEY_UP, "k"):
            state.cursor = max(0, state.cursor - 1)
        elif key in (curses.KEY_DOWN, "j"):
            state.cursor = min(max(0, len(state.results) - 1), state.cursor + 1)
        elif key == curses.KEY_PPAGE:
            state.cursor = max(0, state.cursor - 15)
        elif key == curses.KEY_NPAGE:
            state.cursor = min(max(0, len(state.results) - 1), state.cursor + 15)
        elif key == curses.KEY_HOME:
            state.cursor = 0
        elif key == curses.KEY_END:
            state.cursor = max(0, len(state.results) - 1)
        elif isinstance(key, str) and key == "l":
            state.lang_index = (state.lang_index + 1) % (len(state.langs) + 1) - 1
            state.cursor = 0
            state.refresh()
        elif isinstance(key, str) and key == "o":
            state.platform_index = (state.platform_index + 1) % (len(state.platforms) + 1) - 1
            state.cursor = 0
            state.refresh()
        elif isinstance(key, str) and key == "d":
            state.domain_index = (state.domain_index + 1) % (len(state.domains) + 1) - 1
            state.cursor = 0
            state.refresh()
        elif isinstance(key, str) and key == "s":
            state.sort_index = (state.sort_index + 1) % len(SORTS)
            state.refresh()
        elif isinstance(key, str) and key == "a":
            state.lang_index = state.platform_index = state.domain_index = -1
            state.only_gems = state.only_underrated = False
            state.query = ""
            state.cursor = 0
            state.refresh()
        elif isinstance(key, str) and key == "g":
            state.only_gems = not state.only_gems
            state.only_underrated = False
            state.refresh()
        elif isinstance(key, str) and key == "u":
            state.only_underrated = not state.only_underrated
            state.only_gems = False
            state.refresh()
        elif key in ("\n", "\r", curses.KEY_ENTER):
            state.mode = "detail"
        elif isinstance(key, str) and key == "i":
            tool = state.current()
            if not tool:
                state.status = "brak zaznaczonego narzędzia"
            else:
                state.status = _install(tool)
        elif isinstance(key, str) and key == "?":
            _help(stdscr, rows, height)
        elif isinstance(key, str) and key in ("q", "Q"):
            state.running = False


def _install(tool):
    from core.curator import ToolCurator

    result = ToolCurator().install_tool(tool["name"])
    status = result["status"]
    if status == "installed":
        return f"zainstalowano: {result['path']}"
    if status == "already_installed":
        return f"już zainstalowane: {result['path']}"
    return f"nie zainstalowano: {result.get('message', status)}"


def _help(stdscr, rows, height):
    lines = ["Awesome Core — TUI", ""] + [f"  {key:<8} {label}" for key, label in HELP]
    lines += ["", "  Kolumny: nazwa | język | liczba list | gwiazdki | score | sekcja", "",
              "  Naciśnij dowolny klawisz, aby wrócić"]
    stdscr.erase()
    for index, line in enumerate(lines[: height - 2]):
        try:
            stdscr.addnstr(index, 0, _safe(line, rows), rows,
                           curses.A_BOLD if index == 0 else curses.A_NORMAL)
        except curses.error:
            pass
    stdscr.refresh()
    stdscr.getch()


def run_tui():
    if not store.db_ready(Path(__file__).parent.parent / "data"):
        print("Brak bazy. Zbuduj ją komendą: python3 extract_tools.py")
        return
    curses.wrapper(_run)


if __name__ == "__main__":
    run_tui()
