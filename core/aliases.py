#!/usr/bin/env python3
"""core/aliases.py — seed synonimów: zapytanie po ludzku -> znane narzędzia.

Wyszukiwarka jest leksykalna (FTS5), więc "port scanner" nie znajdzie `nmap`,
bo w jego opisie nie ma tych słów. Ten seed mapuje typowe określenia na
narzędzia, które ludzie mają na myśli. Rozszerzalny — dorzucaj własne.
"""


ALIASES = {
    # skanowanie i sieć
    "port scanner": ["nmap", "masscan", "zmap", "unicornscan", "naabu", "rustscan"],
    "skaner portow": ["nmap", "masscan", "zmap"],
    "port scan": ["nmap", "masscan", "naabu"],
    "network scanner": ["nmap", "masscan", "arp-scan", "netdiscover"],
    "discovery": ["nmap", "masscan", "netdiscover", "zmap"],
    "reconnaissance": ["nmap", "recon-ng", "theharvester", "amass", "subfinder"],
    "recon": ["amass", "subfinder", "recon-ng", "nmap"],
    "subdomain": ["amass", "subfinder", "sublist3r", "assetfinder", "oneforall"],
    "subdomain enumeration": ["subfinder", "amass", "assetfinder", "sublist3r", "censys"],
    "dns": ["dnsx", "massdns", "dnspython", "fierce"],
    "doh": ["cloudflared", "dnscrypt-proxy"],
    "packet capture": ["wireshark", "tcpdump", "tshark", "scapy"],
    "sniffing": ["tcpdump", "wireshark", "mitmproxy"],
    "wifi": ["aircrack-ng", "wifite", "kismet", "bettercap", "hiredis"],
    "wireless": ["aircrack-ng", "wifite", "kismet"],
    "bluetooth": ["bettercap", "bluez", "bluetoothctl"],
    "proxy": ["mitmproxy", "proxychains", "socks5", "privoxy"],
    "vpn": ["wireguard", "openvpn", "tailscale", "strongswan", "amnezia"],
    "firewall": ["nftables", "iptables", "ufw", "pfsense"],
    "ids": ["suricata", "snort", "zeek"],
    "honeypot": ["cowrie", "tarpit", "dionaea"],
    # bezpieczeństwo
    "port scanning": ["nmap", "masscan"],
    "pentest": ["metasploit", "burpsuite", "nmap", "hydra", "responder"],
    "penetration testing": ["metasploit", "burpsuite", "hydra", "impacket"],
    "exploitation": ["metasploit", "cobaltstrike", "sliver", "havoc"],
    "c2": ["sliver", "mythic", "havoc", "empire"],
    "command and control": ["sliver", "mythic", "empire"],
    "password cracking": ["hashcat", "john", "hydra", "medusa"],
    "brute force": ["hydra", "medusa", "ncrack"],
    "hash cracking": ["hashcat", "john"],
    "cracking": ["hashcat", "john", "hydra"],
    "credential": ["hashcat", "john", "secretsdump", "responder"],
    "passwords": ["hashcat", "john", "hydra"],
    "kerberos": ["responder", "impacket", "bloodhound", "mimikatz", "rubeus"],
    "active directory": ["bloodhound", "sharphound", "impacket", "crackmapexec", "netexec"],
    "ad enumeration": ["bloodhound", "sharphound", "netexec", "crackmapexec"],
    "lateral movement": ["impacket", "psexec", "mimikatz", "responder", "evil-winrm"],
    "privilege escalation": ["linpeas", "winpeas", "pspy", "seatbelt", "sharping"],
    "privesc": ["linpeas", "winpeas", "pspy"],
    "persistence": ["seatbelt", "psexec", "empire"],
    "cve": ["nuclei", "nikto", "searchsploit", "nuclei-templates"],
    "vulnerability scanner": ["nuclei", "nikto", "nessus", "openvas"],
    "vuln scan": ["nuclei", "nikto", "openvas"],
    "exploit": ["metasploit", "searchsploit", "nuclei"],
    "malware analysis": ["cuckoo", "yara", "malshare", "any.run", "hybrid-analysis"],
    "yara rules": ["yara", "yara-python", "thor"],
    "reverse engineering": ["ghidra", "radare2", "ida", "binary ninja", "cutter"],
    "decompiler": ["ghidra", "cutter", "retdec"],
    "disassembler": ["radare2", "ghidra", "objdump", "ida"],
    "forensics": ["volatility", "sleuthkit", "autopsy", "yara"],
    "memory forensics": ["volatility", "volatility3", "rekall"],
    "osint": ["maigret", "sherlock", "theharvester", "holehe", "spiderfoot", "recon-ng"],
    "email lookup": ["theharvester", "holehe", "h8mail", "spiderfoot"],
    "username search": ["sherlock", "maigret", "holehe"],
    "people search": ["sherlock", "maigret", "whoisx", "holehe"],
    "domain lookup": ["whois", "amass", "theharvester", "spiderfoot"],
    "geolocation": ["geotastic", "exiftool", "sherlock"],
    "dark web": ["tor", " Ahmia", "spiderfoot"],
    "tor search": ["tor", "ahmia"],
    "phishing": ["goPhishing", "evilginx", "gophish", "socialfish"],
    "phishing kit": ["gophish", "evilginx", "socialfish"],
    "social engineering": ["gophish", "socialfish", "evilginx", "bettercap"],
    "steganography": ["steghide", "stegseek", "zsteg"],
    "tracking": ["maigret", "sherlock", "exiftool"],
    "tracking people": ["maigret", "sherlock"],
    # windows i powershell (to najczęstsze lokalne potrzeby)
    "windows": ["powershell", "sysinternals", "mimikatz", "responder", "seatbelt"],
    "windows admin": ["powershell", "sysinternals", "psmodule", "rmm"],
    "powershell": ["powershell", "invoke-mimikatz", "powerup", "seatbelt", "sharping"],
    "ps1": ["powershell", "powerup", "invoke-mimikatz", "privesc"],
    "active directory pentest": ["netexec", "bloodhound", "impacket", "responder"],
    "remote management": ["evil-winrm", "wmi", "winrs", "psexec", "mimikatz"],
    "rce": ["metasploit", "cobaltstrike", "sliver"],
    # devops / chmura
    "container": ["docker", "podman", "nerdctl", "trivy"],
    "containers": ["docker", "podman", "nerdctl"],
    "kubernetes": ["kubectl", "k9s", "kubectx", "trivy", "kubesec"],
    "k8s": ["kubectl", "k9s", "trivy"],
    "cloud": ["awscli", "gcloud", "az", "doctl", "stealth"],
    "aws": ["awscli", "pacu", "prowler", "cloudmapper"],
    "azure": ["az", "roadtools", "pacu"],
    "gcp": ["gcloud", "scoutsuite"],
    "terraform": ["terraform", "terrascan", "tflint"],
    "ansible": ["ansible", "ansible-lint"],
    "monitoring": ["prometheus", "grafana", "zabbix", "netdata"],
    "logging": ["loki", "elasticsearch", "fluentd", "vector"],
    "sre": ["prometheus", "grafana", "ansible", "terraform", "vagrant"],
    "linux hardening": ["lynis", "openscap", "cis", "falco"],
    "hardening": ["lynis", "openscap", "auditd", "falco"],
    "proxy server": ["squid", "haproxy", "nginx", "traefik"],
    # web
    "web scanner": ["nikto", "gobuster", "ffuf", "dirsearch", "feroxbuster"],
    "directory brute force": ["ffuf", "gobuster", "dirsearch", "feroxbuster"],
    "fuzzing": ["ffuf", "radamsa", "boofuzz", "atheris"],
    "sqli": ["sqlmap", "gobuster"],
    "xss": ["dalfox", "xsser", "burpsuite"],
    "ssrf": ["interactsh", "gopherus"],
    "cors": ["corsy", "cors-scanner"],
    # inżynieria wsteczna / malware
    "obfuscation": ["de4dot", "confuser", "gobfuscate"],
    "anti-debug": ["scylla", "anti-debug"],
    "shellcode": ["scountex", "shellcode"],
    # języki / narzędzia dev
    "http client": ["curl", "httpie", "wget"],
    "json": ["jq", "yq", "gojq"],
    "terminal": ["tmux", "zellij", "kitty", "alacritty"],
    "shell": ["zsh", "fish", "bash", "starship"],
    "editor": ["neovim", "helix", "emacs"],
    "vim": ["neovim", "vim-plug", "lazyvim"],
    "notes": ["obsidian", "logseq", "joplin", "trilium"],
    "password manager": ["keepass", "bitwarden", "pass"],
    "download": ["aria2", "wget", "curl", "yt-dlp"],
    "youtube": ["yt-dlp", "youtube-dl"],
    "self hosted": ["nextcloud", "jellyfin", "portainer", "homarr"],
    "homelab": ["proxmox", "trueNAS", "portainer", "pihole"],
    "raspberry pi": ["pihole", "pi-hole", "homebridge", "raspberrypi"],
}


MAX_EXPANSIONS = 6


def expand(query, limit=MAX_EXPANSIONS):
    """Dodaje nazwy znanych narzędzi pasujących do zapytania."""
    low = (query or "").lower().strip()
    if not low:
        return []
    extra = []
    for phrase, tools in ALIASES.items():
        if phrase in low:
            for tool in tools:
                if tool.lower() not in low and tool not in extra:
                    extra.append(tool)
    return extra[:limit]
