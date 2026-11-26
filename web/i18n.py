"""Proste tłumaczenia UI web (PL/EN)."""

TRANSLATIONS = {
    "pl": {
        "nav_lists": "Listy",
        "nav_categories": "Kategorie",
        "nav_clone_farms": "Farmy kopii",
        "nav_refresh": "Odśwież",
        "nav_help": "Pomoc",
        "nav_my_list": "Moja lista",
        "search_placeholder": "vpn, powershell, osint, windows, docker...",
        "search_button": "Szukaj",
        "tools": "narzędzi",
        "lists": "list",
        "languages": "języków",
        "best_lists": "Listy z najwyższą oceną jakości",
        "biggest_lists": "Największe listy",
        "list": "lista",
        "quality": "jakość",
        "lang_label": "język",
        "platform_label": "platforma",
        "domain_label": "domena",
        "all": "wszystkie",
        "language": "Język",
        "ranking_note": "z opisem · ranking = zgoda niezależnych kuratorów + jakość listy + własne gwiazdki narzędzia",
        "refresh_title": "Odśwież dane",
        "help_title": "Pomoc",
        "lists_title": "Listy awesome w bazie",
        "tools_from_list": "Narzędzia z tej listy, wg score",
        "add_to_my_list": "Do mojej listy",
        "filters": "Filtry",
        "sort": "Sortowanie",
        "results": "wyników",
        "no_results": "Brak wyników.",
        "description": "Opis",
        "stars": "Gwiazdki",
        "mentions": "Wzmianki",
        "score": "Wynik",
        "status": "Stan danych",
        "refresh": "Odśwież",
        "install": "Instaluj",
        "search": "Szukaj",
        "home": "Start",
        "categories": "Kategorie",
        "clones": "Kopie",
        "shortlist": "Moja lista",
        "raw": "Źródło",
        "repo": "Repozytorium",
        "tool": "Narzędzie",
        "top_tools": "Najlepsze narzędzia",
        "underrated": "Niedoceniane",
        "hidden_gems": "Ukryte perełki",
        "stats": "Statystyki",
    },
    "en": {
        "nav_lists": "Lists",
        "nav_categories": "Categories",
        "nav_clone_farms": "Clone farms",
        "nav_refresh": "Refresh",
        "nav_help": "Help",
        "nav_my_list": "My list",
        "search_placeholder": "vpn, powershell, osint, windows, docker...",
        "search_button": "Search",
        "tools": "tools",
        "lists": "lists",
        "languages": "languages",
        "best_lists": "Best lists (by quality)",
        "biggest_lists": "Biggest lists",
        "list": "list",
        "quality": "quality",
        "lang_label": "language",
        "platform_label": "platform",
        "domain_label": "domain",
        "all": "all",
        "language": "Language",
        "ranking_note": "with description · ranking = independent curator consensus + list quality + tool's own stars",
        "refresh_title": "Refresh data",
        "help_title": "Help",
        "lists_title": "Awesome lists in database",
        "tools_from_list": "Tools from this list, by score",
        "add_to_my_list": "Add to my list",
        "filters": "Filters",
        "sort": "Sort",
        "results": "results",
        "no_results": "No results.",
        "description": "Description",
        "stars": "Stars",
        "mentions": "Mentions",
        "score": "Score",
        "status": "Data status",
        "refresh": "Refresh",
        "install": "Install",
        "search": "Search",
        "home": "Home",
        "categories": "Categories",
        "clones": "Clones",
        "shortlist": "My list",
        "raw": "Source",
        "repo": "Repository",
        "tool": "Tool",
        "top_tools": "Top tools",
        "underrated": "Underrated",
        "hidden_gems": "Hidden gems",
        "stats": "Statistics",
    },
}


def normalize_lang(lang):
    lang = (lang or "").lower().replace("_", "-")
    if lang.startswith("pl"):
        return "pl"
    return "en"


def translate(lang, key, **kwargs):
    lang = normalize_lang(lang)
    text = TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS["en"].get(key) or TRANSLATIONS["pl"].get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
