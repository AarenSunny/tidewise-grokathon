#!/usr/bin/env bash
# Sunrise / sunset / civil twilight for Half Moon Bay (verify offline solar calc).
# Primary: USNO AA API. Backup: sunrise-sunset.org. NOAA solcalc is browser JS only.
set -euo pipefail
LAT="${LAT:-37.5025}"
LON="${LON:--122.4822}"
DATE="${DATE:-$(date +%Y-%m-%d)}"
# USNO: tz is hours from UTC; for America/Los_Angeles use -8 in standard time, -7 in PDT.
# Nov–early Mar: PST (-8). Pass dst=false in winter; API still returns isdst.
TZOFF="${TZOFF:--8}"

echo "== USNO rstt/oneday lat=$LAT lon=$LON date=$DATE tz=$TZOFF =="
curl -sS --max-time 30 \
  "https://aa.usno.navy.mil/api/rstt/oneday?date=${DATE}&coords=${LAT},${LON}&tz=${TZOFF}&dst=false" \
  | python3 -m json.tool | head -80

echo "== sunrise-sunset.org (tzid=America/Los_Angeles) =="
curl -sS --max-time 30 \
  "https://api.sunrise-sunset.org/json?lat=${LAT}&lng=${LON}&date=${DATE}&tzid=America/Los_Angeles" \
  | python3 -m json.tool

echo "== sunrise-sunset.org (UTC ISO, formatted=0) =="
curl -sS --max-time 30 \
  "https://api.sunrise-sunset.org/json?lat=${LAT}&lng=${LON}&date=${DATE}&formatted=0" \
  | python3 -m json.tool | head -40
