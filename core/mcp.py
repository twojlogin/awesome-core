#!/usr/bin/env python3
"""core/mcp.py — katalog Awesome Core jako serwer MCP (stdio, tylko stdlib).

Dzięki temu lokalny agent (Claude, Cursor, cokolwiek z protokołem MCP)
przeszukuje Twoją bazę offline: bez kluczy API i bez wysyłania czegokolwiek
do chmury. Serwer jest ściśle tylko-do-odczytu — nie instaluje, nie sieciuje,
nie ma narzędzi z efektem ubocznym.

Protokół: JSON-RPC 2.0 liniami po stdin → stdout. Logi wyłącznie na stderr,
bo stdout jest kanałem protokołu.
"""

import json
import sys
from pathlib import Path

from core import store
from core.tools_db import ToolsDB

PROTOCOL_DEFAULT = "2025-06-18"
SERVER_NAME = "awesome-core"
SERVER_VERSION = "2.0"

MAX_LIMIT = 50
MAX_QUERY = 200
DESC_CHARS = 200

TOOLS = [
    {
        "name": "search_tools",
        "description": (
            "Szukaj narzędzi w lokalnej bazie awesome list (offline). "
            "Wspiera filtry języka, platformy, domeny i minimalnej zgody "
            "kuratorów. Zwrócone wyniki mają prawdziwe gwiazdki z GitHuba, "
            "liczbę niezależnych list i score."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Zapytanie, np. 'port scanner'"},
                "lang": {"type": "string", "description": "Język narzędzia, np. Python, Go"},
                "platform": {
                    "type": "string",
                    "description": "Platforma, np. windows, WSL, Linux, Docker, CLI",
                },
                "domain": {
                    "type": "string",
                    "description": "Domena, np. osint, security, network, devops, ml",
                },
                "min_consensus": {
                    "type": "integer",
                    "description": "Minimalna liczba niezależnych list (2 = sensowne minimum)",
                },
                "min_stars": {"type": "integer", "description": "Minimalne gwiazdki repozytorium"},
                "alive_only": {
                    "type": "boolean",
                    "description": "Tylko linki potwierdzone jako żywe (martwe oznaczamy 'LINK MARTWY')",
                },
                "sort": {
                    "type": "string",
                    "enum": ["score", "stars", "consensus", "underrated", "gem", "name"],
                },
                "limit": {"type": "integer", "description": "Ile wyników (max 50)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "find_undiscovered_tools",
        "description": (
            "Narzędzia dobrej jakości, mało znane: dobre z małych list "
            "(underrated) oraz mało list, ale wysoki score (ukryte perełki)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "lang": {"type": "string"},
                "platform": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "explain_tool",
        "description": (
            "Wyjaśnij ranking narzędzia: z jakich list pochodzi, ile wynosi "
            "zgoda kuratorów, co ważyło w score. Użyj, gdy agent musi uzasadnić "
            "rekomendację."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"tool": {"type": "string", "description": "Nazwa albo URL narzędzia"}},
            "required": ["tool"],
        },
    },
    {
        "name": "lists_with_tool",
        "description": "Wszystkie awesome list, w których występuje narzędzie (z zaznaczeniem kopii).",
        "inputSchema": {
            "type": "object",
            "properties": {"tool": {"type": "string"}},
            "required": ["tool"],
        },
    },
    {
        "name": "catalog_facets",
        "description": (
            "Zawartość katalogu: liczba narzędzi i list, dostępne języki, "
            "platformy, domeny oraz najlepsze listy. Użyj na początku, żeby "
            "wiedzieć, czego w ogóle da się szukać."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _clip(text, limit=DESC_CHARS):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _tool_line(index, tool):
    parts = [f"{index}. {tool.get('name', '?')}"]
    meta = []
    lang = tool.get("lang")
    if lang and lang != "?":
        meta.append(lang)
    if tool.get("tool_stars"):
        meta.append(f"★{tool['tool_stars']:,}")
    if tool.get("lists_count"):
        meta.append(f"{tool['lists_count']} list")
    if tool.get("score"):
        meta.append(f"score {tool['score']:.0f}")
    if tool.get("platform"):
        meta.append(tool["platform"].replace(";", "/"))
    if tool.get("alive") is False:
        meta.append("LINK MARTWY")
    if meta:
        parts.append("[" + " · ".join(meta) + "]")
    parts.append(_clip(tool.get("description"), 140))
    parts.append(tool.get("url", ""))
    return " ".join(part for part in parts if part)


class MCPServer:
    def __init__(self, data_dir=None):
        self.db = ToolsDB(data_dir)
        self.client_protocol = PROTOCOL_DEFAULT
        self.client_info = {}

    def handle(self, request):
        """JSON-RPC w obiekt → odpowiedź albo None (notyfikacja)."""
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            return None
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params") or {}

        if method == "initialize":
            self.client_protocol = params.get("protocolVersion") or PROTOCOL_DEFAULT
            self.client_info = params.get("clientInfo") or {}
            return self._ok(request_id, {
                "protocolVersion": self.client_protocol,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "Katalog narzędzi z awesome list, lokalny i offline. "
                    "Ranking: zgoda niezależnych kuratorów + jakość listy + "
                    "prawdziwe gwiazdki narzędzia. Zacznij od search_tools."
                ),
            })
        if method in {"notifications/initialized", "initialized", "exit"}:
            return None
        if method == "ping":
            return self._ok(request_id, {})
        if method == "tools/list":
            return self._ok(request_id, {"tools": TOOLS})
        if method == "tools/call":
            return self._call(request_id, params)
        if request_id is None:
            return None
        return self._error(request_id, -32601, f"Metoda nieznana: {method}")

    def _call(self, request_id, params):
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            if name == "search_tools":
                text = self._search(arguments)
            elif name == "find_undiscovered_tools":
                text = self._undiscovered(arguments)
            elif name == "explain_tool":
                text = self._explain(arguments)
            elif name == "lists_with_tool":
                text = self._lists_with(arguments)
            elif name == "catalog_facets":
                text = self._facets()
            else:
                return self._error(request_id, -32602, f"Nieznane narzędzie: {name}")
        except Exception as exc:  # agent dostaje tekst błędu, nie wyjątek
            return self._ok(request_id, {
                "content": [{"type": "text", "text": f"Błąd: {exc}"}],
                "isError": True,
            })
        return self._ok(request_id, {"content": [{"type": "text", "text": text}]})

    @staticmethod
    def _ok(request_id, result):
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id, code, message):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    @staticmethod
    def _limit(arguments, default=15):
        try:
            value = int(arguments.get("limit") or default)
        except (TypeError, ValueError):
            value = default
        return max(1, min(value, MAX_LIMIT))

    def _find(self, needle):
        needle = (needle or "").strip()
        if not needle:
            return None
        return self.db.get_tool_by_url(needle) or self.db.tool_by_name(needle)

    def _search(self, arguments):
        query = (arguments.get("query") or "").strip()
        if not query:
            return "Podaj 'query'."
        if len(query) > MAX_QUERY:
            return (f"Zapytanie ma {len(query)} znaków, a maksymalnie {MAX_QUERY}. "
                    "Skróć do 2–3 najważniejszych słów kluczowych.")
        limit = self._limit(arguments)
        raw_consensus = arguments.get("min_consensus")
        min_consensus = 2 if raw_consensus is None else max(0, int(raw_consensus))
        results = self.db.search(
            query,
            limit=limit * 4,
            lang=arguments.get("lang"),
            platform=arguments.get("platform"),
            domain=arguments.get("domain"),
            min_stars=int(arguments.get("min_stars") or 0),  # 0 = brak filtra
            alive_only=bool(arguments.get("alive_only")),
            sort=arguments.get("sort") or "score",
        )
        if min_consensus > 1:
            results = [t for t in results if t["lists_count"] >= min_consensus]
        results = results[:limit]
        if not results:
            return self._no_results(query, arguments, min_consensus)
        header = f"{len(results)} wyników dla '{query}'"
        if min_consensus > 1:
            header += f" (min. {min_consensus} niezależnych list)"
        if arguments.get("alive_only"):
            header += " · tylko żywe linki"
        return "\n".join([header] + [_tool_line(i, t) for i, t in enumerate(results, 1)])

    @staticmethod
    def _no_results(query, arguments, min_consensus):
        """Agent musi wiedzieć, który filtr zabił wyniki — inaczej szuka w ciemno."""
        active = [f"lang={arguments['lang']}" for _ in [0] if arguments.get("lang")]
        active += [f"platform={arguments['platform']}" for _ in [0] if arguments.get("platform")]
        active += [f"domain={arguments['domain']}" for _ in [0] if arguments.get("domain")]
        if arguments.get("min_stars"):
            active.append(f"min_stars={arguments['min_stars']}")
        if min_consensus > 1:
            active.append(f"min_consensus={min_consensus}")
        if arguments.get("alive_only"):
            active.append("alive_only=true")
        hint = ("Filtry, które mogły odsiać wszystko: " + ", ".join(active) + ". "
                if active else "")
        return (f"Brak wyników dla '{query}'. {hint}"
                "Poluzuj: min_consensus=0, mniej filtrów, prostsze zapytanie. "
                "Najpierw catalog_facets, żeby sprawdzić nazwy języków i domen.")

    def _undiscovered(self, arguments):
        limit = self._limit(arguments, 10)
        lang = arguments.get("lang")
        underrated = self.db.underrated(limit=limit, lang=lang,
                                        platform=arguments.get("platform"))
        gems = self.db.gems(limit=limit, lang=lang)
        lines = ["Niedoceniane (dobra jakość, mało gwiazdek):"]
        lines += [_tool_line(i, t) for i, t in enumerate(underrated, 1)] or ["— brak —"]
        lines.append("")
        lines.append("Ukryte perełki (mało list, wysoki score):")
        lines += [_tool_line(i, t) for i, t in enumerate(gems, 1)] or ["— brak —"]
        return "\n".join(lines)

    def _explain(self, arguments):
        tool = self._find(arguments.get("tool"))
        if not tool:
            return f"Nie znaleziono narzędzia: {arguments.get('tool')}"
        detail = self.db.explain(tool)
        rows = "\n".join(
            f"  {key}: {value:.2f} × waga {weight:.2f} = {points:.1f} pkt"
            for key, value, weight, points in detail["rows"]
        )
        mentions = "\n".join(
            f"  - {m['source_repo']} ({m['section'] or '—'})"
            for m in detail["mentions"][:15]
        )
        return "\n".join([
            f"{tool['name']} — {tool.get('url', '')}",
            f"score {detail['score']:.1f} · niedoceniane {detail['underrated']:.1f}",
            f"język {tool.get('lang') or '?'} · platforma {tool.get('platform') or '—'}",
            f"gwiazdki {tool.get('tool_stars', 0)} · zgoda {tool.get('lists_count', 0)} list"
            f" / {tool.get('owners_count', 0)} autorów"
            + (f" · pominięto {detail['clones_skipped']} kopii list"
               if detail.get("clones_skipped") else ""),
            "rozkład punktów:",
            rows,
            "występuje w listach:",
            mentions or "  —",
        ])

    def _lists_with(self, arguments):
        tool = self._find(arguments.get("tool"))
        if not tool:
            return f"Nie znaleziono narzędzia: {arguments.get('tool')}"
        clones = {
            row["clone"]: row["canonical"]
            for row in self.db.conn.execute(
                "SELECT clone, canonical FROM list_similarity"
            ).fetchall()
        }
        lines = []
        for mention in self.db.mentions(tool["url_norm"]):
            marker = ""
            canonical = clones.get(mention["source_repo"])
            if canonical:
                marker = f"  [kopia listy {canonical}]"
            lines.append(f"  - {mention['source_repo']} ({mention['section'] or '—'}){marker}")
        return "\n".join([f"{tool['name']} w {len(lines)} listach:"] + lines)

    def _facets(self):
        stats = self.db.stats()
        parts = [
            f"Katalog: {stats['total']:,} narzędzi · {stats['lists']} list · "
            f"{stats['langs']} języków · {stats['sections']:,} sekcji",
            f"linki sprawdzone: {stats.get('alive', 0):,} żywych / "
            f"{stats.get('dead', 0):,} martwych",
            "",
            "Języki: " + ", ".join(f"{n} ({c})" for n, c in self.db.langs(3, 12)),
            "Platformy: " + ", ".join(f"{n} ({c})" for n, c in self.db.platforms(3, 12)),
            "Domeny: " + ", ".join(f"{n} ({c})" for n, c in self.db.domains(5, 12)),
            "",
            "Najlepsze listy:",
        ]
        for row in self.db.best_lists(n=8, min_tools=20):
            parts.append(
                f"  {row['quality']:.2f} · {row['stars']:,}★ · {row['unique_tool_count']} "
                f"narzędzi · {row['full_name']}"
            )
        return "\n".join(parts)


def serve(data_dir=None, stdin=None, stdout=None):
    """Pętla JSON-RPC po stdin/stdout. Zwraca liczbę obsłużonych żądań."""
    stream_in = stdin or sys.stdin
    stream_out = stdout or sys.stdout
    server = MCPServer(data_dir)
    handled = 0
    for line in stream_in:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError:
            print(f"[awesome-mcp] ignoruję nie-JSON: {line[:80]}", file=sys.stderr)
            continue
        response = server.handle(request)
        if request.get("method") == "exit":
            break
        if response is not None:
            stream_out.write(json.dumps(response, ensure_ascii=False) + "\n")
            stream_out.flush()
            handled += 1
    return handled


def demo(data_dir=None, query="port scanner"):
    """Pokazuje wymianę JSON-RPC, żeby zobaczyć serwer bez agenta."""
    server = MCPServer(data_dir)
    script = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": PROTOCOL_DEFAULT, "capabilities": {},
                    "clientInfo": {"name": "awesome-demo", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "search_tools",
                    "arguments": {"query": query, "min_consensus": 2, "limit": 5}}},
    ]
    for request in script:
        if request.get("method") == "notifications/initialized":
            print("→ " + json.dumps(request, ensure_ascii=False))
            continue
        response = server.handle(request)
        print("→ " + json.dumps(request, ensure_ascii=False))
        print("← " + json.dumps(response, ensure_ascii=False, indent=2))
        print()


def main(argv=None):
    args = list(argv if argv is not None else sys.argv[1:])
    data_dir = Path(__file__).parent.parent / "data"
    if "--demo" in args:
        query = args[args.index("--demo") + 1] if "--demo" in args and len(
            args) > args.index("--demo") + 1 else "port scanner"
        demo(data_dir, query)
        return 0
    if not store.db_ready(data_dir):
        print(f"Brak bazy w {data_dir}. Zbuduj ją: python3 extract_tools.py",
              file=sys.stderr)
        return 1
    print(f"[awesome-mcp] gotowy (baza {data_dir}); loguję na stderr",
          file=sys.stderr)
    serve(data_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
