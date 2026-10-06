#!/usr/bin/env python3
"""core/langmap.py — wnioskowanie języka, platformy i domeny dla narzędzi."""

import re
from functools import lru_cache


HOST_LANG = {
    "pypi.org": "Python",
    "pypi.python.org": "Python",
    "files.pythonhosted.org": "Python",
    "anaconda.org": "Python",
    "conda.anaconda.org": "Python",
    "huggingface.co": "Python",
    "kaggle.com": "Python",
    "npmjs.com": "JavaScript",
    "npmjs.org": "JavaScript",
    "yarnpkg.com": "JavaScript",
    "unpkg.com": "JavaScript",
    "cdnjs.com": "JavaScript",
    "nodejs.org": "JavaScript",
    "deno.land": "TypeScript",
    "crates.io": "Rust",
    "docs.rs": "Rust",
    "rubygems.org": "Ruby",
    "gem.wtf": "Ruby",
    "packagist.org": "PHP",
    "pecl.php.net": "PHP",
    "nuget.org": "C#",
    "hex.pm": "Elixir",
    "hexdocs.pm": "Elixir",
    "cocoapods.org": "Swift",
    "swiftpackageindex.com": "Swift",
    "maven.apache.org": "Java",
    "mvnrepository.com": "Java",
    "repo1.maven.org": "Java",
    "jitpack.io": "Java",
    "go.dev": "Go",
    "pkg.go.dev": "Go",
    "gopkg.in": "Go",
    "godoc.org": "Go",
    "crystal-lang.org": "Crystal",
    "dlang.org": "D",
    "nim-lang.org": "Nim",
    "ziglang.org": "Zig",
    "cran.r-project.org": "R",
    "ctan.org": "TeX",
    "pub.dev": "Dart",
    "hex.pm/packages": "Elixir",
    "sourceforge.net": "",
    "codeberg.org": "",
    "git.sr.ht": "",
    "launchpad.net": "Python",
    "flathub.org": "",
    "snapcraft.io": "",
    "aws.amazon.com": "",
    "marketplace.visualstudio.com": "C#",
    "apps.apple.com": "Swift",
    "play.google.com": "Kotlin",
    "f-droid.org": "Kotlin",
    "source.android.com": "Kotlin",
    "developer.apple.com": "Swift",
    "developer.mozilla.org": "JavaScript",
    "laravel.com": "PHP",
    "rails.org": "Ruby",
    "dotnet.microsoft.com": "C#",
    "golang.org": "Go",
    "docs.python.org": "Python",
    "doc.rust-lang.org": "Rust",
    "kotlinlang.org": "Kotlin",
    "scala-lang.org": "Scala",
    "clojure.org": "Clojure",
    "elixir-lang.org": "Elixir",
    "erlang.org": "Erlang",
    "haskell.org": "Haskell",
    "ocaml.org": "OCaml",
    "julia-lang.org": "Julia",
    "php.net": "PHP",
    "perldoc.perl.org": "Perl",
    "tcltk.org": "Tcl",
    "godotengine.org": "GDScript",
    "unity.com": "C#",
    "godotengine": "GDScript",
    "neovim.io": "Lua",
    "github.io": "",
}


PATH_LANG = [
    (r"\.ps1($|[?#/])", "PowerShell"),
    (r"\.psm1($|[?#/])", "PowerShell"),
    (r"\.bat($|[?#/])", "Batch"),
    (r"\.cmd($|[?#/])", "Batch"),
    (r"\.vbs($|[?#/])", "VBScript"),
    (r"\.py($|[?#/])", "Python"),
    (r"\.pyz($|[?#/])", "Python"),
    (r"\.rb($|[?#/])", "Ruby"),
    (r"\.go($|[?#/])", "Go"),
    (r"\.rs($|[?#/])", "Rust"),
    (r"\.js($|[?#/])", "JavaScript"),
    (r"\.mjs($|[?#/])", "JavaScript"),
    (r"\.ts($|[?#/])", "TypeScript"),
    (r"\.java($|[?#/])", "Java"),
    (r"\.kt($|[?#/])", "Kotlin"),
    (r"\.swift($|[?#/])", "Swift"),
    (r"\.cs($|[?#/])", "C#"),
    (r"\.php($|[?#/])", "PHP"),
    (r"\.sh($|[?#/])", "Shell"),
    (r"\.lua($|[?#/])", "Lua"),
    (r"\.pl($|[?#/])", "Perl"),
    (r"\.scala($|[?#/])", "Scala"),
    (r"\.dart($|[?#/])", "Dart"),
    (r"\.ex($|[?#/])", "Elixir"),
    (r"\.exs($|[?#/])", "Elixir"),
    (r"\.hs($|[?#/])", "Haskell"),
    (r"\.clj($|[?#/])", "Clojure"),
    (r"\.vim($|[?#/])", "Vim script"),
    (r"\.ahk($|[?#/])", "AutoHotkey"),
]


KEYWORD_LANG = [
    ("powershell", "PowerShell"), ("pwsh", "PowerShell"),
    ("posh", "PowerShell"), ("batch script", "Batch"), ("autohotkey", "AutoHotkey"),
    ("ahk", "AutoHotkey"), ("bash script", "Shell"), ("zsh script", "Shell"),
    ("fish shell", "Shell"), ("shell script", "Shell"),
    ("python script", "Python"), ("golang", "Go"), ("rust crate", "Rust"),
    ("npm package", "JavaScript"), ("node.js", "JavaScript"), ("nodejs", "JavaScript"),
    ("typescript", "TypeScript"), ("dotnet", "C#"), ("c#", "C#"), ("f#", "F#"),
    ("objective-c", "Objective-C"), ("assembly", "Assembly"),
    ("dockerfile", "Dockerfile"), ("docker image", "Docker"),
    ("vim plugin", "Vim script"), ("neovim plugin", "Lua"),
    ("emacs lisp", "Emacs Lisp"), ("elisp", "Emacs Lisp"),
    ("visual basic", "Visual Basic"), ("delphi", "Pascal"), ("pascal", "Pascal"),
    ("matlab", "MATLAB"), ("julia", "Julia"), ("r package", "R"),
    ("latex", "TeX"), ("kotlin", "Kotlin"), ("scala", "Scala"),
    ("haskell", "Haskell"), ("clojure", "Clojure"), ("erlang", "Erlang"),
    ("lisp", "Lisp"), ("forth", "Forth"), ("solidity", "Solidity"),
    ("binary", "Assembly"), ("firmware", "C"),
]


PLATFORM_KEYWORDS = [
    ("windows", ("windows", "win32", "win64", "winapi", "msvc", "msys", "cygwin",
                 "windows-only", "for windows", "windows tool", "powershell",
                 "win-rider", "winnt")),
    ("WSL", ("wsl", "windows subsystem for linux")),
    ("Linux", ("linux", "gnu/linux", "debian", "ubuntu", "fedora", "arch linux",
               "alpine", "systemd", "apt ", "yum ", "dnf ", "apk add", "pacman",
               "kernel", "unix", "bsd", "gentoo", "opensuse")),
    ("macOS", ("macos", "mac os", "osx", "darwin", "homebrew", "brew install",
               "macbook", "mac ", "os x")),
    ("FreeBSD", ("freebsd", "openbsd", "netbsd")),
    ("Android", ("android", "termux", "apk ", "dex")),
    ("iOS", ("ios", "iphone", "ipad", "swiftui")),
    ("Docker", ("docker", "dockerfile", "docker-compose", "container", "podman")),
    ("Kubernetes", ("kubernetes", "k8s", "helm chart", "kubectl")),
    ("Cloud", ("aws", "azure", "gcp", "google cloud", "cloudflare", "digitalocean",
               "heroku", "vercel", "netlify")),
    ("CLI", ("cli", "command line", "command-line", "terminal ui", "tui", "shell tool")),
    ("GUI", ("gui", "desktop app", "electron app", "qt", "gtk", "tray")),
    ("Web", ("browser extension", "web app", "webapp", "web ui", "frontend")),
]


DOMAIN_KEYWORDS = [
    ("osint", ("osint", "reconnaissance", "recon ", "footprint", "people search",
               "username search", "email search", "domain lookup", "shodan",
               "sherlock", "maigret", "theHarvester", "dark web", "darkweb",
               "geolocation", "reverse ip", "metadata analysis", "google dork")),
    ("security", ("security", "pentest", "penetration testing", "vulnerability",
                  "cve", "exploit", "malware", "forensics", "incident response",
                  "red team", "blue team", "hardening", "threat", "c2 ", "payload",
                  "phishing", "ransomware", "burp", "fuzzing", "fuzzer", "audit tool",
                  "password", "credential", "cracking", "brute force", "privilege escalation")),
    ("reverse-engineering", ("reverse engineering", "disassembl", "decompil",
                             "binary analysis", "radare", "ghidra", "ida pro",
                             "malware analysis", "binary exploitation", "unpacker")),
    ("network", ("networking", "network scanner", "proxy", "vpn", "firewall", "dns",
                 "snmp", "packet capture", "intrusion detection", "ids ", "ips ",
                 "wireless", "wi-fi", "wifi", "nmap", "wireshark", "port scanner",
                 "traffic analysis", "bandwidth", "load balancer", "tls")),
    ("devops", ("devops", "kubernetes", "docker", "terraform", "ansible",
                "ci/cd", "continuous integration", "monitoring", "logging",
                "observability", "prometheus", "grafana", "infrastructure as code",
                "configuration management", "server", "backup")),
    ("cloud", ("aws", "azure", "gcp", "google cloud", "cloudflare", "s3 ", "lambda",
               "serverless", "cloud migration")),
    ("data", ("database", "sql", "nosql", "postgres", "mysql", "mongodb", "redis",
              "sqlite", "data engineering", "etl", "data pipeline", "big data",
              "spark", "hadoop", "visualization", "dashboard", "analytics")),
    ("ml", ("machine learning", "deep learning", "neural", "llm", "large language model",
            "transformer", "nlp", "natural language", "prompt", "agent", "rag",
            "embedding", "diffusion", "stable diffusion", "computer vision",
            "reinforcement learning", "pytorch", "tensorflow")),
    ("web", ("frontend", "css", "web framework", "template engine", "static site",
             "ui component", "design system", "webassembly", "wasm")),
    ("mobile", ("mobile development", "react native", "flutter", "ionic", "android app",
                "ios app")),
    ("terminal", ("terminal", "tui", "shell", "console", "command line")),
    ("hardware", ("raspberry pi", "arduino", "embedded", "iot", "fpga", "sensor")),
    ("documents", ("pdf", "ebook", "markdown", "documentation", "note taking",
                   "wiki", "knowledge base", "book")),
]


PACKAGE_HOSTS = {
    "pypi.org": ("pip", "https://pypi.org/project/{name}/"),
    "npmjs.com": ("npm", "https://www.npmjs.com/package/{name}"),
    "crates.io": ("cargo", "https://crates.io/crates/{name}"),
    "rubygems.org": ("gem", "https://rubygems.org/gems/{name}"),
    "packagist.org": ("composer", "https://packagist.org/packages/{name}"),
    "nuget.org": ("dotnet", "https://www.nuget.org/packages/{name}"),
    "hex.pm": ("mix", "https://hex.pm/packages/{name}"),
    "go.dev": ("go", "https://pkg.go.dev/{name}"),
    "pkg.go.dev": ("go", "https://pkg.go.dev/{name}"),
    "maven.apache.org": ("maven", "https://central.sonatype.com/artifact/{name}"),
    "mvnrepository.com": ("maven", "https://central.sonatype.com/artifact/{name}"),
    "cocoapods.org": ("cocoapods", "https://cocoapods.org/pods/{name}"),
    "pub.dev": ("dart", "https://pub.dev/packages/{name}"),
    "snapcraft.io": ("snap", "snap install {name}"),
    "flathub.org": ("flatpak", "flatpak install {name}"),
    "sourceforge.net": ("sourceforge", "https://sourceforge.net/projects/{name}/"),
}


GIT_HOSTS = ("github.com", "gitlab.com", "codeberg.org", "git.sr.ht", "gitea.com")


KNOWN_LANGS = frozenset({
    "Python", "JavaScript", "TypeScript", "Java", "Go", "Rust", "Ruby", "PHP",
    "C", "C++", "C#", "F#", "Swift", "Kotlin", "Objective-C", "Scala", "Clojure",
    "Haskell", "Elixir", "Erlang", "Lua", "Perl", "R", "Julia", "MATLAB", "Dart",
    "Zig", "Nim", "Crystal", "D", "Groovy", "Shell", "PowerShell", "Batch",
    "VBScript", "AutoHotkey", "Vim script", "Emacs Lisp", "Assembly", "Solidity",
    "Fortran", "COBOL", "Pascal", "Delphi", "Ada", "OCaml", "F#", "Prolog",
    "Smalltalk", "Tcl", "Verilog", "VHDL", "Solidity", "Markdown", "TeX",
    "reStructuredText", "Makefile", "CMake", "Dockerfile", "HTML", "CSS",
    "SCSS", "Vue", "Svelte", "Jupyter Notebook", "GDScript", "CoffeeScript",
    "LiveScript", "ActionScript", "Visual Basic", "Pascal", "Racket", "Scheme",
    "Standard ML", "Erlang", "Elm", "PureScript", "Reason", "Nix", "HCL",
    "Terraform", "Starlark", "Meson", "Ninja", "Gherkin", "Raku", "Perl6",
})


LANG_ALIASES = {
    "js": "JavaScript", "node": "JavaScript", "nodejs": "JavaScript",
    "ts": "TypeScript", "py": "Python", "python3": "Python", "golang": "Go",
    "rs": "Rust", "rb": "Ruby", "cs": "C#", "csharp": "C#", "c-sharp": "C#",
    "kt": "Kotlin", "ps": "PowerShell", "ps1": "PowerShell", "sh": "Shell",
    "bash": "Shell", "zsh": "Shell", "fish": "Shell", "shell script": "Shell",
    "objc": "Objective-C", "c++": "C++", "cpp": "C++", "cplusplus": "C++",
    "emacs lisp": "Emacs Lisp", "elisp": "Emacs Lisp", "viml": "Vim script",
    "vim script": "Vim script", "neovim": "Lua", "jupyter": "Python",
    "jupyter notebook": "Python", "notebook": "Python", "docker": "Dockerfile",
    "makefile": "Makefile", "cmake": "CMake", "tex": "TeX", "latex": "TeX",
    "md": "Markdown", "markdown": "Markdown", "restructuredtext": "reStructuredText",
    "batch": "Batch", "bat": "Batch", "cmd": "Batch", "autohotkey": "AutoHotkey",
    "c/c++": "C", "golang ": "Go",
}


UNKNOWN = "?"


MAX_NAME_LENGTH = 90


def normalize_lang(value):
    if not value:
        return ""
    value = str(value).strip()
    if not value:
        return ""
    if value in LANG_ALIASES:
        return LANG_ALIASES[value]
    low = value.lower()
    if low in LANG_ALIASES:
        return LANG_ALIASES[low]
    return value


_HOST_RE = re.compile(r"https?://([^/:?#]+)", re.I)


_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")


_MD_STRIP_RE = re.compile(r"\*\*|__|[*`]|~~")


_TRACKING_RE = re.compile(
    r"^(utm_[a-z]+|ref|referrer|source|fbclid|gclid|msclkid|mc_[a-z]+|igshid|"
    r"yclid|si|feature|trk|spm|share_source|_hsenc|_hsmi)$",
    re.I,
)


_URL_RE = re.compile(r"https?://([^/]+)(/.*)?$", re.I)


_TREE_BLOB_RE = re.compile(r"/(tree|blob)/[^/]+(/|$)")


_GIT_SUFFIX_RE = re.compile(r"\.git$")


_WWW_RE = re.compile(r"^https://(www\.)?")


_LOWER_HOST_RE = re.compile(r"^(https?://)([^/]+)(/.*)?$", re.I)


_WS_RE = re.compile(r"\s+")


_NONWORD_RE = re.compile(r"[\W_]+")


_TAG_ONLY_RE = re.compile(r"\[[^\]]{1,24}\]")


_SHORT_NOUN_RE = re.compile(r"[^\w\s]{1,4}")


def host_of(url):
    match = _HOST_RE.match(url or "")
    if not match:
        return ""
    host = match.group(1).lower()
    return host[4:] if host.startswith("www.") else host


def is_package_host(host):
    return host in PACKAGE_HOSTS


def install_hint(url, name=""):
    """Zwraca (metoda, url_referencyjne) dla znanych rejestrów pakietów."""
    host = host_of(url)
    if host not in PACKAGE_HOSTS:
        return "", ""
    method, template = PACKAGE_HOSTS[host]
    slug = (url or "").rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"[?#].*$", "", slug) or name
    if "{" in template:
        return method, template.format(name=slug)
    return method, template.format(name=slug)


def lang_from_topics(topics):
    """Z topiców listy ('awesome;awesome-list;python;…') bierz tylko prawdziwy język."""
    for topic in str(topics or "").split(";"):
        candidate = normalize_lang(topic)
        if candidate in KNOWN_LANGS:
            return candidate
    return ""


def infer_lang(url, name="", description="", repo_language="", topics="",
               tool_meta=None):
    """Język narzędzia: metadane repo → host → ścieżka → słowa → lista."""
    if tool_meta and tool_meta.get("language"):
        normalized = normalize_lang(tool_meta["language"])
        if normalized in KNOWN_LANGS:
            return normalized

    host = host_of(url)
    if host in HOST_LANG and HOST_LANG[host]:
        return HOST_LANG[host]

    lowered_url = (url or "").lower()
    for pattern, lang in PATH_LANG:
        if re.search(pattern, lowered_url):
            return lang

    haystack = f"{name} {description}".lower()
    for keyword, lang in KEYWORD_LANG:
        if keyword in haystack:
            return lang

    from_topics = lang_from_topics(topics)
    if from_topics:
        return from_topics

    normalized = normalize_lang(repo_language)
    if normalized in KNOWN_LANGS and host not in GIT_HOSTS:
        return normalized
    return UNKNOWN


def _matches(haystack, keyword):
    """Krótkie słowa kluczowe muszą być całym słowem, dłuższe — frazą."""
    if " " in keyword:
        return keyword in haystack
    if keyword not in haystack:
        return False
    return _keyword_re(keyword).search(haystack) is not None


@lru_cache(maxsize=4096)
def _keyword_re(keyword):
    return re.compile(rf"(?<![\w]){re.escape(keyword)}(?![\w])")


def infer_platform(url="", name="", description="", section="", subsection="", topics=""):
    """Platformy (Windows/WSL/Linux/macOS/Docker/...) jako lista ';'."""
    haystack = " ".join(
        str(x) for x in (url, name, description, section, subsection, topics)
    ).lower()
    found = []
    for platform, keywords in PLATFORM_KEYWORDS:
        for keyword in keywords:
            if _matches(haystack, keyword):
                found.append(platform)
                break
    return ";".join(found)


def infer_domain(section="", subsection="", topics="", description="", name=""):
    """Domena tematyczna (osint/security/network/...) — '?' gdy nie wiadomo."""
    haystack = " ".join(
        str(x) for x in (section, subsection, topics, description, name)
    ).lower()
    hits = []
    for domain, keywords in DOMAIN_KEYWORDS:
        if any(_matches(haystack, keyword) for keyword in keywords):
            hits.append(domain)
    if not hits:
        return UNKNOWN
    return ";".join(hits[:3])


def normalize_section(section, subsection=""):
    """Normalizuje sekcje: Title Case, bez 'Table of Contents' i śmieci."""
    raw = re.sub(r"\[.*?\]\(.*?\)", "", str(section or ""))
    raw = re.sub(r"[#!@$%^&*()\[\]]", "", raw).strip(" -—:.\t")
    raw = re.sub(r"\s{2,}", " ", raw)
    if not raw or raw.lower() in {
        "table of contents", "contents", "toc", "index", "general", "misc",
        "others", "other", "more", "license", "contributing", "readme",
    }:
        return "Other"
    if len(raw) > 80:
        raw = raw[:80].rstrip()
    return raw[:1].upper() + raw[1:]


_MD_IMAGE_RE = _IMAGE_RE


_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")


_UNDERSCORE_RE = re.compile(r"^_+(.*?)_+$")


_LOOSE_UNDERSCORE_RE = re.compile(r"(?<![\w])_+|_+(?![\w])")


_EMOJI_TAG_RE = re.compile(r"^:\w+:\s*")


@lru_cache(maxsize=300000)
def clean_name(name):
    """Usuwa artefakty markdown z nazw narzędzia ('**Python**: _X_')."""
    text = (name or "").strip()
    if not text:
        return ""
    text = _MD_IMAGE_RE.sub("", text)
    text = _MD_LINK_RE.sub(lambda m: m.group(1), text)
    text = _MD_STRIP_RE.sub("", text)
    text = _UNDERSCORE_RE.sub(r"\1", text)
    text = _LOOSE_UNDERSCORE_RE.sub("", text)
    text = _EMOJI_TAG_RE.sub("", text)
    text = _WS_RE.sub(" ", text).strip(" -—:|.,")
    if "/" in text and " " not in text:
        text = text.rsplit("/", 1)[-1]
    text = text.strip(" -—:|.,")
    if len(text) > MAX_NAME_LENGTH:
        cut = text[:MAX_NAME_LENGTH]
        space = cut.rfind(" ")
        if space > MAX_NAME_LENGTH * 0.6:
            cut = cut[:space]
        text = cut.rstrip(" -—:|.,") + "…"
    return text


BADGE_HOSTS = (
    "shields.io", "badge.fury.io", "travis-ci.org", "circleci.com",
    "codecov.io", "coveralls.io", "img.shields.io", "badgen.net", "appveyor.com",
    "snapcraft.io/badge", "herokucdn.com",
)


ANCHOR_NAMES = {
    "pypi", "npm", "conda", "github", "gitlab", "docker", "docker hub", "home",
    "readme", "license", "contributing", "changelog", "website", "docs",
    "documentation", "twitter", "discord", "slack", "telegram", "sponsor",
    "sponsors", "patreon", "buy me a coffee", "star", "stars", "fork", "watch",
    "toc", "contents", "back to top", "awesome", "list", "more", "index",
    "website", "blog", "newsletter", "subscribe", "demo", "live demo",
    "playground", "try it", "get started", "install", "usage", "api", "wiki",
    "issues", "releases", "changelog", "contributors", "credits", "authors",
    "table of contents", "navigation", "menu", "search", "language", "english",
}


OFFICIAL_HOSTS = {
    "github.com", "gitlab.com", "bitbucket.org", "codeberg.org", "sourceforge.net",
    "git.sr.ht", "gitea.com", "gitcode.com", "gitee.com",
}


TRACKING_PARAMS = re.compile(
    r"(^|&)(utm_[a-z]+|ref|referrer|source|fbclid|gclid|msclkid|mc_[a-z]+|igshid|"
    r"yclid|si|feature|trk|spm|share_source|_hsenc|_hsmi)(=|&|$)",
    re.I,
)


JUNK_URL_PATTERNS = (
    "shields.io", "badge", "/badges/", "twitter.com/intent/tweet",
    "facebook.com/sharer", "linkedin.com/share", "reddit.com/submit",
    "pinterest.com/pin", "wa.me/", "t.me/share", "mailto:", "javascript:void",
    "#readme", "#contents", "#table-of-contents", "#installation",
)


COMMERCE_HOSTS = (
    "amazon.", "goodreads.com", "audible.", "scribd.com", "issuu.com",
    "slideshare.net", "etsy.com", "aliexpress.", "temu.com", "ebay.",
    "gumroad.com", "itch.io", "steampowered.com", "patreon.com", "paypal.",
    "buymeacoffee.com", "ko-fi.com", "opencollective.com", "wise.com",
    "boosty.to", "tidelift.com", "crowdfunding.com",
)


SOCIAL_HOSTS = (
    "twitter.com", "x.com", "facebook.com", "instagram.com", "linkedin.com",
    "pinterest.com", "reddit.com", "weibo.com", "mp.weixin.qq.com",
    "tiktok.com", "snapchat.com", "vk.com", "ok.ru", "bsky.app",
    "quora.com", "medium.com", "substack.com", "towardsdatascience.com",
    "hashnode.dev", "news.ycombinator.com", "lobste.rs", "dev.to/",
    "discord.gg", "discord.com/invite", "t.me", "telegram.me", "wa.me",
)


PUBLISHER_HOSTS = (
    "medium.", "wordpress.com", "blogspot.", "blog.", "blogs.", "substack.com",
    "ghost.io", "notion.site", "dev.to", "hashnode.dev", "towardsdatascience.com",
    "freecodecamp.org", "smashingmagazine.com", "css-tricks.com",
    "book.douban.com", "douban.com", "zhihu.com", "zhuanlan.zhihu.com",
    "juejin.im", "juejin.cn", "csdn.net", "cnblogs.com", "51cto.com",
    "segmentfault.com", "jianshu.com", "csdnimg.cn",
    "clawskills.sh", "officialskills.sh", "skillsmp.com", "agent-skills.",
    "openalternative.co", "toolinbox.ai", "aitoolly.io",
)


KEEP_HOSTS = (
    "en.wikipedia.org", "wikipedia.org", "youtube.com", "youtu.be",
    "play.google.com", "apps.apple.com", "arxiv.org", "doi.org",
)


@lru_cache(maxsize=300000)
def normalize_url(url):
    """Czyści URL: https, bez #, bez trackingu, bez slashes na końcu."""
    raw = (url or "").strip()
    if not raw:
        return ""
    raw = raw.replace("&amp;", "&").strip()
    raw = _WS_RE.sub("%20", raw)
    if raw.startswith("http://"):
        raw = "https://" + raw[len("http://"):]
    raw = raw.split("#", 1)[0]
    if raw.startswith("https://"):
        raw = _WWW_RE.sub("https://", raw)
    raw = _LOWER_HOST_RE.sub(
        lambda m: "https://" + m.group(2).lower() + (m.group(3) or ""), raw
    )
    raw = raw.rstrip(".,);:'\"")
    if "?" in raw:
        base, query = raw.split("?", 1)
        kept = []
        for part in query.split("&"):
            if not part:
                continue
            name = part.split("=", 1)[0]
            if name and not _TRACKING_RE.match(name):
                kept.append(part)
        raw = base.rstrip("/") + ("?" + "&".join(kept) if kept else "")
    return raw.rstrip("/")


VALID_HOST_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$"
)


VALID_SEGMENT_RE = re.compile(r"^[\w\-.+~%()',;!$&=@]+$", re.UNICODE)


def valid_url(raw):
    """Odrzuca URL-e zepsute parsowaniem markdownu ('..', 'image.jpg`', 'a|b')."""
    identity = url_identity(raw)
    if not identity:
        return ""
    host, _, rest = identity.partition("/")
    if not VALID_HOST_RE.match(host):
        return ""
    path = rest.split("?", 1)[0]
    for segment in path.split("/"):
        if segment in {"", ".", ".."}:
            return ""
        if not VALID_SEGMENT_RE.match(segment):
            return ""
    return identity


@lru_cache(maxsize=300000)
def url_identity(url):
    """Klucz dedupe: host + ścieżka (bez www, scheme, query)."""
    raw = normalize_url(url)
    if not raw:
        return ""
    match = _URL_RE.match(raw)
    if not match:
        return raw.lower()
    host = match.group(1).lower()
    path = (match.group(2) or "/").lower()
    if host.startswith("www."):
        host = host[4:]
    path = _TREE_BLOB_RE.sub("/", path)
    path = re.sub(r"//+", "/", path).rstrip("/")
    if host in OFFICIAL_HOSTS:
        path = _GIT_SUFFIX_RE.sub("", path)
    return f"{host}{path}"


def looks_like_junk(name, url, description="", identity=None):
    """Czy pozycja to śmieć (badge, kotwica, link do sekcji, social/sklep)?"""
    identity = identity if identity is not None else url_identity(url)
    if not identity:
        return True
    if any(pattern in identity for pattern in JUNK_URL_PATTERNS):
        return True
    host = host_of(url)
    if host and not _is_keep_host(host):
        if any(pattern in host for pattern in BADGE_HOSTS):
            return True
        if any(pattern in host for pattern in COMMERCE_HOSTS):
            return True
        if any(pattern in host for pattern in PUBLISHER_HOSTS):
            return True
        if any(host == social or host.endswith("." + social) for social in SOCIAL_HOSTS):
            return True
    clean = clean_name(name)
    low = (clean or str(name)).strip().lower()
    if low in ANCHOR_NAMES:
        return True
    if len(clean) < 2:
        return True
    if _NONWORD_RE.fullmatch(clean or ""):
        return True
    if clean.count("|") > 1:
        return True
    return False


def _is_keep_host(host):
    return any(host == keep or host.endswith("." + keep) for keep in KEEP_HOSTS)


def has_description(description):
    desc = str(description or "").strip()
    if not desc:
        return False
    if _TAG_ONLY_RE.fullmatch(desc):
        return False
    if _SHORT_NOUN_RE.fullmatch(desc):
        return False
    return len(desc) >= 5


@lru_cache(maxsize=50000)
def truncate_words(text, limit=220):
    """Ucina opis na granicy słowy, nie w połowie wyrazu."""
    desc = _WS_RE.sub(" ", text or "").strip()
    if len(desc) <= limit:
        return desc
    cut = desc[:limit]
    space = cut.rfind(" ")
    if space > limit * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,;:-") + "…"
