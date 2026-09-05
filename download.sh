#!/usr/bin/env bash
# download.sh — pobierz awesome listy z GitHuba do offline-db
# Użycie: ./download.sh <topic> [per_page] [start_page]
# Zapisuje do: offline-db/data/readmes/ + offline-db/data/index.json
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
README_DIR="$SCRIPT_DIR/offline-db/data/readmes"
INDEX_FILE="$SCRIPT_DIR/offline-db/data/index.json"
TOPIC="${1:-awesome-list}"
PER_PAGE="${2:-100}"
START_PAGE="${3:-1}"

mkdir -p "$README_DIR"

if [ -f "$INDEX_FILE" ]; then
    cp "$INDEX_FILE" "${INDEX_FILE}.bak"
else
    echo '{}' > "$INDEX_FILE"
fi

if ! command -v gh &>/dev/null; then
    echo "[-] gh CLI nie znalezione."
    exit 1
fi
if ! gh auth status &>/dev/null 2>&1; then
    echo "[-] gh CLI nie zalogowane."
    exit 1
fi
echo "[*] Używam tokena z gh CLI"
echo "[*] Pobieram topic: $TOPIC -> $README_DIR (od strony $START_PAGE)"

PAGE=$START_PAGE
NEW_COUNT=0
SKIP_COUNT=0
MAX_RETRIES=5

while :; do
    echo "  Strona $PAGE..."

    # Retry logic
    resp=""
    for attempt in $(seq 1 $MAX_RETRIES); do
        resp=$(gh api "search/repositories?q=topic:${TOPIC}&per_page=${PER_PAGE}&page=${PAGE}" 2>/dev/null) && break
        echo "    Próba $attempt/$MAX_RETRIES nieudana. Czekam ${attempt}0s..."
        sleep $((attempt * 10))
    done

    if [ -z "$resp" ]; then
        echo "  Wszystkie próby nieudane. Kończę."
        break
    fi

    # Sprawdź błąd API
    error_msg=$(echo "$resp" | jq -r '.message // empty' 2>/dev/null)
    if [ -n "$error_msg" ]; then
        echo "  API error: $error_msg"
        if echo "$error_msg" | grep -qi "rate limit"; then
            echo "  Rate limit. Czekam 120s..."
            sleep 120
            # Retry after rate limit
            resp=$(gh api "search/repositories?q=topic:${TOPIC}&per_page=${PER_PAGE}&page=${PAGE}" 2>/dev/null) || {
                echo "  Nieudane po rate limit. Kończę."
                break
            }
            error_msg=$(echo "$resp" | jq -r '.message // empty' 2>/dev/null)
            if [ -n "$error_msg" ]; then
                echo "  Dalej błąd: $error_msg"
                break
            fi
        else
            break
        fi
    fi

    count=$(echo "$resp" | jq '.items | length')
    if [ "$count" -eq 0 ] || [ "$count" = "null" ]; then
        echo "  Koniec (brak wyników)."
        break
    fi

    echo "$resp" | jq -r '.items[] | .full_name + " " + .html_url' \
        | while read -r full url; do
            owner=$(echo "$full" | cut -d/ -f1)
            name=$(echo "$full" | cut -d/ -f2)
            safe_name="${owner}__${name}"
            readme_file="$README_DIR/${safe_name}.md"

            if [ -f "$readme_file" ]; then
                SKIP_COUNT=$((SKIP_COUNT + 1))
                continue
            fi

            downloaded=false
            for branch in main master; do
                raw="https://raw.githubusercontent.com/${full}/${branch}/README.md"
                http_status=$(curl -s -o "$readme_file" -w "%{http_code}" -L "$raw" || echo "000")
                if [ "$http_status" = "200" ]; then
                    downloaded=true
                    break
                else
                    rm -f "$readme_file"
                fi
            done

            if [ "$downloaded" = false ]; then
                continue
            fi

            jq --arg n "$full" --arg o "$owner" --arg na "$name" \
                '. + {($n): {owner: $o, name: $na, readme_downloaded: true, downloaded_at: (now | todate)}}' \
                "$INDEX_FILE" > "${INDEX_FILE}.tmp" && mv "${INDEX_FILE}.tmp" "$INDEX_FILE"

            NEW_COUNT=$((NEW_COUNT + 1))
            echo "  + $full"
            sleep 0.3
        done

    PAGE=$((PAGE + 1))
done

echo ""
echo "[*] Gotowe!"
echo "[*] Nowych: $NEW_COUNT"
echo "[*] Stron pobranych: $((PAGE - START_PAGE))"
echo "[*] Następna strona: $PAGE"
echo "[*] Aby kontynuować: ./download.sh awesome-list 100 $PAGE"
echo "[*] Pliki w: $README_DIR"
