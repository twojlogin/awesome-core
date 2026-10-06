#!/usr/bin/env python3
"""extract_tools.py — buduje data/awesome.db z pobranych README.

Użycie:
    python3 extract_tools.py                 # pełny build
    python3 extract_tools.py --export json   # dodatkowo data/tools.json
    python3 extract_tools.py --export csv    # dodatkowo data/tools.csv
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core import store  # noqa: E402
from core.builder import build  # noqa: E402


EXPORTABLE = {"json": "data/tools.json", "csv": "data/tools.csv"}


def print_stats(conn):
    print("\nRanking języków (narzędzia):")
    for lang, count in conn.execute(
        "SELECT lang, COUNT(*) c FROM tools GROUP BY lang ORDER BY c DESC LIMIT 12"
    ):
        print(f"  {count:>7}  {lang}")

    print("\nPlatformy:")
    for platform, count in conn.execute(
        "SELECT platform, COUNT(*) c FROM tools WHERE platform != ''"
        " GROUP BY platform ORDER BY c DESC LIMIT 12"
    ):
        print(f"  {count:>7}  {platform}")

    print("\nDomeny:")
    for domain, count in conn.execute(
        "SELECT tags, COUNT(*) c FROM tools GROUP BY tags ORDER BY c DESC LIMIT 8"
    ):
        print(f"  {count:>7}  {domain}")

    print("\nNajlepsze listy (jakość):")
    for row in conn.execute(
        "SELECT full_name, stars, quality, unique_tool_count FROM repos"
        " WHERE unique_tool_count > 0 ORDER BY quality DESC, stars DESC LIMIT 10"
    ):
        print(f"  {row['quality']:.2f}  {row['stars']:>7}★  {row['unique_tool_count']:>5}  {row['full_name']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build Awesome Core SQLite database")
    parser.add_argument(
        "--export",
        choices=sorted(EXPORTABLE),
        help="dodatkowy eksport do data/tools.json lub data/tools.csv",
    )
    parser.add_argument("--export-out", help="ścieżka eksportu (zamiast domyślnej)")
    parser.add_argument("--export-limit", type=int, help="maksymalna liczba wierszy w eksporcie")
    parser.add_argument("--quiet", action="store_true", help="bez logowania postępu")
    parser.add_argument("--stats", action="store_true", help="pokaż tylko statystyki bazy")
    parser.add_argument("--vacuum", action="store_true", help="przepakuj bazę (wolniejsze)")
    args = parser.parse_args(argv)

    base = Path(__file__).parent

    if args.stats:
        if not store.db_ready(base / "data"):
            print("Brak bazy. Uruchom: python3 extract_tools.py")
            return 1
        conn = store.connect(base / "data")
        print_stats(conn)
        conn.close()
        return 0

    export = None
    if args.export:
        export = args.export_out or (base / EXPORTABLE[args.export])

    print("Buduję bazę z offline-db/data/readmes...")
    summary = build(
        data_dir=base / "data",
        verbose=not args.quiet,
        export=export,
        export_limit=args.export_limit,
        index_file=base / "offline-db" / "data" / "index.json",
        readme_dir=base / "offline-db" / "data" / "readmes",
        vacuum=args.vacuum,
    )

    print(
        f"\nGotowe w {summary['seconds']}s: {summary['tools']} narzędzi, "
        f"{summary['mentions']} wystąpień w {summary['lists']} listach "
        f"({summary['lists_with_meta']} z metadanymi), {summary['langs']} języków"
    )

    if not args.quiet:
        conn = store.connect(base / "data")
        print_stats(conn)
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
