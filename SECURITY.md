# Security Policy

## Reporting a vulnerability

Please report security issues in **awesome-core** (code, build/process, or tooling behavior) privately:

- Preferred: [GitHub Security Advisories](https://github.com/twojlogin/awesome-core/security/advisories/new) for this repository.
- Alternative: contact [@twojlogin](https://github.com/twojlogin).

When reporting, include:
- affected version/commit or branch,
- clear reproduction steps or a proof of concept (if safe to share),
- expected vs actual behavior and potential impact.

Please avoid public disclosure before a fix or mitigation is available.

## Supported versions

Security fixes are provided for the latest commit on the default branch.

## Scope notes

- **In scope:** vulnerabilities in this repository's code and workflows (CLI, parser, DB/build, web UI, MCP server, packaging/CI), including cases where untrusted input causes unintended behavior in awesome-core itself.
- **Out of scope:** malicious or vulnerable content inside third-party "awesome" lists or third-party tools linked by the catalog. The catalog indexes third-party data; findings about a specific listed project or list should be reported to that upstream project.

## Local inspection helpers (not guarantees)

`awesome audit`, `awesome untrusted`, and `awesome leaks` provide local heuristic signals for manual review. They do not prove that data is safe or that nothing was missed. See `README.md` for details.
