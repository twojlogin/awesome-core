# Awesome Core 2.2.0

Local, offline-first catalog of tools from GitHub awesome lists — exposed as a read-only MCP server (stdio). No network after download, no API keys required for search, no remote code execution.

## Highlights

- **English by default, Polish optional.** CLI help now has EN as default and PL via `./awesome help --lang pl` / `AWESOME_LANG=pl`. Web UI defaults to EN, with PL available through the language switch.
- **Smarter refresh.** `awesome refresh` no longer re-downloads READMEs when local files already exist. Use `--download` to force download, `--full` for full refresh (download + backfill + enrich + build), or `--local/--offline` for local-only refresh.
- **Untrusted-data hardening.** `core/untrusted.py` now catches common prompt-control tokens (`<|im_start|>`, `<<SYS>>`, `[INST]`, etc.), "override your instructions"-style injections, and invisible/bidi Unicode smuggling characters. Destructive-command detection was narrowed to reduce false positives on legitimate security tool descriptions while still flagging dangerous command forms with targets.
- **MCP output hardening.** MCP tool responses now sanitize untrusted tool names as well as descriptions before returning them to agents.

## Details

### CLI / Web / Help
- Aligned CLI help and web `/help` around the same command set.
- EN-first help text, with PL help available.
- Web templates updated for EN/PL where most visible (search, lists, tool, shortlist, stats, facets).

### Refresh behavior
- Quick refresh: light backfill (missing/retry_after) + build.
- Skips README download when local READMEs are present.
- Explicit controls: `--download`, `--full`, `--local`, `--offline`, `--skip-download`.

### Trust / safety
- `untrusted.sanitize()` still marks filtered content with `[odfiltrowano: ...]` instead of silently dropping it.
- Added detection for prompt delimiter tokens, instruction override attempts, and invisible Unicode control/bidi characters.
- Reduced false positives for benign mentions like `rm -rf` in descriptive text; still flags dangerous forms such as `rm -rf /tmp/data`, `mkfs.ext4 /dev/sda1`, `del /s /q C:\Windows\Temp`.
- MCP remains read-only and does not execute code or make network requests.

## Current snapshot (depends on downloaded lists)

- 362,653 tools
- 3,145 lists/repositories
- 501,271 list mentions

Numbers depend on the locally downloaded dataset; verify with `./awesome stats`.

## Upgrade notes

- No DB migration required.
- Existing local READMEs are reused by default during quick refresh.
- If you publish this as an MCP registry/package update, bump/check `pyproject.toml`, `server.json`, and release tag consistently.