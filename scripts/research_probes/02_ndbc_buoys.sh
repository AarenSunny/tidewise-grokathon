#!/usr/bin/env bash
# Verify NDBC realtime2 standard met and spectral files for regional buoys.
set -euo pipefail
IDS=(46026 46012 46013 46042 46237 46214 FTPC1 AAMC1 RTYC1 PXOC1)
BASE="https://www.ndbc.noaa.gov/data/realtime2"
for id in "${IDS[@]}"; do
  code=$(curl -sS -o "/tmp/ndbc_${id}.txt" -w "%{http_code}" --max-time 30 "$BASE/${id}.txt")
  echo "$id HTTP=$code"
  if [[ "$code" == "200" ]]; then head -3 "/tmp/ndbc_${id}.txt"; fi
done
echo "== spectral 46026 =="
curl -sS --max-time 30 "$BASE/46026.spec" | head -4
