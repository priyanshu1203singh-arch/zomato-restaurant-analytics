#!/usr/bin/env bash
# Fetch the raw Zomato extract. Idempotent: skips the download if the file is
# already present and non-trivial in size.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/data/raw/zomato.csv"
URL="https://raw.githubusercontent.com/dsrscientist/dataset4/main/zomato.csv"

mkdir -p "$(dirname "$OUT")"

if [[ -s "$OUT" ]] && [[ "$(wc -c < "$OUT")" -gt 1000000 ]]; then
  echo "Raw extract already present: $OUT ($(wc -c < "$OUT") bytes)"
  exit 0
fi

echo "Downloading Zomato extract..."
curl -fsSL --retry 3 -o "$OUT" "$URL"
echo "Saved $OUT ($(wc -c < "$OUT") bytes)"

# Sanity check: the header must contain the columns the pipeline depends on.
head -1 "$OUT" | grep -q "Average Cost for two" || {
  echo "ERROR: unexpected header — the upstream file may have changed." >&2
  exit 1
}
echo "Header check passed."
