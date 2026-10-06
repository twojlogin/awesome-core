#!/usr/bin/env bash
# download.sh — nakładka. Cała logika jest w Pythonie (core/fetcher.py),
# bo bash + jq + curl nie działały na Windowsie, a projekt ma tam być używany.
# Zostawiam skrypt, bo "./download.sh" jest w nawyku wielu osób i w kilku
# starych instrukcjach. Jedyne zadanie: zignorować stare argumenty liczbowe
# (topic, per_page, page_start, page_max) i przekazać resztę do Pythona.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARGS=()
for arg in "$@"; do
  case "$arg" in
    ''|*[!0-9]*) ARGS+=("$arg") ;;   # coś znaczącego: topic albo flaga
    *) ;;                          # liczba: stary format, ignorujemy
  esac
done
exec python3 "$HERE/core/fetcher.py" ${ARGS[@]+"${ARGS[@]}"}
