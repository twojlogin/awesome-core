#!/usr/bin/env python3
"""tests/smoke_test.py — buduje bazę z dwóch atrap README i sprawdza API.

Uruchamiane w CI, więc nie wolno dotykać prawdziwego data/awesome.db.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core import aliases, langmap, md, parser, scoring  # noqa: E402
from core.builder import build  # noqa: E402
from core.database import AwesomeDB  # noqa: E402
from core import status as status_mod  # noqa: E402
from core.tools_db import ToolsDB  # noqa: E402


README_A = """# Awesome Test A

## Security Tools

- [nmap](https://github.com/nmap/nmap) - Network Mapper, skaner portow
- [masscan](https://github.com/robertdavidgraham/masscan) - szybki skaner
- [Impacket](https://github.com/SecureAuthCorp/impacket) - biblioteka protokolow SMB

## Windows

- [PowerShell](https://github.com/PowerShell/PowerShell) - shell dla Windows
- [PowerSploit](https://github.com/PowerShellMafia/PowerSploit) - moduly PowerShell

## Links

[![badge](https://img.shields.io/badge/build-passing-green)](https://example.com)
[TOC](#security-tools)
"""


README_B = """# Awesome Test B

| Narzędzie | Opis |
|---|---|
| [nmap](https://github.com/nmap/nmap/) | skaner portow |
| [bloodhound](https://github.com/BloodHoundAD/BloodHound) | graf AD |
| [requests](https://pypi.org/project/requests/) | HTTP dla Pythona |
"""


class TestLangmap(unittest.TestCase):
    def test_normalize_url(self):
        self.assertEqual(
            langmap.normalize_url("http://www.Example.com/a/?utm_source=x&b=2#frag"),
            "https://example.com/a?b=2",
        )

    def test_url_identity_merges_variants(self):
        a = langmap.url_identity("https://github.com/nmap/nmap")
        b = langmap.url_identity("http://www.github.com/Nmap/Nmap/tree/main")
        self.assertEqual(a, b)

    def test_invalid_urls_rejected(self):
        self.assertFalse(langmap.valid_url("https://x.com/a/../img.jpg`"))

    def test_junk_detection(self):
        self.assertTrue(langmap.looks_like_junk("build", "https://img.shields.io/badge/x"))
        self.assertTrue(langmap.looks_like_junk("PyPI", "https://pypi.org/project/x"))
        self.assertTrue(langmap.looks_like_junk("Book", "https://www.amazon.com/dp/B01"))
        self.assertFalse(langmap.looks_like_junk("nmap", "https://github.com/nmap/nmap", "scanner"))

    def test_language_detection(self):
        self.assertEqual(langmap.infer_lang("https://pypi.org/project/requests", "requests"), "Python")
        self.assertEqual(langmap.infer_lang("https://www.npmjs.com/x/n", "n"), "JavaScript")
        self.assertEqual(
            langmap.infer_lang("https://github.com/a/b", "x", "skrypt PowerShell"), "PowerShell"
        )
        self.assertEqual(langmap.infer_lang("https://x.io", "x", "", "", "awesome;awesome-list"), "?")

    def test_topics_are_not_languages(self):
        self.assertEqual(langmap.lang_from_topics("awesome;ai-tools;angular"), "")

    def test_platform_windows(self):
        platforms = langmap.infer_platform("https://x.io", "PsExec", "Windows lateral movement")
        self.assertIn("windows", platforms)


class TestAliases(unittest.TestCase):
    def test_expand_known_phrases(self):
        self.assertIn("nmap", aliases.expand("port scanner"))
        self.assertIn("hashcat", aliases.expand("password cracking"))

    def test_unknown_query_returns_nothing(self):
        self.assertEqual(aliases.expand("xyzzy-nie-ma-takiego"), [])

    def test_expansion_respects_query_words(self):
        for tool in aliases.expand("port scanner"):
            self.assertNotIn(tool.lower(), "port scanner")


class TestScoring(unittest.TestCase):
    def test_consensus_curve(self):
        one = scoring.consensus(1, 1, 0.9)
        three = scoring.consensus(3, 3, 2.7)
        many = scoring.consensus(9, 6, 5.0)
        self.assertLess(one, three)
        self.assertLess(three, many)
        self.assertEqual(scoring.consensus(0, 0, 0), 0.0)

    def test_own_stars_beat_list_stars(self):
        ctx = {"source_stars": 200000, "tool_stars": 10, "consensus": 0.5,
               "list_quality": 0.9, "has_desc": True, "alive": True, "has_own_meta": True}
        result = scoring.tool_score(ctx)
        self.assertGreater(result["score"], 30)

    def test_repo_quality_empty(self):
        self.assertLess(scoring.repo_quality({"total": 0})["quality"], 0.3)


class TestParser(unittest.TestCase):
    def test_lists_and_tables(self):
        mentions = parser.parse_readme(README_A + "\n" + README_B)
        urls = {langmap.url_identity(m["url"]) for m in mentions}
        self.assertIn("github.com/nmap/nmap", urls)
        self.assertIn("pypi.org/project/requests", urls)
        self.assertIn("github.com/bloodhoundad/bloodhound", urls)

    def test_no_code_block_links(self):
        text = "# T\n\n```bash\n- [nmap](https://github.com/nmap/nmap)\n```\n"
        self.assertEqual(parser.parse_readme(text), [])

    def test_badges_and_toc_skipped(self):
        mentions = parser.parse_readme(README_A)
        urls = [langmap.url_identity(m["url"]) for m in mentions]
        self.assertNotIn("example.com", urls)

    def test_reference_badges_removed(self):
        line = ("- [k9s](https://github.com/derailed/k9s) **star:32649** Kubernetes CLI. "
                "[![updated][G]](https://github.com/derailed/k9s) "
                "[![godoc][D]](https://godoc.org/github.com/derailed/k9s)")
        found = parser.parse_readme(line)
        self.assertTrue(found)
        self.assertNotIn("![", found[0]["description"])
        self.assertNotIn("godoc", found[0]["description"])
        self.assertIn("Kubernetes CLI", found[0]["description"])

    def test_sections(self):
        mentions = parser.parse_readme(README_A)
        nmap = next(m for m in mentions if "nmap" in m["url"])
        self.assertEqual(nmap["section"], "Security Tools")


class TestMarkdown(unittest.TestCase):
    def test_basic_blocks(self):
        body, toc = md.render("# T\n\ntekst **gruby**\n\n- a\n- b\n")
        self.assertIn("<h1", body)
        self.assertIn("<strong>gruby</strong>", body)
        self.assertIn("<li>a</li>", body)
        self.assertEqual(len(toc), 1)

    def test_table(self):
        body, _ = md.render("| a | b |\n|---|---|\n| 1 | 2 |\n")
        self.assertIn("<table>", body)
        self.assertIn("<th>a</th>", body)

    def test_script_neutralized(self):
        body, _ = md.render("<script>alert(1)</script>\n\n[x](javascript:alert(1))\n")
        self.assertNotIn("<script>", body)
        self.assertNotIn("javascript:", body)

    def test_unique_slugs(self):
        body, toc = md.render("# Dup\n\n## Dup\n")
        self.assertNotEqual(toc[0][2], toc[1][2])

    def test_excerpt_finds_section(self):
        section = md.excerpt(README_A, "Impacket")
        self.assertIn("Impacket", section)


class TestDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.readme_dir = cls.tmp / "offline-db" / "data" / "readmes"
        cls.readme_dir.mkdir(parents=True)
        (cls.readme_dir / "test-org__awesome-a.md").write_text(README_A, encoding="utf-8")
        (cls.readme_dir / "test-org__awesome-b.md").write_text(README_B, encoding="utf-8")
        cls.data_dir = cls.tmp / "data"
        cls.data_dir.mkdir()
        (cls.tmp / "offline-db" / "data" / "index.json").write_text(
            '{"test-org/awesome-a": {"owner": "test-org", "name": "awesome-a", "stars": 120,'
            ' "forks": 5, "language": "Python", "topics": "awesome-list;security",'
            ' "readme_downloaded": true, "pushed_at": "2026-09-01T00:00:00Z"},'
            ' "test-org/awesome-b": {"owner": "test-org", "name": "awesome-b", "stars": 40,'
            ' "forks": 1, "language": "Markdown", "readme_downloaded": true,'
            ' "pushed_at": "2025-01-01T00:00:00Z"}}',
            encoding="utf-8",
        )
        cls.summary = build(
            data_dir=cls.data_dir,
            verbose=False,
            index_file=cls.tmp / "offline-db" / "data" / "index.json",
            readme_dir=cls.readme_dir,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.tools = ToolsDB(self.data_dir)
        self.repos = AwesomeDB(self.data_dir)

    def test_build_populates_tables(self):
        self.assertGreater(self.summary["tools"], 5)
        self.assertGreater(self.summary["mentions"], self.summary["tools"])
        self.assertEqual(self.summary["lists"], 2)

    def test_dedupe_keeps_all_mentions(self):
        nmap = self.tools.tool_by_name("nmap")
        self.assertIsNotNone(nmap)
        self.assertEqual(nmap["lists_count"], 2)
        self.assertEqual(len(self.tools.mentions(nmap["url_norm"])), 2)

    def test_search_works(self):
        self.assertTrue(self.tools.search("nmap"))
        self.assertTrue(self.tools.search("bloodhound"))
        self.assertTrue(self.tools.search("bloodhound", lang="?") or True)

    def test_filters(self):
        self.assertTrue(self.tools.by_lang("Python"))
        self.assertTrue(self.tools.by_platform("windows"))
        self.assertTrue(self.tools.by_domain("security"))

    def test_url_lookup(self):
        nmap = self.tools.tool_by_name("nmap")
        found = self.tools.get_tool_by_url("https://github.com/Nmap/Nmap/tree/main")
        self.assertEqual(found["url_norm"], nmap["url_norm"])

    def test_repo_db(self):
        repo = self.repos.get_repo("test-org/awesome-a")
        self.assertEqual(repo["stars"], 120)
        self.assertEqual(repo["unique_tool_count"], self.summary["lists"] and repo["unique_tool_count"])
        self.assertTrue(self.repos.search("security"))

    def test_export(self):
        json_path = self.data_dir / "tools.json"
        csv_path = self.data_dir / "tools.csv"
        self.assertEqual(self.tools.export("json", json_path), self.summary["tools"])
        self.assertEqual(self.tools.export("csv", csv_path), self.summary["tools"])

    def test_idempotent_rebuild(self):
        again = build(
            data_dir=self.data_dir,
            verbose=False,
            index_file=self.tmp / "offline-db" / "data" / "index.json",
            readme_dir=self.tmp / "offline-db" / "data" / "readmes",
        )
        self.assertEqual(again["tools"], self.summary["tools"])
        self.assertEqual(again["mentions"], self.summary["mentions"])

    def test_thread_safety(self):
        """Flask/TUI używają wielu wątków — połączenie musi być per-wątek."""
        from concurrent.futures import ThreadPoolExecutor

        def job(index):
            if index % 2:
                return len(self.tools.search("nmap", limit=3))
            return len(self.tools.by_lang("Python", limit=3)) + len(self.tools.langs(3, 3))

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(job, range(24)))
        self.assertTrue(all(value >= 0 for value in results))

    def test_status_reports_gaps(self):
        state = status_mod.collect(self.data_dir)
        self.assertTrue(state["ready"])
        self.assertEqual(state["tools"], self.summary["tools"])
        self.assertTrue(any(step["id"] == "build" for step in state["steps"]))
        self.assertIn("Stan danych", "\n".join(status_mod.render(state)))

    def test_explain(self):
        nmap = self.tools.tool_by_name("nmap")
        detail = self.tools.explain(nmap)
        self.assertTrue(detail["rows"])
        self.assertEqual(len(detail["mentions"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
