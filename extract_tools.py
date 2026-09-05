#!/usr/bin/env python3
"""Parse awesome list READMEs and extract individual tools with descriptions."""

import os
import re
import json
import csv
from pathlib import Path
from collections import defaultdict


README_DIR = Path(__file__).parent / "offline-db" / "data" / "readmes"
INDEX_FILE = Path(__file__).parent / "offline-db" / "data" / "index.json"
TOOLS_FILE = Path(__file__).parent / "data" / "tools.json"
TOOLS_CSV = Path(__file__).parent / "data" / "tools.csv"
SUMMARY_FILE = Path(__file__).parent / "data" / "summary_enriched.csv"


def load_repo_stars():
    """Load star counts from summary_enriched.csv."""
    stars = {}
    if SUMMARY_FILE.exists():
        with open(SUMMARY_FILE) as f:
            for row in csv.DictReader(f):
                name = row.get("full_name", "").lower()
                s = int(row.get("stars", 0) or 0)
                stars[name] = s
    return stars


def extract_tools_from_readme(content, repo_name):
    """Extract individual tools/links from a README."""
    tools = []
    lines = content.split("\n")
    current_section = ""
    current_subsection = ""

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("## ") and not stripped.startswith("### "):
            current_section = stripped[3:].strip()
            current_section = re.sub(r'\[.*?\]\(.*?\)', '', current_section).strip()
            current_section = re.sub(r'[#!@$%^&*()]', '', current_section).strip()
            continue

        if stripped.startswith("### "):
            current_subsection = stripped[4:].strip()
            current_subsection = re.sub(r'\[.*?\]\(.*?\)', '', current_subsection).strip()
            current_subsection = re.sub(r'[#!@$%^&*()]', '', current_subsection).strip()
            continue

        match = re.match(r'^[\-\*]\s+\[([^\]]+)\]\(([^)]+)\)\s*[-–—]?\s*(.*)', stripped)
        if match:
            name = match.group(1).strip()
            url = match.group(2).strip()
            desc = match.group(3).strip()
            desc = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', desc).strip()
            desc = desc.rstrip('.')

            if url.startswith("http") and name and len(name) > 1:
                tools.append({
                    "name": name,
                    "url": url,
                    "description": desc[:200],
                    "section": current_section,
                    "subsection": current_subsection,
                    "source_repo": repo_name,
                })
            continue

        match2 = re.match(r'^[\-\*]\s+\[([^\]]+)\]\(([^)]+)\)\s*$', stripped)
        if match2:
            name = match2.group(1).strip()
            url = match2.group(2).strip()
            if url.startswith("http") and name and len(name) > 1:
                tools.append({
                    "name": name,
                    "url": url,
                    "description": "",
                    "section": current_section,
                    "subsection": current_subsection,
                    "source_repo": repo_name,
                })

    return tools


def filter_tools(tools, repo_stars):
    """Filter low quality and duplicates, add stars."""
    seen_urls = {}
    filtered = []

    for tool in tools:
        url = tool["url"].rstrip("/").lower()

        # Skip duplicates (keep first occurrence = from most popular repo)
        if url in seen_urls:
            continue
        seen_urls[url] = True

        # Skip tools with no description or very short
        desc = tool.get("description", "")
        if desc and len(desc) < 5:
            continue

        # Skip tools with generic names
        name = tool.get("name", "")
        if name.lower() in ["home", "readme", "table of contents", "contents", "toc", "license", "contributing"]:
            continue

        # Add source stars
        repo_lower = tool.get("source_repo", "").lower()
        tool["source_stars"] = repo_stars.get(repo_lower, 0)

        # Skip tools from repos with < 5 stars (probably junk)
        # But keep if it has a good description
        if tool["source_stars"] < 5 and not desc:
            continue

        filtered.append(tool)

    return filtered


def main():
    print("Loading README index...")
    with open(INDEX_FILE) as f:
        index = json.load(f)

    print(f"Found {len(index)} READMEs to parse")

    repo_stars = load_repo_stars()
    print(f"Loaded stars for {len(repo_stars)} repos")

    all_tools = []

    for i, (repo_name, meta) in enumerate(index.items()):
        readme_path = README_DIR / f"{meta['owner']}__{meta['name']}.md"
        if not readme_path.exists():
            continue

        try:
            content = readme_path.read_text(encoding="utf-8", errors="replace")
            tools = extract_tools_from_readme(content, repo_name)
            all_tools.extend(tools)
        except Exception:
            pass

        if (i + 1) % 200 == 0:
            print(f"  Parsed {i+1}/{len(index)} READMEs, {len(all_tools)} raw tools")

    print(f"\nRaw tools: {len(all_tools)}")

    # Filter
    filtered = filter_tools(all_tools, repo_stars)
    print(f"After filter: {len(filtered)}")

    # Save as JSON
    with open(TOOLS_FILE, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)
    print(f"Saved to {TOOLS_FILE}")

    # Save as CSV
    fields = ["name", "url", "description", "section", "subsection", "source_repo", "source_stars"]
    with open(TOOLS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(filtered)
    print(f"Saved to {TOOLS_CSV}")

    # Stats
    print(f"\nStats:")
    sections = defaultdict(int)
    for t in filtered:
        if t["section"]:
            sections[t["section"]] += 1

    print(f"Top sections:")
    for sec, count in sorted(sections.items(), key=lambda x: -x[1])[:15]:
        print(f"  {sec:40s} {count}")

    with_stars = sum(1 for t in filtered if t.get("source_stars", 0) > 0)
    print(f"\nWith stars: {with_stars}/{len(filtered)}")


if __name__ == "__main__":
    main()
