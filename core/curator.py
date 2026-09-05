#!/usr/bin/env python3
"""core/curator.py - Grupuje narzędzia tematycznie, zarządza instalacją."""

import json
import subprocess
import os
from pathlib import Path
from collections import defaultdict


class ToolCurator:
    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"
        self.data_dir = Path(data_dir)
        self.tools_file = self.data_dir / "tools.json"
        self.collections_file = self.data_dir / "collections.json"
        self.installed_file = self.data_dir / "installed.json"
        
        self.tools = []
        self.collections = {}
        self.installed = {}
        
        self._load()
    
    def _load(self):
        if self.tools_file.exists():
            self.tools = json.loads(self.tools_file.read_text())
        
        if self.collections_file.exists():
            self.collections = json.loads(self.collections_file.read_text())
        
        if self.installed_file.exists():
            self.installed = json.loads(self.installed_file.read_text())
    
    def _save_collections(self):
        self.collections_file.write_text(json.dumps(self.collections, indent=2, ensure_ascii=False))
    
    def _save_installed(self):
        self.installed_file.write_text(json.dumps(self.installed, indent=2, ensure_ascii=False))
    
    def get_tool_by_name(self, name):
        name_lower = name.lower()
        for tool in self.tools:
            if tool.get("name", "").lower() == name_lower:
                return tool
            if tool.get("url", "").lower().endswith(f"/{name_lower}"):
                return tool
        return None
    
    def get_tool_by_url(self, url):
        url_lower = url.lower().rstrip("/")
        for tool in self.tools:
            if tool.get("url", "").lower().rstrip("/") == url_lower:
                return tool
        return None
    
    def create_collection(self, name, description, tool_names):
        self.collections[name] = {
            "description": description,
            "tools": tool_names,
            "created_at": __import__("datetime").datetime.now().isoformat()
        }
        self._save_collections()
        return True
    
    def add_to_collection(self, collection_name, tool_name):
        if collection_name not in self.collections:
            return False
        if tool_name not in self.collections[collection_name]["tools"]:
            self.collections[collection_name]["tools"].append(tool_name)
            self._save_collections()
        return True
    
    def remove_from_collection(self, collection_name, tool_name):
        if collection_name not in self.collections:
            return False
        if tool_name in self.collections[collection_name]["tools"]:
            self.collections[collection_name]["tools"].remove(tool_name)
            self._save_collections()
        return True
    
    def list_collections(self):
        return {name: {
            "description": info["description"],
            "tool_count": len(info["tools"])
        } for name, info in self.collections.items()}
    
    def get_collection_tools(self, collection_name):
        if collection_name not in self.collections:
            return []
        tools = []
        for tool_name in self.collections[collection_name]["tools"]:
            tool = self.get_tool_by_name(tool_name)
            if tool:
                tools.append(tool)
        return tools
    
    def detect_install_method(self, tool):
        url = tool.get("url", "")
        if not url:
            return None
        
        url_lower = url.lower()
        
        # Git repos (GitHub, GitLab, etc.)
        if "github.com" in url_lower or "gitlab.com" in url_lower or "bitbucket.org" in url_lower:
            return "git"
        
        # Python packages
        if url_lower.endswith(".py") or "pypi.org" in url_lower or "pypi.python.org" in url_lower:
            return "pip"
        
        # Node.js packages
        if "npmjs.com" in url_lower or "npmjs.org" in url_lower:
            return "npm"
        
        # Rust packages
        if "crates.io" in url_lower:
            return "cargo"
        
        # Ruby gems
        if "rubygems.org" in url_lower:
            return "gem"
        
        # Go packages
        if "pkg.go.dev" in url_lower or "godoc.org" in url_lower:
            return "go"
        
        # Docker
        if "hub.docker.com" in url_lower or "docker.com" in url_lower:
            return "docker"
        
        # APT packages
        if "packages.ubuntu.com" in url_lower or "packages.debian.org" in url_lower:
            return "apt"
        
        return None
    
    def install_tool(self, tool_name, install_dir=None):
        tool = self.get_tool_by_name(tool_name)
        if not tool:
            return {"status": "error", "message": f"Tool '{tool_name}' not found"}
        
        url = tool.get("url", "")
        method = self.detect_install_method(tool)
        
        if install_dir is None:
            install_dir = Path.home() / ".local" / "share" / "awesome-tools"
        
        install_dir = Path(install_dir)
        install_dir.mkdir(parents=True, exist_ok=True)
        
        safe_name = url.rstrip("/").split("/")[-1]
        target_dir = install_dir / safe_name
        
        if target_dir.exists():
            return {"status": "already_installed", "path": str(target_dir)}
        
        if method == "git":
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", url, str(target_dir)],
                    check=True, capture_output=True, timeout=60
                )
                self.installed[tool_name] = {
                    "url": url,
                    "method": "git",
                    "path": str(target_dir),
                    "installed_at": __import__("datetime").datetime.now().isoformat()
                }
                self._save_installed()
                return {"status": "installed", "path": str(target_dir)}
            except subprocess.CalledProcessError as e:
                return {"status": "error", "message": str(e.stderr)}
            except subprocess.TimeoutExpired:
                return {"status": "error", "message": "Clone timeout"}
        
        return {"status": "error", "message": f"Unknown install method: {method}"}
    
    def uninstall_tool(self, tool_name):
        if tool_name not in self.installed:
            return {"status": "error", "message": "Not installed"}
        
        info = self.installed[tool_name]
        path = Path(info["path"])
        
        if path.exists():
            import shutil
            shutil.rmtree(path)
        
        del self.installed[tool_name]
        self._save_installed()
        return {"status": "uninstalled"}
    
    def list_installed(self):
        return self.installed
    
    def search_tools(self, query, limit=50):
        q = query.lower()
        results = []
        for tool in self.tools:
            name = tool.get("name", "").lower()
            desc = tool.get("description", "").lower()
            url = tool.get("url", "").lower()
            
            score = 0
            if q in name:
                score += 100
            if q in desc:
                score += 50
            if q in url:
                score += 30
            
            if score > 0:
                results.append((score, tool))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in results[:limit]]
    
    def get_popular_tools(self, limit=50):
        tools_with_install = []
        for tool in self.tools:
            method = self.detect_install_method(tool)
            if method:
                tools_with_install.append(tool)
        
        tools_with_install.sort(
            key=lambda t: len(t.get("name", "")),
            reverse=True
        )
        
        return tools_with_install[:limit]
    
    def get_tools_by_method(self, method):
        return [t for t in self.tools if self.detect_install_method(t) == method]
    
    def get_stats(self):
        methods = defaultdict(int)
        for tool in self.tools:
            method = self.detect_install_method(tool)
            if method:
                methods[method] += 1
        
        return {
            "total_tools": len(self.tools),
            "installable": sum(methods.values()),
            "methods": dict(methods),
            "collections": len(self.collections),
            "installed": len(self.installed)
        }
