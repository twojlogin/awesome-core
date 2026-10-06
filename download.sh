#!/usr/bin/env bash
# download.sh — pobiera awesome listy z GitHuba do offline-db/data/readmes
#
# Użycie:
#   ./download.sh <topic> [per_page] [start_page] [max_pages] [opcje]
#
# Opcje:
#   --sort stars|forks|updated|best   sortowanie wyników (domyślnie stars)
#   --refresh                        pobierz ponownie już istniejące README
#   --wide                           kilka zapytań połączonych w union
#                                   (wyszukiwarka GitHuba ma limit 1000 wyników
#                                    na zapytanie, więc jedno zapytanie nie wystarczy)
#
# Przykłady:
#   ./download.sh awesome-list
#   ./download.sh awesome-list 100 1 20 --wide
#   ./download.sh awesome-list 100 1 20 --refresh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
README_DIR="$SCRIPT_DIR/offline-db/data/readmes"
INDEX_FILE="$SCRIPT_DIR/offline-db/data/index.json"
TOPIC="${1:-awesome-list}"
PER_PAGE="${2:-100}"
START_PAGE="${3:-1}"
MAX_PAGES="${4:-20}"

REFRESH=0
SORT="stars"
WIDE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --refresh) REFRESH=1 ;;
        --wide) WIDE=1 ;;
        --sort)
            shift
            SORT="${1:-stars}"
            ;;
        --sort=*) SORT="${1#*=}" ;;
        *) ;;
    esac
    shift
done

ORDER="desc"
case "$SORT" in
    best) SORT="" ;;
    stars|forks|updated|help-wanted-issues) ORDER="desc" ;;
    *) SORT="" ;;
esac

mkdir -p "$README_DIR"

if [ -f "$INDEX_FILE" ]; then
    cp "$INDEX_FILE" "${INDEX_FILE}.bak"
else
    echo '{}' > "$INDEX_FILE"
fi

for cmd in gh jq curl; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "[-] $cmd nie znalezione."
        exit 1
    fi
done
if ! gh auth status &>/dev/null 2>&1; then
    echo "[-] gh CLI nie zalogowane (gh auth login)."
    exit 1
fi

PAGE=$START_PAGE
NEW_COUNT=0
SKIP_COUNT=0
MISS_COUNT=0
REFRESHED=0
MAX_RETRIES=5
LAST_ERROR=""
PREV_FIRST=""
SCRIPT_PY="$(command -v python3 || command -v python)"

RESP_FILE="$(mktemp)"
HAVE_FILE="$(mktemp)"
NEW_FILE="$(mktemp)"
ERR_FILE="$(mktemp)"
cleanup() { rm -f "$RESP_FILE" "$HAVE_FILE" "$NEW_FILE" "$ERR_FILE"; }
trap cleanup EXIT

fetch_page() {
    local query="$1" page="$2" attempt err
    for attempt in $(seq 1 "$MAX_RETRIES"); do
        if [ -n "$SORT" ]; then
            if gh api "search/repositories?q=${query}&sort=${SORT}&order=${ORDER}&per_page=${PER_PAGE}&page=${page}" \
                > "$RESP_FILE" 2>"$ERR_FILE"; then
                return 0
            fi
        else
            if gh api "search/repositories?q=${query}&per_page=${PER_PAGE}&page=${page}" \
                > "$RESP_FILE" 2>"$ERR_FILE"; then
                return 0
            fi
        fi
        err="$(tr '\n' ' ' < "$ERR_FILE")"
        LAST_ERROR="$err"
        if printf '%s' "$err" | grep -qi "rate limit"; then
            echo "    Rate limit. Czekam 120s..."
            sleep 120
        else
            echo "    Próba $attempt/$MAX_RETRIES nieudana: $err"
            sleep $((attempt * 10))
        fi
    done
    return 1
}

# Jedno jq na stronę: metadane trafiają do index.json tylko dla repo,
# które faktycznie mają pobrany README (nowe LUB już obecne wcześniej).
merge_index() {
    "$SCRIPT_PY" - "$RESP_FILE" "$NEW_FILE" "$INDEX_FILE" <<'PY'
import json, subprocess, sys, tempfile, os

resp_file, new_file, index_file = sys.argv[1:4]
with open(resp_file, encoding="utf-8") as fh:
    try:
        items = (json.load(fh) or {}).get("items") or []
    except ValueError:
        items = []
with open(new_file, encoding="utf-8") as fh:
    fresh = {line.strip() for line in fh if line.strip()}

index = {}
if os.path.exists(index_file):
    with open(index_file, encoding="utf-8") as fh:
        try:
            index = json.load(fh) or {}
        except ValueError:
            index = {}

for item in items:
    full = item.get("full_name")
    if not full:
        continue
    entry = index.get(full) or {}
    topics = item.get("topics")
    entry.update({
        "owner": full.split("/")[0],
        "name": full.split("/")[1],
        "html_url": item.get("html_url", ""),
        "stars": item.get("stargazers_count", entry.get("stars", 0)) or 0,
        "forks": item.get("forks_count", entry.get("forks", 0)) or 0,
        "language": item.get("language") or entry.get("language", ""),
        "topics": ";".join(topics) if isinstance(topics, list) else (topics or entry.get("topics", "")),
        "created_at": item.get("created_at") or entry.get("created_at", ""),
        "pushed_at": item.get("pushed_at") or entry.get("pushed_at", ""),
        "archived": bool(item.get("archived", entry.get("archived", False))),
        "readme_downloaded": True,
    })
    license_obj = item.get("license")
    spdx = license_obj.get("spdx_id") if isinstance(license_obj, dict) else ""
    if spdx and spdx != "NOASSERTION":
        entry["license"] = spdx
    if full in fresh:
        entry["downloaded_at"] = subprocess.run(
            ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True
        ).stdout.strip()
    index[full] = entry

tmp = index_file + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(index, fh, indent=2, ensure_ascii=False)
os.replace(tmp, index_file)
PY
}

process_page() {
    local query="$1" page="$2"

    echo "  Strona $page zapytania: $query"

    if [ $((page - START_PAGE)) -ge "$MAX_PAGES" ]; then
        echo "  Limit $MAX_PAGES stron osiągnięty. Kończę."
        return 2
    fi

    if ! fetch_page "$query" "$page"; then
        echo "  Nieudane po $MAX_RETRIES próbach. Ostatni błąd: $LAST_ERROR"
        return 2
    fi

    local count
    count=$(jq -r '(.items // []) | length' "$RESP_FILE")
    if ! [[ "$count" =~ ^[0-9]+$ ]] || [ "$count" -eq 0 ]; then
        echo "  Brak wyników (koniec tej listy)."
        return 1
    fi

    # GitHubsearch ma limit 1000 wyników i zaczyna zacyklać strony.
    local first
    first=$(jq -r '.items[0].full_name // ""' "$RESP_FILE")
    if [ -n "$PREV_FIRST" ] && [ "$first" = "$PREV_FIRST" ]; then
        echo "  Paginacja zapętliła się na $first (limit 1000 wyników). Kończę."
        return 2
    fi
    PREV_FIRST="$first"

    : > "$HAVE_FILE"
    : > "$NEW_FILE"

    # Po jednym elemencie wiersza (bez pól pustych!) — bez parsowania TSV,
    # bo IFS=$'\t' gubi puste kolumny i przesuwał argumenty do --argjson.
    while IFS= read -r full; do
        [ -n "$full" ] || continue
        owner="${full%%/*}"
        name="${full#*/}"
        [ -n "$owner" ] && [ -n "$name" ] || continue
        readme_file="$README_DIR/${owner}__${name}.md"

        if [ -f "$readme_file" ] && [ "$REFRESH" -eq 0 ]; then
            SKIP_COUNT=$((SKIP_COUNT + 1))
            continue
        fi

        downloaded=false
        for branch in main master; do
            raw="https://raw.githubusercontent.com/${full}/${branch}/README.md"
            http_status=$(curl -f -s -o "$readme_file" -w '%{http_code}' -L \
                --max-time 30 "$raw" || true)
            if [ "$http_status" = "200" ] && [ -s "$readme_file" ]; then
                downloaded=true
                break
            fi
            rm -f "$readme_file"
        done

        if [ "$downloaded" = false ]; then
            MISS_COUNT=$((MISS_COUNT + 1))
            continue
        fi

        echo "$full" >> "$NEW_FILE"
        if [ -f "$README_DIR/${owner}__${name}.md" ] && [ "$REFRESH" -eq 1 ] && \
           grep -q . "$readme_file"; then :; fi
        NEW_COUNT=$((NEW_COUNT + 1))
        REFRESHED=$((REFRESHED + 1))
        echo "  + $full"
        sleep 0.3
    done < <(jq -r '.items[].full_name' "$RESP_FILE")

    merge_index
    return 0
}

echo "[*] Używam tokena z gh CLI"
if [ -n "$SORT" ]; then
    echo "[*] Topic: $TOPIC | sort=$SORT | strony od $START_PAGE"
else
    echo "[*] Topic: $TOPIC | bez sortowania | strony od $START_PAGE"
fi
[ "$WIDE" -eq 1 ] && echo "[*] Tryb --wide: kilka zapytań (union), bo limit to 1000 wyników"
[ "$REFRESH" -eq 1 ] && echo "[*] Tryb --refresh: pobieram ponownie istniejące README"

QUERIES=("topic:${TOPIC}")
if [ "$WIDE" -eq 1 ]; then
    QUERIES+=("topic:${TOPIC} stars:>=200")
    QUERIES+=("topic:awesome")
    QUERIES+=("topic:curated-list")
    QUERIES+=("topic:awesome-resources")
    QUERIES+=("awesome in:name topic:list")
    QUERIES+=("awesome in:name stars:>=500")
fi

STATUS=0
for query in "${QUERIES[@]}"; do
    PREV_FIRST=""
    echo ""
    echo "[*] Zapytanie: $query"
    PAGE=$START_PAGE
    while :; do
        process_page "$query" "$PAGE"
        rc=$?
        [ "$rc" -eq 1 ] && break
        [ "$rc" -eq 2 ] && { STATUS=$rc; break; }
        PAGE=$((PAGE + 1))
    done
    [ "$STATUS" -ne 0 ] && break
done

echo ""
echo "[*] Gotowe!"
echo "[*] Nowych/pobranych: $NEW_COUNT"
echo "[*] Pominiętych (już było): $SKIP_COUNT"
echo "[*] Bez README: $MISS_COUNT"
echo "[*] Pliki w: $README_DIR"
echo "[*] Następny krok: python3 extract_tools.py  (albo ./awesome build)"
echo "[*] Potem: ./awesome backfill   (uzupełni metadane list)"
echo "[*] Potem: ./awesome enrich    (języki i gwiazdki samych narzędzi)"
exit "$STATUS"
